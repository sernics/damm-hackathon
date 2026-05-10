"""Command-line entry points.

Usage:

    python -m veteran_capture.cli profiles
        Build customer profiles + driver-customer affinity. Saves parquet.

    python -m veteran_capture.cli select [--top-n N]
        Read profiles, score (client, driver) pairs, write the queue.

    python -m veteran_capture.cli show-customer <client_id>
        Print the profile for a specific client (sanity check).

    python -m veteran_capture.cli show-queue [--head N]
        Print the top N rows of the queue (sanity check).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import uvicorn

from veteran_capture.config import get_settings
from veteran_capture.demo import write_seed_captures
from veteran_capture.logging_setup import configure_logging, get_logger
from veteran_capture.mining.affinity import build_driver_customer_affinity
from veteran_capture.mining.customers import build_customer_profiles
from veteran_capture.mining.io import (
    load_detalle,
    load_direcciones,
    load_horarios,
)
from veteran_capture.selection import build_priority_queue, load_inputs
from veteran_capture.writer.markdown import write_all_notes


def cmd_profiles() -> int:
    settings = get_settings()
    logger = get_logger("veteran_capture.cli")

    settings.profiles_dir.mkdir(parents=True, exist_ok=True)

    detalle = load_detalle()
    direcciones = load_direcciones()
    horarios = load_horarios()

    customers = build_customer_profiles(detalle, direcciones, horarios)
    affinity = build_driver_customer_affinity(detalle)

    customers_path = settings.profiles_dir / "customers.parquet"
    affinity_path = settings.profiles_dir / "driver_customer_affinity.parquet"
    customers.to_parquet(customers_path, index=False)
    affinity.to_parquet(affinity_path, index=False)

    logger.info(
        "wrote profiles",
        extra={
            "customers_path": str(customers_path),
            "affinity_path": str(affinity_path),
            "customers_rows": len(customers),
            "affinity_rows": len(affinity),
        },
    )
    return 0


def cmd_select(top_n: int) -> int:
    settings = get_settings()
    logger = get_logger("veteran_capture.cli")
    settings.queues_dir.mkdir(parents=True, exist_ok=True)

    customers, affinity = load_inputs()
    queue = build_priority_queue(customers, affinity, top_n=top_n)
    out_path = settings.queues_dir / "queue.parquet"
    queue.to_parquet(out_path, index=False)
    logger.info(
        "wrote queue",
        extra={"path": str(out_path), "rows": len(queue), "top_n": top_n},
    )
    return 0


def cmd_show_queue(head: int) -> int:
    settings = get_settings()
    path = settings.queues_dir / "queue.parquet"
    if not path.exists():
        print(f"queue not built yet: {path}", file=sys.stderr)
        return 2

    df = pd.read_parquet(path)
    if df.empty:
        print("queue is empty", file=sys.stderr)
        return 3

    pd.set_option("display.max_colwidth", 60)
    pd.set_option("display.width", 200)
    cols = [
        "client_id",
        "client_name",
        "driver_id",
        "score",
        "n_existing_tips",
        "n_deliveries_driver_to_client",
        "client_total_cases",
        "reason",
    ]
    print(df.head(head)[cols].to_string(index=False))
    return 0


def cmd_seed_demo(*, overwrite: bool) -> int:
    logger = get_logger("veteran_capture.cli")
    written = write_seed_captures(overwrite=overwrite)
    logger.info("demo seed written", extra={"captures": written})
    print(f"wrote {written} seed capture file(s)")
    return 0


def cmd_write_notes(manifest_top_recommend: int) -> int:
    logger = get_logger("veteran_capture.cli")
    report = write_all_notes(manifest_top_recommend=manifest_top_recommend)
    logger.info(
        "wrote markdown KB",
        extra={
            "clients_written": report.clients_written,
            "captures_loaded": report.captures_loaded,
            "out_dir": str(report.out_dir),
            "manifest_md": str(report.manifest_md_path),
            "manifest_json": str(report.manifest_json_path),
            "filled": report.filled,
            "empty": report.empty,
        },
    )
    print(
        f"wrote {report.clients_written} client note(s) "
        f"from {report.captures_loaded} capture file(s) into {report.out_dir}\n"
        f"manifest: {report.filled} filled / {report.empty} empty "
        f"out of {report.total_clients} active clients"
    )
    return 0


def cmd_serve(*, host: str | None, port: int | None, reload: bool) -> int:
    settings = get_settings()
    bind_host = host or settings.server_host
    bind_port = port or settings.server_port
    logger = get_logger("veteran_capture.cli")
    logger.info("starting capture webapp", extra={"host": bind_host, "port": bind_port})
    uvicorn.run(
        "veteran_capture.capture.web:app",
        host=bind_host,
        port=bind_port,
        reload=reload,
        log_level=settings.log_level.lower(),
    )
    return 0


def cmd_show_customer(client_id: str) -> int:
    settings = get_settings()
    path = settings.profiles_dir / "customers.parquet"
    if not path.exists():
        print(f"profiles not built yet: {path}", file=sys.stderr)
        return 2

    df = pd.read_parquet(path)
    row = df[df["client_id"] == client_id]
    if row.empty:
        print(f"client_id {client_id!r} not found", file=sys.stderr)
        return 3
    pd.set_option("display.max_colwidth", 80)
    print(row.iloc[0].to_string())
    return 0


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0911
    configure_logging()
    parser = argparse.ArgumentParser(prog="veteran-capture")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("profiles", help="Build customer profiles + driver affinity from CSVs.")

    sel = sub.add_parser("select", help="Build the priority queue of (client, driver) pairs.")
    sel.add_argument("--top-n", type=int, default=50, help="Cap on queue length. 0 = all.")

    sq = sub.add_parser("show-queue", help="Print the top of the priority queue.")
    sq.add_argument("--head", type=int, default=20, help="Number of queue rows to display.")

    sv = sub.add_parser("serve", help="Run the FastAPI capture webapp.")
    sv.add_argument("--host", default=None)
    sv.add_argument("--port", type=int, default=None)
    sv.add_argument("--reload", action="store_true", help="Enable auto-reload (dev only).")

    wn = sub.add_parser(
        "write-notes",
        help="Aggregate capture JSONs and (re)write the per-client markdown KB.",
    )
    wn.add_argument(
        "--manifest-top-recommend",
        type=int,
        default=20,
        help="How many top-priority rows to highlight in the manifest header.",
    )

    sd = sub.add_parser(
        "seed-demo",
        help="Write hand-authored demo capture JSONs to data/captures/.",
    )
    sd.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete existing *.seed.json before writing new ones.",
    )

    sc = sub.add_parser("show-customer", help="Print the profile for a single client.")
    sc.add_argument("client_id", help="10-digit (91xxxxxxxx) or 6-digit chain code.")
    args = parser.parse_args(argv)

    cmd: str = args.cmd
    if cmd == "profiles":
        return cmd_profiles()
    if cmd == "select":
        return cmd_select(args.top_n)
    if cmd == "show-queue":
        return cmd_show_queue(args.head)
    if cmd == "show-customer":
        return cmd_show_customer(args.client_id)
    if cmd == "serve":
        return cmd_serve(host=args.host, port=args.port, reload=args.reload)
    if cmd == "write-notes":
        return cmd_write_notes(args.manifest_top_recommend)
    if cmd == "seed-demo":
        return cmd_seed_demo(overwrite=args.overwrite)
    parser.error(f"unknown command: {cmd}")
    return 1  # pragma: no cover - parser.error raises


if __name__ == "__main__":
    Path(__file__)  # keep import for editors
    raise SystemExit(main())
