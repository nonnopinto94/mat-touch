"""Persistent settings in ~/.config/mat-touch/config.json."""
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "mat-touch" / "config.json"


@dataclass
class Config:
    camera: str = "/dev/video0"
    corners: list | None = None  # 4 [x, y] normalized camera coords [0,1], ordered TL, TR, BR, BL
    cdp_port: int = 9222
    detector: str = "pose"  # "pose" or "hands"
    feet: bool = True       # pose only: feet are touch points too
    min_confidence: float = 0.5
    frames_in: int = 2   # consecutive frames before a touch starts
    frames_out: int = 5  # missing frames before a touch ends
    filter_min_cutoff: float = 1.0  # One Euro, Hz: lower = smoother but laggier when slow
    filter_beta: float = 1.0        # One Euro: higher = less lag on fast moves (units: area/s)
    margin: float = 0.05  # points this far outside the projected area still count (clamped)


def load(path: Path = CONFIG_PATH) -> Config:
    """Return saved config, or defaults if missing/corrupt. Unknown keys are ignored."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return Config()
    if not isinstance(data, dict):
        return Config()
    known = {f.name for f in fields(Config)}
    return Config(**{k: v for k, v in data.items() if k in known})


def save(cfg: Config, path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(cfg), indent=2))
    tmp.replace(path)  # atomic: a crash never leaves a half-written config
