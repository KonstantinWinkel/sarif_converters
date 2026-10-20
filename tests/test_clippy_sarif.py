# Author: Konstantin M.J. Winkel, M.Sc.

"""Functional and security regression tests for the Clippy JSON-lines to SARIF converter."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import convert_clippy
from src.core.file_io import load_json_lines

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def clippy_record(**diagnostic_overrides):
    """Return one valid Cargo compiler-message record containing a Clippy diagnostic."""

    diagnostic = {
        "message": "length comparison to zero",
        "code": {"code": "clippy::len_zero", "explanation": None},
        "level": "warning",
        "spans": [{
            "file_name": "src/main.rs",
            "byte_start": 10,
            "byte_end": 25,
            "line_start": 5,
            "line_end": 5,
            "column_start": 8,
            "column_end": 25,
            "is_primary": True,
            "text": [],
            "label": None,
            "suggested_replacement": None,
            "suggestion_applicability": None,
            "expansion": None,
        }],
        "children": [{
            "message": "for further information visit https://rust-lang.github.io/rust-clippy/master/index.html#len_zero",
            "code": None,
            "level": "help",
            "spans": [],
            "children": [],
            "rendered": None,
        }],
        "rendered": None,
        "$message_type": "diagnostic",
    }
    diagnostic.update(diagnostic_overrides)
    return {"reason": "compiler-message", "message": diagnostic}


def non_clippy_record():
    """Return a valid Cargo record that the converter must ignore."""

    return {"reason": "build-finished", "success": True}


class ClippyConverterTestCase(unittest.TestCase):
    """Create an isolated filesystem for each Clippy converter test."""

    def setUp(self):
        """Sets up the test cases for the converter"""

        self.temporary_directory = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.root = Path(self.temporary_directory.name)
        self.input_path = self.root / "clippy.json"
        self.output_path = self.root / "clippy.sarif"

    def tearDown(self):
        """Performs cleanup after the test cases"""

        self.temporary_directory.cleanup()

    def write_report(self, records=None, path=None):
        """Write newline-delimited Cargo JSON records."""

        target = path or self.input_path
        records = records if records is not None else [clippy_record()]
        target.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
        return target

    def run_cli(self, *extra_arguments, input_path=None, output_path=None, timeout=10):
        """Runs the converter in the CLI"""

        command = [
            sys.executable, "-m", "src.main", "--converter", "clippy",
            "-i", str(input_path or self.input_path),
            "-o", str(output_path or self.output_path),
            *map(str, extra_arguments),
        ]
        return subprocess.run(
            command, cwd=PROJECT_ROOT, capture_output=True, text=True,
            timeout=timeout, check=False,
        )


class FunctionalTests(ClippyConverterTestCase):
    """Test Clippy-specific conversion through the public API and CLI."""

    def test_clippy_diagnostic_is_converted(self):
        """Tests to check if the example message is converted correctly"""

        self.write_report()
        convert_clippy(self.input_path, self.output_path)
        run = json.loads(self.output_path.read_text(encoding="utf-8"))["runs"][0]
        driver = run["tool"]["driver"]
        self.assertEqual("Clippy", driver["name"])
        self.assertEqual("unknown", driver["version"])
        self.assertEqual("clippy::len_zero", driver["rules"][0]["id"])
        self.assertEqual("len_zero", driver["rules"][0]["name"])
        self.assertEqual("warning", driver["rules"][0]["defaultConfiguration"]["level"])
        self.assertEqual("clippy::len_zero", run["results"][0]["ruleId"])
        self.assertEqual("warning", run["results"][0]["level"])
        self.assertEqual("src/main.rs", run["artifacts"][0]["location"]["uri"])
        self.assertEqual("rust", run["artifacts"][0]["sourceLanguage"])

    def test_non_clippy_cargo_records_and_non_clippy_diagnostics_are_ignored(self):
        """Teest to check that only diagnostic records are passed"""

        rustc_record = clippy_record(code={"code": "dead_code", "explanation": None})
        self.write_report([non_clippy_record(), rustc_record, clippy_record()])
        convert_clippy(self.input_path, self.output_path)
        run = json.loads(self.output_path.read_text(encoding="utf-8"))["runs"][0]
        self.assertEqual(1, len(run["results"]))
        self.assertEqual("clippy::len_zero", run["results"][0]["ruleId"])

    def test_help_uri_is_taken_from_clippy_child_message(self):
        """Test to check the the help URI is taken from a clippy child message"""

        expected = "https://rust-lang.github.io/rust-clippy/rust-1.98.0/index.html#len_zero"
        record = clippy_record(children=[{
            "message": f"for further information visit {expected}",
            "code": None, "level": "help", "spans": [], "children": [], "rendered": None,
        }])
        self.write_report([record])
        convert_clippy(self.input_path, self.output_path)
        rule = json.loads(self.output_path.read_text(encoding="utf-8"))["runs"][0]["tool"]["driver"]["rules"][0]
        self.assertEqual(expected, rule["helpUri"])

    def test_rules_and_artifacts_are_deduplicated_but_results_are_preserved(self):
        """Test to check that rules and artifacts are not duplicated"""

        second = clippy_record(message="another occurrence")
        second["message"]["spans"][0].update({"line_start": 9, "line_end": 9})
        self.write_report([clippy_record(), second])
        convert_clippy(self.input_path, self.output_path)
        run = json.loads(self.output_path.read_text(encoding="utf-8"))["runs"][0]
        self.assertEqual(1, len(run["tool"]["driver"]["rules"]))
        self.assertEqual(1, len(run["artifacts"]))
        self.assertEqual(2, len(run["results"]))

    def test_cli_selects_clippy_converter(self):
        """Test to check that the CLI interface works correctly"""

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
                    convert_clippy(self.input_path, self.output_path, max_messages=value)


class OutputSafetyTests(ClippyConverterTestCase):
    """Apply shared atomic-output and path-alias regressions to Clippy."""

    def test_existing_output_is_not_overwritten(self):
        """Test to check that already existing output is not overwritten"""

        self.write_report()
        self.output_path.write_text("keep me", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            convert_clippy(self.input_path, self.output_path)
        self.assertEqual("keep me", self.output_path.read_text(encoding="utf-8"))

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_symlink_output_is_refused_without_modifying_target(self):
        """Test to check that symlinks as outputs are refuesed without changes"""

        self.write_report()
        target = self.root / "target.txt"
        target.write_text("keep me", encoding="utf-8")
        self.output_path.symlink_to(target)
        with self.assertRaises(FileExistsError):
            convert_clippy(self.input_path, self.output_path)
        self.assertEqual("keep me", target.read_text(encoding="utf-8"))

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_dangling_symlink_output_is_refused(self):
        """Test to check that dangling symlinks as outputs are refused"""

        self.write_report()
        self.output_path.symlink_to(self.root / "missing-target")
        with self.assertRaises(FileExistsError):
            convert_clippy(self.input_path, self.output_path)

    def test_identical_input_and_output_are_rejected_before_modification(self):
        """Test to check that identical input and output paths are rejected"""

        self.write_report()
        original = self.input_path.read_bytes()
        with self.assertRaises(ValueError):
            convert_clippy(self.input_path, self.input_path)
        self.assertEqual(original, self.input_path.read_bytes())

    @unittest.skipUnless(hasattr(os, "link"), "hard links are unavailable")
    def test_hard_link_alias_is_rejected_before_modification(self):
        """Test to check that hard-link aliasses are refuesed"""

        self.write_report()
        os.link(self.input_path, self.output_path)
        original = self.input_path.read_bytes()
        with self.assertRaises(ValueError):
            convert_clippy(self.input_path, self.output_path)
        self.assertEqual(original, self.input_path.read_bytes())

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are unavailable")
    def test_symlink_alias_to_input_is_rejected_before_modification(self):
        """Test to check that symplink aliases to the input are rejected as output paths"""

        self.write_report()
        self.output_path.symlink_to(self.input_path)
        original = self.input_path.read_bytes()
        with self.assertRaises(ValueError):
            convert_clippy(self.input_path, self.output_path)
        self.assertEqual(original, self.input_path.read_bytes())


class ResourceLimitTests(ClippyConverterTestCase):
    """Apply shared resource-limit regressions to JSON-lines input."""

    def test_input_size_limit_rejects_oversized_file_without_output(self):
        """Test to check that oversized files are rejected"""

        self.input_path.write_bytes(b" " * (1024 * 1024 + 1))
        with self.assertRaises(ValueError):
            convert_clippy(self.input_path, self.output_path, max_input_size_mib=1)
        self.assertFalse(self.output_path.exists())

    def test_message_rule_and_artifact_limits(self):
        """Test to check message, rule and artifact limits"""

        second_rule = clippy_record(code={"code": "clippy::needless_return", "explanation": None})
        second_artifact = clippy_record()
        second_artifact["message"]["spans"][0]["file_name"] = "src/lib.rs"
        cases = [
            ({"max_messages": 1}, [clippy_record(), clippy_record()]),
            ({"max_rules": 1}, [clippy_record(), second_rule]),
            ({"max_artifacts": 1}, [clippy_record(), second_artifact]),
        ]
        for index, (limits, records) in enumerate(cases):
            with self.subTest(limits=limits):
                input_path = self.root / f"limit-{index}.json"
                output_path = self.root / f"limit-{index}.sarif"
                self.write_report(records, input_path)
                kwargs = {"max_messages": 100000, "max_rules": 10000, "max_artifacts": 100000}
                kwargs.update(limits)
                with self.assertRaises(ValueError):
                    convert_clippy(input_path, output_path, **kwargs)
                self.assertFalse(output_path.exists())

    def test_output_size_limit_does_not_publish_partial_file(self):
        """Test to check that outputfiles that are too large are not published as partial files"""

        self.write_report([clippy_record(message="x" * 700000)])
        with self.assertRaises(ValueError):
            convert_clippy(
                self.input_path, self.output_path,
                max_input_size_mib=2, max_output_size_mib=1,
            )
        self.assertFalse(self.output_path.exists())


class ValidationTests(ClippyConverterTestCase):
    """Test malformed JSON-lines records and Clippy diagnostic validation."""

    def test_malformed_records_raise_controlled_validation_errors(self):
        """Test that checks if a malformed report raises the correct errors (or any errors at all)"""

        invalid_records = [
            None,
            {"reason": "compiler-message", "message": None},
            clippy_record(message=""),
            clippy_record(level="unknown"),
            clippy_record(spans={}),
            clippy_record(spans=[]),
            clippy_record(spans=[{"is_primary": False}]),
        ]
        invalid_records.extend([
            clippy_record(spans=[{
                **clippy_record()["message"]["spans"][0], key: value
            }])
            for key, value in (
                ("file_name", ""), ("line_start", True), ("line_start", 0),
                ("line_end", 4), ("column_start", 0), ("column_end", 7),
            )
        ])
        for index, record in enumerate(invalid_records):
            with self.subTest(index=index):
                input_path = self.root / f"invalid-{index}.json"
                output_path = self.root / f"invalid-{index}.sarif"
                self.write_report([record], input_path)
                with self.assertRaises((TypeError, ValueError)):
                    convert_clippy(input_path, output_path)
                self.assertFalse(output_path.exists())

    def test_invalid_json_line_identifies_line_and_cli_hides_traceback(self):
        """Test to check that there are no tracebacks in the CLI for errors"""

        self.input_path.write_text(json.dumps(non_clippy_record()) + "\n{invalid\n", encoding="utf-8")
        completed = self.run_cli()
        self.assertEqual(1, completed.returncode)
        self.assertIn("Conversion failed:", completed.stderr)
        self.assertIn("line 2", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertFalse(self.output_path.exists())


class SpecialFileAndParserRobustnessTests(ClippyConverterTestCase):
    """Apply shared special-file and parser robustness tests to JSON-lines loading."""

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFOs are unavailable")
    def test_fifo_input_is_rejected_without_blocking(self):
        """Test to check that fifo inputs are rejected without blocking"""

        fifo = self.root / "input.fifo"
        os.mkfifo(fifo)
        completed = self.run_cli(input_path=fifo, timeout=3)
        self.assertEqual(1, completed.returncode)
        self.assertIn("regular file", completed.stderr)
        self.assertFalse(self.output_path.exists())

    def test_character_device_input_is_rejected_when_available(self):
        """Test to check that devices as inputs are rejected"""

        device = Path("/dev/null")
        if not device.exists():
            self.skipTest("/dev/null is unavailable")
        with self.assertRaises(ValueError):
            load_json_lines(str(device), 1024)

    def test_deep_json_line_returns_controlled_cli_error_without_traceback(self):
        """Test to check that deeply nested json lines produce the correct errors and no tracebacks"""

        depth = 2000
        self.input_path.write_text(("[" * depth) + ("]" * depth) + "\n", encoding="utf-8")
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
                load_json_lines(str(self.input_path), 1024)


if __name__ == "__main__":
    unittest.main()
