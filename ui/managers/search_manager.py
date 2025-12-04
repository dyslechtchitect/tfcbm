"""Search state management."""

from typing import Any, List


class SearchManager:
    def __init__(self, page_size: int = 100):
        self.query: str = ""
        self.timer: int = None
        self.active: bool = False
        self.results: List[Any] = []
        self.page_size = page_size

    def set_query(self, query: str):
        self.query = query

    def clear(self):
        self.query = ""
        self.active = False
        self.results = []
