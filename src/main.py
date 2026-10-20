# Author: Konstantin M.J. Winkel, M.Sc.

"""
This file contains the main entry point for the SARIF converters.
"""

import json
import logging
import sys

from . import convert_pylint, convert_shellcheck, convert_clippy
from .core.cli import configure_logging, parse_arguments


def main() -> int:
    """Run the converter from command-line arguments."""
    try:
        args = parse_arguments()
        configure_logging(args.verbose)

        conversion_arguments = {
            "max_input_size_mib": args.max_input_size,
            "max_output_size_mib": args.max_output_size,
            "max_messages": args.max_messages,
            "max_rules": args.max_rules,
            "max_artifacts": args.max_artifacts,
        }
        converters = {
            "pylint": convert_pylint,
            "shellcheck": convert_shellcheck,
            "clippy": convert_clippy,
        }
        converters[args.converter](args.input, args.output, **conversion_arguments)
    except (FileExistsError, json.JSONDecodeError, MemoryError, OSError,
            RecursionError, TypeError, ValueError) as exc:
        logging.getLogger(__name__).error("Conversion failed: %s", exc)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
