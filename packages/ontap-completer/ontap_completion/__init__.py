"""ONTAP CLI autocompletion library."""

from ontap_completion.backend import (
    CompletionBackend,
    GcnvPoolBackend,
    SessionCacheBackend,
    build_help_query,
    create_gcnv_session_backend,
    normalize_cli_output,
)
from ontap_completion.engine import (
    CompletionPhase,
    LineContext,
    OntapCompleter,
    flag_at_cursor,
    flag_prefix_at_cursor,
    format_readline_completion,
    parse_enum_values,
    should_complete_flag_name,
    tab_help_eligible,
    ONTAP_COMPLETER_DELIMS,
)
from ontap_completion.parser import (
    classify_response,
    parse_parameter_help,
    parse_subcommand_help,
    split_chained_line,
    unique_parameter_flags,
)
from ontap_completion.providers import ValueProviderRegistry, build_default_registry
from ontap_completion.readline_ui import ReadlineUI, setup_readline

__all__ = [
    "CompletionBackend",
    "CompletionPhase",
    "GcnvPoolBackend",
    "HelpEntry",
    "LineContext",
    "OntapCompleter",
    "ParamKind",
    "ReadlineUI",
    "ResponseKind",
    "SessionCacheBackend",
    "ValueProviderRegistry",
    "build_default_registry",
    "build_help_query",
    "classify_response",
    "create_gcnv_session_backend",
    "flag_at_cursor",
    "flag_prefix_at_cursor",
    "format_readline_completion",
    "normalize_cli_output",
    "ONTAP_COMPLETER_DELIMS",
    "parse_enum_values",
    "parse_parameter_help",
    "parse_subcommand_help",
    "should_complete_flag_name",
    "setup_readline",
    "split_chained_line",
    "tab_help_eligible",
    "unique_parameter_flags",
]
