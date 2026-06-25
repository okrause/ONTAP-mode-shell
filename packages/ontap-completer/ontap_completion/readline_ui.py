"""Readline TAB completion and help display for the ONTAP-mode shell."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

try:
    import gnureadline as readline
except ImportError:
    import readline

from ontap_completion.engine import (
    LineContext,
    OntapCompleter,
    ONTAP_COMPLETER_DELIMS,
    format_readline_completion,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class ReadlineUI:
    """Wire OntapCompleter into readline (TAB help + completions)."""

    def __init__(
        self,
        completer: OntapCompleter,
        *,
        display_prompt: str,
        input_prompt: str,
        help_fetcher: Callable[[str], str] | None = None,
    ) -> None:
        self._completer = completer
        self._display_prompt = display_prompt
        self._input_prompt = input_prompt
        self._help_fetcher = help_fetcher
        self._matches: list[str] = []

    def setup(self) -> None:
        readline.set_completer_delims(ONTAP_COMPLETER_DELIMS)
        readline.set_completer(self._readline_completer)
        if readline.__doc__ and "libedit" in readline.__doc__:
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")

    def _readline_completer(self, text: str, state: int) -> str | None:
        if state == 0:
            line = readline.get_line_buffer()
            begidx = readline.get_begidx()
            endidx = readline.get_endidx()
            ctx = LineContext(line, begidx, endidx, text)
            raw, show_help = self._completer.tab_completions(ctx)
            if show_help:
                self._print_tab_help(ctx)
                self._matches = []
            else:
                self._matches = [
                    format_readline_completion(
                        match, line, begidx, endidx, text
                    )
                    for match in raw
                ]
        if state < len(self._matches):
            return self._matches[state]
        return None

    def _print_tab_help(self, ctx: LineContext) -> None:
        buf = readline.get_line_buffer()
        empty = not buf.strip()
        try:
            if self._help_fetcher is not None:
                out = self._help_fetcher(ctx.help_query_line)
            else:
                out = self._completer.help_text(ctx)
            out_s = str(out).rstrip("\n") if out is not None else ""
            if empty:
                sys.stdout.write(out_s + "\n" + self._display_prompt + buf)
            else:
                sys.stdout.write("\n" + out_s + "\n" + self._display_prompt + buf)
        except Exception as exc:
            if empty:
                sys.stdout.write(f"Error: {exc}\n" + self._display_prompt + buf)
            else:
                sys.stdout.write(f"\nError: {exc}\n" + self._display_prompt + buf)
        sys.stdout.flush()


def setup_readline(
    completer: OntapCompleter,
    *,
    display_prompt: str,
    input_prompt: str,
    help_fetcher: Callable[[str], str] | None = None,
) -> ReadlineUI:
    """Configure readline and return the UI handle."""
    ui = ReadlineUI(
        completer,
        display_prompt=display_prompt,
        input_prompt=input_prompt,
        help_fetcher=help_fetcher,
    )
    ui.setup()
    return ui
