from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ResponseKind(Enum):
    SUBCOMMAND_LIST = "subcommand_list"
    PARAMETERS = "parameters"
    MISSING_ARGUMENT = "missing_argument"
    EMPTY_RESULT = "empty_result"
    ERROR = "error"
    UNKNOWN = "unknown"


class ParamKind(Enum):
    SWITCH = "switch"
    NAMED_LIST = "named_list"
    ENUM = "enum"
    BOOLEAN = "boolean"
    SIZE = "size"
    PERCENT = "percent"
    INTEGER = "integer"
    TEXT = "text"
    DATE = "date"


@dataclass(frozen=True)
class HelpEntry:
    """One subcommand or parameter from ? help text."""

    name: str
    help_text: str
    is_directory: bool = False
    type_syntax: str = ""
    optional: bool = False
    aliases: tuple[str, ...] = ()
    kind: ParamKind | None = None
