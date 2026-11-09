from .base import OutputBackend, Touches


class DryRunOutput(OutputBackend):
    """Print touches instead of sending them. For tests."""

    def send(self, touches: Touches) -> None:
        print({i: (round(x), round(y)) for i, (x, y) in touches.items()})
