"""Window positioning and size management."""

from typing import Tuple


class WindowManager:
    def __init__(
        self,
        default_width: int = 350,
        default_height: int = 800,
        position: str = "left",
    ):
        self.default_width = default_width
        self.default_height = default_height
        self.position = position

    def get_default_size(self) -> Tuple[int, int]:
        return self.default_width, self.default_height

    def calculate_size_from_monitor(
        self, monitor_width: int, monitor_height: int
    ) -> Tuple[int, int]:
        width = monitor_width // 3
        height = self.default_height
        return width, height
