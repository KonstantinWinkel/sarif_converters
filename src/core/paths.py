# Author: Konstantin M.J. Winkel, M.Sc.

"""This File contains constants that include the path to different files and folders"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SRC_DIR = PROJECT_ROOT / "src"
DATA_DIR = PROJECT_ROOT / "data"

SARIF_TEMPLATE_PATH = DATA_DIR / "sarif_template.json"
RULE_TEMPLATE_PATH = DATA_DIR / "rule_template.json"
ARTEFACT_TEMPLATE_PATH = DATA_DIR / "artefact_template.json"
RESULT_TEMPLATE_PATH = DATA_DIR / "result_template.json"
