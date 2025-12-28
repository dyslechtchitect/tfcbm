"""Tag management for clipboard items."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from ui.services.tag_service import TagService


@dataclass
class TagManager:
    """Manages tag state and filtering."""

    tag_service: TagService

    # All available tags (system + user)
    all_tags: List[Dict[str, Any]] = field(default_factory=list)
    # Currently selected tag IDs for filtering
    selected_tag_ids: Set[str] = field(default_factory=set)
    # Dict of tag_id -> button widget (optional, can be moved to UI builder)
    tag_buttons: Dict[str, Any] = field(default_factory=dict)
    # Track if tag filtering is active
    filter_active: bool = False
    # Filtered items when tag filter is active (can be moved to list manager)
    filtered_items: List[Dict[str, Any]] = field(default_factory=list)
    dragged_tag: Any = None  # Keep track of dragged tag for DND

    def __post_init__(self):
        self.load_all_tags()

    def load_all_tags(self):
        """Load all tags from the database and system."""
        # System tags are hardcoded for now, can be dynamic later
        system_tags = [
            {"id": "system_text", "name": "Text", "icon": "text-x-generic-symbolic"},
            {"id": "system_image", "name": "Images", "icon": "image-x-generic-symbolic"},
            {"id": "system_url", "name": "URLs", "icon": "web-browser-symbolic"},
            {"id": "system_file", "name": "Files", "icon": "folder-documents-symbolic"},
            {"id": "system_code", "name": "Code", "icon": "text-x-script-symbolic"},
        ]

        user_tags = [
            {"id": f"user_{tag['id']}", "name": tag["name"], "color": tag["color"] if tag["color"] else "#9a9996"}
            for tag in self.tag_service.get_all_tags()
        ]
        self.all_tags = system_tags + user_tags

    def clear_filter(self):
        """Clear all active tag filters."""
        self.selected_tag_ids.clear()
        self.filter_active = False
        self.filtered_items.clear()
        # Visual clear of tag buttons will be handled by UI layer

    def toggle_tag(self, tag_id: str):
        """Toggle a tag's active state."""
        if tag_id in self.selected_tag_ids:
            self.selected_tag_ids.remove(tag_id)
        else:
            self.selected_tag_ids.add(tag_id)
        self.filter_active = bool(self.selected_tag_ids)
        # Trigger filter update in list manager

    def get_user_tags(self) -> List[Dict[str, Any]]:
        """Return only user-defined tags."""
        return [tag for tag in self.all_tags if tag.get("id", "").startswith("user_")]
