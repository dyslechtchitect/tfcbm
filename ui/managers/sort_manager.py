"""Sort state management."""

from dataclasses import dataclass


@dataclass
class SortState:
    order: str = "DESC"  # Default: newest first

    def toggle(self):
        self.order = "ASC" if self.order == "DESC" else "DESC"


class SortManager:
    def __init__(self):
        self.copied_sort = SortState()
        self.pasted_sort = SortState()
