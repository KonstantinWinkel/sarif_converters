# Author: Konstantin M.J. Winkel, M.Sc.

"""ShellCheck JSON to SARIF conversion."""

import logging
from copy import deepcopy
from importlib.metadata import PackageNotFoundError, version

from ..core.file_io import load_json, load_template, save_json_atomically, validate_input_output_paths
from ..core.paths import ARTEFACT_TEMPLATE_PATH, RESULT_TEMPLATE_PATH, RULE_TEMPLATE_PATH, SARIF_TEMPLATE_PATH
from ..core.sarif_types import SarifSeverity, sarif_severity_to_string
from .shellcheck_types import ShellCheckMessage
from .shellcheck_validation import validate_message

logger = logging.getLogger(__name__)


class ShellCheckSarifConverter:
    """Convert the JSON array produced by ``shellcheck --format=json`` to SARIF."""

    def __init__(self, args):
        self.args = args
        self.json_content = []
        self.sarif_content = {}
        self.max_input_size_bytes = self.args.max_input_size * 1024 * 1024
        self.max_output_size_bytes = self.args.max_output_size * 1024 * 1024
        self.max_messages = self.args.max_messages
        self.max_rules = self.args.max_rules
        self.max_artifacts = self.args.max_artifacts

    def run(self) -> None:
        """Run the complete conversion."""
        validate_input_output_paths(self.args.input, self.args.output)
        self.load_json_file(self.args.input)

        sarif_template = load_template(str(SARIF_TEMPLATE_PATH))
        rule_template = load_template(str(RULE_TEMPLATE_PATH))
        result_template = load_template(str(RESULT_TEMPLATE_PATH))
        artefact_template = load_template(str(ARTEFACT_TEMPLATE_PATH))

        rules = self._get_sarif_rule_definitions(rule_template)
        results = self._get_sarif_result_definitions(result_template)
        artifacts = self._get_sarif_artifact_definitions(artefact_template)
        self._build_sarif_file(sarif_template, rules, results, artifacts)
        save_json_atomically(self.sarif_content, self.args.output, self.max_output_size_bytes)

    @staticmethod
    def _get_sarif_severity(level: str) -> SarifSeverity:
        return {
            "error": SarifSeverity.ERROR,
            "warning": SarifSeverity.WARNING,
            "info": SarifSeverity.NOTE,
            "style": SarifSeverity.NOTE,
        }[level]

    @staticmethod
    def _rule_id(message: ShellCheckMessage) -> str:
        return f"SC{message.code}"

    def _get_sarif_rule_definitions(self, rule_template: dict) -> list:
        rules = {}
        for message in self.json_content:
            rule_id = self._rule_id(message)
            if rule_id in rules:
                continue
            if len(rules) >= self.max_rules:
                raise ValueError(f"ShellCheck report exceeds the {self.max_rules}-rule limit")
            rule = deepcopy(rule_template)
            rule["id"] = rule_id
            rule["name"] = rule_id
            rule["helpUri"] = f"https://www.shellcheck.net/wiki/{rule_id}"
            rule["fullDescription"]["text"] = message.message
            rule["messageStrings"]["default"]["text"] = message.message
            rule["defaultConfiguration"]["level"] = sarif_severity_to_string(
                self._get_sarif_severity(message.level)
            )
            rules[rule_id] = rule
        return list(rules.values())

    def _get_sarif_result_definitions(self, result_template: dict) -> list:
        results = []
        for message in self.json_content:
            result = deepcopy(result_template)
            result["ruleId"] = self._rule_id(message)
            result["level"] = sarif_severity_to_string(self._get_sarif_severity(message.level))
            result["message"]["text"] = message.message
            physical_location = result["locations"][0]["physicalLocation"]
            physical_location["artifactLocation"]["uri"] = message.file
            physical_location["region"] = {
                "startLine": message.line,
                "startColumn": message.column,
                "endLine": message.end_line,
                "endColumn": message.end_column,
            }
            results.append(result)
        return results

    def _get_sarif_artifact_definitions(self, artefact_template: dict) -> list:
        artifacts = {}
        for message in self.json_content:
            if message.file in artifacts:
                continue
            if len(artifacts) >= self.max_artifacts:
                raise ValueError(f"ShellCheck report exceeds the {self.max_artifacts}-artifact limit")
            artifact = deepcopy(artefact_template)
            artifact["location"]["uri"] = message.file
            artifact["sourceLanguage"] = "shell"
            artifacts[message.file] = artifact
        return list(artifacts.values())

    @staticmethod
    def get_shellcheck_version() -> str:
        """Return Python package metadata when available without executing a program."""
        try:
            return version("shellcheck")
        except PackageNotFoundError:
            return "unknown"

    def _build_sarif_file(self, sarif_template: dict, rules: list, results: list, artifacts: list) -> None:
        self.sarif_content = deepcopy(sarif_template)
        driver = self.sarif_content["runs"][0]["tool"]["driver"]
        driver["name"] = "ShellCheck"
        driver["informationUri"] = "https://www.shellcheck.net/"
        driver["version"] = self.get_shellcheck_version()
        driver["rules"] = rules
        self.sarif_content["runs"][0]["artifacts"] = artifacts
        self.sarif_content["runs"][0]["results"] = results

    def load_json_file(self, path: str) -> None:
        """Load and validate a ShellCheck JSON report."""
        content = load_json(path, self.max_input_size_bytes)
        if not isinstance(content, list):
            raise ValueError("ShellCheck report must be a JSON array")
        if len(content) > self.max_messages:
            raise ValueError(f"ShellCheck report exceeds the {self.max_messages}-message limit")

        messages = []
        for index, message in enumerate(content):
            validate_message(message, index)
            messages.append(ShellCheckMessage(
                file=message["file"], line=message["line"], end_line=message["endLine"],
                column=message["column"], end_column=message["endColumn"],
                level=message["level"], code=message["code"], message=message["message"],
                fix=message["fix"],
            ))
        self.json_content = messages

