"""Webcam listing and opening (V4L2)."""
from pathlib import Path

import cv2


def list_cameras() -> list[tuple[str, str]]:
    """Return (device, name) for each capture node, e.g. ("/dev/video0", "USB Webcam")."""
    cams = []
    for d in sorted(Path("/sys/class/video4linux").glob("video*"), key=lambda p: int(p.name[5:])):
        # shortcut: index 0 = main capture node on UVC webcams (others are metadata); probe with
        # VIDIOC_QUERYCAP if a camera ever shows up wrong.
        if (d / "index").read_text().strip() != "0":
            continue
        cams.append((f"/dev/{d.name}", (d / "name").read_text().strip()))
    return cams


def open_camera(device: str, width: int = 1280, height: int = 720) -> cv2.VideoCapture:
    """Open a webcam at the requested size (the driver may pick the nearest). Raises OSError."""
    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    if not cap.isOpened():
        raise OSError(f"Impossibile aprire la webcam {device}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # always get the latest frame, not a stale one
    return cap
