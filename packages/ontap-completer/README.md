# ONTAP completer

Readline autocompletion for GCNV ONTAP-mode CLI.

Parser rules, fixtures, and behavioral spec: `dev-tools/ontap-auto-completion.md` in the parent ONTAP-mode repo.

## Development

```bash
cd ONTAP-mode-shell/packages/ontap-completer
uv sync --extra dev
uv run pytest
```

## Components

| Module | Role |
|--------|------|
| `parser.py` | Pure help-text parsing (`ResponseKind`, subcommands, parameters, OR-groups, expansion hints) |
| `backend.py` | `CompletionBackend` protocol, `GcnvPoolBackend`, session cache |
| `providers.py` | Flag value providers (`-vserver`, `-volume`, `-snapshot`, …) |
| `engine.py` | `OntapCompleter` — phases, probe-on-type command-path completion, flag completion |
| `readline_ui.py` | Readline TAB integration |

The interactive shell lives in the sibling package `../ontap-mode-shell/` (`ontap-mode-shell` console script).

```python
from ontap_completion import OntapCompleter, create_gcnv_session_backend

backend = create_gcnv_session_backend(pool)
completer = OntapCompleter(backend)
match = completer.complete(line, begidx, endidx, text, state)
help_text = completer.help_text(LineContext(line, begidx, endidx, text))
```
