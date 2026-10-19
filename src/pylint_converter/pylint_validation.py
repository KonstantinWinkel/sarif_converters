# Author: Konstantin M.J. Winkel, M.Sc.

"""Validation rules for Pylint json2 messages."""

import re

from ..pylint_converter.pylint_types import PYLINT_MESSAGE_KEYS

MAX_STRING_LENGTH = 1_000_000

PYLINT_MESSAGE_ID_PATTERN = re.compile(r"^[FEWCRI][0-9]{4}$")
PYLINT_MESSAGE_TYPES = {"fatal", "error", "warning", "refactor", "convention", "info"}
PYLINT_CONFIDENCE_VALUES = {
    "UNDEFINED", "INFERENCE_FAILURE", "INFERENCE", "CONTROL_FLOW", "HIGH"
}
PYLINT_STRING_FIELDS = {
    "type", "symbol", "message", "messageId", "confidence", "module", "obj",
    "path", "absolutePath"
}
PYLINT_REQUIRED_NON_EMPTY_STRING_FIELDS = {
    "type", "symbol", "messageId", "confidence", "path", "absolutePath"
}
PYLINT_INTEGER_FIELDS = {"line", "column"}
PYLINT_OPTIONAL_INTEGER_FIELDS = {"endLine", "endColumn"}


def validate_message(message: object, message_index: int) -> None:
    """Validate one Pylint json2 message before conversion."""

    location = f"messages[{message_index}]"
    if not isinstance(message, dict):
        raise ValueError(f"{location} must be an object")
    missing_keys = [key for key in PYLINT_MESSAGE_KEYS if key not in message]
    if missing_keys:
        raise ValueError(f"{location} is missing required field '{missing_keys[0]}'")
    unexpected_keys = set(message) - set(PYLINT_MESSAGE_KEYS)
    if unexpected_keys:
        raise ValueError(f"{location} contains unsupported field '{sorted(unexpected_keys)[0]}'")
    for key in PYLINT_STRING_FIELDS:
        value = message[key]
        if not isinstance(value, str):
            raise ValueError(f"{location}.{key} must be a string")
        if key in PYLINT_REQUIRED_NON_EMPTY_STRING_FIELDS and not value:
            raise ValueError(f"{location}.{key} must not be empty")
        if len(value) > MAX_STRING_LENGTH:
            raise ValueError(
                f"{location}.{key} exceeds the {MAX_STRING_LENGTH}-character limit"
            )
    if message["type"] not in PYLINT_MESSAGE_TYPES:
        raise ValueError(f"{location}.type has unsupported value '{message['type']}'")
    if message["confidence"] not in PYLINT_CONFIDENCE_VALUES:
        raise ValueError(
            f"{location}.confidence has unsupported value '{message['confidence']}'"
        )
    if PYLINT_MESSAGE_ID_PATTERN.fullmatch(message["messageId"]) is None:
        raise ValueError(
            f"{location}.messageId must match one severity letter followed by four digits"
        )
    for key in PYLINT_INTEGER_FIELDS:
        value = message[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{location}.{key} must be an integer")
    for key in PYLINT_OPTIONAL_INTEGER_FIELDS:
        value = message[key]
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            raise ValueError(f"{location}.{key} must be an integer or null")
    if message["line"] < 1:
        raise ValueError(f"{location}.line must be at least 1")
    if message["column"] < 0:
        raise ValueError(f"{location}.column must be at least 0")
    if message["endLine"] is not None and message["endLine"] < 1:
        raise ValueError(f"{location}.endLine must be at least 1 when provided")
    if message["endColumn"] is not None and message["endColumn"] < 0:
        raise ValueError(f"{location}.endColumn must be at least 0 when provided")
    if message["endLine"] is None and message["endColumn"] is not None:
        raise ValueError(f"{location}.endColumn requires endLine")
    if message["endLine"] is not None and message["endLine"] < message["line"]:
        raise ValueError(f"{location}.endLine must not be before line")
    if (message["endLine"] == message["line"] and message["endColumn"] is not None
            and message["endColumn"] < message["column"]):
        raise ValueError(
            f"{location}.endColumn must not be before column on the same line"
        )
