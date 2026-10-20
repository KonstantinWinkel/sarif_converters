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

from src import convert_pylint
from src.core.file_io import load_json
from src.pylint_converter.pylint_sarif_converter import PylintSarifConverter

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def pylint_message(**overrides):
    """Return one valid Pylint json2 message, optionally changing fields."""

    message = {'type': 'convention', 'symbol': 'missing-function-docstring', 'message': 'Missing function or method docstring', 'messageId': 'C0116', 'confidence': 'HIGH', 'module': 'example.sample', 'obj': 'sample', 'line': 3, 'column': 0, 'endLine': 4, 'endColumn': 1, 'path': 'example/sample.py', 'absolutePath': '/workspace/example/sample.py'}
    message.update(overrides)
    return message

class ConverterTestCase(unittest.TestCase):
    """Create an isolated filesystem for each converter test."""

    def setUp(self):
        """Sets up the test cases for the converter"""

        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.input_path = self.root / 'input.json'
        self.output_path = self.root / 'output.sarif'

    def tearDown(self):
        """Performs cleanup after the test cases"""

        self.temporary_directory.cleanup()

    def write_report(self, messages=None, path=None):
        """Writes and safes the report after the tests"""

        target = path or self.input_path
        target.write_text(json.dumps({'messages': messages if messages is not None else [pylint_message()]}), encoding='utf-8')
        return target

    def run_cli(self, *extra_arguments, input_path=None, output_path=None, timeout=10):
        """Runs the converter in the CLI"""

        command = [sys.executable, '-m', 'src.main', '--converter', 'pylint', '-i', str(input_path or self.input_path), '-o', str(output_path or self.output_path), *map(str, extra_arguments)]
        return subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=timeout, check=False)

class FunctionalTests(ConverterTestCase):
    """Test definitions and functiosn for the functional tests"""

    def test_module_api_converts_valid_report(self):
        """Test to check if the tool creates a valid report"""

        self.write_report()
        with mock.patch('src.pylint_converter.pylint_sarif_converter.version', return_value='3.2.1'):
            convert_pylint(self.input_path, self.output_path)
        sarif = json.loads(self.output_path.read_text(encoding='utf-8'))
        run = sarif['runs'][0]
        self.assertEqual('2.1.0', sarif['version'])
        self.assertEqual('3.2.1', run['tool']['driver']['version'])
        self.assertEqual('C0116', run['tool']['driver']['rules'][0]['id'])
        self.assertEqual('note', run['tool']['driver']['rules'][0]['defaultConfiguration']['level'])
        self.assertEqual('C0116', run['results'][0]['ruleId'])
        self.assertEqual('example/sample.py', run['artifacts'][0]['location']['uri'])

    def test_optional_end_coordinates_are_omitted_when_null(self):
        """Test to check that end locations are omitted"""

        self.write_report([pylint_message(endLine=None, endColumn=None, column=0)])
        convert_pylint(self.input_path, self.output_path)
        region = json.loads(self.output_path.read_text(encoding='utf-8'))['runs'][0]['results'][0]['locations'][0]['physicalLocation']['region']
        self.assertNotIn('startColumn', region)
        self.assertNotIn('endLine', region)
        self.assertNotIn('endColumn', region)

class ExecutableResolutionTests(ConverterTestCase):
    """SEC-1-PYSARIF-001 and SEC-1-PYSARIF-009."""

    def test_version_lookup_does_not_execute_a_path_program(self):
        """Test to check that version checking does not execute pylint"""

        self.write_report()
        fake_bin = self.root / 'bin'
        fake_bin.mkdir()
        marker = self.root / 'executed'
        fake_pylint = fake_bin / 'pylint'
        fake_pylint.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding='utf-8')
        fake_pylint.chmod(493)
        args = SimpleNamespace(input=str(self.input_path), output=str(self.output_path), max_input_size=50, max_output_size=250, max_messages=100000, max_rules=10000, max_artifacts=100000)
        with mock.patch.dict(os.environ, {'PATH': str(fake_bin)}), mock.patch('src.pylint_converter.pylint_sarif_converter.version', return_value='9.9.9'), mock.patch('subprocess.run', side_effect=AssertionError('external process executed')):
            PylintSarifConverter(args).run()
        self.assertFalse(marker.exists())
        sarif = json.loads(self.output_path.read_text(encoding='utf-8'))
        self.assertEqual('9.9.9', sarif['runs'][0]['tool']['driver']['version'])

    def test_missing_package_metadata_uses_safe_fallback(self):
        """Test to check that if the package is missing, the correct fallback is selected"""

        from importlib.metadata import PackageNotFoundError
        args = SimpleNamespace(input='unused', output='unused', max_input_size=1, max_output_size=1, max_messages=1, max_rules=1, max_artifacts=1)
        with mock.patch('src.pylint_converter.pylint_sarif_converter.version', side_effect=PackageNotFoundError):
            self.assertEqual('unknown', PylintSarifConverter(args).get_pylint_version())

class ValidationTests(ConverterTestCase):
    """SEC-1-PYSARIF-005."""

    def test_malformed_reports_raise_controlled_validation_errors(self):
        """Test that checks if a malformed report raises the correct errors (or any errors at all)"""

        valid = pylint_message()
        invalid_reports = [[], {}, {'messages': {}}, {'messages': [None]}, {'messages': [{key: value for key, value in valid.items() if key != 'messageId'}]}, {'messages': [{**valid, 'unexpected': 'value'}]}, {'messages': [{**valid, 'messageId': ''}]}, {'messages': [{**valid, 'messageId': 'X1234'}]}, {'messages': [{**valid, 'type': 'unknown'}]}, {'messages': [{**valid, 'confidence': 'LOW'}]}, {'messages': [{**valid, 'line': True}]}, {'messages': [{**valid, 'column': -1}]}, {'messages': [{**valid, 'endLine': 2}]}, {'messages': [{**valid, 'endLine': None, 'endColumn': 2}]}]
        for index, report in enumerate(invalid_reports):
            with self.subTest(index=index):
                input_path = self.root / f'invalid-{index}.json'
                output_path = self.root / f'invalid-{index}.sarif'
                input_path.write_text(json.dumps(report), encoding='utf-8')
                with self.assertRaises((TypeError, ValueError)):
                    convert_pylint(input_path, output_path)
                self.assertFalse(output_path.exists())

if __name__ == '__main__':
    unittest.main()
