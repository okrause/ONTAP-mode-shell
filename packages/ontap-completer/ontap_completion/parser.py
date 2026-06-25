"""Pure parsing of ONTAP CLI ? help text. No I/O."""

from __future__ import annotations

import re

from ontap_completion.types import HelpEntry, ParamKind, ResponseKind

MISSING_ARG_RE = re.compile(r"Missing required argument:\s+(-[\w-]+)")
SUBCOMMAND_LINE_RE = re.compile(r"^\s*(\S+?)(>?)\s{2,}(.+)$")
FLAG_TOKEN_RE = re.compile(r"-[\w.-]+")
BARE_PARAM_LINE_RE = re.compile(
    r"^\s*(-[\w.-]+(?:\|[-\w.-]+)?\s+.+?)(?:\s{2,}(.+))?\s*$"
)


def classify_response(text: str) -> tuple[ResponseKind, str | None]:
    """Classify raw ? response. detail holds missing flag name when applicable."""
    stripped = text.strip()
    if not stripped:
        return ResponseKind.UNKNOWN, "empty response"

    if stripped.startswith("code:") or '"code"' in stripped:
        if "404" in stripped and (
            "entry doesn't exist" in stripped
            or "no matching" in stripped.lower()
        ):
            return ResponseKind.EMPTY_RESULT, None
        m = MISSING_ARG_RE.search(stripped)
        if m:
            return ResponseKind.MISSING_ARGUMENT, m.group(1)
        return ResponseKind.ERROR, stripped.split("\n", 1)[0][:200]

    if parse_subcommand_help(stripped):
        return ResponseKind.SUBCOMMAND_LIST, None

    if parse_parameter_help(stripped):
        return ResponseKind.PARAMETERS, None

    return ResponseKind.UNKNOWN, stripped[:200]


def split_chained_line(line: str) -> tuple[str, str]:
    """Return (prefix including ';', active_segment) for chained commands."""
    if ";" not in line:
        return "", line.strip()
    parts = line.split(";")
    prefix = ";".join(parts[:-1]) + ";"
    return prefix, parts[-1].strip()


def parse_subcommand_help(text: str) -> list[HelpEntry]:
    """Parse subcommand list from ? help (e.g. output of 'volume ?')."""
    entries: list[HelpEntry] = []
    pending: HelpEntry | None = None

    for line in text.splitlines():
        m = SUBCOMMAND_LINE_RE.match(line)
        if m:
            token, gt, help_text = m.group(1), m.group(2), m.group(3).strip()
            name = token[:-1] if token.endswith(">") else token
            is_dir = bool(gt) or token.endswith(">")
            entries.append(
                HelpEntry(
                    name=name,
                    help_text=help_text,
                    is_directory=is_dir,
                )
            )
            pending = None
            continue

        # Wrapped description continuation (indented, no subcommand token at column ~2)
        if entries and line.startswith("  ") and not SUBCOMMAND_LINE_RE.match(line):
            cont = line.strip()
            if cont and not cont.startswith("["):
                last = entries[-1]
                entries[-1] = HelpEntry(
                    name=last.name,
                    help_text=f"{last.help_text} {cont}",
                    is_directory=last.is_directory,
                )
    return entries


def _split_spec_and_help(line: str) -> tuple[str, str] | None:
    """Split a parameter help line into bracket/spec portion and description."""
    raw = line.rstrip()
    if not raw.strip():
        return None

    lead = len(raw) - len(raw.lstrip())
    pos = lead
    if pos < len(raw) and raw[pos] == "[":
        depth = 0
        i = pos
        while i < len(raw):
            if raw[i] == "[":
                depth += 1
            elif raw[i] == "]":
                depth -= 1
                if depth == 0:
                    spec_end = i + 1
                    rest = raw[spec_end:]
                    type_m = re.match(r"\s*(<[^>]+>)", rest)
                    if type_m:
                        spec_end += type_m.end()
                    if spec_end < len(raw) and raw[spec_end] == "]":
                        spec_end += 1
                    spec = raw[pos:spec_end]
                    tail = raw[spec_end:].strip()
                    help_text = _help_after_gap(tail)
                    return spec, help_text
            i += 1
        return None

    m = BARE_PARAM_LINE_RE.match(raw)
    if m:
        return m.group(1).strip(), (m.group(2) or "").strip()
    return None


def _help_after_gap(tail: str) -> str:
    if not tail:
        return ""
    parts = re.split(r"\s{2,}", tail, maxsplit=1)
    if len(parts) == 2:
        return parts[1].strip()
    return tail.strip() if not tail.startswith("-") else ""


