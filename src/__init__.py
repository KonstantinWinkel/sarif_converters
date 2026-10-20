# Author: Konstantin M.J. Winkel, M.Sc.
"""Public API for the SARIF converters library."""
from os import PathLike, fspath
from types import SimpleNamespace
from typing import Union

from .core.cli import (
    DEFAULT_MAX_ARTIFACTS,
    DEFAULT_MAX_INPUT_SIZE_MIB,
    DEFAULT_MAX_MESSAGES,
    DEFAULT_MAX_OUTPUT_SIZE_MIB,
    DEFAULT_MAX_RULES,
)

from .clippy_converter.clippy_sarif_converter import ClippySarifConverter
from .pylint_converter.pylint_sarif_converter import PylintSarifConverter
from .shellcheck_converter.shellcheck_sarif_converter import ShellCheckSarifConverter

PathValue = Union[str, PathLike]


def _validate_limits(limits: dict) -> None:
    for name, value in limits.items():
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")


def _converter_arguments(input_path: PathValue, output_path: PathValue, limits: dict) -> SimpleNamespace:
    _validate_limits(limits)
    return SimpleNamespace(
        input=fspath(input_path),
        output=fspath(output_path),
        max_input_size=limits["max_input_size_mib"],
        max_output_size=limits["max_output_size_mib"],
        max_messages=limits["max_messages"],
        max_rules=limits["max_rules"],
        max_artifacts=limits["max_artifacts"],
    )


def _run_converter(converter, input_path, output_path, max_input_size_mib,
                   max_output_size_mib, max_messages, max_rules, max_artifacts) -> None:
    limits = {
        "max_input_size_mib": max_input_size_mib,
        "max_output_size_mib": max_output_size_mib,
        "max_messages": max_messages,
        "max_rules": max_rules,
        "max_artifacts": max_artifacts,
    }
    converter(_converter_arguments(input_path, output_path, limits)).run()


def convert_pylint(input_path: PathValue, output_path: PathValue, *,
                   max_input_size_mib: int = DEFAULT_MAX_INPUT_SIZE_MIB,
                   max_output_size_mib: int = DEFAULT_MAX_OUTPUT_SIZE_MIB,
                   max_messages: int = DEFAULT_MAX_MESSAGES,
                   max_rules: int = DEFAULT_MAX_RULES,
                   max_artifacts: int = DEFAULT_MAX_ARTIFACTS) -> None:
    """Convert a Pylint JSON2 report to a SARIF file."""

    _run_converter(PylintSarifConverter, input_path, output_path, max_input_size_mib,
                   max_output_size_mib, max_messages, max_rules, max_artifacts)


def convert_shellcheck(input_path: PathValue, output_path: PathValue, *,
                       max_input_size_mib: int = DEFAULT_MAX_INPUT_SIZE_MIB,
                       max_output_size_mib: int = DEFAULT_MAX_OUTPUT_SIZE_MIB,
                       max_messages: int = DEFAULT_MAX_MESSAGES,
                       max_rules: int = DEFAULT_MAX_RULES,
                       max_artifacts: int = DEFAULT_MAX_ARTIFACTS) -> None:
    """Convert a ShellCheck JSON report to a SARIF file."""

    _run_converter(ShellCheckSarifConverter, input_path, output_path, max_input_size_mib,
                   max_output_size_mib, max_messages, max_rules, max_artifacts)

def convert_clippy(input_path: PathValue, output_path: PathValue, *,
                   max_input_size_mib: int = DEFAULT_MAX_INPUT_SIZE_MIB,
                   max_output_size_mib: int = DEFAULT_MAX_OUTPUT_SIZE_MIB,
                   max_messages: int = DEFAULT_MAX_MESSAGES,
                   max_rules: int = DEFAULT_MAX_RULES,
                   max_artifacts: int = DEFAULT_MAX_ARTIFACTS) -> None:
    """Convert Cargo Clippy JSON-lines output to a SARIF file."""

    _run_converter(ClippySarifConverter, input_path, output_path, max_input_size_mib,
                   max_output_size_mib, max_messages, max_rules, max_artifacts)

__all__ = [
    "convert_pylint",
    "convert_shellcheck",
    "convert_clippy",
    "PylintSarifConverter",
    "ShellCheckSarifConverter",
    "ClippySarifConverter"
]
