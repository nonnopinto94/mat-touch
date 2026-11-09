"""Background thread: webcam -> detection -> mapping -> tracking -> output.

The UI never blocks, and touches have a single sender (this thread).
"""
import threading
import time

import cv2

from . import calibration, camera
from .tracker import Tracker

MOUSE_ID = 10000   # test touch from the preview; never collides with tracker ids
MIN_SEND_DT = 1 / 60  # at most 60 touch events per second


def make_detector(name: str, feet: bool):
    # Lazy import: mediapipe takes ~1 s to load, not needed for calibration.
    if name == "pose":
        from .detectors.pose import PoseDetector
        return PoseDetector(feet=feet)
    if name == "hands":
        from .detectors.hands import HandsDetector
        return HandsDetector()
    raise ValueError(f"Rilevatore sconosciuto: {name}")


class Pipeline(threading.Thread):
    """Parameters are read live from `cfg`. From the UI thread set `running`, `paused`,
    `homography`, `output` and `mouse`; read `latest()` for (frame, points, touches)."""

    def __init__(self, device: str, cfg):
        super().__init__(daemon=True)
        self.cap = camera.open_camera(device)  # raises OSError
        self.cfg = cfg
        self.running = False   # detection + touch output (step 3 only)
        self.paused = False    # detection on, touches not sent
        self.homography = None
        self.output = None
        self.mouse = None      # (u, v) of the preview test touch, or None
        self.error = ""
        self.send_error = ""
        self.fps = 0.0
        self.tracker = Tracker()
        self._lock = threading.Lock()
        self._latest = (None, [], {})
        self._stop_event = threading.Event()
        self.start()

    def latest(self):
        with self._lock:
            return self._latest

    def map_points(self, points):
        """Camera points -> projected-area coords; drop those outside the area + margin."""
        m = self.cfg.margin
        out = []
        for x, y, _label in points:
            u, v = calibration.to_projection(self.homography, (x, y))
            if -m <= u <= 1 + m and -m <= v <= 1 + m:
                out.append((min(max(u, 0.0), 1.0), min(max(v, 0.0), 1.0)))
        return out

    def run(self):
        current_name, det = None, None
        failed_name = None  # don't retry a broken detector every frame
        last_ts, last_t = 0, time.monotonic()
        sent, sent_t, sent_output = {}, 0.0, None
        while not self._stop_event.is_set():
            ok, frame = self.cap.read()
            if not ok:
                self.error = "Nessun fotogramma dalla webcam"
                time.sleep(0.1)
                continue
            cfg = self.cfg
            name = cfg.detector if self.running and self.homography is not None else None
            if name != current_name and name != failed_name:
                if det is not None:
                    det.close()
                det, current_name = None, None
                self.tracker.reset()
                if name:
                    try:
                        det = make_detector(name, cfg.feet)
                        current_name, failed_name, self.error = name, None, ""
                    except Exception as e:  # download, model or mediapipe errors: show, keep running
                        failed_name, self.error = name, f"Rilevatore non disponibile: {e}"
                else:
                    failed_name, self.error = None, ""

            now = time.monotonic()
            points, touches = [], {}
            if det is not None and name == current_name:
                last_ts = max(int(now * 1000), last_ts + 1)  # must strictly increase
                points = det.detect(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), last_ts, cfg.min_confidence)
                touches = self.tracker.update(self.map_points(points), now, cfg.frames_in,
                                              cfg.frames_out, cfg.filter_min_cutoff, cfg.filter_beta)
            mouse = self.mouse
            if self.running and mouse is not None:
                touches[MOUSE_ID] = mouse

            # Send only on change, rate-limited; a new output starts from "no fingers".
            output = self.output
            if output is not sent_output:
                sent, sent_output = {}, output
            wanted = touches if self.running and not self.paused else {}
            if output is not None and wanted != sent and now - sent_t >= MIN_SEND_DT:
                try:
                    output.send(wanted)
                    self.send_error = ""
                except OSError as e:
                    self.send_error = f"{e} – usa 'Cambia scheda' per ricollegarti"
                sent, sent_t = wanted, now

            self.fps = 0.9 * self.fps + 0.1 / max(now - last_t, 1e-3)
            last_t = now
            with self._lock:
                self._latest = (frame, points, touches)
        if det is not None:
            det.close()
        self.cap.release()

    def stop(self):
        self._stop_event.set()
        self.join(timeout=2)
