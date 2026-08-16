#!/usr/bin/env python
"""Tokopedia scraper CLI.

    python main.py search                    # stage 1: collect listings
    python main.py enrich                    # stage 2: descriptions + image URLs
    python main.py images                    # download the image files
    python main.py export --format jsonl csv parquet
    python main.py stats

Every command resumes automatically: finished keywords are skipped, and only
products without a PDP are enriched. Interrupting with Ctrl-C is safe — the
database is committed after each page and each product.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if (REPO_ROOT / "src").is_dir():
    sys.path.insert(0, str(REPO_ROOT / "src"))

from rich.console import Console  # noqa: E402
from rich.progress import (  # noqa: E402
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table  # noqa: E402

from tokopedia_scraper.config import Config, MissingCredential  # noqa: E402
from tokopedia_scraper.logging_setup import setup_logging  # noqa: E402
from tokopedia_scraper.pipeline import (  # noqa: E402
    RunStats,
    export_dataset,
    reparse_from_raw,
    run_enrich,
    run_images,
    run_search,
)
from tokopedia_scraper.ratelimit import CircuitOpen  # noqa: E402
from tokopedia_scraper.storage import Storage  # noqa: E402

console = Console()
log = logging.getLogger("tokopedia_scraper.cli")

FETCHER_CHOICES = ["graphql", "playwright", "managed", "auto"]


def make_progress(description: str):
    """A rich progress bar wired to pipeline's progress(done, total, label)."""
    bar = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TextColumn("[dim]{task.fields[label]}"),
        TimeElapsedColumn(),
        console=console,
    )
    task_id = bar.add_task(description, total=1, label="")

    def report(done: int, total: int, label: str) -> None:
        bar.update(task_id, completed=done, total=max(total, 1), label=label[:40])

    return bar, report


def show_stats(stats: RunStats, title: str) -> None:
    table = Table(title=title, show_header=False, box=None)
    for key, value in stats.as_dict().items():
        if value:
            table.add_row(key.replace("_", " "), str(value))
    console.print(table)

    if stats.notes:
        console.print(f"[yellow]{len(stats.notes)} note(s):[/yellow]")
        for note in stats.notes[:15]:
            console.print(f"  - {note}")
        if len(stats.notes) > 15:
            console.print(f"  ... and {len(stats.notes) - 15} more (see the log file)")


def cmd_search(cfg: Config, args: argparse.Namespace) -> int:
    from tokopedia_scraper.fetchers.base import get_fetcher

    keywords = args.keyword or cfg.keywords
    if not keywords:
        console.print("[red]No keywords: pass --keyword or fill config.yaml[/red]")
        return 1

    console.print(
        f"stage 1 - {len(keywords)} keyword(s), up to "
        f"{args.max_pages or cfg.search.max_pages_per_keyword} pages each"
    )

    with Storage(cfg.storage.db_path) as storage:
        fetcher = get_fetcher(cfg, args.fetcher)
        bar, report = make_progress("search")
        try:
            with bar:
                stats = run_search(
                    cfg,
                    storage,
                    fetcher,
                    keywords,
                    max_pages=args.max_pages,
                    progress=report,
                )
        finally:
            fetcher.close()

    show_stats(stats, "stage 1 - search")
    return 0


def cmd_enrich(cfg: Config, args: argparse.Namespace) -> int:
    from tokopedia_scraper.fetchers.base import get_fetcher

    with Storage(cfg.storage.db_path) as storage:
        pending = storage.stats()["pending_pdp"]
        if not pending:
            console.print("Nothing pending - every product already has a PDP.")
            return 0
        console.print(f"stage 2 - {pending} product(s) pending")

        fetcher = get_fetcher(cfg, args.fetcher)
        bar, report = make_progress("enrich")
        try:
            with bar:
                stats = run_enrich(
                    cfg, storage, fetcher, limit=args.limit, progress=report
                )
        finally:
            fetcher.close()

    show_stats(stats, "stage 2 - product detail")
    return 0


def cmd_images(cfg: Config, args: argparse.Namespace) -> int:
    with Storage(cfg.storage.db_path) as storage:
        bar, report = make_progress("images")
        with bar:
            stats = run_images(cfg, storage, limit=args.limit, progress=report)
    show_stats(stats, "images")
    return 0


def cmd_reparse(cfg: Config, args: argparse.Namespace) -> int:
    with Storage(cfg.storage.db_path) as storage:
        stored = storage.stats()["raw_responses"]
        if not stored:
            console.print("[yellow]No stored raw responses to re-parse.[/yellow]")
            return 1
        console.print(f"re-parsing {stored} stored response(s) - no network")

        bar, report = make_progress("reparse")
        with bar:
            stats = reparse_from_raw(cfg, storage, args.stage, progress=report)

    show_stats(stats, "reparse")
    return 0


