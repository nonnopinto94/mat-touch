"""Output backend interface: where touches go (CDP today, maybe uinput later)."""
from abc import ABC, abstractmethod

# Active touches: stable touch id -> (x, y) in page CSS pixels.
Touches = dict[int, tuple[float, float]]


class OutputBackend(ABC):
    @abstractmethod
    def send(self, touches: Touches) -> None:
        """Send the full set of active touches. Empty dict = all fingers up."""

    def close(self) -> None:
        pass
