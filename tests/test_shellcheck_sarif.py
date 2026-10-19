# Author: Konstantin M.J. Winkel, M.Sc.

"""Functional and security regression tests for the ShellCheck JSON to SARIF converter."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from src import convert_shellcheck
from src.core.file_io import load_json
from src.shellcheck_converter.shellcheck_sarif_converter import ShellCheckSarifConverter

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def shellcheck_message(**overrides):
    """Return one valid ShellCheck message."""
    message = {
        "file": "lib/cleaning.sh",
        "line": 8,
        "endLine": 8,
        "column": 20,
        "endColumn": 22,
        "level": "info",
        "code": 2015,
        "message": "Note that A && B || C is not if-then-else. C may run when A is true.",
        "fix": None,
    }
    message.update(overrides)
    return message


class ShellCheckConverterTestCase(unittest.TestCase):
    """Create an isolated filesystem for each ShellCheck converter test."""

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.input_path = self.root / "shellcheck.json"
        self.output_path = self.root / "shellcheck.sarif"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def write_report(self, messages=None, path=None):
        target = path or self.input_path
        target.write_text(
            json.dumps(messages if messages is not None else [shellcheck_message()]),
            encoding="utf-8",
        )
        return target

    def run_cli(self, *extra_arguments, input_path=None, output_path=None, timeout=10):
        command = [
            sys.executable,
            "-m",
            "src.main",
            "--converter",
            "shellcheck",
            "-i",
            str(input_path or self.input_path),
            "-o",
            str(output_path or self.output_path),
            *map(str, extra_arguments),
        ]
        return subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )


class FunctionalTests(ShellCheckConverterTestCase):
    """Test ShellCheck conversion through the public API and CLI."""

    def test_example_shape_is_converted(self):
        self.write_report([
            shellcheck_message(),
            shellcheck_message(
                file="shell-utils.sh", line=11, endLine=11, column=29, endColumn=35,
                code=2317,
                message="Command appears to be unreachable. Check usage (or ignore if invoked indirectly).",
            ),
        ])
        with mock.patch(
                "src.shellcheck_converter.shellcheck_sarif_converter.version",
                return_value="0.10.0"):
            convert_shellcheck(self.input_path, self.output_path)
        run = json.loads(self.output_path.read_text(encoding="utf-8"))["runs"][0]

        self.assertEqual("ShellCheck", run["tool"]["driver"]["name"])
        self.assertEqual("0.10.0", run["tool"]["driver"]["version"])
        self.assertEqual(
            ["SC2015", "SC2317"],
            [rule["id"] for rule in run["tool"]["driver"]["rules"]],
        )
        self.assertEqual(2, len(run["results"]))
        self.assertEqual("note", run["results"][0]["level"])
        self.assertEqual(
            "lib/cleaning.sh",
            run["results"][0]["locations"][0]["physicalLocation"]
            ["artifactLocation"]["uri"],
        )
        self.assertEqual("shell", run["artifacts"][0]["sourceLanguage"])

    def test_rules_and_artifacts_are_deduplicated_but_results_are_preserved(self):
        self.write_report([
            shellcheck_message(),
            shellcheck_message(line=10, endLine=10),
        ])
        convert_shellcheck(self.input_path, self.output_path)
        run = json.loads(self.output_path.read_text(encoding="utf-8"))["runs"][0]
        self.assertEqual(1, len(run["tool"]["driver"]["rules"]))
        self.assertEqual(1, len(run["artifacts"]))
        self.assertEqual(2, len(run["results"]))

    def test_cli_selects_shellcheck_converter(self):
        self.write_report()
        completed = self.run_cli()
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertTrue(self.output_path.is_file())

    def test_public_api_rejects_invalid_limits(self):
        self.write_report()
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    convert_shellcheck(
                        self.input_path, self.output_path, max_messages=value
                    )


class ExecutableResolutionTests(ShellCheckConverterTestCase):
    """Ensure version detection never executes a PATH program."""

    def test_version_lookup_does_not_execute_a_path_program(self):
        self.write_report()
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        marker = self.root / "executed"
        fake_shellcheck = fake_bin / "shellcheck"
        fake_shellcheck.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
        fake_shellcheck.chmod(0o755)
        args = SimpleNamespace(
            input=str(self.input_path), output=str(self.output_path),
            max_input_size=50, max_output_size=250,
            max_messages=100000, max_rules=10000, max_artifacts=100000,
        )
        with mock.patch.dict(os.environ, {"PATH": str(fake_bin)}), \
                mock.patch(
                    "src.shellcheck_converter.shellcheck_sarif_converter.version",
                    return_value="0.10.0",
                ), \
                mock.patch(
                    "subprocess.run",
                    side_effect=AssertionError("external process executed"),
                ):
            ShellCheckSarifConverter(args).run()
        self.assertFalse(marker.exists())
        sarif = json.loads(self.output_path.read_text(encoding="utf-8"))
        self.assertEqual("0.10.0", sarif["runs"][0]["tool"]["driver"]["version"])

    def test_missing_package_metadata_uses_safe_fallback(self):
        from importlib.metadata import PackageNotFoundError  # pylint: disable=import-outside-toplevel
        args = SimpleNamespace(
            input="unused", output="unused", max_input_size=1, max_output_size=1,
            max_messages=1, max_rules=1, max_artifacts=1,
        )
        with mock.patch(
                "src.shellcheck_converter.shellcheck_sarif_converter.version",
                side_effect=PackageNotFoundError):
            self.assertEqual(
                "unknown", ShellCheckSarifConverter(args).get_shellcheck_version()
            )


class OutputSafetyTests(ShellCheckConverterTestCase):
    """Test atomic output and input/output alias protections."""

    def test_existing_output_is_not_overwritten(self):
        self.write_report()
        self.output_path.write_text("keep me", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            convert_shellcheck(self.input_path, self.output_path)
        self.assertEqual("keep me", self.output_path.read_text(encoding="utf-8"))

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_symlink_output_is_refused_without_modifying_target(self):
        self.write_report()
        target = self.root / "target.txt"
        target.write_text("keep me", encoding="utf-8")
        self.output_path.symlink_to(target)
        with self.assertRaises(FileExistsError):
            convert_shellcheck(self.input_path, self.output_path)
        self.assertEqual("keep me", target.read_text(encoding="utf-8"))

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_dangling_symlink_output_is_refused(self):
        self.write_report()
        self.output_path.symlink_to(self.root / "missing-target")
        with self.assertRaises(FileExistsError):
            convert_shellcheck(self.input_path, self.output_path)

    def test_identical_input_and_output_are_rejected_before_modification(self):
        original = json.dumps([shellcheck_message()])
        self.input_path.write_text(original, encoding="utf-8")
        with self.assertRaises(ValueError):
            convert_shellcheck(self.input_path, self.input_path)
        self.assertEqual(original, self.input_path.read_text(encoding="utf-8"))

    @unittest.skipUnless(hasattr(os, "link"), "hard links are unavailable")
    def test_hard_link_alias_is_rejected_before_modification(self):
        self.write_report()
        os.link(self.input_path, self.output_path)
        original = self.input_path.read_bytes()
        with self.assertRaises(ValueError):
            convert_shellcheck(self.input_path, self.output_path)
        self.assertEqual(original, self.input_path.read_bytes())

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_symlink_alias_to_input_is_rejected_before_modification(self):
        self.write_report()
        self.output_path.symlink_to(self.input_path)
        original = self.input_path.read_bytes()
        with self.assertRaises(ValueError):
            convert_shellcheck(self.input_path, self.output_path)
        self.assertEqual(original, self.input_path.read_bytes())


class ResourceLimitTests(ShellCheckConverterTestCase):
    """Test configured input, output, message, rule, and artifact limits."""

    def test_input_size_limit_rejects_oversized_file_without_output(self):
        self.input_path.write_bytes(b" " * (1024 * 1024 + 1))
        with self.assertRaises(ValueError):
            convert_shellcheck(
                self.input_path, self.output_path, max_input_size_mib=1
            )
        self.assertFalse(self.output_path.exists())

    def test_message_rule_and_artifact_limits(self):
        cases = [
            ({"max_messages": 1}, [shellcheck_message(), shellcheck_message(line=9, endLine=9)]),
            ({"max_rules": 1}, [shellcheck_message(), shellcheck_message(code=2317)]),
            ({"max_artifacts": 1}, [shellcheck_message(), shellcheck_message(file="other.sh")]),
        ]
        for index, (limits, messages) in enumerate(cases):
            with self.subTest(limits=limits):
                input_path = self.root / f"limit-{index}.json"
                output_path = self.root / f"limit-{index}.sarif"
                self.write_report(messages, input_path)
                kwargs = {
                    "max_messages": 100000,
                    "max_rules": 10000,
                    "max_artifacts": 100000,
                }
                kwargs.update(limits)
                with self.assertRaises(ValueError):
                    convert_shellcheck(input_path, output_path, **kwargs)
                self.assertFalse(output_path.exists())

    def test_output_size_limit_does_not_publish_partial_file(self):
        self.write_report([shellcheck_message(message="x" * 700000)])
        with self.assertRaises(ValueError):
            convert_shellcheck(
                self.input_path, self.output_path,
                max_input_size_mib=2, max_output_size_mib=1,
            )
        self.assertFalse(self.output_path.exists())


class ValidationTests(ShellCheckConverterTestCase):
    """Test malformed ShellCheck reports and controlled CLI failures."""

    def test_malformed_reports_raise_controlled_validation_errors(self):
        valid = shellcheck_message()
        invalid_reports = [
            {},
            [None],
            [{key: value for key, value in valid.items() if key != "code"}],
            [{**valid, "unexpected": "value"}],
            [shellcheck_message(file="")],
            [shellcheck_message(level="unknown")],
            [shellcheck_message(line=True)],
            [shellcheck_message(line=0)],
            [shellcheck_message(column=0)],
            [shellcheck_message(code=0)],
            [shellcheck_message(endLine=7)],
            [shellcheck_message(endColumn=19)],
            [shellcheck_message(fix="invalid")],
        ]
        for index, report in enumerate(invalid_reports):
            with self.subTest(index=index):
                input_path = self.root / f"invalid-{index}.json"
                output_path = self.root / f"invalid-{index}.sarif"
                input_path.write_text(json.dumps(report), encoding="utf-8")
                with self.assertRaises((TypeError, ValueError)):
                    convert_shellcheck(input_path, output_path)
                self.assertFalse(output_path.exists())

    def test_cli_reports_error_without_traceback_for_invalid_input(self):
        self.input_path.write_text('[{"file":', encoding="utf-8")
        completed = self.run_cli()
        self.assertEqual(1, completed.returncode)
        self.assertIn("Conversion failed:", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertFalse(self.output_path.exists())


class SpecialFileAndParserRobustnessTests(ShellCheckConverterTestCase):
    """Test special-file rejection and parser failure handling."""

    def test_character_device_input_is_rejected_when_available(self):
        device = Path("/dev/null")
        if not device.exists():
            self.skipTest("/dev/null is unavailable")
        with self.assertRaises(ValueError):
            load_json(str(device), 1024)

    def test_deep_json_returns_controlled_cli_error_without_traceback(self):
        depth = 2000
        self.input_path.write_text(("[" * depth) + ( "]" * depth), encoding="utf-8")
        completed = self.run_cli(timeout=10)
        self.assertEqual(1, completed.returncode)
        self.assertIn("Conversion failed:", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertFalse(self.output_path.exists())

    def test_size_decision_uses_open_descriptor_status(self):
        self.write_report()
        real_fstat = os.fstat

        def oversized_status(file_descriptor):
            status = real_fstat(file_descriptor)
            values = list(status)
            values[6] = 2048
            return os.stat_result(values)

        with mock.patch("src.core.file_io.os.fstat", side_effect=oversized_status):
            with self.assertRaises(ValueError):
                load_json(str(self.input_path), 1024)


if __name__ == "__main__":
    unittest.main()
