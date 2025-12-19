"""Tracks shortcut activation events."""
from typing import Protocol


class ActivationObserver(Protocol):
    """Observer protocol for activation events."""

    def on_activation_count_changed(self, count: int) -> None:
        """Called when the activation count changes."""
        pass


class ActivationTracker:
    """Tracks how many times the shortcut has been activated."""

    def __init__(self):
        """Initialize the tracker."""
        self._count = 0
        self._observers: list[ActivationObserver] = []

    def add_observer(self, observer: ActivationObserver) -> None:
        """Add an observer for activation events."""
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer: ActivationObserver) -> None:
        """Remove an observer."""
        if observer in self._observers:
            self._observers.remove(observer)

    @property
    def count(self) -> int:
        """Get the current activation count."""
        return self._count

    def increment(self) -> int:
        """
        Increment the activation count.

        Returns:
            New count value
        """
        self._count += 1
        self._notify_observers()
        return self._count

    def reset(self) -> None:
        """Reset the activation count to zero."""
        self._count = 0
        self._notify_observers()

    def _notify_observers(self) -> None:
        """Notify all observers of count change."""
        for observer in self._observers:
            observer.on_activation_count_changed(self._count)
