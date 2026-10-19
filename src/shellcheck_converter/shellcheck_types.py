# Author: Konstantin M.J. Winkel, M.Sc.
"""Type definitions for ShellCheck JSON output."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ShellCheckMessage:
    """One diagnostic emitted by ShellCheck's JSON output format."""

    file: str
    line: int
    end_line: int
    column: int
    end_column: int
    level: str
    code: int
    message: str
    fix: Optional[dict]

