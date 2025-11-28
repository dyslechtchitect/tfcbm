"""Database operations service."""

from typing import List, Optional

from database import ClipboardDB


class DatabaseService:
    def __init__(self, db_path: Optional[str] = None):
        self.db = ClipboardDB(db_path) if db_path else ClipboardDB()

    def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_asc: bool = False,
        type_filter: Optional[str] = None,
        tag_filter: Optional[List[int]] = None,
    ) -> List[dict]:
        return self.db.get_history(
            limit=limit,
            offset=offset,
            sort_asc=sort_asc,
            type_filter=type_filter,
            tag_filter=tag_filter,
        )

    def get_pasted_history(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_asc: bool = False,
    ) -> List[dict]:
        return self.db.get_pasted_history(
            limit=limit, offset=offset, sort_asc=sort_asc
        )

    def search_items(self, query: str, limit: int = 50) -> List[dict]:
        return self.db.search_items(query, limit=limit)

    def update_item_name(self, item_id: int, name: str) -> None:
        self.db.update_item_name(item_id, name)

    def delete_item(self, item_id: int) -> None:
        self.db.delete_item(item_id)
