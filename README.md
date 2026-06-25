# ONTAP-mode shell

Interactive ONTAP-mode shell for Google Cloud NetApp Volumes. Commands run against your storage pool through the GCNV ONTAP-mode API; TAB completion is driven by live `?` help from the pool.

The shell app lives in `packages/ontap-mode-shell/` (formerly `ontap_mode_shell.py` at the repo root).

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- Google Cloud credentials: `gcloud auth application-default login`
- A GCNV storage pool in ONTAP-mode

## Install

```bash
cd ONTAP-mode-shell
uv sync
```

## Run

**Interactive shell** (default):

```bash
uv run ontap-mode-shell --storage-pool <pool-name>
```

Optional flags:

| Flag | Description |
|------|-------------|
| `--project` | GCP project ID (default: `gcloud config get-value project`) |
| `--location` | GCP region (default: `gcloud config get-value compute/region`) |
| `--command` | Run one command and exit instead of starting the shell |

Examples:

```bash
# Use explicit project and region
uv run ontap-mode-shell --project my-project --location us-central1 --storage-pool my-pool

# Single command, no interactive prompt
uv run ontap-mode-shell --storage-pool my-pool --command "volume show"
```

On startup the shell prints the pool URN, cluster name, SVM/aggregate table, and LIF table. The prompt is `{cluster_name}> `.

Type `exit` to quit. Command history is saved to `~/.ontap_mode_shell_history`.

## What TAB completes

Completion is **help-driven**: the completer sends your current line (plus `?` when needed) to the pool and parses the response. Nothing is hard-coded per command beyond the value providers listed below.

TAB behaves in four modes depending on cursor position:

### 1. Help (raw `?` output)

TAB shows the same text as appending ` ?` and pressing Enter when:

- the line is **empty**, or
- the line ends with a **trailing space** and the last token is **not** a flag (e.g. `volume show ` → TAB shows parameter help)

TAB does **not** steal completion after `-flag ` — there it completes flag values instead.

You can always type ` ?` explicitly for help on any line.

### 2. Command path (subcommands)

While typing the command before any `-flag`, TAB completes the next token from the subcommand list in `?` help.

Example: `vol<TAB>` → `volume `; `volume cr<TAB>` → `volume create ` (when help lists `create`).

### 3. Flag names

After the command path (or when help returns a missing-argument error), TAB completes `-parameter` names from `?` parameter help, including aliases.

Examples:

- `volume show -v<TAB>` → `-vserver `
- `volume create ` + TAB → offers the next required flag from a 400 missing-argument response

### 4. Flag values

After a flag that takes an argument (`-flag ` or partial value), TAB completes allowed values.

**Chained commands** (`set advanced; volume show -vserver `) are supported; completion applies to the segment after the last `;`.

## Supported value completions

These flags get live values from the pool (via the GCNV REST API):

| Flag | Source |
|------|--------|
| `-vserver` | SVM names (`/svm/svms`) |
| `-volume` | Volume names (`/storage/volumes`) |
| `-aggregate` | Aggregate names (all SVMs in the pool) |
| `-interface`, `-lif` | Network interface / LIF names (`/network/ip/interfaces`) |
| `-snapshot` | Snapshot names (`/storage/snapshots`) |

For **other flags**, TAB can still complete values when `?` help declares an **enum** in the type syntax, e.g. `{online|offline}` → offers `online` and `offline`. Integer ranges and free-text parameters are not completed.

Switch-style flags (no argument) do not get value completion.

## Layout

```
ONTAP-mode-shell/
  pyproject.toml              # uv workspace root
  packages/
    gcnv-client/              # GCNV auth and REST API
    ontap-completer/          # TAB completion library
    ontap-mode-shell/         # interactive shell (entry point: ontap-mode-shell)
```

## Tests

```bash
cd packages/ontap-completer && uv sync --extra dev && uv run pytest
cd ../gcnv-client && uv sync --extra dev && uv run pytest
```

Parser rules and fixtures are documented in the repo’s `ontap-auto-completion.md`.

## Debug

Set `NETAPP_DEBUG=1` for verbose API logging (via `gcnv-client`).