def _strip_bracket_content(spec: str) -> tuple[str, bool]:
    s = spec.strip()
    doubly = s.startswith("[[")
    if s.startswith("["):
        s = s[1:]
    if s.endswith("]"):
        s = s[:-1]
    return s.strip(), doubly


def _classify_type_hint(hint: str) -> ParamKind:
    h = hint.strip()
    if re.search(r",\s*\.\.\.", h):
        return ParamKind.NAMED_LIST
    if h == "{true|false}":
        return ParamKind.BOOLEAN
    if h.startswith("{") and "|" in h:
        return ParamKind.ENUM
    if re.search(r"\{<integer>\[KB", h):
        return ParamKind.SIZE
    if "percent" in h.lower():
        return ParamKind.PERCENT
    if h in ("<integer>", "{0..1023}") or (h.startswith("{") and ".." in h):
        return ParamKind.INTEGER
    if "Date" in h or "MM/DD/YYYY" in h:
        return ParamKind.DATE
    return ParamKind.TEXT


def _split_or_parts(inner: str) -> list[str]:
    # Flag aliases use tight syntax: -long|-short {enum}
    if re.match(r"-[\w.-]+\|[-\w.-]+\s+", inner):
        return [inner]
    parts = [p.strip() for p in inner.split(" | ")]
    return [p for p in parts if p]


def _parse_param_part(
    part: str, optional: bool, help_text: str
) -> list[HelpEntry]:
    opt_named = re.match(r"\[(-[\w.-]+)\]\s+(.+)", part)
    if opt_named:
        hint = opt_named.group(2).strip()
        return [
            HelpEntry(
                name=opt_named.group(1),
                help_text=help_text,
                type_syntax=hint,
                optional=True,
                kind=_classify_type_hint(hint),
            )
        ]

    alias_match = re.match(r"(-[\w.-]+)\|(-[\w.-]+)\s+(.+)", part)
    if alias_match:
        hint = alias_match.group(3).strip()
        kind = _classify_type_hint(hint)
        return [
            HelpEntry(
                name=alias_match.group(1),
                help_text=help_text,
                type_syntax=hint,
                optional=optional,
                aliases=(alias_match.group(2),),
                kind=kind,
            )
        ]

    m = re.match(r"(-[\w.-]+)\s+(.+)", part)
    if m:
        hint = m.group(2).strip()
        return [
            HelpEntry(
                name=m.group(1),
                help_text=help_text,
                type_syntax=hint,
                optional=optional,
                kind=_classify_type_hint(hint),
            )
        ]

    entries: list[HelpEntry] = []
    for flag in FLAG_TOKEN_RE.findall(part):
        entries.append(
            HelpEntry(
                name=flag,
                help_text=help_text,
                optional=optional,
                kind=ParamKind.SWITCH,
            )
        )
    return entries


def _parse_param_entries(
    inner: str, optional: bool, help_text: str
) -> list[HelpEntry]:
    entries: list[HelpEntry] = []
    for part in _split_or_parts(inner):
        if part:
            entries.extend(_parse_param_part(part, optional, help_text))
    return entries


def parse_parameter_help(text: str) -> list[HelpEntry]:
    """Parse parameter list from ? help (e.g. output of 'volume show ?')."""
    entries: list[HelpEntry] = []
    pending_help = ""

    for line in text.splitlines():
        parsed = _split_spec_and_help(line)
        if parsed:
            spec, help_text = parsed
            if help_text:
                pending_help = ""
            elif pending_help:
                help_text = pending_help
                pending_help = ""

            inner, doubly = _strip_bracket_content(spec)
            if inner:
                entries.extend(
                    _parse_param_entries(inner, optional=doubly, help_text=help_text)
                )
            continue

        # Wrapped description for previous entry
        if entries and line.startswith("  ") and "[" not in line.strip()[:1]:
            cont = line.strip()
            if cont:
                last = entries[-1]
                entries[-1] = HelpEntry(
                    name=last.name,
                    help_text=f"{last.help_text} {cont}".strip(),
                    is_directory=last.is_directory,
                    type_syntax=last.type_syntax,
                    optional=last.optional,
                    aliases=last.aliases,
                    kind=last.kind,
                )
                pending_help = ""
        elif line.strip() and not entries:
            pending_help = line.strip()

    return entries


def unique_parameter_flags(entries: list[HelpEntry]) -> list[HelpEntry]:
    """Deduplicate by flag name; aliases remain on the primary entry."""
    seen: dict[str, HelpEntry] = {}
    for entry in entries:
        if entry.name not in seen:
            seen[entry.name] = entry
    return list(seen.values())
