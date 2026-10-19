# Author: Konstantin M.J. Winkel, M.Sc.

"""This File contains the class definitions for the pylint converter"""

import logging
from copy import deepcopy
from importlib.metadata import PackageNotFoundError, version

from ..core.file_io import load_json, load_template, save_json_atomically, validate_input_output_paths
from ..core.paths import SARIF_TEMPLATE_PATH, RULE_TEMPLATE_PATH, ARTEFACT_TEMPLATE_PATH, RESULT_TEMPLATE_PATH
from ..pylint_converter.pylint_types import PylintMessage, pylint_confidence_from_string
from ..pylint_converter.pylint_validation import validate_message
from ..core.sarif_types import SarifSeverity, sarif_severity_to_string

logger = logging.getLogger(__name__)

class PylintSarifConverter:
    """This class handles the conversion from pylint json to sarif"""

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
        """This method runs the whole conversion algorithm"""

        # reject input/output aliases before reading or writing either path
        validate_input_output_paths(self.args.input, self.args.output)

        # load pylint json file
        self.load_json_file(self.args.input)

        # load templates
        sarif_template = load_template(str(SARIF_TEMPLATE_PATH))
        rule_template = load_template(str(RULE_TEMPLATE_PATH))
        result_template = load_template(str(RESULT_TEMPLATE_PATH))
        artefact_template = load_template(str(ARTEFACT_TEMPLATE_PATH))

        # build parts
        rules = self._get_sarif_rule_definitions(rule_template)
        results = self._get_sarif_result_definitions(result_template)
        artifacts = self._get_sarif_artifact_definitions(artefact_template)

        # build final sarif file

        self._build_sarif_file(sarif_template, rules, results, artifacts)

        # safe sarif file
        self.save_sarif_file(self.args.output)

    def _get_sarif_severity_from_message_id(self, message_id: str) -> SarifSeverity:
        """
        Extracts the severity according to the SARIF standard from the message id provided by
        pylint. Information is found in the first letter of the message id.
        """

        conversion_dict = {
            'F': SarifSeverity.ERROR,   # Failure
            'E': SarifSeverity.ERROR,   # Error
            'W': SarifSeverity.WARNING, # Warning
            'C': SarifSeverity.NOTE,    # Convention
            'R': SarifSeverity.NOTE,    # Refactor
            'I': SarifSeverity.NOTE,    # Informational
            }

        if message_id[0] not in conversion_dict:
            logger.warning("Message ID %s does not start with a known letter, defaulting to Failure", message_id)
            return SarifSeverity.ERROR

        return conversion_dict[message_id[0]]

    def _get_sarif_severity_from_type(self, pylint_type: str) -> SarifSeverity:
        """
        Extracts the severity according to the SARIF standard directly from the type of a pylint
        message.
        """

        conversion_dict = {
                'fatal':      SarifSeverity.ERROR,
                'error':      SarifSeverity.ERROR,
                'warning':    SarifSeverity.WARNING,
                'convention': SarifSeverity.NOTE,
                'refactor':   SarifSeverity.NOTE,
                'info':       SarifSeverity.NOTE,
                }

        if pylint_type not in conversion_dict:
            logger.warning("Type %s does not match conversion, defaulting to Failure", pylint_type)
            return SarifSeverity.ERROR

        return conversion_dict[pylint_type]

    def _get_sarif_rule_definitions(self, rule_template: dict) -> list:
        """
        This method builds the rule definitions for the final SARIF file
        by collecting all rules present in the pylint json file
        """

        rules_dict = {}

        for message in self.json_content:
            if message.message_id in rules_dict:
                continue
            if len(rules_dict) >= self.max_rules:
                raise ValueError(f"Pylint report exceeds the {self.max_rules}-rule limit")
            template_copy = deepcopy(rule_template)

            template_copy["id"] = message.message_id
            template_copy["name"] = message.symbol
            template_copy["helpUri"] = "https://pylint.readthedocs.io/en/latest/user_guide/messages/" + message.type + "/" + message.symbol
            template_copy["fullDescription"]["text"] = message.message
            template_copy["messageStrings"]["default"]["text"] = message.message + "."
            template_copy["defaultConfiguration"]["level"] = sarif_severity_to_string(self._get_sarif_severity_from_type(message.type))

            rules_dict[message.message_id] = template_copy

        rules = []
        for _, rule in rules_dict.items():
            rules.append(rule)

        return rules

    def _get_sarif_result_definitions(self, result_template: dict) -> list:
        """
        This method builds the result definitions for the final SARIF file
        by collecting all messages present in the pylint json file
        """

        results = []

        for message in self.json_content:

            template_copy = deepcopy(result_template)

            # fill content
            template_copy["ruleId"] = message.message_id
            template_copy["message"]["text"] = message.message
            template_copy["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] = message.absolute_path
            template_copy["locations"][0]["physicalLocation"]["region"]["startLine"] = message.line
            template_copy["locations"][0]["physicalLocation"]["region"]["startColumn"] = message.column
            template_copy["locations"][0]["physicalLocation"]["region"]["endLine"] = message.end_line
            template_copy["locations"][0]["physicalLocation"]["region"]["endColumn"] = message.end_column

            # check if values satisfy lower limits of SARIF

            def _check_and_delete(dictionary: dict, key: str):
                if key not in dictionary:
                    return

                if dictionary[key] is None:
                    del dictionary[key]
                    return

                if dictionary[key] < 1:
                    del dictionary[key]
                    return

            if template_copy["locations"][0]["physicalLocation"]["region"]["startLine"] < 1:
                template_copy["locations"][0]["physicalLocation"]["region"]["startLine"] = 1

            _check_and_delete(template_copy["locations"][0]["physicalLocation"]["region"], "startColumn")
            _check_and_delete(template_copy["locations"][0]["physicalLocation"]["region"], "endLine")
            _check_and_delete(template_copy["locations"][0]["physicalLocation"]["region"], "endColumn")

            results.append(template_copy)

        return results

    def _get_sarif_artifact_definitions(self, artefact_template: dict) -> list:
        """This method builds the artefact definitions for the final SARIF file"""

        artefact_dict = {}

        for message in self.json_content:
            if message.path in artefact_dict:
                continue
            if len(artefact_dict) >= self.max_artifacts:
                raise ValueError(f"Pylint report exceeds the {self.max_artifacts}-artifact limit")

            template_copy = deepcopy(artefact_template)

            template_copy["location"]["uri"] = message.path

            artefact_dict[message.path] = template_copy

        artefacts = []

        for _, artefact in artefact_dict.items():
            artefacts.append(artefact)

        return artefacts

    def get_pylint_version(self) -> str:
        """Returns the installed Pylint package version without executing an external command."""
        try:
            return version("pylint")
        except PackageNotFoundError:
            logger.warning("Unable to determine Pylint version: package metadata is unavailable")
            return "unknown"

    def _build_sarif_file(self, sarif_template: dict, rules: list, results: list, artifacts: list) -> None:
        """This method builds the final sarif file using the generated definitions."""

        self.sarif_content = deepcopy(sarif_template)

        self.sarif_content["runs"][0]["tool"]["driver"]["version"] = self.get_pylint_version()
        self.sarif_content["runs"][0]["tool"]["driver"]["rules"] = rules
        self.sarif_content["runs"][0]["artifacts"] = artifacts
        self.sarif_content["runs"][0]["results"] = results

    def load_json_file(self, path: str) -> None:
        """This method loads and validates the json content"""

        file_content = load_json(path, self.max_input_size_bytes)

        if not isinstance(file_content, dict):
            raise ValueError("Pylint report must be a JSON object")
        if "messages" not in file_content:
            raise ValueError("Pylint report is missing required 'messages' array")
        messages = file_content["messages"]
        if not isinstance(messages, list):
            raise ValueError("Pylint report 'messages' must be an array")
        if len(messages) > self.max_messages:
            raise ValueError(f"Pylint report exceeds the {self.max_messages}-message limit")

        validated_messages = []
        for message_index, message in enumerate(messages):
            validate_message(message, message_index)
            validated_messages.append(PylintMessage(
                message['type'], message['symbol'], message['message'], message['messageId'],
                pylint_confidence_from_string(message['confidence']), message['module'], message['obj'],
                message['line'], message['column'], message['endLine'], message['endColumn'],
                message['path'], message['absolutePath']))
        self.json_content = validated_messages

    def save_sarif_file(self, path: str) -> None:
        """Atomically publish a complete SARIF file without overwriting an existing entry."""

        save_json_atomically(self.sarif_content, path, self.max_output_size_bytes)
