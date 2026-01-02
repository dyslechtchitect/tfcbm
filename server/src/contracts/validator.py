"""
Contract validator for IPC messages.

Clean, testable validator using dependency injection.
"""
import json
from pathlib import Path
from typing import Tuple, Optional
from jsonschema import validate, ValidationError, Draft7Validator


class ContractValidator:
    """
    Validates IPC messages against the contract schema.

    Injectable validator for easy testing.

    Example:
        validator = ContractValidator()
        valid, error = validator.validate_request('get_history', request_data)
        if not valid:
            logger.error("Invalid request", extra={'error': error})
    """

    def __init__(self, schema_path: Optional[str] = None):
        """
        Initialize validator with schema.

        Args:
            schema_path: Path to schema JSON file.
                        If None, uses default bundled schema.
        """
        if schema_path is None:
            schema_path = Path(__file__).parent / "ipc_contract_v1.json"

        with open(schema_path) as f:
            self.schema = json.load(f)

        self.validator = Draft7Validator(self.schema)

    def _validate_with_refs(self, data: dict, schema: dict) -> Tuple[bool, Optional[str]]:
        """
        Validate data against schema with $ref resolution.

        Internal helper that resolves $ref to definitions in main schema.
        """
        # Create a full schema with definitions for $ref resolution
        full_schema = {
            **schema,
            "definitions": self.schema.get("definitions", {})
        }

        try:
            validate(data, full_schema)
            return True, None
        except ValidationError as e:
            return False, e.message

    def validate_request(self, message_type: str, data: dict) -> Tuple[bool, Optional[str]]:
        """
        Validate a request message against the contract.

        Args:
            message_type: Type of message (e.g., 'get_history')
            data: Request data to validate

        Returns:
            Tuple of (is_valid, error_message)
            - (True, None) if valid
            - (False, "error description") if invalid

        Example:
            valid, error = validator.validate_request('get_history', {
                'action': 'get_history',
                'limit': 20
            })
        """
        try:
            schema = self.schema['messages'][message_type]['request']
            return self._validate_with_refs(data, schema)
        except KeyError:
            return False, f"Unknown message type: {message_type}"

    def validate_response(self, message_type: str, data: dict) -> Tuple[bool, Optional[str]]:
        """
        Validate a response message against the contract.

        Args:
            message_type: Type of message (e.g., 'get_history')
            data: Response data to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            schema = self.schema['messages'][message_type]['response']
            return self._validate_with_refs(data, schema)
        except KeyError:
            return False, f"Unknown message type: {message_type}"

    def validate_signal(self, signal_type: str, data: dict) -> Tuple[bool, Optional[str]]:
        """
        Validate a signal/broadcast message against the contract.

        Args:
            signal_type: Type of signal (e.g., 'new_item')
            data: Signal data to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            schema = self.schema['messages'][signal_type]['signal']
            return self._validate_with_refs(data, schema)
        except KeyError:
            return False, f"Unknown signal type: {signal_type}"
