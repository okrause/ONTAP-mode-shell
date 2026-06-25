import pytest

from ontap_completion.parser import (
    classify_response,
    parse_parameter_help,
    parse_subcommand_help,
    split_chained_line,
    unique_parameter_flags,
)
from ontap_completion.types import ParamKind, ResponseKind


@pytest.fixture
def fixtures_dir():
    from pathlib import Path

    return Path(__file__).parent / "fixtures"


def load_fixture(fixtures_dir, name: str) -> str:
    return (fixtures_dir / name).read_text(encoding="utf-8")


class TestSplitChainedLine:
    def test_no_chain(self):
        assert split_chained_line("volume show") == ("", "volume show")

    def test_set_advanced_prefix(self):
        prefix, segment = split_chained_line("set advanced; volume show")
        assert prefix == "set advanced;"
        assert segment == "volume show"

    def test_multiple_segments(self):
        prefix, segment = split_chained_line("set advanced; set diag; volume show")
        assert prefix == "set advanced; set diag;"
        assert segment == "volume show"


class TestClassifyResponse:
    def test_subcommand_list(self, fixtures_dir):
        text = load_fixture(fixtures_dir, "volume_subcommands.txt")
        kind, detail = classify_response(text)
        assert kind == ResponseKind.SUBCOMMAND_LIST
        assert detail is None

    def test_parameters(self, fixtures_dir):
        text = load_fixture(fixtures_dir, "volume_show_parameters.txt")
        kind, detail = classify_response(text)
        assert kind == ResponseKind.PARAMETERS
        assert detail is None

    def test_missing_argument(self, fixtures_dir):
        text = load_fixture(fixtures_dir, "missing_argument_vserver.txt")
        kind, detail = classify_response(text)
        assert kind == ResponseKind.MISSING_ARGUMENT
        assert detail == "-vserver"

    def test_empty_result_404(self, fixtures_dir):
        text = load_fixture(fixtures_dir, "empty_result_404.txt")
        kind, detail = classify_response(text)
        assert kind == ResponseKind.EMPTY_RESULT
        assert detail is None


class TestParseSubcommandHelp:
    def test_directories_and_leaves(self, fixtures_dir):
        entries = parse_subcommand_help(
            load_fixture(fixtures_dir, "volume_subcommands.txt")
        )
        by_name = {e.name: e for e in entries}

        assert by_name["clone"].is_directory is True
        assert by_name["clone"].help_text == "Manage FlexClones"
        assert by_name["show"].is_directory is False
        assert by_name["show"].help_text == "Display a list of volumes"
        assert by_name["snapshot"].is_directory is True

    def test_wrapped_description(self, fixtures_dir):
        entries = parse_subcommand_help(
            load_fixture(fixtures_dir, "volume_subcommands.txt")
        )
        autosize = next(e for e in entries if e.name == "autosize")
        assert "flexible" in autosize.help_text
        assert "volume." in autosize.help_text


class TestParseParameterHelp:
    def test_switches_and_fields_in_or_group(self, fixtures_dir):
        entries = unique_parameter_flags(
            parse_parameter_help(load_fixture(fixtures_dir, "volume_show_parameters.txt"))
        )
        by_name = {e.name: e for e in entries}

        assert by_name["-instance"].kind == ParamKind.SWITCH
        assert by_name["-encryption"].kind == ParamKind.SWITCH
        assert by_name["-junction"].kind == ParamKind.SWITCH
        assert by_name["-fields"].kind == ParamKind.NAMED_LIST
        assert "<fieldname>" in by_name["-fields"].type_syntax

    def test_optional_volume_not_switch(self, fixtures_dir):
        entries = unique_parameter_flags(
            parse_parameter_help(load_fixture(fixtures_dir, "volume_show_parameters.txt"))
        )
        by_name = {e.name: e for e in entries}

        assert "-volume" in by_name
        assert by_name["-volume"].kind == ParamKind.TEXT
        assert by_name["-volume"].optional is True
        assert by_name["-volume"].help_text == "Volume Name"

    def test_enum_with_help_text(self, fixtures_dir):
        entries = unique_parameter_flags(
            parse_parameter_help(load_fixture(fixtures_dir, "volume_show_parameters.txt"))
        )
        state = next(e for e in entries if e.name == "-state")
        assert state.kind == ParamKind.ENUM
        assert "online" in state.type_syntax
        assert state.help_text == "Volume State"

    def test_flag_alias(self, fixtures_dir):
        entries = unique_parameter_flags(
            parse_parameter_help(load_fixture(fixtures_dir, "volume_show_parameters.txt"))
        )
        sg = next(e for e in entries if e.name == "-space-guarantee")
        assert sg.aliases == ("-s",)
        assert sg.kind == ParamKind.ENUM
        assert sg.help_text == "Space Guarantee Style"

    def test_vserver_named_param(self, fixtures_dir):
        entries = unique_parameter_flags(
            parse_parameter_help(load_fixture(fixtures_dir, "volume_show_parameters.txt"))
        )
        vs = next(e for e in entries if e.name == "-vserver")
        assert vs.type_syntax == "<vserver name>"
        assert vs.help_text == "Vserver Name"

    def test_bare_first_line_create_style(self, fixtures_dir):
        entries = unique_parameter_flags(
            parse_parameter_help(load_fixture(fixtures_dir, "snapshot_create_parameters.txt"))
        )
        by_name = {e.name: e for e in entries}
        assert "-vserver" in by_name
        assert by_name["-vserver"].help_text == "Vserver"

    def test_wrapped_parameter_help(self, fixtures_dir):
        text = load_fixture(fixtures_dir, "volume_show_parameters.txt")
        entries = unique_parameter_flags(parse_parameter_help(text))
        state = next(e for e in entries if e.name == "-state")
        assert "Volume State" in state.help_text


