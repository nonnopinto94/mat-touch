"""MediaPipe PoseLandmarker: hands and feet from the body pose (robust with an oblique camera)."""
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision

from .base import Detector, Point, model_path

# shortcut: "full" model is a CPU speed/accuracy middle ground; try lite/heavy if fps or accuracy is poor.
URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
       "pose_landmarker_full/float16/latest/pose_landmarker_full.task")

# Hand = mean of wrist, pinky, index; foot = foot index (toe). Indices from the Pose model.
PARTS = {"L": (15, 17, 19), "R": (16, 18, 20)}
FEET = {"L": (31,), "R": (32,)}


class PoseDetector(Detector):
    def __init__(self, num_poses: int = 3, feet: bool = True):
        opts = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path("pose_landmarker_full.task", URL)),
            running_mode=vision.RunningMode.VIDEO, num_poses=num_poses)
        self.landmarker = vision.PoseLandmarker.create_from_options(opts)
        self.groups = [("mano " + s, idx) for s, idx in PARTS.items()]
        if feet:
            self.groups += [("piede " + s, idx) for s, idx in FEET.items()]

    def detect(self, rgb, timestamp_ms, min_confidence):
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self.landmarker.detect_for_video(image, timestamp_ms)
        points: list[Point] = []
        for pose in result.pose_landmarks:
            for label, idx in self.groups:
                lms = [pose[i] for i in idx]
                if min(lm.visibility for lm in lms) < min_confidence:
                    continue
                points.append((sum(lm.x for lm in lms) / len(lms),
                               sum(lm.y for lm in lms) / len(lms), label))
        return points

    def close(self):
        self.landmarker.close()
