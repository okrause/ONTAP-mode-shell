# ontap-mode-shell

Interactive ONTAP-mode shell for Google Cloud NetApp Volumes with help-driven TAB completion.

Depends on workspace libraries `gcnv-client` (API/auth) and `ontap-completer` (completion engine).

## Run from repo root

```bash
uv sync
uv run ontap-mode-shell --storage-pool <pool-name>
# or with a full pool resource name:
uv run ontap-mode-shell --pool-urn projects/PROJECT/locations/LOCATION/storagePools/POOL
```

Command history is stored in `~/.ontap_mode_shell_history`.
