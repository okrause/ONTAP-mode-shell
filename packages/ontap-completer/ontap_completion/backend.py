"""Completion backend protocol, GCNV pool adapter, and session cache."""

from __future__ import annotations

import json
from typing import Any, Protocol

from ontap_completion.providers import ValueProviderRegistry, build_default_registry, flag_value_in_line


def build_help_query(line: str) -> str:
    """Normalize line and append ' ?' for ONTAP help lookup."""
    line = line.replace("\n", "").rstrip()
    if line.endswith("?"):
        return line
    return f"{line} ?"


def normalize_cli_output(raw: Any) -> str:
    """Convert ontap_cli() return value to text for the parser."""
    if raw is None:
        return ""
    if isinstance(raw, dict):
        return json.dumps(raw)
    return str(raw)


class CompletionBackend(Protocol):
    def help_for_line(self, line: str) -> str:
        """Return raw ? help text for the given (possibly incomplete) command line."""
        ...

    def values_for_flag(self, flag: str, *, line: str = "") -> list[str]:
        """Return completion candidates for a flag value, or [] if unknown."""
        ...


class OntapPoolProtocol(Protocol):
    """Minimal pool surface used by GcnvPoolBackend."""

    ontap_aggregates: dict[str, list[str]]

    def ontap_cli(self, cli_command: str) -> Any: ...

    def ontap_get(self, ontap_urn: str) -> Any: ...


class GcnvPoolBackend:
    """GCNV ONTAP-mode backend using an OntapModePool-like object."""

    def __init__(
        self,
        pool: OntapPoolProtocol,
        registry: ValueProviderRegistry | None = None,
    ) -> None:
        self._pool = pool
        self._registry = registry or build_default_registry(pool)

    def help_for_line(self, line: str) -> str:
        raw = self._pool.ontap_cli(build_help_query(line))
        return normalize_cli_output(raw)

    def values_for_flag(self, flag: str, *, line: str = "") -> list[str]:
        return self._registry.values_for_flag(flag, line=line)


class SessionCacheBackend:
    """In-memory per-session cache wrapper. Not persisted to disk."""

    def __init__(self, inner: CompletionBackend) -> None:
        self._inner = inner
        self._help_cache: dict[str, str] = {}
        self._value_cache: dict[str, list[str]] = {}

    def clear(self) -> None:
        """Drop all cached help and value lookups."""
        self._help_cache.clear()
        self._value_cache.clear()

    def help_for_line(self, line: str) -> str:
        query = build_help_query(line)
        if query not in self._help_cache:
            self._help_cache[query] = self._inner.help_for_line(line)
        return self._help_cache[query]

    def values_for_flag(self, flag: str, *, line: str = "") -> list[str]:
        cache_key = _value_cache_key(flag, line)
        if cache_key not in self._value_cache:
            self._value_cache[cache_key] = self._inner.values_for_flag(
                flag, line=line
            )
        return self._value_cache[cache_key]


def _value_cache_key(flag: str, line: str) -> tuple[str, ...]:
    if flag == "-snapshot":
        return (
            flag,
            flag_value_in_line(line, "-volume") or "",
            flag_value_in_line(line, "-vserver") or "",
        )
    return (flag,)


def create_gcnv_session_backend(pool: OntapPoolProtocol) -> SessionCacheBackend:
    """Build a session-cached GCNV backend (typical entry point for the REPL)."""
    return SessionCacheBackend(GcnvPoolBackend(pool))
