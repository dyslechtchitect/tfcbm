"""Pagination state management for infinite scroll."""


class PaginationManager:
    def __init__(self, page_size: int = 50):
        self.page_size = page_size
        self.offset = 0
        self.has_more = True
        self.loading = False

    def can_load_more(self) -> bool:
        return self.has_more and not self.loading

    def start_loading(self) -> None:
        self.loading = True

    def finish_loading(self, items_loaded: int) -> None:
        self.loading = False
        self.offset += items_loaded
        self.has_more = items_loaded == self.page_size

    def reset(self) -> None:
        self.offset = 0
        self.has_more = True
        self.loading = False
