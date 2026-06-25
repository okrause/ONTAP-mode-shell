"""Registry of per-flag value completion providers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ontap_completion.backend import OntapPoolProtocol


Provider = Callable[[], list[str]]


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

    def values_for_flag(self, flag: str) -> list[str]:
        provider = self._providers.get(flag)
        if provider is None:
            return []
        return provider()


def build_default_registry(pool: OntapPoolProtocol) -> ValueProviderRegistry:
    """Built-in GCNV value providers from ontap-auto-completion.md."""
    registry = ValueProviderRegistry()

    registry.register(
        "-vserver",
        lambda: [_name(record) for record in _as_list(pool.ontap_get("/svm/svms"))],
    )
    registry.register(
        "-volume",
        lambda: [_name(record) for record in _as_list(pool.ontap_get("/storage/volumes"))],
    )
    registry.register(
        "-aggregate",
        lambda: _aggregate_names(pool),
    )
    registry.register_shared(
        ["-interface", "-lif"],
        lambda: [
            _name(record)
            for record in _as_list(pool.ontap_get("/network/ip/interfaces"))
        ],
    )
    registry.register(
        "-snapshot",
        lambda: [
            _name(record)
            for record in _as_list(pool.ontap_get("/storage/snapshots"))
        ],
    )
    return registry


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
