"""Projection corners and camera -> projection homography.

Corners are in normalized camera coordinates [0,1]x[0,1], the same space as MediaPipe
landmarks, so the calibration does not depend on the camera resolution.
"""
import math

import cv2
import numpy as np

from . import config

MIN_AREA = 0.01  # quad must cover at least 1% of the camera frame


def order_corners(pts) -> list[list[float]]:
    """Order 4 points as TL, TR, BR, BL (image coords, y down), whatever the click order."""
    cx = sum(p[0] for p in pts) / 4
    cy = sum(p[1] for p in pts) / 4
    # Angle sort gives a clockwise ring even for strong perspective; then start from top-left.
    ring = sorted(pts, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
    start = min(range(4), key=lambda i: ring[i][0] + ring[i][1])
    return [[float(x), float(y)] for x, y in ring[start:] + ring[:start]]


def area(corners) -> float:
    """Shoelace area of the ordered quad."""
    return abs(sum(corners[i][0] * corners[i - 3][1] - corners[i - 3][0] * corners[i][1]
                   for i in range(4))) / 2


def homography(corners) -> np.ndarray:
    """3x3 matrix mapping normalized camera coords to the projected area [0,1]x[0,1]."""
    src = np.float32(corners)
    dst = np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])
    return cv2.getPerspectiveTransform(src, dst)


def to_projection(h: np.ndarray, p) -> tuple[float, float]:
    """Map a normalized camera point to projected-area coords (inside if both are in [0,1])."""
    u, v = cv2.perspectiveTransform(np.float32([[p]]), h)[0][0]
    return float(u), float(v)


def save(cfg: config.Config, camera: str, pts) -> list[list[float]]:
    """Validate, order and persist the corners. Raises ValueError if the quad is unusable."""
    if len(pts) != 4:
        raise ValueError("Servono esattamente 4 angoli")
    corners = order_corners(pts)
    if area(corners) < MIN_AREA:
        raise ValueError("Area troppo piccola o punti allineati")
    cfg.camera = camera
    cfg.corners = corners
    config.save(cfg)
    return corners
