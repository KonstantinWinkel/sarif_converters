# Author: Konstantin M.J. Winkel, M.Sc.

"""This file contains type definitions for types needed to interact SARIF files"""

from enum import Enum


class SarifSeverity(Enum):
    """This Enum defines values for the SARIF Severity levels"""

    ERROR = 0
    WARNING = 1
    NOTE = 2
    NONE = 3

def sarif_severity_to_string(severity: SarifSeverity) -> str:
    """This function converts a SARIF Severity enum to a string"""

    converison_dict = { SarifSeverity.ERROR: "error",
                        SarifSeverity.WARNING: "warning",
                        SarifSeverity.NOTE: "note",
                        SarifSeverity.NONE: "none"
                        }

    return converison_dict[severity]
