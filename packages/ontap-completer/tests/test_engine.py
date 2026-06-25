from __future__ import annotations

from pathlib import Path

import pytest

from ontap_completion.backend import build_help_query
from ontap_completion.engine import (
    CompletionPhase,
    LineContext,
    OntapCompleter,
    flag_at_cursor,
    flag_prefix_at_cursor,
    format_readline_completion,
    parse_enum_values,
    should_complete_flag_name,
    split_chained_line_with_offset,
    tab_help_eligible,
)
from ontap_completion.parser import split_chained_line


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


def load_fixture(fixtures_dir: Path, name: str) -> str:
    return (fixtures_dir / name).read_text(encoding="utf-8")


class StaticBackend:
    def __init__(
        self,
        help_responses: dict[str, str],
        values: dict[str, list[str]] | None = None,
    ) -> None:
        self.help_responses = help_responses
        self.values = values or {}
        self.help_calls: list[str] = []

    def help_for_line(self, line: str) -> str:
        query = build_help_query(line)
        self.help_calls.append(query)
        return self.help_responses.get(query, "")

    def values_for_flag(self, flag: str) -> list[str]:
        return self.values.get(flag, [])


class TestLineContextPhase:
    def test_empty_line_is_help(self):
        ctx = LineContext("", 0, 0, "")
        assert ctx.phase() == CompletionPhase.HELP

    def test_trailing_space_after_path_is_help(self):
        ctx = LineContext("volume show ", 12, 12, "")
        assert ctx.phase() == CompletionPhase.HELP

    def test_partial_path_token(self):
        ctx = LineContext("volume sh", 7, 9, "sh")
        assert ctx.phase() == CompletionPhase.COMMAND_PATH

    def test_partial_flag_name(self):
        ctx = LineContext("volume show -vol", 12, 16, "-vol")
        assert ctx.phase() == CompletionPhase.FLAG_NAME

    def test_flag_value_after_space(self):
        ctx = LineContext("volume show -vserver ", 21, 21, "")
        assert ctx.phase() == CompletionPhase.FLAG_VALUE

    def test_chained_prefix_preserved_in_query_line(self):
        ctx = LineContext("set advanced; volume sh", 20, 22, "sh")
        assert ctx.query_line == "set advanced; volume sh"
        assert ctx.help_query_line == "set advanced; volume"
        assert ctx.chain_prefix == "set advanced;"


class TestTabHelpEligible:
    def test_empty_line(self):
        assert tab_help_eligible("")

    def test_trailing_space_not_flag(self):
        assert tab_help_eligible("volume ")

    def test_no_trailing_space(self):
        assert not tab_help_eligible("volume show")

    def test_trailing_space_after_flag(self):
        assert not tab_help_eligible("volume show -vserver ")


class TestFlagAtCursor:
    def test_after_flag_space(self):
        line = "volume show -vserver "
        assert flag_at_cursor(line, len(line), len(line), "") == "-vserver"

    def test_partial_flag_name_is_not_value(self):
        line = "volume show -vol"
        assert flag_at_cursor(line, 16, 16, "-vol") is None

    def test_partial_value(self):
        line = "volume show -vserver sv"
        assert flag_at_cursor(line, 21, 23, "sv") == "-vserver"

    def test_partial_value_when_readline_splits_on_dash(self):
        # Simulates default readline treating '-' as a word break.
        line = "volume show -vserver sv"
        assert flag_at_cursor(line, 22, 24, "sv") == "-vserver"


class TestFlagPrefixWithSplitDelimiter:
    def test_flag_prefix_at_cursor_includes_dash(self):
        assert flag_prefix_at_cursor("volume show -vol", 13, 16, "vol") == "-vol"

    def test_help_query_strips_dangling_dash(self):
        ctx = LineContext("volume show -vol", 13, 16, "vol")
        assert ctx.help_query_line == "volume show"

    def test_completes_when_readline_splits_on_dash(self, fixtures_dir: Path):
        backend = StaticBackend(
            {
                build_help_query("volume show"): load_fixture(
                    fixtures_dir, "volume_show_parameters.txt"
                )
            }
        )
        completer = OntapCompleter(backend)
        matches = completer.completions_for(
            LineContext("volume show -vol", 13, 16, "vol")
        )
        assert "-volume " in matches

    def test_readline_insert_when_dash_already_typed(self):
        assert (
            format_readline_completion("-volume ", "volume show -vol", 13, 16, "vol")
            == "ume "
        )


class TestParseEnumValues:
    def test_state_enum(self):
        assert parse_enum_values("{online|restricted|offline}") == [
            "online",
            "restricted",
            "offline",
        ]

    def test_integer_range_returns_empty(self):
        assert parse_enum_values("{120..86400}") == []


