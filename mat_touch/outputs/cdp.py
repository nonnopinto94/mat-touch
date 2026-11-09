"""Chrome DevTools Protocol backend: touches go only to one browser tab."""
import json
import time
import urllib.request

import websocket

from .base import OutputBackend, Touches

VIEWPORT_TTL = 1.0  # seconds between viewport size refreshes


def list_pages(port: int) -> list[dict]:
    """Tabs of type "page" from http://127.0.0.1:<port>/json. Raises OSError if unreachable."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as r:
            targets = json.load(r)
    except ValueError as e:
        raise OSError(f"Risposta non valida dalla porta {port}") from e
    return [t for t in targets if t.get("type") == "page" and "webSocketDebuggerUrl" in t]


class CdpOutput(OutputBackend):
    # shortcut: synchronous calls on the caller's thread, no reconnect; dedicated thread +
    # automatic reconnection come in M4/M6.
    def __init__(self, ws_url: str):
        try:
            self.ws = websocket.create_connection(ws_url, timeout=2, suppress_origin=True)
        except (websocket.WebSocketException, OSError) as e:
            raise OSError(f"Connessione alla scheda fallita: {e}") from e
        self.next_id = 0
        self.active: dict[int, dict] = {}  # id -> last sent CDP touch point
        self.viewport = (0, 0)
        self.viewport_time = 0.0
        self.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=10)

    def call(self, method: str, **params) -> dict:
        """Send a command and wait for its result. Events received meanwhile are dropped."""
        self.next_id += 1
        msg_id = self.next_id
        try:
            self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params}))
            while True:
                msg = json.loads(self.ws.recv())
                if msg.get("id") == msg_id:
                    break
        except (websocket.WebSocketException, OSError) as e:
            raise OSError(f"Connessione al browser persa: {e}") from e
        if "error" in msg:
            raise OSError(f"{method}: {msg['error'].get('message')}")
        return msg.get("result", {})

    def get_viewport(self) -> tuple[int, int]:
        """Page size in CSS pixels, refreshed at most every VIEWPORT_TTL seconds."""
        now = time.monotonic()
        if now - self.viewport_time > VIEWPORT_TTL:
            r = self.call("Runtime.evaluate", expression="[innerWidth, innerHeight]", returnByValue=True)
            self.viewport = tuple(r["result"]["value"])
            self.viewport_time = now
        return self.viewport

    def send(self, touches: Touches) -> None:
        # Verified on Chromium: touchStart/touchMove take the full set and Chromium diffs it,
        # but a finger missing from touchMove is NOT lifted. touchEnd lifts exactly the listed
        # points (empty list = all), and fails if no touch is active.
        lifted = [p for i, p in self.active.items() if i not in touches]
        if lifted:
            self.call("Input.dispatchTouchEvent", type="touchEnd",
                      touchPoints=lifted if touches else [])
        if not touches:
            self.active = {}
            return
        w, h = self.get_viewport()
        points = {i: {"x": x * w, "y": y * h, "id": i} for i, (x, y) in touches.items()}
        kind = "touchStart" if points.keys() - self.active.keys() else "touchMove"
        self.call("Input.dispatchTouchEvent", type=kind, touchPoints=list(points.values()))
        self.active = points

    def close(self) -> None:
        try:
            if self.active:
                self.send({})
        except OSError:
            pass
        self.ws.close()