def cmd_export(cfg: Config, args: argparse.Namespace) -> int:
    from tokopedia_scraper.pipeline import (
        SLIM_COLUMNS,
        resolve_columns,
        write_dataset_card,
    )

    columns = resolve_columns(SLIM_COLUMNS if args.slim else None, args.ready)
    stem = "products_slim" if args.slim else "products"
    if args.ready:
        stem += "_ready"

    with Storage(cfg.storage.db_path) as storage:
        paths = export_dataset(
            cfg,
            storage,
            args.format,
            columns=columns,
            stem=stem,
            ready_only=args.ready,
            csv_single_line=args.csv_single_line,
        )
        if paths:
            paths.append(write_dataset_card(cfg, storage, columns=columns))
    if not paths:
        console.print("[yellow]Nothing exported - the products table is empty.[/yellow]")
        return 1
    for path in paths:
        console.print(f"  {path}  ({path.stat().st_size:,} bytes)")
    return 0


def cmd_stats(cfg: Config, args: argparse.Namespace) -> int:
    if not cfg.storage.db_path.exists():
        console.print(f"[yellow]No database yet at {cfg.storage.db_path}[/yellow]")
        return 1

    with Storage(cfg.storage.db_path) as storage:
        data = storage.stats()

    table = Table(title=str(cfg.storage.db_path))
    table.add_column("metric")
    table.add_column("value", justify="right")
    for key, value in data.items():
        table.add_row(key.replace("_", " "), f"{value:,}")
    console.print(table)

    total = data["products"]
    if total:
        done = data["pdp_fetched"]
        described = data["with_description"]
        console.print(
            f"\nenriched {done}/{total} ({done / total:.0%}), "
            f"with description {described}/{total} ({described / total:.0%}), "
            f"short descriptions {data['short_description']}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config.yaml")
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="overrides logging.level from config.yaml",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="stage 1: collect product listings")
    search.add_argument(
        "--keyword", action="append", help="repeatable; defaults to config.yaml"
    )
    search.add_argument("--max-pages", type=int, default=None)
    search.add_argument("--fetcher", choices=FETCHER_CHOICES, default=None)
    search.set_defaults(func=cmd_search)

    enrich = sub.add_parser("enrich", help="stage 2: fetch descriptions from PDPs")
    enrich.add_argument("--limit", type=int, default=None)
    enrich.add_argument("--fetcher", choices=FETCHER_CHOICES, default=None)
    enrich.set_defaults(func=cmd_enrich)

    images = sub.add_parser("images", help="download image files")
    images.add_argument("--limit", type=int, default=None)
    images.set_defaults(func=cmd_images)

    reparse = sub.add_parser(
        "reparse",
        help="rebuild the products table from stored raw responses (no network)",
    )
    reparse.add_argument(
        "--stage", nargs="+", choices=["search", "pdp"], default=["search", "pdp"]
    )
    reparse.set_defaults(func=cmd_reparse)

    export = sub.add_parser("export", help="write JSONL / CSV / Parquet")
    export.add_argument(
        "--format",
        nargs="+",
        choices=["jsonl", "csv", "parquet"],
        default=["jsonl", "csv"],
    )
    export.add_argument(
        "--slim",
        action="store_true",
        help=(
            "training-ready fields only (title, price, description, category, "
            "images) -> products_slim.*, leaving products.* untouched"
        ),
    )
    export.add_argument(
        "--ready",
        action="store_true",
        help=(
            "only rows a model can train on: PDP fetched and a non-empty "
            "description. Use this for anything you hand to someone else"
        ),
    )
    export.add_argument(
        "--csv-single-line",
        action="store_true",
        help=(
            "CSV only: collapse newlines inside descriptions so one record is "
            "one line. Quoted newlines are valid CSV, but tools that split on "
            "lines choke on them. Loses paragraph breaks; JSONL keeps them"
        ),
    )
    export.set_defaults(func=cmd_export)

    stats = sub.add_parser("stats", help="dataset summary")
    stats.set_defaults(func=cmd_stats)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        cfg = Config.load(args.config)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    cfg.ensure_dirs()
    setup_logging(args.log_level or cfg.logging.level, cfg.logging.file, force=True)

    try:
        return int(args.func(cfg, args))
    except KeyboardInterrupt:
        console.print(
            "\n[yellow]Interrupted. Progress is saved - re-run to resume.[/yellow]"
        )
        return 130
    except CircuitOpen as exc:
        console.print(f"\n[red]Stopped by the circuit breaker:[/red]\n{exc}")
        return 2
    except MissingCredential as exc:
        console.print(f"\n[red]{exc}[/red]")
        return 1
    except Exception as exc:  # noqa: BLE001 - top-level guard
        # The traceback goes to the log file; the console gets the short version.
        log.exception("unhandled error")
        console.print(f"\n[red]{type(exc).__name__}: {exc}[/red]")
        console.print(f"[dim]full traceback in {cfg.logging.file}[/dim]")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
