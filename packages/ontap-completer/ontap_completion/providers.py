"""Registry of per-flag value completion providers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ontap_completion.backend import OntapPoolProtocol


Provider = Callable[[str], list[str]]


class ValueProviderRegistry:
    """Maps -flag names to lazy value providers."""

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}

    def register(self, flag: str, provider: Provider) -> None:
        if not flag.startswith("-"):
            raise ValueError(f"flag must start with '-': {flag!r}")
        self._providers[flag] = provider

    def register_shared(self, flags: list[str], provider: Provider) -> None:
        for flag in flags:
            self.register(flag, provider)

    def registered_flags(self) -> frozenset[str]:
        return frozenset(self._providers)

    def values_for_flag(self, flag: str, *, line: str = "") -> list[str]:
        provider = self._providers.get(flag)
        if provider is None:
            return []
        return provider(line)


def build_default_registry(pool: OntapPoolProtocol) -> ValueProviderRegistry:
    """Built-in GCNV value providers from ontap-auto-completion.md."""
    registry = ValueProviderRegistry()

    registry.register(
        "-vserver",
        lambda _line: [_name(record) for record in _as_list(pool.ontap_get("/svm/svms"))],
    )
    registry.register(
        "-volume",
        lambda _line: [
            _name(record) for record in _as_list(pool.ontap_get("/storage/volumes"))
        ],
    )
    registry.register(
        "-aggregate",
        lambda _line: _aggregate_names(pool),
    )
    registry.register_shared(
        ["-interface", "-lif"],
        lambda _line: [
            _name(record)
            for record in _as_list(pool.ontap_get("/network/ip/interfaces"))
        ],
    )
    registry.register("-snapshot", lambda line: _snapshot_names(pool, line))
    return registry


def flag_value_in_line(line: str, flag: str) -> str | None:
    """Return the argument following flag when already present on the line."""
    tokens = line.replace("\n", "").split()
    for index, token in enumerate(tokens):
        if token == flag and index + 1 < len(tokens) and not tokens[index + 1].startswith(
            "-"
        ):
            return tokens[index + 1]
    return None


def _snapshot_names(pool: OntapPoolProtocol, line: str) -> list[str]:
    """Snapshot names via GET /storage/volumes/{uuid}/snapshots (ONTAP REST)."""
    volumes = _matching_volumes(pool, line)
    names: list[str] = []
    for volume in volumes:
        uuid = volume["uuid"]
        snaps = _as_list(
            pool.ontap_get(f"/storage/volumes/{uuid}/snapshots?ontap_fields=name")
        )
        names.extend(_name(record) for record in snaps)
    return sorted(set(names))


def _matching_volumes(pool: OntapPoolProtocol, line: str) -> list[dict]:
    volume_name = flag_value_in_line(line, "-volume")
    vserver_name = flag_value_in_line(line, "-vserver")
    volumes = _as_list(
        pool.ontap_get("/storage/volumes?ontap_fields=name,uuid,svm.name")
    )
    if volume_name:
        volumes = [volume for volume in volumes if _name(volume) == volume_name]
    if vserver_name:
        volumes = [
            volume for volume in volumes if _svm_name(volume) == vserver_name
        ]
    return [volume for volume in volumes if isinstance(volume, dict) and "uuid" in volume]


def _svm_name(volume: dict) -> str:
    svm = volume.get("svm")
    if isinstance(svm, dict):
        return str(svm.get("name", ""))
    return ""


def _as_list(raw: object) -> list:
    if isinstance(raw, list):
        return raw
    return []


def _name(record: object) -> str:
    if isinstance(record, dict):
        return str(record["name"])
    raise TypeError(f"expected dict with 'name', got {type(record)!r}")


def _aggregate_names(pool: OntapPoolProtocol) -> list[str]:
    names: list[str] = []
    for aggs in pool.ontap_aggregates.values():
        names.extend(aggs)
    return names
