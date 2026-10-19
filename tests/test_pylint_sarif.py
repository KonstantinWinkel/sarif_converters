# Author: Konstantin M.J. Winkel, M.Sc.

"""
Functional and security regression tests for the Pylint JSON2 to SARIF converter.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from src import convert
from src.core.file_io import load_json
from src.pylint_converter.pylint_sarif_converter import PylintSarifConverter


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def pylint_message(**overrides):
    """Return one valid Pylint json2 message, optionally changing fields."""
    message = {
        "type": "convention",
        "symbol": "missing-function-docstring",
        "message": "Missing function or method docstring",
        "messageId": "C0116",
        "confidence": "HIGH",
        "module": "example.sample",
        "obj": "sample",
        "line": 3,
        "column": 0,
        "endLine": 4,
        "endColumn": 1,
        "path": "example/sample.py",
        "absolutePath": "/workspace/example/sample.py",
    }
    message.update(overrides)
    return message


class ConverterTestCase(unittest.TestCase):
    """Create an isolated filesystem for each converter test."""

    def setUp(self):
        """Sets up the test cases for the converter"""

        # no with here, as this will be used later on too, outside of this function
        self.temporary_directory = tempfile.TemporaryDirectory() # pylint: disable=consider-using-with
        self.root = Path(self.temporary_directory.name)
        self.input_path = self.root / "input.json"
        self.output_path = self.root / "output.sarif"

    def tearDown(self):
        """Performs cleanup after the test cases"""

        self.temporary_directory.cleanup()

    def write_report(self, messages=None, path=None):
        """Writes and safes the report after the tests"""

        target = path or self.input_path
        target.write_text(
            json.dumps({"messages": messages if messages is not None else [pylint_message()]}),
            encoding="utf-8",
        )
        return target

    def run_cli(self, *extra_arguments, input_path=None, output_path=None, timeout=10):
        """Runs the converter in the CLI"""

        command = [
            sys.executable,
            "-m",
            "src.main",
            "--converter",
            "pylint",
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


class FunctionalTests(ConverterTestCase):
    """Test definitions and functiosn for the functional tests"""

    def test_module_api_converts_valid_report(self):
        """Test to check if the tool creates a valid report"""

        self.write_report()
        with mock.patch("src.pylint_converter.pylint_sarif_converter.version", return_value="3.2.1"):
            convert(self.input_path, self.output_path)

        sarif = json.loads(self.output_path.read_text(encoding="utf-8"))
        run = sarif["runs"][0]
        self.assertEqual("2.1.0", sarif["version"])
        self.assertEqual("3.2.1", run["tool"]["driver"]["version"])
        self.assertEqual("C0116", run["tool"]["driver"]["rules"][0]["id"])
        self.assertEqual("note", run["tool"]["driver"]["rules"][0]["defaultConfiguration"]["level"])
        self.assertEqual("C0116", run["results"][0]["ruleId"])
        self.assertEqual("example/sample.py", run["artifacts"][0]["location"]["uri"])

    def test_duplicate_rules_and_artifacts_are_deduplicated_but_results_are_preserved(self):
        """Test to check if rules and artifacts are not duplicated"""

        self.write_report([
            pylint_message(line=3),
            pylint_message(line=9, endLine=10, message="A second occurrence"),
        ])
        convert(self.input_path, self.output_path)
        run = json.loads(self.output_path.read_text(encoding="utf-8"))["runs"][0]
        self.assertEqual(1, len(run["tool"]["driver"]["rules"]))
        self.assertEqual(1, len(run["artifacts"]))
        self.assertEqual(2, len(run["results"]))

    def test_optional_end_coordinates_are_omitted_when_null(self):
        """Test to check that end locations are omitted"""

        self.write_report([pylint_message(endLine=None, endColumn=None, column=0)])
        convert(self.input_path, self.output_path)
        region = json.loads(self.output_path.read_text(encoding="utf-8"))["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]
        self.assertNotIn("startColumn", region)
        self.assertNotIn("endLine", region)
        self.assertNotIn("endColumn", region)

    def test_cli_returns_success_for_valid_report(self):
        """Test to check that a valid return code is given for correct reports"""

        self.write_report()
        completed = self.run_cli()
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertTrue(self.output_path.is_file())

    def test_public_api_rejects_invalid_limits(self):
        """Test to check that invalid limits are rejected"""

        self.write_report()
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    convert(self.input_path, self.output_path, max_messages=value)


class ExecutableResolutionTests(ConverterTestCase):
    """SEC-1-PYSARIF-001 and SEC-1-PYSARIF-009."""

    def test_version_lookup_does_not_execute_a_path_program(self):
        """Test to check that version checking does not execute pylint"""

        self.write_report()
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        marker = self.root / "executed"
        fake_pylint = fake_bin / "pylint"
        fake_pylint.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
        fake_pylint.chmod(0o755)

        args = SimpleNamespace(
            input=str(self.input_path), output=str(self.output_path),
            max_input_size=50, max_output_size=250,
            max_messages=100000, max_rules=10000, max_artifacts=100000,
        )
        with mock.patch.dict(os.environ, {"PATH": str(fake_bin)}), \
                mock.patch("src.pylint_converter.pylint_sarif_converter.version", return_value="9.9.9"), \
                mock.patch("subprocess.run", side_effect=AssertionError("external process executed")):
            PylintSarifConverter(args).run()

        self.assertFalse(marker.exists())
        sarif = json.loads(self.output_path.read_text(encoding="utf-8"))
        self.assertEqual("9.9.9", sarif["runs"][0]["tool"]["driver"]["version"])

    def test_missing_package_metadata_uses_safe_fallback(self):
        """Test to check that if the package is missing, the correct fallback is selected"""

        from importlib.metadata import PackageNotFoundError # pylint: disable=import-outside-toplevel

        args = SimpleNamespace(
            input="unused", output="unused", max_input_size=1, max_output_size=1,
            max_messages=1, max_rules=1, max_artifacts=1,
        )
        with mock.patch("src.pylint_converter.pylint_sarif_converter.version", side_effect=PackageNotFoundError):
            self.assertEqual("unknown", PylintSarifConverter(args).get_pylint_version())


class OutputSafetyTests(ConverterTestCase):
    """SEC-1-PYSARIF-002 and SEC-1-PYSARIF-003."""

    def test_existing_output_is_not_overwritten(self):
        """Test to check that already existing output is not overwritten"""

        self.write_report()
        self.output_path.write_text("keep me", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            convert(self.input_path, self.output_path)
        self.assertEqual("keep me", self.output_path.read_text(encoding="utf-8"))

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_symlink_output_is_refused_without_modifying_target(self):
        """Test to check that symlinks as outputs are refuesed without changes"""

        self.write_report()
        target = self.root / "target.txt"
        target.write_text("keep me", encoding="utf-8")
        self.output_path.symlink_to(target)
        with self.assertRaises(FileExistsError):
            convert(self.input_path, self.output_path)
        self.assertEqual("keep me", target.read_text(encoding="utf-8"))

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_dangling_symlink_output_is_refused(self):
        """Test to check that dangling symlinks as outputs are refused"""

        self.write_report()
        self.output_path.symlink_to(self.root / "missing-target")
        with self.assertRaises(FileExistsError):
            convert(self.input_path, self.output_path)

    def test_identical_input_and_output_are_rejected_before_modification(self):
        """Test to check that identical input and output paths are rejected"""

        original = json.dumps({"messages": [pylint_message()]})
        self.input_path.write_text(original, encoding="utf-8")
        with self.assertRaises(ValueError):
            convert(self.input_path, self.input_path)
        self.assertEqual(original, self.input_path.read_text(encoding="utf-8"))

    @unittest.skipUnless(hasattr(os, "link"), "hard links are unavailable")
    def test_hard_link_alias_is_rejected_before_modification(self):
        """Test to check that hard-link aliasses are refuesed"""

        self.write_report()
        os.link(self.input_path, self.output_path)
        original = self.input_path.read_bytes()
        with self.assertRaises(ValueError):
            convert(self.input_path, self.output_path)
        self.assertEqual(original, self.input_path.read_bytes())

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_symlink_alias_to_input_is_rejected_before_modification(self):
        """Test to check that symplink aliases to the input are rejected as output paths"""

        self.write_report()
        self.output_path.symlink_to(self.input_path)
        original = self.input_path.read_bytes()
        with self.assertRaises(ValueError):
            convert(self.input_path, self.output_path)
        self.assertEqual(original, self.input_path.read_bytes())


class ResourceLimitTests(ConverterTestCase):
    """SEC-1-PYSARIF-004."""

    def test_input_size_limit_rejects_oversized_file_without_output(self):
        """Test to check that oversized files are rejected"""

        self.input_path.write_bytes(b" " * (1024 * 1024 + 1))
        with self.assertRaises(ValueError):
            convert(self.input_path, self.output_path, max_input_size_mib=1)
        self.assertFalse(self.output_path.exists())

    def test_message_rule_and_artifact_limits(self):
        """Test to check message, rule and artifact limits"""

        cases = [
            ({"max_messages": 1}, [pylint_message(), pylint_message(line=5)]),
            ({"max_rules": 1}, [pylint_message(), pylint_message(messageId="W0612", type="warning", symbol="unused-variable")]),
            ({"max_artifacts": 1}, [pylint_message(), pylint_message(path="other.py", absolutePath="/workspace/other.py")]),
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
                    convert(input_path, output_path, **kwargs)
                self.assertFalse(output_path.exists())

    def test_output_size_limit_does_not_publish_partial_file(self):
        """Test to check that outputfiles that are too large are not published as partial files"""

        large_text = "x" * 700000
        self.write_report([pylint_message(message=large_text)])
        with self.assertRaises(ValueError):
            convert(
                self.input_path, self.output_path,
                max_input_size_mib=2, max_output_size_mib=1,
            )
        self.assertFalse(self.output_path.exists())


class ValidationTests(ConverterTestCase):
    """SEC-1-PYSARIF-005."""

    def test_malformed_reports_raise_controlled_validation_errors(self):
        """Test that checks if a malformed report raises the correct errors (or any errors at all)"""

        valid = pylint_message()
        invalid_reports = [
            [],
            {},
            {"messages": {}},
            {"messages": [None]},
            {"messages": [{key: value for key, value in valid.items() if key != "messageId"}]},
            {"messages": [{**valid, "unexpected": "value"}]},
            {"messages": [{**valid, "messageId": ""}]},
            {"messages": [{**valid, "messageId": "X1234"}]},
            {"messages": [{**valid, "type": "unknown"}]},
            {"messages": [{**valid, "confidence": "LOW"}]},
            {"messages": [{**valid, "line": True}]},
            {"messages": [{**valid, "column": -1}]},
            {"messages": [{**valid, "endLine": 2}]},
            {"messages": [{**valid, "endLine": None, "endColumn": 2}]},
        ]
        for index, report in enumerate(invalid_reports):
            with self.subTest(index=index):
                input_path = self.root / f"invalid-{index}.json"
                output_path = self.root / f"invalid-{index}.sarif"
                input_path.write_text(json.dumps(report), encoding="utf-8")
                with self.assertRaises((TypeError, ValueError)):
                    convert(input_path, output_path)
                self.assertFalse(output_path.exists())

    def test_cli_reports_error_without_traceback_for_invalid_input(self):
        """Test to check that there are no tracebacks in the CLI for errors"""

        self.input_path.write_text('{"messages": [', encoding="utf-8")
        completed = self.run_cli()
        self.assertEqual(1, completed.returncode)
        self.assertIn("Conversion failed:", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertFalse(self.output_path.exists())


class SpecialFileAndParserRobustnessTests(ConverterTestCase):
    """H-1, H-2, and L-1 from security_report.md."""

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFOs are unavailable")
    def test_fifo_input_is_rejected_without_blocking(self):
        """Test to check that fifo inputs are rejected without blocking"""

        fifo = self.root / "input.fifo"
        os.mkfifo(fifo)
        completed = self.run_cli(input_path=fifo, output_path=self.output_path, timeout=3)
        self.assertEqual(1, completed.returncode)
        self.assertIn("regular file", completed.stderr)
        self.assertFalse(self.output_path.exists())

    def test_character_device_input_is_rejected_when_available(self):
        """Test to check that devices as inputs are rejected"""

        device = Path("/dev/null")
        if not device.exists():
            self.skipTest("/dev/null is unavailable")
        with self.assertRaises(ValueError):
            load_json(str(device), 1024)

    def test_deep_json_returns_controlled_cli_error_without_traceback(self):
        """Test to check that deeply nested jsons are rejected with the appropriate error message"""

        depth = 2000
        self.input_path.write_text(
            '{"messages":' + ('[' * depth) + (']' * depth) + '}',
            encoding="utf-8",
        )
        completed = self.run_cli(timeout=10)
        self.assertEqual(1, completed.returncode)
        self.assertIn("Conversion failed:", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertFalse(self.output_path.exists())

    def test_size_decision_uses_open_descriptor_status(self):
        """Test to check that size decisions uses open descriptor status"""

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
