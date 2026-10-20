# Author: Konstantin M.J. Winkel, M.Sc.

"""Command-line entry point for the SARIF converters test suite."""

import argparse
import sys
import unittest

from . import test_clippy_sarif, test_pylint_sarif, test_shellcheck_sarif
from .platform import build_platform_suite


def parse_arguments(arguments=None) -> argparse.Namespace:
    """Parse test-suite command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Run all SARIF converter tests or the tests for one converter."
    )
    parser.add_argument(
        "--converter",
        choices=["pylint", "shellcheck", "clippy"],
        help="Only run the tests for the selected converter.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Show individual test names and results.",
    )
    return parser.parse_args(arguments)


def build_suite(converter: str | None = None) -> unittest.TestSuite:
    """Build the complete suite or one explicitly selected converter suite."""

    suites = {
        "pylint": unittest.defaultTestLoader.loadTestsFromModule(test_pylint_sarif),
        "shellcheck": unittest.defaultTestLoader.loadTestsFromModule(test_shellcheck_sarif),
        "clippy": unittest.defaultTestLoader.loadTestsFromModule(test_clippy_sarif),
    }
    analyzer_suite = suites[converter] if converter is not None else unittest.TestSuite(suites.values())
    return unittest.TestSuite([build_platform_suite(converter), analyzer_suite])


def main(arguments=None) -> int:
    """Run the requested tests and return a process exit code."""

    args = parse_arguments(arguments)
    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(
        build_suite(args.converter)
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
