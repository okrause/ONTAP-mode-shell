"""Interactive ONTAP-mode shell for Google Cloud NetApp Volumes."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

try:
    import gnureadline as readline
except ImportError:
    import readline

from gcnv_client import NetappVolumes, OntapLif, OntapModePool, configure_logging

configure_logging()

from ontap_completion import OntapCompleter, create_gcnv_session_backend
from ontap_completion.readline_ui import setup_readline

HISTORY_FILE = os.path.expanduser("~/.ontap_mode_shell_history")

_BLUE, _GREEN, _CYAN, _MAGENTA, _RESET = "\033[94m", "\033[92m", "\033[36m", "\033[95m", "\033[0m"


def make_cluster_prompts(cluster_name: str) -> tuple[str, str]:
    """Return (display_prompt, input_prompt) for readline."""
    prompt_text = f"{cluster_name}> "
    display_prompt = f"{_BLUE}{prompt_text}{_RESET}"
    input_prompt = f"\001{_BLUE}\002{prompt_text}\001{_RESET}\002"
    return display_prompt, input_prompt


def get_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive ONTAP-mode shell for Google Cloud NetApp Volumes",
    )
    parser.add_argument("--project", help="GCP project ID or number")
    parser.add_argument("--location", help="GCP location or region")
    parser.add_argument("--storage-pool", required=True, help="Storage pool name")
    parser.add_argument(
        "--command",
        help="ONTAP CLI command to execute (optional; interactive shell if omitted)",
    )
    return parser.parse_args()


def _resolve_project_and_location(args: argparse.Namespace) -> tuple[str, str]:
    if args.project:
        project_id = args.project
    else:
        project_id = (
            subprocess.check_output(["gcloud", "config", "get-value", "project"])
            .decode()
            .strip()
        )

    if args.location:
        location = args.location
    else:
        location = (
            subprocess.check_output(["gcloud", "config", "get-value", "compute/region"])
            .decode()
            .strip()
        )
    return project_id, location


def _print_lifs(lifs: list[OntapLif]) -> None:
    if not lifs:
        return
    name_w = max(len(lif.name) for lif in lifs)
    addr_w = max(len(lif.address) for lif in lifs)
    svc_w = max(len(lif.service) for lif in lifs)
    ipspace_w = max(len(lif.ipspace) for lif in lifs)

    print(
        f"{'LIF':<{name_w}}   {'IP address':<{addr_w}}  "
        f"{'Service':<{svc_w}}  {'IPspace':<{ipspace_w}}"
    )
    for lif in sorted(lifs, key=lambda item: (item.service, item.name)):
        ip = f"{_MAGENTA}{lif.address}{_RESET}"
        pad = addr_w - len(lif.address)
        print(
            f" {lif.name:<{name_w}}  {ip}{' ' * pad}  "
            f"{lif.service:<{svc_w}}  {lif.ipspace}"
        )
    print()


def _print_svms(pool: OntapModePool) -> None:
    if not pool.ontap_svms:
        return
    rows = [
        (svm_name, ", ".join(pool.ontap_aggregates.get(svm_name, [])))
        for svm_name in sorted(pool.ontap_svms)
    ]
    svm_w = max(len("SVM"), max(len(name) for name, _ in rows))
    aggr_w = max(len("Aggregates"), max(len(aggr) for _, aggr in rows))

    print(f"{'SVM':<{svm_w}}   {'Aggregate':<{aggr_w}}")
    for svm_name, aggregates in rows:
        svm = f"{_GREEN}{svm_name}{_RESET}"
        aggr = f"{_CYAN}{aggregates}{_RESET}"
        svm_pad = svm_w - len(svm_name)
        aggr_pad = aggr_w - len(aggregates)
        print(f" {svm}{' ' * svm_pad}  {aggr}{' ' * aggr_pad}")
    print()


def _print_banner(pool: OntapModePool) -> None:
    print(
        "\033[92mGCNV ONTAP-mode shell\033[0m "
        "(help-driven TAB completion)\n"
    )
    print(f"Pool: \033[33m{pool.google_pool_urn}\033[0m")
    print(f"Cluster: \033[94m{pool.ontap_cluster_name}\033[0m")
    _print_svms(pool)
    _print_lifs(pool.ontap_lifs)
    print("Type ONTAP CLI commands. Type 'exit' to quit.\n")
    print(
        "Append ' ?' and press Enter for help, or press TAB on an empty line "
        "/ after a trailing space.\n"
    )
    print("TAB completes command paths, flags, and known flag values.\n")


def _run_interactive(pool: OntapModePool) -> None:
    if os.path.exists(HISTORY_FILE):
        readline.read_history_file(HISTORY_FILE)
    readline.set_history_length(1000)

    display_prompt, input_prompt = make_cluster_prompts(pool.ontap_cluster_name)

    backend = create_gcnv_session_backend(pool)
    completer = OntapCompleter(backend)
    setup_readline(
        completer,
        display_prompt=display_prompt,
        input_prompt=input_prompt,
        help_fetcher=backend.help_for_line,
    )

    _print_banner(pool)
    while True:
        try:
            cmd = input(input_prompt).strip()
            if cmd.lower() == "exit":
                break
            if cmd:
                result = pool.ontap_cli(cmd)
                print(result)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break
        except Exception as exc:
            print(f"Error: {exc}")
        finally:
            readline.write_history_file(HISTORY_FILE)


def main() -> None:
    args = get_arguments()
    project_id, location = _resolve_project_and_location(args)
    pool_urn = f"/locations/{location}/storagePools/{args.storage_pool}"

    nv = NetappVolumes(project=project_id)
    pool = OntapModePool(nv, pool_urn)

    if args.command:
        try:
            print(pool.ontap_cli(args.command))
        except Exception as exc:
            print(f"Error: {exc}")
            sys.exit(1)
    else:
        _run_interactive(pool)
