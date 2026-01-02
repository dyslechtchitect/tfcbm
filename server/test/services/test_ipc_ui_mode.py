"""
Tests for UI mode IPC handlers.

TDD: Write tests first for get_ui_mode and set_ui_mode actions.
"""
import pytest
import json
from unittest.mock import AsyncMock, Mock
from server.src.services.ipc_service import IPCService
from server.src.services.settings_service import SettingsService
from server.src.contracts.validator import ContractValidator


@pytest.fixture
def settings_service(tmp_path):
    """Provide a test settings service."""
    config_file = tmp_path / "settings.yml"
    config_file.write_text("ui:\n  mode: windowed\n  sidepanel_alignment: right\n")
    return SettingsService(config_path=config_file)


@pytest.fixture
def ipc_service(settings_service):
    """Provide IPC service with mocked dependencies."""
    # Mock other dependencies
    db_service = Mock()
    clipboard_service = Mock()

    service = IPCService(
        database_service=db_service,
        settings_service=settings_service,
        clipboard_service=clipboard_service
    )
    return service


@pytest.fixture
def contract_validator():
    """Provide contract validator."""
    return ContractValidator()


class TestGetUIModeAction:
    """Test get_ui_mode IPC action."""

    @pytest.mark.asyncio
    async def test_get_ui_mode_returns_current_mode(self, ipc_service, contract_validator):
        """get_ui_mode should return current UI mode."""
        connection = AsyncMock()

        # Send get_ui_mode request
        request = {"action": "get_ui_mode"}
        await ipc_service._handle_message(connection, request)

        # Should have sent a response
        assert connection.send_json.called
        response_data = connection.send_json.call_args[0][0]

        # Validate response against contract
        valid, error = contract_validator.validate_response("get_ui_mode", response_data)
        assert valid, f"Response validation failed: {error}"

        # Check response content
        assert response_data['type'] == 'ui_mode'
        assert response_data['mode'] == 'windowed'  # Default from fixture
        assert response_data['alignment'] == 'right'

    @pytest.mark.asyncio
    async def test_get_ui_mode_reflects_sidepanel_mode(self, ipc_service, settings_service, contract_validator):
        """get_ui_mode should reflect sidepanel mode when set."""
        # Change to sidepanel mode
        settings_service.update_settings(ui={'mode': 'sidepanel', 'sidepanel_alignment': 'left'})

        connection = AsyncMock()
        request = {"action": "get_ui_mode"}
        await ipc_service._handle_message(connection, request)

        response_data = connection.send_json.call_args[0][0]

        # Validate against contract
        valid, error = contract_validator.validate_response("get_ui_mode", response_data)
        assert valid, f"Response validation failed: {error}"

        assert response_data['mode'] == 'sidepanel'
        assert response_data['alignment'] == 'left'


class TestSetUIModeAction:
    """Test set_ui_mode IPC action."""

    @pytest.mark.asyncio
    async def test_set_ui_mode_to_sidepanel(self, ipc_service, settings_service, contract_validator):
        """set_ui_mode should update mode to sidepanel."""
        connection = AsyncMock()

        request = {
            "action": "set_ui_mode",
            "mode": "sidepanel",
            "alignment": "right"
        }

        # Validate request against contract
        valid, error = contract_validator.validate_request("set_ui_mode", request)
        assert valid, f"Request validation failed: {error}"

        await ipc_service._handle_message(connection, request)

        # Should have sent success response
        assert connection.send_json.called
        response_data = connection.send_json.call_args[0][0]

        # Validate response against contract
        valid, error = contract_validator.validate_response("set_ui_mode", response_data)
        assert valid, f"Response validation failed: {error}"

        # Check response
        assert response_data['type'] == 'ui_mode_updated'
        assert response_data['success'] is True
        assert response_data['mode'] == 'sidepanel'
        assert response_data['alignment'] == 'right'

        # Verify settings were actually updated
        assert settings_service.ui_mode == 'sidepanel'
        assert settings_service.ui_sidepanel_alignment == 'right'

    @pytest.mark.asyncio
    async def test_set_ui_mode_to_windowed(self, ipc_service, settings_service, contract_validator):
        """set_ui_mode should update mode to windowed."""
        # Start in sidepanel mode
        settings_service.update_settings(ui={'mode': 'sidepanel'})

        connection = AsyncMock()
        request = {
            "action": "set_ui_mode",
            "mode": "windowed"
        }

        await ipc_service._handle_message(connection, request)

        response_data = connection.send_json.call_args[0][0]

        # Validate response
        valid, error = contract_validator.validate_response("set_ui_mode", response_data)
        assert valid, f"Response validation failed: {error}"

        assert response_data['success'] is True
        assert response_data['mode'] == 'windowed'

        # Verify settings updated
        assert settings_service.ui_mode == 'windowed'

    @pytest.mark.asyncio
    async def test_set_ui_mode_rejects_invalid_mode(self, ipc_service, contract_validator):
        """set_ui_mode should reject invalid mode values."""
        connection = AsyncMock()

        request = {
            "action": "set_ui_mode",
            "mode": "invalid_mode"
        }

        # Request should fail contract validation
        valid, error = contract_validator.validate_request("set_ui_mode", request)
        assert not valid, "Should reject invalid mode"
