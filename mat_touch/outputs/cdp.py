"""Chrome DevTools Protocol backend: touches go only to one browser tab."""
import json
import threading
import time
import urllib.request

import websocket

from .base import OutputBackend, Touches

VIEWPORT_TTL = 1.0  # seconds between viewport size refreshes
CALL_TIMEOUT = 2.0
BINDING = "matTouchCommand"

# Generic hardening for any page: no context menu on long press, no text selection,
# touch-action none; Ctrl+Alt+P / Ctrl+Alt+Q are forwarded to mat-touch.
HARDENING_JS = """
(() => {
  if (window.__matTouch) return;
  window.__matTouch = true;
  const stop = e => e.preventDefault();
  addEventListener("contextmenu", stop, true);
  addEventListener("selectstart", stop, true);
  addEventListener("dragstart", stop, true);
  const css = () => {
    const s = document.documentElement.style;
    s.touchAction = "none";
    s.userSelect = "none";
    s.webkitUserSelect = "none";
  };
  if (document.documentElement) css(); else addEventListener("DOMContentLoaded", css);
  addEventListener("keydown", e => {
    if (!e.ctrlKey || !e.altKey) return;
    const cmd = {KeyP: "pause", KeyQ: "quit"}[e.code];
    if (cmd && window.%s) { e.preventDefault(); window.%s(cmd); }
  }, true);
})();
""" % (BINDING, BINDING)


def list_pages(port: int) -> list[dict]:
    """Tabs of type "page" from http://127.0.0.1:<port>/json. Raises OSError if unreachable."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2) as r:
            targets = json.load(r)
    except ValueError as e:
        raise OSError(f"Risposta non valida dalla porta {port}") from e
    return [t for t in targets if t.get("type") == "page" and "webSocketDebuggerUrl" in t]


class CdpOutput(OutputBackend):
    """Thread-safe: a reader thread routes replies to callers and binding calls to on_command."""

    # shortcut: no automatic reconnection; the user reconnects from step 2. Add it in M6.
    def __init__(self, ws_url: str, on_command=None):
        try:
            self.ws = websocket.create_connection(ws_url, timeout=CALL_TIMEOUT, suppress_origin=True)
        except (websocket.WebSocketException, OSError) as e:
            raise OSError(f"Connessione alla scheda fallita: {e}") from e
        self.ws.settimeout(None)  # the reader blocks; call() has its own timeout
        self.on_command = on_command
        self.lock = threading.Lock()       # websocket send + pending table
        self.send_lock = threading.Lock()  # touch state
        self.pending: dict[int, list] = {}  # id -> [Event, reply]
        self.next_id = 0
        self.closed = False
        self.active: dict[int, dict] = {}  # id -> last sent CDP touch point
        self.viewport = (0, 0)
        self.viewport_time = 0.0
        threading.Thread(target=self._reader, daemon=True).start()
        try:
            self.call("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=10)
            self.call("Runtime.enable")  # needed to receive Runtime.bindingCalled
            self.call("Runtime.addBinding", name=BINDING)
            self.call("Page.addScriptToEvaluateOnNewDocument", source=HARDENING_JS)
            self.call("Runtime.evaluate", expression=HARDENING_JS)  # current document too
        except OSError:
            self.ws.close()
            raise

    def _reader(self):
        try:
            while True:
                msg = json.loads(self.ws.recv())
                if "id" in msg:
                    with self.lock:
                        slot = self.pending.pop(msg["id"], None)
                    if slot:
                        slot[1] = msg
                        slot[0].set()
                elif (msg.get("method") == "Runtime.bindingCalled"
                      and msg["params"].get("name") == BINDING and self.on_command):
                    self.on_command(msg["params"].get("payload", ""))
        except (websocket.WebSocketException, OSError, ValueError):
            pass
        self.closed = True
        with self.lock:
            for slot in self.pending.values():
                slot[0].set()  # wake callers: reply stays None -> error
            self.pending.clear()

    def call(self, method: str, **params) -> dict:
        """Send a command and wait for its result. Raises OSError."""
        slot = [threading.Event(), None]
        with self.lock:
            if self.closed:
                raise OSError("Connessione al browser persa")
            self.next_id += 1
            msg_id = self.next_id
            self.pending[msg_id] = slot
            try:
                self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params}))
            except (websocket.WebSocketException, OSError) as e:
                self.pending.pop(msg_id, None)
                raise OSError(f"Connessione al browser persa: {e}") from e
        if not slot[0].wait(CALL_TIMEOUT):
            with self.lock:
                self.pending.pop(msg_id, None)
            raise OSError(f"{method}: nessuna risposta dal browser")
        msg = slot[1]
        if msg is None:
            raise OSError("Connessione al browser persa")
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
        with self.send_lock:
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
            self.send({})
        except OSError:
            pass
        self.ws.close()
