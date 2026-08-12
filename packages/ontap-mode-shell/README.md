# ontap-mode-shell

Interactive ONTAP-mode shell for Google Cloud NetApp Volumes with help-driven TAB completion.

Depends on workspace libraries `gcnv-client` (API/auth) and `ontap-completer` (completion engine).

## Run from workspace root

```bash
uv sync
uv run ontap-mode-shell --storage-pool <pool-name>
```

Or pass a full pool resource name (project, location, and pool name are extracted from the URN):

```bash
uv run ontap-mode-shell --pool-urn projects/PROJECT/locations/LOCATION/storagePools/POOL
```

| Flag | Description |
|------|-------------|
| `--pool-urn` | Full storage pool resource name (alternative to `--project` + `--location` + `--storage-pool`) |
| `--project` | GCP project ID (default: `gcloud config get-value project`) |
| `--location` | GCP region or zone (default: `gcloud config get-value compute/region`) |
| `--storage-pool` | Storage pool name (required unless `--pool-urn` is set) |
| `--command` | Run one command and exit |

Command history is stored in `~/.ontap_mode_shell_history`.

See the workspace [README](../../README.md) for TAB completion behavior and empty-result (404) handling.
