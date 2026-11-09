from .base import OutputBackend, Touches


class DryRunOutput(OutputBackend):
    """Print touches instead of sending them. For tests."""

    def send(self, touches: Touches) -> None:
        print({i: (round(x, 3), round(y, 3)) for i, (x, y) in touches.items()})
