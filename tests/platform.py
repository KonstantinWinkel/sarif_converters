# Author: Konstantin M.J. Winkel, M.Sc.

"""Shared platform-level regression tests for every SARIF converter."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

from dataclasses import dataclass
from pathlib import Path
from unittest import mock

from src import convert_clippy, convert_pylint, convert_shellcheck
from src.core.file_io import load_json, load_json_lines

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def _pylint_message(**overrides):
    message = {"type":"convention","symbol":"missing-function-docstring","message":"Missing function or method docstring","messageId":"C0116","confidence":"HIGH","module":"example.sample","obj":"sample","line":3,"column":0,"endLine":4,"endColumn":1,"path":"example/sample.py","absolutePath":"/workspace/example/sample.py"}
    message.update(overrides)
    return message


def _shellcheck_message(**overrides):
    message = {"file":"lib/cleaning.sh","line":8,"endLine":8,"column":20,"endColumn":22,"level":"info","code":2015,"message":"Note that A && B || C is not if-then-else.","fix":None}
    message.update(overrides)
    return message


def _clippy_record(**overrides):
    diagnostic = {"message":"length comparison to zero","code":{"code":"clippy::len_zero","explanation":None},"level":"warning","spans":[{"file_name":"src/main.rs","byte_start":10,"byte_end":25,"line_start":5,"line_end":5,"column_start":8,"column_end":25,"is_primary":True,"text":[],"label":None,"suggested_replacement":None,"suggestion_applicability":None,"expansion":None}],"children":[],"rendered":None,"$message_type":"diagnostic"}
    diagnostic.update(overrides)
    return {"reason":"compiler-message","message":diagnostic}


@dataclass(frozen=True)
class ConverterAdapter:
    """Adapter class to test the platform with different converters"""

    name: str
    convert: object
    extension: str
    loader: object
    line_format: bool

    def write(self, path, records):
        """Writes given records to a specific path."""

        if self.line_format:
            path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
        else:
            path.write_text(json.dumps(records), encoding="utf-8")

    def valid_records(self):
        """Returns a valid record for the given converter"""

        if self.name == "pylint": return {"messages":[_pylint_message()]}
        if self.name == "shellcheck": return [_shellcheck_message()]
        return [_clippy_record()]

    def write_valid(self, path):
        """Writes a valid record to a given path"""

        records = self.valid_records()
        if self.name == "pylint": path.write_text(json.dumps(records), encoding="utf-8")
        else: self.write(path, records)

    def duplicate_records(self):
        """Creates duplicated records for the given converter"""

        if self.name == "pylint": return {"messages":[_pylint_message(), _pylint_message(line=9,endLine=10)]}
        if self.name == "shellcheck": return [_shellcheck_message(), _shellcheck_message(line=10,endLine=10)]
        return [_clippy_record(), _clippy_record(message="another occurrence")]

    def limit_records(self, kind):
        """Limits the created records to a specific kind for the given converter"""

        if self.name == "pylint":
            values={"messages":[_pylint_message(),_pylint_message(line=5)],"rules":[_pylint_message(),_pylint_message(messageId="W0612",type="warning",symbol="unused-variable")],"artifacts":[_pylint_message(),_pylint_message(path="other.py",absolutePath="/workspace/other.py")]}
            return {"messages": values[kind]}
        if self.name == "shellcheck":
            return {"messages":[_shellcheck_message(),_shellcheck_message(line=9,endLine=9)],"rules":[_shellcheck_message(),_shellcheck_message(code=2317)],"artifacts":[_shellcheck_message(),_shellcheck_message(file="other.sh")]}[kind]
        second_rule=_clippy_record(code={"code":"clippy::needless_return","explanation":None})
        second_artifact=_clippy_record(); second_artifact["message"]["spans"][0]["file_name"]="src/lib.rs"
        return {"messages":[_clippy_record(),_clippy_record()],"rules":[_clippy_record(),second_rule],"artifacts":[_clippy_record(),second_artifact]}[kind]

    def write_records(self, path, records):
        """Writes the records to a given path, depending on which converter is used"""

        if self.name == "pylint": path.write_text(json.dumps(records), encoding="utf-8")
        else: self.write(path, records)

    def write_large(self, path):
        """Writes a large record, depending on the selected converter"""

        if self.name == "pylint": self.write_records(path,{"messages":[_pylint_message(message="x"*700000)]})
        elif self.name == "shellcheck": self.write_records(path,[_shellcheck_message(message="x"*700000)])
        else: self.write_records(path,[_clippy_record(message="x"*700000)])

    def invalid_text(self):
        """Creates invalid Text for pylint"""

        return {'pylint':'{"messages": [','shellcheck':'[{"file":','clippy':'{"reason":"build-finished"}\n{invalid\n'}[self.name]

    def deep_text(self):
        """Creates a deeply nested json"""

        depth=2000
        if self.name == "pylint": return '{"messages":' + '['*depth + ']'*depth + '}'
        return ('['*depth + ']'*depth + ('\n' if self.line_format else ''))


ADAPTERS = {
    "pylint": ConverterAdapter("pylint", convert_pylint, "json", load_json, False),
    "shellcheck": ConverterAdapter("shellcheck", convert_shellcheck, "json", load_json, False),
    "clippy": ConverterAdapter("clippy", convert_clippy, "json", load_json_lines, True),
}


class PlatformTestCase(unittest.TestCase):
    """Base-Class for the Platform Test Cases"""

    adapter = None
    def setUp(self):
        """Sets up the test cases for the converter"""

        # no with here, as this will be used later on too, outside of this function
        self.temporary_directory=tempfile.TemporaryDirectory() # pylint: disable=consider-using-with
        self.root=Path(self.temporary_directory.name)
        self.input_path=self.root/f"input.{self.adapter.extension}"
        self.output_path=self.root/"output.sarif"

    def tearDown(self):
        """Performs cleanup after the test cases"""

        self.temporary_directory.cleanup()

    def write_valid(self, path=None):
        """Writes and safes a valid report"""

        self.adapter.write_valid(path or self.input_path)

    def run_cli(self, input_path=None, output_path=None, timeout=10):
        """Runs the converter in the CLI"""

        return subprocess.run([ sys.executable,"-m","src.main",
                                "--converter",self.adapter.name,
                                "-i",str(input_path or self.input_path),
                                "-o",str(output_path or self.output_path) ],
                              cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=timeout, check=False)

class PlatformTests(PlatformTestCase):
    """Test Cases for the shared platform"""

    def test_cli_selects_converter(self):
        """Test to check selection of converters through the CLI"""

        self.write_valid()
        completed=self.run_cli()
        self.assertEqual(0,completed.returncode,completed.stderr)
        self.assertTrue(self.output_path.is_file())

    def test_public_api_rejects_invalid_limits(self):
        """Test to check that the API rejects invalid limits"""

        self.write_valid()
        for value in (0,-1,True,1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.adapter.convert(self.input_path,self.output_path,max_messages=value)

    def test_rules_and_artifacts_are_deduplicated_but_results_are_preserved(self):
        """Test to check if rules and artifacts are not duplicated"""

        self.adapter.write_records(self.input_path,self.adapter.duplicate_records())
        self.adapter.convert(self.input_path,self.output_path)
        run=json.loads(self.output_path.read_text(encoding="utf-8"))["runs"][0]
        self.assertEqual(1,len(run["tool"]["driver"]["rules"]))
        self.assertEqual(1,len(run["artifacts"]))
        self.assertEqual(2,len(run["results"]))

    def test_existing_output_is_not_overwritten(self):
        """Test to check that already existing output is not overwritten"""

        self.write_valid()
        self.output_path.write_text("keep me",encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.adapter.convert(self.input_path,self.output_path)
        self.assertEqual("keep me",self.output_path.read_text(encoding="utf-8"))

    @unittest.skipUnless(hasattr(os,"symlink"),"symbolic links are unavailable")
    def test_symlink_output_is_refused_without_modifying_target(self):
        """Test to check that symlinks as outputs are refuesed without changes"""

        self.write_valid()
        target=self.root/"target.txt"
        target.write_text("keep me",encoding="utf-8")
        self.output_path.symlink_to(target)
        with self.assertRaises(FileExistsError):
            self.adapter.convert(self.input_path,self.output_path)
        self.assertEqual("keep me",target.read_text(encoding="utf-8"))

    @unittest.skipUnless(hasattr(os,"symlink"),"symbolic links are unavailable")
    def test_dangling_symlink_output_is_refused(self):
        """Test to check that dangling symlinks as outputs are refused"""

        self.write_valid()
        self.output_path.symlink_to(self.root/"missing-target")
        with self.assertRaises(FileExistsError):
            self.adapter.convert(self.input_path,self.output_path)

    def test_identical_input_and_output_are_rejected_before_modification(self):
        """Test to check that identical input and output paths are rejected"""

        self.write_valid()
        original=self.input_path.read_bytes()
        with self.assertRaises(ValueError):
            self.adapter.convert(self.input_path,self.input_path)
        self.assertEqual(original,self.input_path.read_bytes())

    @unittest.skipUnless(hasattr(os,"link"),"hard links are unavailable")
    def test_hard_link_alias_is_rejected_before_modification(self):
        """Test to check that hard-link aliasses are refuesed"""

        self.write_valid()
        os.link(self.input_path,self.output_path)
        original=self.input_path.read_bytes()
        with self.assertRaises(ValueError):
            self.adapter.convert(self.input_path,self.output_path)
        self.assertEqual(original,self.input_path.read_bytes())

    def test_input_size_limit_rejects_oversized_file_without_output(self):
        """Test to check that oversized files are rejected"""

        self.input_path.write_bytes(b" "*(1024*1024+1))
        with self.assertRaises(ValueError):
            self.adapter.convert(self.input_path,self.output_path,max_input_size_mib=1)
        self.assertFalse(self.output_path.exists())

    def test_message_rule_and_artifact_limits(self):
        """Test to check message, rule and artifact limits"""

        for index,kind in enumerate(("messages","rules","artifacts")):
            with self.subTest(kind=kind):
                input_path=self.root/f"limit-{index}.json"
                output_path=self.root/f"limit-{index}.sarif"
                self.adapter.write_records(input_path,self.adapter.limit_records(kind))
                kwargs={"max_messages":100000,"max_rules":10000,"max_artifacts":100000,"max_"+kind:1}
                with self.assertRaises(ValueError):
                    self.adapter.convert(input_path,output_path,**kwargs)
                self.assertFalse(output_path.exists())

    def test_output_size_limit_does_not_publish_partial_file(self):
        """Test to check that outputfiles that are too large are not published as partial files"""

        self.adapter.write_large(self.input_path)
        with self.assertRaises(ValueError):
            self.adapter.convert(self.input_path,self.output_path,max_input_size_mib=2,max_output_size_mib=1)
        self.assertFalse(self.output_path.exists())

    def test_cli_reports_invalid_input_without_traceback(self):
        """Test to check that there are no tracebacks in the CLI for errors"""

        self.input_path.write_text(self.adapter.invalid_text(),encoding="utf-8")
        completed=self.run_cli()
        self.assertEqual(1,completed.returncode)
        self.assertIn("Conversion failed:",completed.stderr)
        self.assertNotIn("Traceback",completed.stderr)
        self.assertFalse(self.output_path.exists())

    def test_character_device_input_is_rejected_when_available(self):
        """Test to check that devices as inputs are rejected"""

        device=Path("/dev/null")
        if not device.exists():
            self.skipTest("/dev/null is unavailable")
        with self.assertRaises(ValueError):
            self.adapter.loader(str(device),1024)

    def test_deep_json_returns_controlled_cli_error_without_traceback(self):
        """Test to check that deeply nested jsons are rejected with the appropriate error message"""

        self.input_path.write_text(self.adapter.deep_text(),encoding="utf-8")
        completed=self.run_cli(timeout=10)
        self.assertEqual(1,completed.returncode)
        self.assertIn("Conversion failed:",completed.stderr)
        self.assertNotIn("Traceback",completed.stderr)
        self.assertFalse(self.output_path.exists())

    def test_size_decision_uses_open_descriptor_status(self):
        """Test to check that size decisions uses open descriptor status"""

        self.write_valid()
        real_fstat=os.fstat

        def oversized_status(fd):
            values=list(real_fstat(fd))
            values[6]=2048
            return os.stat_result(values)

        with mock.patch("src.core.file_io.os.fstat",side_effect=oversized_status), self.assertRaises(ValueError):
            self.adapter.loader(str(self.input_path),1024)

def build_platform_suite(converter=None):
    """Build the Platform test suite"""

    suite=unittest.TestSuite()
    names=[converter] if converter else list(ADAPTERS)
    for name in names:
        case=type(f"{name.title()}PlatformTests",(PlatformTests,),{"adapter":ADAPTERS[name],"__module__":__name__})
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(case))
    return suite
