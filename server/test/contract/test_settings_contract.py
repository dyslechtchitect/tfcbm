"""
Contract tests for settings IPC messages
TDD: RED phase - tests written first, should fail initially
"""
import pytest
from server.src.contracts.validator import ContractValidator


@pytest.fixture
def validator():
    """Create contract validator instance"""
    return ContractValidator()


class TestGetSettingsContract:
    """Test get_settings message contract"""

    def test_request_minimal(self, validator):
        """Minimal valid get_settings request"""
        request = {
            "action": "get_settings"
        }
        valid, error = validator.validate_request("get_settings", request)
        assert valid, f"Validation failed: {error}"

    def test_request_with_extra_fields_ignored(self, validator):
        """Extra fields in request should not break validation"""
        request = {
            "action": "get_settings",
            "extra_field": "ignored"
        }
        valid, error = validator.validate_request("get_settings", request)
        assert valid, f"Validation failed: {error}"

    def test_response_complete_settings(self, validator):
        """Complete settings response conforms to contract"""
        response = {
            "type": "settings",
            "settings": {
                "display": {
                    "max_page_length": 20,
                    "item_width": 200,
                    "item_height": 200
                },
                "retention": {
                    "enabled": True,
                    "max_items": 250
                },
                "clipboard": {
                    "refocus_on_copy": True
                },
                "ui": {
                    "mode": "sidepanel",
                    "sidepanel_alignment": "right"
                }
            }
        }
        valid, error = validator.validate_response("get_settings", response)
        assert valid, f"Response validation failed: {error}"

    def test_response_missing_required_field(self, validator):
        """Response missing required field should fail"""
        response = {
            "type": "settings",
            "settings": {
                "display": {
                    "max_page_length": 20,
                    "item_width": 200
                    # Missing item_height
                },
                "retention": {
                    "enabled": True,
                    "max_items": 250
                },
                "clipboard": {
                    "refocus_on_copy": True
                },
                "ui": {
                    "mode": "sidepanel",
                    "sidepanel_alignment": "right"
                }
            }
        }
        valid, error = validator.validate_response("get_settings", response)
        assert not valid, "Should fail validation with missing field"

    def test_response_invalid_ui_mode(self, validator):
        """Invalid UI mode value should fail"""
        response = {
            "type": "settings",
            "settings": {
                "display": {
                    "max_page_length": 20,
                    "item_width": 200,
                    "item_height": 200
                },
                "retention": {
                    "enabled": True,
                    "max_items": 250
                },
                "clipboard": {
                    "refocus_on_copy": True
                },
                "ui": {
                    "mode": "invalid_mode",  # Invalid value
                    "sidepanel_alignment": "right"
                }
            }
        }
        valid, error = validator.validate_response("get_settings", response)
        assert not valid, "Should fail with invalid UI mode"

    def test_response_boundary_values(self, validator):
        """Test boundary values for numeric settings"""
        # Minimum values
        response = {
            "type": "settings",
            "settings": {
                "display": {
                    "max_page_length": 1,  # Minimum
                    "item_width": 50,      # Minimum
                    "item_height": 50      # Minimum
                },
                "retention": {
                    "enabled": False,
                    "max_items": 10        # Minimum
                },
                "clipboard": {
                    "refocus_on_copy": False
                },
                "ui": {
                    "mode": "windowed",
                    "sidepanel_alignment": "left"
                }
            }
        }
        valid, error = validator.validate_response("get_settings", response)
        assert valid, f"Minimum boundary values failed: {error}"

        # Maximum values
        response["settings"]["display"]["max_page_length"] = 100
        response["settings"]["display"]["item_width"] = 1000
        response["settings"]["display"]["item_height"] = 1000
        response["settings"]["retention"]["max_items"] = 10000

        valid, error = validator.validate_response("get_settings", response)
        assert valid, f"Maximum boundary values failed: {error}"

    def test_response_out_of_bounds(self, validator):
        """Values outside allowed range should fail"""
        response = {
            "type": "settings",
            "settings": {
                "display": {
                    "max_page_length": 101,  # Above maximum
                    "item_width": 200,
                    "item_height": 200
                },
                "retention": {
                    "enabled": True,
                    "max_items": 250
                },
                "clipboard": {
                    "refocus_on_copy": True
                },
                "ui": {
                    "mode": "sidepanel",
                    "sidepanel_alignment": "right"
                }
            }
        }
        valid, error = validator.validate_response("get_settings", response)
        assert not valid, "Should fail with out of bounds value"


