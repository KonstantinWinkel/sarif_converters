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

    diagnostic = {'message': 'length comparison to zero', 'code': {'code': 'clippy::len_zero', 'explanation': None}, 'level': 'warning', 'spans': [{'file_name': 'src/main.rs', 'byte_start': 10, 'byte_end': 25, 'line_start': 5, 'line_end': 5, 'column_start': 8, 'column_end': 25, 'is_primary': True, 'text': [], 'label': None, 'suggested_replacement': None, 'suggestion_applicability': None, 'expansion': None}], 'children': [{'message': 'for further information visit https://rust-lang.github.io/rust-clippy/master/index.html#len_zero', 'code': None, 'level': 'help', 'spans': [], 'children': [], 'rendered': None}], 'rendered': None, '$message_type': 'diagnostic'}
    diagnostic.update(diagnostic_overrides)
    return {'reason': 'compiler-message', 'message': diagnostic}

def non_clippy_record():
    """Return a valid Cargo record that the converter must ignore."""

    return {'reason': 'build-finished', 'success': True}

class ClippyConverterTestCase(unittest.TestCase):
    """Create an isolated filesystem for each Clippy converter test."""

    def setUp(self):
        """Sets up the test cases for the converter"""

        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.input_path = self.root / 'clippy.json'
        self.output_path = self.root / 'clippy.sarif'

    def tearDown(self):
        """Performs cleanup after the test cases"""

        self.temporary_directory.cleanup()

    def write_report(self, records=None, path=None):
        """Write newline-delimited Cargo JSON records."""

        target = path or self.input_path
        records = records if records is not None else [clippy_record()]
        target.write_text('\n'.join((json.dumps(record) for record in records)) + '\n', encoding='utf-8')
        return target

    def run_cli(self, *extra_arguments, input_path=None, output_path=None, timeout=10):
        """Runs the converter in the CLI"""

        command = [sys.executable, '-m', 'src.main', '--converter', 'clippy', '-i', str(input_path or self.input_path), '-o', str(output_path or self.output_path), *map(str, extra_arguments)]
        return subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=timeout, check=False)

class FunctionalTests(ClippyConverterTestCase):
    """Test Clippy-specific conversion through the public API and CLI."""

    def test_clippy_diagnostic_is_converted(self):
        """Tests to check if the example message is converted correctly"""

        self.write_report()
        convert_clippy(self.input_path, self.output_path)
        run = json.loads(self.output_path.read_text(encoding='utf-8'))['runs'][0]
        driver = run['tool']['driver']
        self.assertEqual('Clippy', driver['name'])
        self.assertEqual('unknown', driver['version'])
        self.assertEqual('clippy::len_zero', driver['rules'][0]['id'])
        self.assertEqual('len_zero', driver['rules'][0]['name'])
        self.assertEqual('warning', driver['rules'][0]['defaultConfiguration']['level'])
        self.assertEqual('clippy::len_zero', run['results'][0]['ruleId'])
        self.assertEqual('warning', run['results'][0]['level'])
        self.assertEqual('src/main.rs', run['artifacts'][0]['location']['uri'])
        self.assertEqual('rust', run['artifacts'][0]['sourceLanguage'])

    def test_non_clippy_cargo_records_and_non_clippy_diagnostics_are_ignored(self):
        """Teest to check that only diagnostic records are passed"""

        rustc_record = clippy_record(code={'code': 'dead_code', 'explanation': None})
        self.write_report([non_clippy_record(), rustc_record, clippy_record()])
        convert_clippy(self.input_path, self.output_path)
        run = json.loads(self.output_path.read_text(encoding='utf-8'))['runs'][0]
        self.assertEqual(1, len(run['results']))
        self.assertEqual('clippy::len_zero', run['results'][0]['ruleId'])

    def test_help_uri_is_taken_from_clippy_child_message(self):
        """Test to check the the help URI is taken from a clippy child message"""

        expected = 'https://rust-lang.github.io/rust-clippy/rust-1.98.0/index.html#len_zero'
        record = clippy_record(children=[{'message': f'for further information visit {expected}', 'code': None, 'level': 'help', 'spans': [], 'children': [], 'rendered': None}])
        self.write_report([record])
        convert_clippy(self.input_path, self.output_path)
        rule = json.loads(self.output_path.read_text(encoding='utf-8'))['runs'][0]['tool']['driver']['rules'][0]
        self.assertEqual(expected, rule['helpUri'])

class ValidationTests(ClippyConverterTestCase):
    """Test malformed JSON-lines records and Clippy diagnostic validation."""

    def test_malformed_records_raise_controlled_validation_errors(self):
        """Test that checks if a malformed report raises the correct errors (or any errors at all)"""

        invalid_records = [None, {'reason': 'compiler-message', 'message': None}, clippy_record(message=''), clippy_record(level='unknown'), clippy_record(spans={}), clippy_record(spans=[]), clippy_record(spans=[{'is_primary': False}])]
        invalid_records.extend([clippy_record(spans=[{**clippy_record()['message']['spans'][0], key: value}]) for key, value in (('file_name', ''), ('line_start', True), ('line_start', 0), ('line_end', 4), ('column_start', 0), ('column_end', 7))])
        for index, record in enumerate(invalid_records):
            with self.subTest(index=index):
                input_path = self.root / f'invalid-{index}.json'
                output_path = self.root / f'invalid-{index}.sarif'
                self.write_report([record], input_path)
                with self.assertRaises((TypeError, ValueError)):
                    convert_clippy(input_path, output_path)
                self.assertFalse(output_path.exists())

if __name__ == '__main__':
    unittest.main()
