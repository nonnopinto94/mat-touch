"""Webcam listing and opening on Linux (V4L2), Windows (DirectShow) and macOS (AVFoundation)."""
import sys
from pathlib import Path

import cv2

BACKEND = {"linux": cv2.CAP_V4L2, "win32": cv2.CAP_DSHOW, "darwin": cv2.CAP_AVFOUNDATION}.get(
    sys.platform, cv2.CAP_ANY)
MAX_PROBE = 6  # camera indices tried where devices can't be listed


def list_cameras() -> list[tuple[str, str]]:
    """Return (device, name) per webcam: ("/dev/video0", "USB Webcam") on Linux, ("0", "Webcam 0") elsewhere."""
    if sys.platform != "linux":
        # OpenCV can't list devices or names on Windows/macOS: try opening each index.
        cams = []
        for i in range(MAX_PROBE):
            cap = cv2.VideoCapture(i, BACKEND)
            if cap.isOpened():
                cams.append((str(i), f"Webcam {i}"))
            cap.release()
        return cams
    cams = []
    for d in sorted(Path("/sys/class/video4linux").glob("video*"), key=lambda p: int(p.name[5:])):
        # shortcut: index 0 = main capture node on UVC webcams (others are metadata); probe with
        # VIDIOC_QUERYCAP if a camera ever shows up wrong.
        try:
            if (d / "index").read_text().strip() != "0":
                continue
            name = (d / "name").read_text().strip()
        except OSError:  # some capture cards / virtual cameras lack these files
            continue
        cams.append((f"/dev/{d.name}", name))
    return cams


def open_camera(device: str, width: int = 1280, height: int = 720) -> cv2.VideoCapture:
    """Open a webcam at the requested size (the driver may pick the nearest). Raises OSError."""
    cap = cv2.VideoCapture(int(device) if device.isdigit() else device, BACKEND)
    if not cap.isOpened():
        raise OSError(f"Impossibile aprire la webcam {device}")
    # MJPG first: over USB 2.0, raw YUYV at 720p drops to a few fps. Ignored if unsupported.
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # always get the latest frame, not a stale one
    return cap
