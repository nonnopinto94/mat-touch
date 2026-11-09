"""One Euro filter: little lag on fast moves, no jitter when still."""
import math


def _alpha(dt: float, cutoff: float) -> float:
    tau = 1 / (2 * math.pi * cutoff)
    return 1 / (1 + tau / dt)


class OneEuro2D:
    def __init__(self, d_cutoff: float = 1.0):
        self.d_cutoff = d_cutoff
        self.t = None
        self.x = self.y = 0.0
        self.dx = self.dy = 0.0

    def __call__(self, t: float, x: float, y: float, min_cutoff: float, beta: float):
        """Filter a point at time t (seconds). Params are passed per call so they can be tuned live."""
        if self.t is None:
            self.t, self.x, self.y = t, x, y
            return x, y
        dt = max(t - self.t, 1e-3)
        a = _alpha(dt, self.d_cutoff)
        self.dx += a * ((x - self.x) / dt - self.dx)
        self.dy += a * ((y - self.y) / dt - self.dy)
        a = _alpha(dt, min_cutoff + beta * math.hypot(self.dx, self.dy))
        self.x += a * (x - self.x)
        self.y += a * (y - self.y)
        self.t = t
        return self.x, self.y
