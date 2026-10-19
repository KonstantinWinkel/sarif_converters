# Author: Konstantin M.J. Winkel, M.Sc.
"""Validation rules for ShellCheck JSON messages."""

MAX_STRING_LENGTH = 1_000_000
SHELLCHECK_MESSAGE_KEYS = {
    "file", "line", "endLine", "column", "endColumn", "level", "code", "message", "fix"
}
SHELLCHECK_LEVELS = {"error", "warning", "info", "style"}


def validate_message(message: object, message_index: int) -> None:
    """Validate one ShellCheck JSON message before conversion."""
    location = f"messages[{message_index}]"
    if not isinstance(message, dict):
        raise ValueError(f"{location} must be an object")

    missing_keys = SHELLCHECK_MESSAGE_KEYS - set(message)
    if missing_keys:
        raise ValueError(f"{location} is missing required field '{sorted(missing_keys)[0]}'")

    unexpected_keys = set(message) - SHELLCHECK_MESSAGE_KEYS
    if unexpected_keys:
        raise ValueError(f"{location} contains unsupported field '{sorted(unexpected_keys)[0]}'")

    for key in ("file", "level", "message"):
        value = message[key]
        if not isinstance(value, str):
            raise ValueError(f"{location}.{key} must be a string")
        if not value:
            raise ValueError(f"{location}.{key} must not be empty")
        if len(value) > MAX_STRING_LENGTH:
            raise ValueError(f"{location}.{key} exceeds the {MAX_STRING_LENGTH}-character limit")

    if message["level"] not in SHELLCHECK_LEVELS:
        raise ValueError(f"{location}.level has unsupported value '{message['level']}'")

    for key in ("line", "endLine", "column", "endColumn", "code"):
        value = message[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{location}.{key} must be an integer")

    if message["line"] < 1 or message["endLine"] < 1:
        raise ValueError(f"{location} line values must be at least 1")
    if message["column"] < 1 or message["endColumn"] < 1:
        raise ValueError(f"{location} column values must be at least 1")
    if message["code"] < 1:
        raise ValueError(f"{location}.code must be at least 1")
    if message["endLine"] < message["line"]:
        raise ValueError(f"{location}.endLine must not be before line")
    if message["endLine"] == message["line"] and message["endColumn"] < message["column"]:
        raise ValueError(f"{location}.endColumn must not be before column on the same line")
    if message["fix"] is not None and not isinstance(message["fix"], dict):
        raise ValueError(f"{location}.fix must be an object or null")

