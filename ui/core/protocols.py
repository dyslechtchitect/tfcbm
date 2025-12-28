"""Protocol definitions for dependency injection."""

from typing import List, Optional, Protocol


class DatabasePort(Protocol):
    def get_history(
        self,
        limit: int,
        offset: int,
        sort_asc: bool = False,
        type_filter: Optional[str] = None,
        tag_filter: Optional[List[int]] = None,
    ) -> List[dict]: ...

    def get_pasted_history(
        self, limit: int, offset: int, sort_asc: bool = False
    ) -> List[dict]: ...

    def search_items(self, query: str, limit: int = 50) -> List[dict]: ...

    def update_item_name(self, item_id: int, name: str) -> None: ...

    def delete_item(self, item_id: int) -> None: ...


class ClipboardPort(Protocol):
    def copy_text(self, text: str) -> None: ...

    def copy_image(self, texture) -> None: ...


class FileServicePort(Protocol):
    def save_file(self, data: bytes, suggested_name: str) -> Optional[str]: ...

    def read_file(self, path: str) -> bytes: ...


class TagServicePort(Protocol):
    def get_all_tags(self) -> List[dict]: ...

    def create_tag(self, name: str) -> int: ...

    def delete_tag(self, tag_id: int) -> None: ...

    def add_tag_to_item(self, item_id: int, tag_id: int) -> None: ...

    def remove_tag_from_item(self, item_id: int, tag_id: int) -> None: ...

    def get_item_tags(self, item_id: int) -> List[int]: ...
