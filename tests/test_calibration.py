"""Run: python -m tests.test_calibration"""
import itertools

import cv2
import numpy as np

from mat_touch import calibration

# Trapezoid like an oblique projection: top edge shorter than bottom.
QUAD = [[0.3, 0.2], [0.7, 0.2], [0.9, 0.8], [0.1, 0.8]]


def test_order_any_click_order():
    for perm in itertools.permutations(QUAD):
        assert calibration.order_corners(list(perm)) == QUAD


def test_order_rotated_quad():
    diamond = [[0.5, 0.1], [0.9, 0.5], [0.5, 0.9], [0.1, 0.5]]
    ordered = calibration.order_corners(diamond[::-1])
    assert ordered[0] == [0.5, 0.1] and ordered[1] == [0.9, 0.5]


def test_homography_maps_corners():
    h = calibration.homography(QUAD)
    out = cv2.perspectiveTransform(np.float32([QUAD]), h)[0]
    assert np.allclose(out, [[0, 0], [1, 0], [1, 1], [0, 1]], atol=1e-5)
    u, v = calibration.to_projection(h, [0.5, 0.2])  # middle of the top edge
    assert abs(u - 0.5) < 1e-5 and abs(v) < 1e-5


def test_area():
    assert abs(calibration.area(QUAD) - 0.36) < 1e-9
    assert calibration.area([[0, 0], [0.5, 0.5], [1, 1], [0.2, 0.2]]) < calibration.MIN_AREA


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
