# Author: Konstantin M.J. Winkel, M.Sc.

"""Clippy JSON-lines to SARIF conversion."""

from copy import deepcopy

from ..core.file_io import load_json_lines, load_template, save_json_atomically, validate_input_output_paths
from ..core.paths import ARTEFACT_TEMPLATE_PATH, RESULT_TEMPLATE_PATH, RULE_TEMPLATE_PATH, SARIF_TEMPLATE_PATH
from ..core.sarif_types import SarifSeverity, sarif_severity_to_string
from .clippy_types import ClippyMessage
from .clippy_validation import parse_message


class ClippySarifConverter:
    """Convert ``cargo clippy --message-format=json`` output to SARIF."""

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
            "note": SarifSeverity.NOTE,
            "help": SarifSeverity.NOTE,
            "failure-note": SarifSeverity.NOTE,
        }[level]

    def _get_sarif_rule_definitions(self, rule_template: dict) -> list:
        rules = {}
        for message in self.json_content:
            if message.rule_id in rules:
                continue
            if len(rules) >= self.max_rules:
                raise ValueError(f"Clippy report exceeds the {self.max_rules}-rule limit")
            rule = deepcopy(rule_template)
            rule["id"] = message.rule_id
            rule["name"] = message.rule_id.removeprefix("clippy::")
            rule["helpUri"] = message.help_uri
            rule["fullDescription"]["text"] = message.message
            rule["messageStrings"]["default"]["text"] = message.message
            rule["defaultConfiguration"]["level"] = sarif_severity_to_string(
                self._get_sarif_severity(message.level)
            )
            rules[message.rule_id] = rule
        return list(rules.values())

    def _get_sarif_result_definitions(self, result_template: dict) -> list:
        results = []
        for message in self.json_content:
            result = deepcopy(result_template)
            result["ruleId"] = message.rule_id
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
                raise ValueError(f"Clippy report exceeds the {self.max_artifacts}-artifact limit")
            artifact = deepcopy(artefact_template)
            artifact["location"]["uri"] = message.file
            artifact["sourceLanguage"] = "rust"
            artifacts[message.file] = artifact
        return list(artifacts.values())

    def _build_sarif_file(self, sarif_template: dict, rules: list, results: list, artifacts: list) -> None:
        self.sarif_content = deepcopy(sarif_template)
        driver = self.sarif_content["runs"][0]["tool"]["driver"]
        driver["name"] = "Clippy"
        driver["informationUri"] = "https://doc.rust-lang.org/clippy/"
        driver["version"] = "unknown"
        driver["rules"] = rules
        self.sarif_content["runs"][0]["artifacts"] = artifacts
        self.sarif_content["runs"][0]["results"] = results

    def load_json_file(self, path: str) -> None:
        """Load and validate a Cargo JSON-lines report, retaining Clippy diagnostics."""

        records = load_json_lines(path, self.max_input_size_bytes)
        messages: list[ClippyMessage] = []
        for index, record in enumerate(records):
            message = parse_message(record, index)
            if message is None:
                continue
            if len(messages) >= self.max_messages:
                raise ValueError(f"Clippy report exceeds the {self.max_messages}-message limit")
            messages.append(message)
        self.json_content = messages