class TestOntapCompleter:
    def test_command_path_subcommands(self, fixtures_dir: Path):
        backend = StaticBackend(
            {build_help_query("volume"): load_fixture(fixtures_dir, "volume_subcommands.txt")}
        )
        completer = OntapCompleter(backend)
        matches = completer.completions_for(LineContext("volume sh", 7, 9, "sh"))
        assert matches == ["show "]

    def test_hyphenated_subcommand_path_not_treated_as_flag(self, fixtures_dir: Path):
        backend = StaticBackend(
            {
                build_help_query("vserver export-policy"): load_fixture(
                    fixtures_dir, "vserver_export_policy_subcommands.txt"
                )
            }
        )
        completer = OntapCompleter(backend)
        line = "vserver export-policy ru"
        ctx = LineContext(line, 22, 24, "ru")
        assert ctx.phase() == CompletionPhase.COMMAND_PATH
        assert completer.completions_for(ctx) == ["rule "]

    def test_flag_names_from_parameter_help(self, fixtures_dir: Path):
        backend = StaticBackend(
            {
                build_help_query("volume show"): load_fixture(
                    fixtures_dir, "volume_show_parameters.txt"
                )
            }
        )
        completer = OntapCompleter(backend)
        matches = completer.completions_for(
            LineContext("volume show -vol", 12, 16, "-vol")
        )
        assert "-volume " in matches

    def test_flag_values_from_backend(self, fixtures_dir: Path):
        backend = StaticBackend(
            {
                build_help_query("volume show"): load_fixture(
                    fixtures_dir, "volume_show_parameters.txt"
                )
            },
            values={"-vserver": ["svm-a", "svm-b"]},
        )
        completer = OntapCompleter(backend)
        line = "volume show -vserver "
        matches = completer.completions_for(
            LineContext(line, len(line), len(line), "")
        )
        assert matches == ["svm-a ", "svm-b "]

    def test_volume_create_volume_value_with_missing_arg_help(
        self, fixtures_dir: Path
    ):
        """volume create returns missing-arg help, not parameter list."""
        backend = StaticBackend(
            {
                build_help_query("volume create"): load_fixture(
                    fixtures_dir, "missing_argument_vserver.txt"
                )
            },
            values={"-volume": ["vol1", "vol2"]},
        )
        completer = OntapCompleter(backend)
        line = "volume create -volume "
        end = len(line)
        ctx = LineContext(line, end, end, "")
        assert completer.completions_for(ctx) == ["vol1 ", "vol2 "]

    def test_flag_values_enum_fallback(self, fixtures_dir: Path):
        backend = StaticBackend(
            {
                build_help_query("volume show"): load_fixture(
                    fixtures_dir, "volume_show_parameters.txt"
                )
            }
        )
        completer = OntapCompleter(backend)
        line = "volume show -state on"
        matches = completer.completions_for(
            LineContext(line, 20, 22, "on")
        )
        assert matches == ["online "]

    def test_missing_argument_flag(self, fixtures_dir: Path):
        backend = StaticBackend(
            {
                build_help_query("volume create"): load_fixture(
                    fixtures_dir, "missing_argument_vserver.txt"
                )
            }
        )
        completer = OntapCompleter(backend)
        matches = completer.completions_for(
            LineContext("volume create -v", 13, 15, "-v")
        )
        assert matches == ["-vserver "]

    def test_missing_argument_after_trailing_space(self, fixtures_dir: Path):
        backend = StaticBackend(
            {
                build_help_query("vol create"): load_fixture(
                    fixtures_dir, "missing_argument_vserver.txt"
                )
            }
        )
        completer = OntapCompleter(backend)
        line = "vol create "
        end = len(line)
        ctx = LineContext(line, end, end, "")
        matches, show_help = completer.tab_completions(ctx)
        assert show_help is False
        assert matches == ["-vserver "]

    def test_help_text_only_in_help_phase(self, fixtures_dir: Path):
        backend = StaticBackend(
            {" ?": load_fixture(fixtures_dir, "volume_subcommands.txt")}
        )
        completer = OntapCompleter(backend)
        ctx = LineContext("", 0, 0, "")
        assert completer.help_text(ctx) is not None
        assert completer.help_text(LineContext("volume sh", 9, 9, "sh")) is None

    def test_readline_complete_state_machine(self, fixtures_dir: Path):
        backend = StaticBackend(
            {build_help_query("volume"): load_fixture(fixtures_dir, "volume_subcommands.txt")}
        )
        completer = OntapCompleter(backend)
        assert completer.complete("volume sh", 7, 9, "sh", 0) == "show "
        assert completer.complete("volume sh", 7, 9, "sh", 1) is None

    def test_switch_flag_does_not_complete_values(self, fixtures_dir: Path):
        backend = StaticBackend(
            {
                build_help_query("volume show -instance"): load_fixture(
                    fixtures_dir, "volume_show_parameters.txt"
                )
            }
        )
        completer = OntapCompleter(backend)
        line = "volume show -instance "
        matches = completer.completions_for(
            LineContext(line, len(line), len(line), "")
        )
        assert matches == []

    def test_chained_line_uses_full_query(self, fixtures_dir: Path):
        backend = StaticBackend(
            {
                build_help_query("set advanced; volume"): load_fixture(
                    fixtures_dir, "volume_subcommands.txt"
                )
            }
        )
        completer = OntapCompleter(backend)
        completer.completions_for(LineContext("set advanced; volume sh", 20, 22, "sh"))
        assert backend.help_calls == [build_help_query("set advanced; volume")]


class TestSplitChainedLineWithOffset:
    def test_no_chain(self):
        assert split_chained_line_with_offset("volume show") == ("", "volume show", 0)

    def test_chain_offset(self):
        prefix, active, start = split_chained_line_with_offset("set advanced; volume show")
        assert prefix == "set advanced;"
        assert active == "volume show"
        assert "volume show" in "set advanced; volume show"[start:]

    def test_parser_compat(self):
        prefix, segment = split_chained_line("set advanced; volume show")
        assert prefix == "set advanced;"
        assert segment == "volume show"
