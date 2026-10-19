# Author: Konstantin M.J. Winkel, M.Sc.

"""Command-line parsing and logging configuration for the converter."""

import argparse
import logging

from pathlib import Path

DEFAULT_MAX_INPUT_SIZE_MIB = 50
DEFAULT_MAX_OUTPUT_SIZE_MIB = 250
DEFAULT_MAX_MESSAGES = 100_000
DEFAULT_MAX_RULES = 10_000
DEFAULT_MAX_ARTIFACTS = 100_000

def positive_integer(value: str) -> int:
    """Return a positive integer for resource-limit command-line options."""

    parsed_value = int(value)
    if parsed_value <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")

    return parsed_value

def parse_arguments() -> argparse.Namespace:
    """Parse converter command-line arguments."""

    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Increase verbosity (-v, -vv, -vvv)")
    parser.add_argument("-c", "--converter", choices=["pylint", "shellcheck"], required=True,
                        help="The converter that was used to invoke the original report.")
    parser.add_argument("-i", "--input", type=Path, required=True,
                        help="Path to the input json file")
    parser.add_argument("-o", "--output", type=Path, required=True,
                        help="Path to the output sarif file")
    parser.add_argument("--max-input-size", type=positive_integer,
                        default=DEFAULT_MAX_INPUT_SIZE_MIB,
                        help="The maximum size of the input json file, in megabyte")
    parser.add_argument("--max-output-size", type=positive_integer,
                        default=DEFAULT_MAX_OUTPUT_SIZE_MIB,
                        help="The maximum size of the output sarif file, in megabyte")
    parser.add_argument("--max-messages", type=positive_integer,
                        default=DEFAULT_MAX_MESSAGES,
                        help="The maximum number of Pylint messages to process")
    parser.add_argument("--max-rules", type=positive_integer,
                        default=DEFAULT_MAX_RULES,
                        help="The maximum number of unique Pylint rules to process")
    parser.add_argument("--max-artifacts", type=positive_integer,
                        default=DEFAULT_MAX_ARTIFACTS,
                        help="The maximum number of unique artifacts to process")

    return parser.parse_args()


def configure_logging(verbosity: int) -> None:
    """Configure application logging from the requested verbosity."""

    logging_levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    logging.basicConfig(
        level=logging_levels.get(verbosity, logging.DEBUG),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
