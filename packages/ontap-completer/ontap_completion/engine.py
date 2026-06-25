"""Completion engine: line context, phases, and OntapCompleter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from ontap_completion.backend import CompletionBackend
from ontap_completion.parser import (
    classify_response,
    parse_parameter_help,
    parse_subcommand_help,
    unique_parameter_flags,
)
from ontap_completion.types import HelpEntry, ParamKind, ResponseKind

FLAG_RE = re.compile(r"^-[\w.-]+$")
FLAG_PREFIX_RE = re.compile(r"^-[\w.-]*$")
ENUM_VALUES_RE = re.compile(r"^\{([^}]+)\}$")

# Word breaks for readline: space, tab, newline, and ';' for chained commands.
# Must not include '-' or ONTAP flags are split into '-' + 'vol'.
ONTAP_COMPLETER_DELIMS = " \t\n;"


class CompletionPhase(Enum):
    """What kind of completion applies at the cursor."""

    HELP = "help"
    COMMAND_PATH = "command_path"
    FLAG_NAME = "flag_name"
    FLAG_VALUE = "flag_value"
    NONE = "none"


def split_chained_line_with_offset(line: str) -> tuple[str, str, int]:
    """Return (prefix through ';', active segment, index where active starts)."""
    line = line.replace("\n", "")
    if ";" not in line:
        return "", line, 0
    semi = line.rindex(";")
    prefix = line[: semi + 1]
    rest = line[semi + 1 :]
    lead = len(rest) - len(rest.lstrip())
    active_start = semi + 1 + lead
    return prefix, line[active_start:], active_start


def tab_help_eligible(line: str) -> bool:
    """True when TAB should show raw ONTAP ? help instead of completions."""
    line = line.replace("\n", "")
    if not line.strip():
        return True
    if not line.endswith(" "):
        return False
    tokens = line.split()
    if not tokens:
        return True
    if tokens[-1].startswith("-"):
        return False
    return True


def flag_prefix_at_cursor(
    line: str, begidx: int, endidx: int, text: str
) -> str | None:
    """Return the partial -flag at the cursor, including when readline split on '-'."""
    if not text or text[-1] == " ":
        return None
    if text.startswith("-"):
        return text
    if begidx > 0 and line[begidx - 1] == "-":
        return f"-{text}"
    return None


def should_complete_flag_name(line: str, begidx: int, endidx: int, text: str) -> bool:
    """True when the cursor is on a partial -flag name."""
    prefix_flag = flag_prefix_at_cursor(line, begidx, endidx, text)
    if prefix_flag is None:
        return False
    return bool(FLAG_PREFIX_RE.match(prefix_flag))


def format_readline_completion(
    candidate: str, line: str, begidx: int, endidx: int, text: str
) -> str:
    """Map an internal match to the string readline inserts at [begidx:endidx]."""
    full = candidate.rstrip() + " "
    if text.startswith("-"):
        return full
    if begidx > 0 and line[begidx - 1] == "-":
        body = full.lstrip("-").rstrip()
        if body.startswith(text):
            return body[len(text) :] + " "
        return body + " "
    return full


def flag_at_cursor(line: str, begidx: int, endidx: int, text: str) -> str | None:
    """Return the flag whose value is being completed, if any."""
    if should_complete_flag_name(line, begidx, endidx, text):
        return None

    prefix = line[:begidx]
    suffix = line[endidx:].lstrip()
    tokens_before = prefix.split()

    if begidx > 0 and line[begidx - 1].isspace() and tokens_before:
        flag = tokens_before[-1]
        if FLAG_RE.match(flag):
            return flag

    if (
        len(tokens_before) >= 2
        and FLAG_RE.match(tokens_before[-2])
        and not tokens_before[-1].startswith("-")
    ):
        return tokens_before[-2]

    if tokens_before and FLAG_RE.match(tokens_before[-1]) and suffix.startswith("-"):
        return tokens_before[-1]

    if tokens_before and FLAG_RE.match(tokens_before[-1]) and not suffix:
        return tokens_before[-1]

    return None


def parse_enum_values(type_syntax: str) -> list[str]:
    """Extract enum literals from help type syntax like {online|offline}."""
    m = ENUM_VALUES_RE.match(type_syntax.strip())
    if not m:
        return []
    inner = m.group(1)
    if inner.startswith("<integer>") or ".." in inner:
        return []
    return [part.strip() for part in inner.split("|") if part.strip()]


def _first_flag_index(tokens: list[str]) -> int | None:
    for index, token in enumerate(tokens):
        if FLAG_RE.match(token):
            return index
    return None


def _has_flag_token(text: str) -> bool:
    return _first_flag_index(text.split()) is not None


def _flag_starts_at_cursor(line: str, begidx: int) -> bool:
    return begidx > 0 and line[begidx - 1] == "-"


@dataclass(frozen=True)
class LineContext:
    """Readline cursor state for one completion request."""

    full_line: str
    begidx: int
    endidx: int
    text: str

    @property
    def chain_prefix(self) -> str:
        return split_chained_line_with_offset(self.full_line)[0]

    @property
    def active_segment(self) -> str:
        return split_chained_line_with_offset(self.full_line)[1]

    @property
    def active_start(self) -> int:
        return split_chained_line_with_offset(self.full_line)[2]

    @property
    def active_before_cursor(self) -> str:
        if self.begidx < self.active_start:
            return ""
        return self.full_line[self.active_start : self.begidx]

    @property
    def query_line(self) -> str:
        """Full chained line sent to the backend (without '?')."""
        return self.full_line.replace("\n", "").rstrip()

    @property
    def help_query_line(self) -> str:
        """Line for ? lookups — omits the partial token at the cursor."""
        if self.text:
            before = self.full_line[: self.begidx]
            if _flag_starts_at_cursor(self.full_line, self.begidx):
                before = before[: before.rfind("-")].rstrip()
            else:
                before = before.rstrip()
            return before
        return self.query_line

    @property
    def parameter_help_query_line(self) -> str:
        """Line for loading parameter metadata (command path only)."""
        tokens = self.active_before_cursor.split()
        flag_idx = _first_flag_index(tokens)
        if flag_idx is None:
            return self.help_query_line
        path = " ".join(tokens[:flag_idx])
        if self.chain_prefix:
            return f"{self.chain_prefix}{path}"
        return path

    def phase(self) -> CompletionPhase:
        if tab_help_eligible(self.full_line):
            return CompletionPhase.HELP
        if flag_at_cursor(self.full_line, self.begidx, self.endidx, self.text):
            return CompletionPhase.FLAG_VALUE
        if should_complete_flag_name(
            self.full_line, self.begidx, self.endidx, self.text
        ):
            return CompletionPhase.FLAG_NAME
        tokens = self.active_before_cursor.split()
        if (
            _first_flag_index(tokens) is not None
            or _has_flag_token(self.active_before_cursor)
            or _flag_starts_at_cursor(self.full_line, self.begidx)
        ):
            return CompletionPhase.FLAG_NAME
        if self.text or self._in_command_path():
            return CompletionPhase.COMMAND_PATH
        return CompletionPhase.NONE

    def _in_command_path(self) -> bool:
        tokens = self.active_before_cursor.split()
        return _first_flag_index(tokens) is None

    def flag_prefix(self) -> str:
        prefix = flag_prefix_at_cursor(
            self.full_line, self.begidx, self.endidx, self.text
        )
        if prefix is not None:
            return prefix
        return f"-{self.text.lstrip('-')}"


class OntapCompleter:
    """Stateless-over-keystroke completer wired to parser + backend."""

    def __init__(self, backend: CompletionBackend) -> None:
        self._backend = backend
        self._matches: list[str] = []

    def complete(self, line: str, begidx: int, endidx: int, text: str, state: int) -> str | None:
        if state == 0:
            self._matches = self.completions_for(LineContext(line, begidx, endidx, text))
        if state < len(self._matches):
            return self._matches[state]
        return None

    def help_text(self, ctx: LineContext) -> str | None:
        if ctx.phase() != CompletionPhase.HELP:
            return None
        return self._backend.help_for_line(ctx.help_query_line)

    def completions_for(self, ctx: LineContext) -> list[str]:
        phase = ctx.phase()
        if phase == CompletionPhase.HELP:
            return []
        if phase == CompletionPhase.COMMAND_PATH:
            return self._complete_command_path(ctx)
        if phase == CompletionPhase.FLAG_NAME:
            return self._complete_flag_names(ctx)
        if phase == CompletionPhase.FLAG_VALUE:
            return self._complete_flag_values(ctx)
        return []

    def tab_completions(self, ctx: LineContext) -> tuple[list[str], bool]:
        """TAB handling: return (matches, show_help).

        When show_help is True, print raw ? help. When False, insert matches
        (e.g. missing-argument flag on ``volume create ``).
        """
        if ctx.phase() != CompletionPhase.HELP:
            return self.completions_for(ctx), False

        help_text = self._backend.help_for_line(ctx.help_query_line)
        kind, _ = classify_response(help_text)
        if kind == ResponseKind.MISSING_ARGUMENT:
            return self._complete_flag_names(ctx, help_text=help_text), False
        return [], True

    def _complete_command_path(self, ctx: LineContext) -> list[str]:
        partial = ctx.text
        help_text = self._backend.help_for_line(ctx.help_query_line)
        kind, _ = classify_response(help_text)
        if kind == ResponseKind.SUBCOMMAND_LIST:
            entries = parse_subcommand_help(help_text)
            return _filter_prefix(
                (entry.name for entry in entries),
                partial,
                trailing_space=True,
            )
        if kind in (ResponseKind.PARAMETERS, ResponseKind.MISSING_ARGUMENT):
            return self._complete_flag_names(ctx, help_text=help_text)
        return []

    def _complete_flag_names(
        self, ctx: LineContext, *, help_text: str | None = None
    ) -> list[str]:
        if should_complete_flag_name(
            ctx.full_line, ctx.begidx, ctx.endidx, ctx.text
        ):
            partial = ctx.flag_prefix()
        else:
            partial = ""

        help_text = help_text or self._backend.help_for_line(ctx.help_query_line)
        flags = self._flag_names_from_help(help_text)
        names = [flag for flag in flags if not partial or flag.startswith(partial)]
        return _dedupe([f"{name} " for name in names])

    def _complete_flag_values(self, ctx: LineContext) -> list[str]:
        flag = flag_at_cursor(ctx.full_line, ctx.begidx, ctx.endidx, ctx.text)
        if flag is None:
            return []

        partial = ctx.text
        values = list(self._backend.values_for_flag(flag))
        if not values:
            entry = self._parameter_entry_for_flag(ctx, flag)
            if entry is not None and entry.kind == ParamKind.SWITCH:
                return []
            if entry is not None:
                values = parse_enum_values(entry.type_syntax)

        return _filter_prefix(values, partial, trailing_space=True)

    def _flag_names_from_help(self, help_text: str) -> list[str]:
        kind, detail = classify_response(help_text)
        if kind == ResponseKind.MISSING_ARGUMENT and detail:
            return [detail]
        if kind != ResponseKind.PARAMETERS:
            return []
        names: list[str] = []
        for entry in unique_parameter_flags(parse_parameter_help(help_text)):
            names.append(entry.name)
            names.extend(entry.aliases)
        return names

    def _parameter_entries(self, ctx: LineContext) -> list[HelpEntry]:
        help_text = self._backend.help_for_line(ctx.parameter_help_query_line)
        kind, detail = classify_response(help_text)
        if kind == ResponseKind.MISSING_ARGUMENT and detail:
            return [HelpEntry(name=detail, help_text="")]
        if kind != ResponseKind.PARAMETERS:
            return []
        return unique_parameter_flags(parse_parameter_help(help_text))

    def _parameter_entry_for_flag(
        self, ctx: LineContext, flag: str
    ) -> HelpEntry | None:
        for entry in self._parameter_entries(ctx):
            if entry.name == flag or flag in entry.aliases:
                return entry
        return None


def _filter_prefix(
    items: list[str] | tuple[str, ...],
    prefix: str,
    *,
    trailing_space: bool,
) -> list[str]:
    matches = [item for item in items if item.startswith(prefix)]
    if trailing_space:
        return [f"{item} " for item in matches]
    return matches


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