class TestVserverShowParameters:
    def test_classify_as_parameters(self, fixtures_dir):
        text = load_fixture(fixtures_dir, "vserver_show_parameters.txt")
        kind, detail = classify_response(text)
        assert kind == ResponseKind.PARAMETERS
        assert detail is None

    def test_or_group_switches(self, fixtures_dir):
        entries = unique_parameter_flags(
            parse_parameter_help(load_fixture(fixtures_dir, "vserver_show_parameters.txt"))
        )
        by_name = {e.name: e for e in entries}
        assert by_name["-instance"].kind == ParamKind.SWITCH
        assert by_name["-protocols"].kind == ParamKind.SWITCH
        assert by_name["-fields"].kind == ParamKind.NAMED_LIST

    def test_optional_vserver_flag(self, fixtures_dir):
        entries = unique_parameter_flags(
            parse_parameter_help(load_fixture(fixtures_dir, "vserver_show_parameters.txt"))
        )
        vs = next(e for e in entries if e.name == "-vserver")
        assert vs.optional is True
        assert vs.help_text == "Vserver"
        assert vs.type_syntax == "<vserver name>"

    def test_enum_and_list_params(self, fixtures_dir):
        entries = unique_parameter_flags(
            parse_parameter_help(load_fixture(fixtures_dir, "vserver_show_parameters.txt"))
        )
        by_name = {e.name: e for e in entries}
        assert by_name["-admin-state"].kind == ParamKind.ENUM
        assert "running" in by_name["-admin-state"].type_syntax
        assert by_name["-allowed-protocols"].kind == ParamKind.NAMED_LIST
        assert by_name["-is-repository"].kind == ParamKind.BOOLEAN

    def test_wrapped_max_volumes_help(self, fixtures_dir):
        entries = unique_parameter_flags(
            parse_parameter_help(load_fixture(fixtures_dir, "vserver_show_parameters.txt"))
        )
        mv = next(e for e in entries if e.name == "-max-volumes")
        assert "Volumes allowed" in mv.help_text


class TestVserverNfsShowParameters:
    def test_classify_as_parameters(self, fixtures_dir):
        text = load_fixture(fixtures_dir, "vserver_nfs_show_parameters.txt")
        kind, detail = classify_response(text)
        assert kind == ResponseKind.PARAMETERS
        assert detail is None

    def test_dotted_flag_names(self, fixtures_dir):
        entries = unique_parameter_flags(
            parse_parameter_help(
                load_fixture(fixtures_dir, "vserver_nfs_show_parameters.txt")
            )
        )
        by_name = {e.name: e for e in entries}
        assert "-v4.0" in by_name
        assert by_name["-v4.0"].kind == ParamKind.ENUM
        assert by_name["-v4.0"].help_text == "NFS v4.0"
        assert "-v4.0-read-delegation" in by_name
        assert "-v4.1-pnfs" in by_name

    def test_wrapped_delegation_help(self, fixtures_dir):
        entries = unique_parameter_flags(
            parse_parameter_help(
                load_fixture(fixtures_dir, "vserver_nfs_show_parameters.txt")
            )
        )
        wd = next(e for e in entries if e.name == "-v4.0-write-delegation")
        assert "Write Delegation" in wd.help_text
        assert "Support" in wd.help_text

    def test_integer_range_enum(self, fixtures_dir):
        entries = unique_parameter_flags(
            parse_parameter_help(
                load_fixture(fixtures_dir, "vserver_nfs_show_parameters.txt")
            )
        )
        idle = next(e for e in entries if e.name == "-idle-connection-timeout")
        assert idle.kind == ParamKind.INTEGER
        assert "120..86400" in idle.type_syntax
        assert "seconds" in idle.help_text

    def test_nfs_subcommand_path_has_show_leaf(self, fixtures_dir):
        """vserver nfs ? must expose show as a leaf before vserver nfs show ?."""
        entries = parse_subcommand_help(
            load_fixture(fixtures_dir, "vserver_nfs_subcommands.txt")
        )
        by_name = {e.name: e for e in entries}
        assert by_name["show"].is_directory is False
        assert "NFS configurations" in by_name["show"].help_text
        assert by_name["kerberos"].is_directory is True
