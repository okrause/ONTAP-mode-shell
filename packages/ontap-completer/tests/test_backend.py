from __future__ import annotations

from dataclasses import dataclass, field

from ontap_completion.backend import (
    GcnvPoolBackend,
    SessionCacheBackend,
    build_help_query,
    create_gcnv_session_backend,
)
from ontap_completion.providers import ValueProviderRegistry, build_default_registry


@dataclass
class FakePool:
    """Test double for OntapModePool."""

    ontap_aggregates: dict[str, list[str]] = field(
        default_factory=lambda: {"svm1": ["aggr1", "aggr2"]}
    )
    cli_calls: list[str] = field(default_factory=list)
    get_calls: list[str] = field(default_factory=list)
    cli_responses: dict[str, str] = field(default_factory=dict)
    get_responses: dict[str, list[dict]] = field(default_factory=dict)

    def ontap_cli(self, cli_command: str) -> str:
        self.cli_calls.append(cli_command)
        return self.cli_responses.get(cli_command, "")

    def ontap_get(self, ontap_urn: str) -> list[dict]:
        self.get_calls.append(ontap_urn)
        return self.get_responses.get(ontap_urn, [])


class TestBuildHelpQuery:
    def test_appends_question_mark(self):
        assert build_help_query("volume show") == "volume show ?"

    def test_preserves_existing_question_mark(self):
        assert build_help_query("volume ?") == "volume ?"

    def test_strips_trailing_whitespace(self):
        assert build_help_query("volume show  ") == "volume show ?"


class TestValueProviderRegistry:
    def test_register_and_lookup(self):
        reg = ValueProviderRegistry()
        reg.register("-policy", lambda _line: ["default", "strict"])
        assert reg.values_for_flag("-policy") == ["default", "strict"]

    def test_unknown_flag_returns_empty(self):
        reg = ValueProviderRegistry()
        assert reg.values_for_flag("-unknown") == []

    def test_register_shared(self):
        reg = ValueProviderRegistry()
        reg.register_shared(["-interface", "-lif"], lambda _line: ["lif1"])
        assert reg.values_for_flag("-interface") == ["lif1"]
        assert reg.values_for_flag("-lif") == ["lif1"]

    def test_flag_must_start_with_dash(self):
        reg = ValueProviderRegistry()
        try:
            reg.register("vserver", lambda _line: [])
            assert False, "expected ValueError"
        except ValueError:
            pass


class TestBuildDefaultRegistry:
    def test_builtin_providers(self):
        pool = FakePool(
            get_responses={
                "/svm/svms": [{"name": "svm-a"}],
                "/storage/volumes": [{"name": "vol1"}],
                "/network/ip/interfaces": [{"name": "lif1"}],
                "/storage/volumes?ontap_fields=name,uuid,svm.name": [
                    {
                        "name": "vol1",
                        "uuid": "uuid-1",
                        "svm": {"name": "svm-a"},
                    }
                ],
                "/storage/volumes/uuid-1/snapshots?ontap_fields=name": [
                    {"name": "snap1"}
                ],
            }
        )
        reg = build_default_registry(pool)
        assert reg.values_for_flag("-vserver") == ["svm-a"]
        assert reg.values_for_flag("-volume") == ["vol1"]
        assert reg.values_for_flag("-aggregate") == ["aggr1", "aggr2"]
        assert reg.values_for_flag("-interface") == ["lif1"]
        assert reg.values_for_flag("-lif") == ["lif1"]
        assert reg.values_for_flag("-snapshot", line="snapshot show") == ["snap1"]
        assert "-vserver" in reg.registered_flags()

    def test_snapshot_provider_filters_by_volume(self):
        pool = FakePool(
            get_responses={
                "/storage/volumes?ontap_fields=name,uuid,svm.name": [
                    {"name": "vol1", "uuid": "uuid-1", "svm": {"name": "svm1"}},
                    {"name": "vol2", "uuid": "uuid-2", "svm": {"name": "svm1"}},
                ],
                "/storage/volumes/uuid-1/snapshots?ontap_fields=name": [
                    {"name": "snap-a"}
                ],
                "/storage/volumes/uuid-2/snapshots?ontap_fields=name": [
                    {"name": "snap-b"}
                ],
            }
        )
        reg = build_default_registry(pool)
        assert set(reg.values_for_flag("-snapshot", line="snapshot show")) == {
            "snap-a",
            "snap-b",
        }
        assert reg.values_for_flag(
            "-snapshot", line="snapshot show -volume vol1"
        ) == ["snap-a"]

    def test_extra_provider_without_changing_defaults(self):
        pool = FakePool()
        reg = build_default_registry(pool)
        reg.register("-policy", lambda _line: ["default"])
        assert reg.values_for_flag("-policy") == ["default"]


class TestGcnvPoolBackend:
    def test_help_for_line(self):
        pool = FakePool(
            cli_responses={"volume ?": "create\n  show\n"}
        )
        backend = GcnvPoolBackend(pool)
        assert "create" in backend.help_for_line("volume")
        assert pool.cli_calls == ["volume ?"]

    def test_values_delegates_to_registry(self):
        pool = FakePool()
        reg = ValueProviderRegistry()
        reg.register("-volume", lambda _line: ["v1"])
        backend = GcnvPoolBackend(pool, registry=reg)
        assert backend.values_for_flag("-volume") == ["v1"]


class TestSessionCacheBackend:
    def test_caches_help_lookups(self):
        pool = FakePool(
            cli_responses={"volume ?": "create\n  show\n"}
        )
        inner = GcnvPoolBackend(pool)
        cached = SessionCacheBackend(inner)

        assert cached.help_for_line("volume") == cached.help_for_line("volume")
        assert pool.cli_calls == ["volume ?"]

    def test_caches_value_lookups(self):
        pool = FakePool()
        calls = {"n": 0}

        def provider(_line: str) -> list[str]:
            calls["n"] += 1
            return ["a"]

        reg = ValueProviderRegistry()
        reg.register("-volume", provider)
        cached = SessionCacheBackend(GcnvPoolBackend(pool, registry=reg))

        assert cached.values_for_flag("-volume") == ["a"]
        assert cached.values_for_flag("-volume") == ["a"]
        assert calls["n"] == 1

    def test_clear_resets_caches(self):
        pool = FakePool(cli_responses={"volume ?": "show"})
        cached = SessionCacheBackend(GcnvPoolBackend(pool))
        cached.help_for_line("volume")
        cached.clear()
        cached.help_for_line("volume")
        assert pool.cli_calls == ["volume ?", "volume ?"]

    def test_create_gcnv_session_backend(self):
        pool = FakePool(cli_responses={" ?": "volume>"})
        backend = create_gcnv_session_backend(pool)
        assert isinstance(backend, SessionCacheBackend)
        assert "volume>" in backend.help_for_line("")