class TestUpdateSettingsContract:
    """Test update_settings message contract"""

    def test_request_update_all_settings(self, validator):
        """Update all settings at once"""
        request = {
            "action": "update_settings",
            "settings": {
                "display": {
                    "max_page_length": 50,
                    "item_width": 300,
                    "item_height": 250
                },
                "retention": {
                    "enabled": False,
                    "max_items": 500
                },
                "clipboard": {
                    "refocus_on_copy": False
                },
                "ui": {
                    "mode": "windowed",
                    "sidepanel_alignment": "left"
                }
            }
        }
        valid, error = validator.validate_request("update_settings", request)
        assert valid, f"Validation failed: {error}"

    def test_request_partial_update(self, validator):
        """Update only some settings (partial update)"""
        request = {
            "action": "update_settings",
            "settings": {
                "clipboard": {
                    "refocus_on_copy": False
                }
            }
        }
        valid, error = validator.validate_request("update_settings", request)
        assert valid, f"Partial update validation failed: {error}"

    def test_request_empty_settings(self, validator):
        """Empty settings object should be valid (no-op update)"""
        request = {
            "action": "update_settings",
            "settings": {}
        }
        valid, error = validator.validate_request("update_settings", request)
        assert valid, f"Empty settings validation failed: {error}"

    def test_request_invalid_values(self, validator):
        """Invalid setting values should fail"""
        request = {
            "action": "update_settings",
            "settings": {
                "retention": {
                    "max_items": 5  # Below minimum of 10
                }
            }
        }
        valid, error = validator.validate_request("update_settings", request)
        assert not valid, "Should fail with value below minimum"

    def test_response_success(self, validator):
        """Successful update response conforms to contract"""
        response = {
            "type": "settings_updated",
            "success": True,
            "settings": {
                "display": {
                    "max_page_length": 50,
                    "item_width": 300,
                    "item_height": 250
                },
                "retention": {
                    "enabled": False,
                    "max_items": 500
                },
                "clipboard": {
                    "refocus_on_copy": False
                },
                "ui": {
                    "mode": "windowed",
                    "sidepanel_alignment": "left"
                }
            }
        }
        valid, error = validator.validate_response("update_settings", response)
        assert valid, f"Response validation failed: {error}"

    def test_response_failure(self, validator):
        """Failed update response should still conform"""
        response = {
            "type": "settings_updated",
            "success": False,
            "settings": {
                "display": {
                    "max_page_length": 20,
                    "item_width": 200,
                    "item_height": 200
                },
                "retention": {
                    "enabled": True,
                    "max_items": 250
                },
                "clipboard": {
                    "refocus_on_copy": True
                },
                "ui": {
                    "mode": "sidepanel",
                    "sidepanel_alignment": "right"
                }
            }
        }
        valid, error = validator.validate_response("update_settings", response)
        assert valid, f"Failure response validation failed: {error}"


class TestSettingsBackendIntegration:
    """Test that backend handlers return contract-compliant responses"""

    @pytest.fixture
    def ipc_service(self, mock_database_service, mock_clipboard_service):
        """Create IPC service with mock dependencies"""
        from server.src.services.ipc_service import IPCService
        from server.src.services.settings_service import SettingsService

        settings_service = SettingsService()
        return IPCService(
            mock_database_service,
            settings_service,
            mock_clipboard_service
        )

    @pytest.mark.asyncio
    async def test_get_settings_returns_valid_response(self, ipc_service, validator):
        """Backend get_settings returns contract-valid response"""
        request = {"action": "get_settings"}

        # Mock connection that captures response
        class MockConnection:
            def __init__(self):
                self.response = None

            async def send_json(self, data):
                self.response = data

        connection = MockConnection()

        # Call handler
        await ipc_service._handle_get_settings(connection, request)
        response = connection.response

        # Validate response against contract
        valid, error = validator.validate_response("get_settings", response)
        assert valid, f"Backend response doesn't match contract: {error}"

        # Verify structure
        assert response["type"] == "settings"
        assert "settings" in response
        assert "display" in response["settings"]
        assert "retention" in response["settings"]
        assert "clipboard" in response["settings"]
        assert "ui" in response["settings"]

    @pytest.mark.asyncio
    async def test_update_settings_returns_valid_response(self, ipc_service, validator):
        """Backend update_settings returns contract-valid response"""
        request = {
            "action": "update_settings",
            "settings": {
                "clipboard": {
                    "refocus_on_copy": False
                }
            }
        }

        # Mock connection that captures response
        class MockConnection:
            def __init__(self):
                self.response = None

            async def send_json(self, data):
                self.response = data

        connection = MockConnection()

        # Call handler
        await ipc_service._handle_update_settings(connection, request)
        response = connection.response

        # Validate response against contract
        valid, error = validator.validate_response("update_settings", response)
        assert valid, f"Backend response doesn't match contract: {error}"

        # Verify structure
        assert response["type"] == "settings_updated"
        assert "success" in response
        assert "settings" in response


# Mock fixtures for testing
@pytest.fixture
def mock_database_service():
    """Mock database service"""
    class MockDatabaseService:
        def get_latest_id(self):
            return 1
    return MockDatabaseService()


@pytest.fixture
def mock_clipboard_service():
    """Mock clipboard service"""
    class MockClipboardService:
        pass
    return MockClipboardService()
