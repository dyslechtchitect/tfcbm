"""
Tests for ContractValidator.

TDD: Test-driven development approach.
Tests written FIRST, then implementation.
"""
import pytest
from server.src.contracts.validator import ContractValidator


@pytest.fixture
def validator():
    """Provide a fresh validator instance for each test."""
    return ContractValidator()


class TestGetHistoryContract:
    """Test get_history message contract."""

    def test_request_minimal_valid(self, validator):
        """Minimal valid get_history request should pass."""
        request = {"action": "get_history"}

        valid, error = validator.validate_request("get_history", request)

        assert valid is True
        assert error is None

    def test_request_with_pagination(self, validator):
        """get_history with pagination parameters should pass."""
        request = {
            "action": "get_history",
            "offset": 20,
            "limit": 50
        }

        valid, error = validator.validate_request("get_history", request)

        assert valid is True
        assert error is None

    def test_request_with_filters(self, validator):
        """get_history with type filters should pass."""
        request = {
            "action": "get_history",
            "filters": ["text", "url"]
        }

        valid, error = validator.validate_request("get_history", request)

        assert valid is True

    def test_request_invalid_limit_too_high(self, validator):
        """get_history with limit > 100 should fail."""
        request = {
            "action": "get_history",
            "limit": 200  # Exceeds maximum of 100
        }

        valid, error = validator.validate_request("get_history", request)

        assert valid is False
        assert error is not None

    def test_request_invalid_offset_negative(self, validator):
        """get_history with negative offset should fail."""
        request = {
            "action": "get_history",
            "offset": -1
        }

        valid, error = validator.validate_request("get_history", request)

        assert valid is False

    def test_request_missing_action(self, validator):
        """get_history without action field should fail."""
        request = {"offset": 0, "limit": 20}

        valid, error = validator.validate_request("get_history", request)

        assert valid is False

    def test_response_valid(self, validator):
        """Valid get_history response should pass."""
        response = {
            "type": "history",
            "items": [
                {
                    "id": 1,
                    "type": "text",
                    "content": "Hello",
                    "thumbnail": None,
                    "timestamp": "2024-01-15T10:30:00Z",
                    "is_favorite": False,
                    "is_secret": False
                }
            ],
            "total_count": 1,
            "offset": 0
        }

        valid, error = validator.validate_response("get_history", response)

        assert valid is True
        assert error is None

    def test_response_empty_items(self, validator):
        """Response with zero items should pass."""
        response = {
            "type": "history",
            "items": [],
            "total_count": 0,
            "offset": 0
        }

        valid, error = validator.validate_response("get_history", response)

        assert valid is True

    def test_response_missing_required_field(self, validator):
        """Response missing required field should fail."""
        response = {
            "type": "history",
            "items": [],
            # Missing total_count
            "offset": 0
        }

        valid, error = validator.validate_response("get_history", response)

        assert valid is False


class TestNewItemSignal:
    """Test new_item signal contract."""

    def test_signal_text_item(self, validator):
        """new_item signal for text should pass."""
        signal = {
            "type": "new_item",
            "item": {
                "id": 42,
                "type": "text",
                "content": "Hello world",
                "thumbnail": None,
                "timestamp": "2024-01-15T10:30:00Z",
                "is_favorite": False,
                "is_secret": False
            }
        }

        valid, error = validator.validate_signal("new_item", signal)

        assert valid is True
        assert error is None

    def test_signal_image_with_thumbnail(self, validator):
        """new_item signal for image with thumbnail should pass."""
        signal = {
            "type": "new_item",
            "item": {
                "id": 43,
                "type": "image/png",
                "content": None,
                "thumbnail": "iVBORw0KGgo...",  # Base64
                "timestamp": "2024-01-15T10:31:00Z",
                "is_favorite": False,
                "is_secret": False
            }
        }

        valid, error = validator.validate_signal("new_item", signal)

        assert valid is True

    def test_signal_missing_item(self, validator):
        """new_item signal without item should fail."""
        signal = {
            "type": "new_item"
            # Missing item field
        }

        valid, error = validator.validate_signal("new_item", signal)

        assert valid is False

    def test_signal_invalid_item_type(self, validator):
        """new_item with invalid type should fail."""
        signal = {
            "type": "new_item",
            "item": {
                "id": 44,
                "type": "invalid_type",  # Not in enum
                "timestamp": "2024-01-15T10:32:00Z"
            }
        }

        valid, error = validator.validate_signal("new_item", signal)

        assert valid is False


class TestUIModeContract:
    """Test UI mode messages contract."""

    def test_get_ui_mode_request(self, validator):
        """get_ui_mode request should pass."""
        request = {"action": "get_ui_mode"}

        valid, error = validator.validate_request("get_ui_mode", request)

        assert valid is True
        assert error is None

    def test_get_ui_mode_response_windowed(self, validator):
        """get_ui_mode response for windowed mode should pass."""
        response = {
            "type": "ui_mode",
            "mode": "windowed",
            "alignment": "none"
        }

        valid, error = validator.validate_response("get_ui_mode", response)

        assert valid is True

    def test_get_ui_mode_response_sidepanel(self, validator):
        """get_ui_mode response for sidepanel should pass."""
        response = {
            "type": "ui_mode",
            "mode": "sidepanel",
            "alignment": "right"
        }

        valid, error = validator.validate_response("get_ui_mode", response)

        assert valid is True

    def test_set_ui_mode_request_sidepanel(self, validator):
        """set_ui_mode request to switch to sidepanel should pass."""
        request = {
            "action": "set_ui_mode",
            "mode": "sidepanel",
            "alignment": "right"
        }

        valid, error = validator.validate_request("set_ui_mode", request)

        assert valid is True

    def test_set_ui_mode_request_windowed(self, validator):
        """set_ui_mode request to switch to windowed should pass."""
        request = {
            "action": "set_ui_mode",
            "mode": "windowed"
        }

        valid, error = validator.validate_request("set_ui_mode", request)

        assert valid is True

    def test_set_ui_mode_response_success(self, validator):
        """set_ui_mode response indicating success should pass."""
        response = {
            "type": "ui_mode_updated",
            "success": True,
            "mode": "sidepanel",
            "alignment": "right"
        }

        valid, error = validator.validate_response("set_ui_mode", response)

        assert valid is True

    def test_set_ui_mode_invalid_mode(self, validator):
        """set_ui_mode with invalid mode should fail."""
        request = {
            "action": "set_ui_mode",
            "mode": "invalid_mode"
        }

        valid, error = validator.validate_request("set_ui_mode", request)

        assert valid is False

    def test_set_ui_mode_invalid_alignment(self, validator):
        """set_ui_mode with invalid alignment should fail."""
        request = {
            "action": "set_ui_mode",
            "mode": "sidepanel",
            "alignment": "center"  # Not 'left' or 'right'
        }

        valid, error = validator.validate_request("set_ui_mode", request)

        assert valid is False


class TestUnknownMessageType:
    """Test handling of unknown message types."""

    def test_unknown_request_type(self, validator):
        """Validation should fail for unknown request type."""
        request = {"action": "unknown_action"}

        valid, error = validator.validate_request("unknown_action", request)

        assert valid is False
        assert "Unknown message type" in error

    def test_unknown_response_type(self, validator):
        """Validation should fail for unknown response type."""
        response = {"type": "unknown_response"}

        valid, error = validator.validate_response("unknown_type", response)

        assert valid is False
        assert "Unknown message type" in error
