# ONTAP completer

Readline autocompletion for GCNV ONTAP-mode CLI, based on `../ontap-auto-completion.md`.

## Development

```bash
cd ONTAP-mode-shell/packages/ontap-completer
uv sync --extra dev
uv run pytest
```

Phase 1 implements pure help-text parsing (`ontap_completion/parser.py`) with no network or readline dependencies.

Phase 2 adds the completion backend (`backend.py`, `providers.py`):

- `CompletionBackend` protocol
- `GcnvPoolBackend` wrapping an `OntapModePool`-like object
- `ValueProviderRegistry` for extensible flag value providers
- `SessionCacheBackend` for in-memory per-session caching

Phase 3 adds the completion engine (`engine.py`):

- `LineContext` and `CompletionPhase` (command path, flag name, flag value, help)
- `OntapCompleter` wiring parser + backend into readline-ready completions

Phase 4 adds readline integration (`readline_ui.py`). The interactive shell lives in the sibling package `../ontap-mode-shell/` (`ontap-mode-shell` console script).

```python
from ontap_completion import OntapCompleter, create_gcnv_session_backend

backend = create_gcnv_session_backend(pool)
completer = OntapCompleter(backend)
match = completer.complete(line, begidx, endidx, text, state)
help_text = completer.help_text(LineContext(line, begidx, endidx, text))
```
