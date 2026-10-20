# Author: Konstantin M.J. Winkel, M.Sc.

"""Validation and extraction rules for Clippy JSON messages."""

from .clippy_types import ClippyMessage

MAX_STRING_LENGTH = 1_000_000
CLIPPY_LEVELS = {"error", "warning", "note", "help", "failure-note"}


def _string(value: object, location: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{location} must be a string")
    if not allow_empty and not value:
        raise ValueError(f"{location} must not be empty")
    if len(value) > MAX_STRING_LENGTH:
        raise ValueError(f"{location} exceeds the {MAX_STRING_LENGTH}-character limit")
    return value


def _integer(value: object, location: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{location} must be an integer")
    if value < minimum:
        raise ValueError(f"{location} must be at least {minimum}")
    return value


def parse_message(record: object, record_index: int) -> ClippyMessage | None:
    """Validate one Cargo JSON record and return a Clippy diagnostic when present."""

    location = f"records[{record_index}]"
    if not isinstance(record, dict):
        raise ValueError(f"{location} must be an object")
    reason = record.get("reason")
    if reason != "compiler-message":
        return None
    diagnostic = record.get("message")
    if not isinstance(diagnostic, dict):
        raise ValueError(f"{location}.message must be an object")
    code = diagnostic.get("code")
    if not isinstance(code, dict):
        return None
    rule_id = _string(code.get("code"), f"{location}.message.code.code")
    if not rule_id.startswith("clippy::"):
        return None
    message = _string(diagnostic.get("message"), f"{location}.message.message")
    level = _string(diagnostic.get("level"), f"{location}.message.level")
    if level not in CLIPPY_LEVELS:
        raise ValueError(f"{location}.message.level has unsupported value '{level}'")
    spans = diagnostic.get("spans")
    if not isinstance(spans, list):
        raise ValueError(f"{location}.message.spans must be an array")
    primary_spans = [span for span in spans if isinstance(span, dict) and span.get("is_primary") is True]
    if not primary_spans:
        raise ValueError(f"{location}.message.spans must contain a primary span")
    span = primary_spans[0]
    file_name = _string(span.get("file_name"), f"{location}.message.spans[0].file_name")
    line = _integer(span.get("line_start"), f"{location}.message.spans[0].line_start")
    end_line = _integer(span.get("line_end"), f"{location}.message.spans[0].line_end")
    column = _integer(span.get("column_start"), f"{location}.message.spans[0].column_start")
    end_column = _integer(span.get("column_end"), f"{location}.message.spans[0].column_end")
    if end_line < line:
        raise ValueError(f"{location}.message.spans[0].line_end must not be before line_start")
    if end_line == line and end_column < column:
        raise ValueError(f"{location}.message.spans[0].column_end must not be before column_start")
    rule_name = rule_id.removeprefix("clippy::")
    help_uri = f"https://rust-lang.github.io/rust-clippy/master/index.html#{rule_name}"
    for child in diagnostic.get("children", []):
        if not isinstance(child, dict):
            continue
        child_message = child.get("message")
        if isinstance(child_message, str) and child_message.startswith("for further information visit "):
            help_uri = child_message.removeprefix("for further information visit ")
            break
    return ClippyMessage(
        rule_id=rule_id,
        message=message,
        level=level,
        file=file_name,
        line=line,
        end_line=end_line,
        column=column,
        end_column=end_column,
        help_uri=help_uri,
    )
