"""Detector interface and model download."""
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"

# Detected point: (x, y, label), x/y in normalized camera coords [0,1].
Point = tuple[float, float, str]


def model_path(name: str, url: str) -> str:
    """Return the local model file, downloading it on first use. Raises OSError."""
    path = MODELS_DIR / name
    if not path.exists():
        MODELS_DIR.mkdir(exist_ok=True)
        tmp = path.with_suffix(".part")
        try:
            with urllib.request.urlopen(url, timeout=30) as r, open(tmp, "wb") as f:
                while chunk := r.read(1 << 16):
                    f.write(chunk)
        except OSError as e:
            tmp.unlink(missing_ok=True)
            raise OSError(f"Download del modello {name} fallito: {e}") from e
        tmp.replace(path)  # no half-downloaded model if interrupted
    return str(path)


class Detector(ABC):
    @abstractmethod
    def detect(self, rgb, timestamp_ms: int, min_confidence: float) -> list[Point]:
        """Find hands/feet in an RGB frame. Timestamps must increase."""

    def close(self) -> None:
        pass
