# Author: Konstantin M.J. Winkel, M.Sc.

"""Type definitions for Clippy JSON output."""

# pylint: disable=duplicate-code

from dataclasses import dataclass

@dataclass(frozen=True)
class ClippyMessage:
    """One diagnostic emitted by ``cargo clippy --message-format=json``."""
    rule_id: str
    message: str
    level: str
    file: str
    line: int
    end_line: int
    column: int
    end_column: int
    help_uri: str
