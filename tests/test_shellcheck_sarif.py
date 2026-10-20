# Author: Konstantin M.J. Winkel, M.Sc.

"""
Functional and security regression tests for the ShellCheck JSON to SARIF converter.
"""

# pylint: disable=duplicate-code

import json
import os
import subprocess
import sys
import tempfile
import unittest

from importlib.metadata import PackageNotFoundError
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from src import convert_shellcheck
from src.shellcheck_converter.shellcheck_sarif_converter import ShellCheckSarifConverter

PROJECT_ROOT = Path(__file__).resolve().parents[1]

def shellcheck_message(**overrides):
    """Return one valid ShellCheck message."""

    message = {'file': 'lib/cleaning.sh', 'line': 8, 'endLine': 8, 'column': 20, 'endColumn': 22, 'level': 'info', 'code': 2015, 'message': 'Note that A && B || C is not if-then-else. C may run when A is true.', 'fix': None}
    message.update(overrides)
    return message

class ShellCheckConverterTestCase(unittest.TestCase):
    """Create an isolated filesystem for each ShellCheck converter test."""

    def setUp(self):
        """Sets up the test cases for the converter"""

        # no with here, as this will be used later on too, outside of this function
        self.temporary_directory = tempfile.TemporaryDirectory() # pylint: disable=consider-using-with
        self.root = Path(self.temporary_directory.name)
        self.input_path = self.root / 'shellcheck.json'
        self.output_path = self.root / 'shellcheck.sarif'

    def tearDown(self):
        """Performs cleanup after the test cases"""

        self.temporary_directory.cleanup()

    def write_report(self, messages=None, path=None):
        """Writes and safes the report after the tests"""

        target = path or self.input_path
        target.write_text(json.dumps(messages if messages is not None else [shellcheck_message()]), encoding='utf-8')
        return target

    def run_cli(self, *extra_arguments, input_path=None, output_path=None, timeout=10):
        """Runs the converter in the CLI"""

        command = [sys.executable, '-m', 'src.main', '--converter', 'shellcheck', '-i', str(input_path or self.input_path), '-o', str(output_path or self.output_path), *map(str, extra_arguments)]
        return subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=timeout, check=False)

class FunctionalTests(ShellCheckConverterTestCase):
    """Test ShellCheck conversion through the public API and CLI."""

    def test_example_shape_is_converted(self):
        """Tests to check if the example message is converted correctly"""

        self.write_report([shellcheck_message(), shellcheck_message(file='shell-utils.sh', line=11, endLine=11, column=29, endColumn=35, code=2317, message='Command appears to be unreachable. Check usage (or ignore if invoked indirectly).')])
        with mock.patch('src.shellcheck_converter.shellcheck_sarif_converter.version', return_value='0.10.0'):
            convert_shellcheck(self.input_path, self.output_path)
        run = json.loads(self.output_path.read_text(encoding='utf-8'))['runs'][0]
        self.assertEqual('ShellCheck', run['tool']['driver']['name'])
        self.assertEqual('0.10.0', run['tool']['driver']['version'])
        self.assertEqual(['SC2015', 'SC2317'], [rule['id'] for rule in run['tool']['driver']['rules']])
        self.assertEqual(2, len(run['results']))
        self.assertEqual('note', run['results'][0]['level'])
        self.assertEqual('lib/cleaning.sh', run['results'][0]['locations'][0]['physicalLocation']['artifactLocation']['uri'])
        self.assertEqual('shell', run['artifacts'][0]['sourceLanguage'])

class ExecutableResolutionTests(ShellCheckConverterTestCase):
    """Ensure version detection never executes a PATH program."""

    def test_version_lookup_does_not_execute_a_path_program(self):
        """Test to check that version checking does not execute shellcheck"""

        self.write_report()
        fake_bin = self.root / 'bin'
        fake_bin.mkdir()
        marker = self.root / 'executed'
        fake_shellcheck = fake_bin / 'shellcheck'
        fake_shellcheck.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding='utf-8')
        fake_shellcheck.chmod(493)
        args = SimpleNamespace(input=str(self.input_path), output=str(self.output_path), max_input_size=50, max_output_size=250, max_messages=100000, max_rules=10000, max_artifacts=100000)
        with mock.patch.dict(os.environ, {'PATH': str(fake_bin)}), mock.patch('src.shellcheck_converter.shellcheck_sarif_converter.version', return_value='0.10.0'), mock.patch('subprocess.run', side_effect=AssertionError('external process executed')):
            ShellCheckSarifConverter(args).run()
        self.assertFalse(marker.exists())
        sarif = json.loads(self.output_path.read_text(encoding='utf-8'))
        self.assertEqual('0.10.0', sarif['runs'][0]['tool']['driver']['version'])

    def test_missing_package_metadata_uses_safe_fallback(self):
        """Test to check that if the package is missing, the correct fallback is selected"""

        args = SimpleNamespace(input='unused', output='unused', max_input_size=1, max_output_size=1, max_messages=1, max_rules=1, max_artifacts=1)
        with mock.patch('src.shellcheck_converter.shellcheck_sarif_converter.version', side_effect=PackageNotFoundError):
            self.assertEqual('unknown', ShellCheckSarifConverter(args).get_shellcheck_version())

class ValidationTests(ShellCheckConverterTestCase):
    """Test malformed ShellCheck reports and controlled CLI failures."""

    def test_malformed_reports_raise_controlled_validation_errors(self):
        """Test that checks if a malformed report raises the correct errors (or any errors at all)"""

        valid = shellcheck_message()
        invalid_reports = [{}, [None], [{key: value for key, value in valid.items() if key != 'code'}], [{**valid, 'unexpected': 'value'}], [shellcheck_message(file='')], [shellcheck_message(level='unknown')], [shellcheck_message(line=True)], [shellcheck_message(line=0)], [shellcheck_message(column=0)], [shellcheck_message(code=0)], [shellcheck_message(endLine=7)], [shellcheck_message(endColumn=19)], [shellcheck_message(fix='invalid')]]
        for index, report in enumerate(invalid_reports):
            with self.subTest(index=index):
                input_path = self.root / f'invalid-{index}.json'
                output_path = self.root / f'invalid-{index}.sarif'
                input_path.write_text(json.dumps(report), encoding='utf-8')
                with self.assertRaises((TypeError, ValueError)):
                    convert_shellcheck(input_path, output_path)
                self.assertFalse(output_path.exists())

if __name__ == '__main__':
    unittest.main()
