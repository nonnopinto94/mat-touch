"""MediaPipe HandLandmarker: palm centers. Better when the camera is close to the mat."""
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision

from .base import Detector, Point, model_path

URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
       "hand_landmarker/float16/latest/hand_landmarker.task")

PALM = (0, 5, 9, 13, 17)  # wrist + finger bases


class HandsDetector(Detector):
    def __init__(self, num_hands: int = 4):
        opts = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path("hand_landmarker.task", URL)),
            running_mode=vision.RunningMode.VIDEO, num_hands=num_hands)
        self.landmarker = vision.HandLandmarker.create_from_options(opts)

    def detect(self, rgb, timestamp_ms, min_confidence):
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.landmarker.detect_for_video(image, timestamp_ms)
        points: list[Point] = []
        for lms, handedness in zip(result.hand_landmarks, result.handedness):
            if handedness[0].score < min_confidence:
                continue
            points.append((sum(lms[i].x for i in PALM) / len(PALM),
                           sum(lms[i].y for i in PALM) / len(PALM), "mano"))
        return points

    def close(self):
        self.landmarker.close()
