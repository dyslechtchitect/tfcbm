"""Tag management service."""

from typing import List

from server.src.database import ClipboardDB


class TagService:
    def __init__(self, db: ClipboardDB):
        self.db = db

    def get_all_tags(self) -> List[dict]:
        return self.db.get_all_tags()

    def create_tag(self, name: str) -> int:
        return self.db.create_tag(name)

    def delete_tag(self, tag_id: int) -> None:
        self.db.delete_tag(tag_id)

    def add_tag_to_item(self, item_id: int, tag_id: int) -> None:
        self.db.add_tag_to_item(item_id, tag_id)

    def remove_tag_from_item(self, item_id: int, tag_id: int) -> None:
        self.db.remove_tag_from_item(item_id, tag_id)

    def get_item_tags(self, item_id: int) -> List[int]:
        return self.db.get_item_tags(item_id)
