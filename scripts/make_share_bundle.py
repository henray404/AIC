#!/usr/bin/env python
"""Pack the CSV, the dataset card and the images into one archive.

    python scripts/make_share_bundle.py                  # everything
    python scripts/make_share_bundle.py --max-images 1   # 1 image/product
    python scripts/make_share_bundle.py --no-images      # CSV only

Stored, not deflated: JPEGs are already compressed, so deflating them costs
minutes and saves almost nothing.

Run `python main.py export --slim --ready --format csv` first — this script
packs whatever is already in data/exports/.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from tokopedia_scraper.config import Config  # noqa: E402

# Sorts 0000000001_02.jpeg after _01 and before _10 — plain string sort would
# put _10 between _01 and _02.
INDEX_RE = re.compile(r"_(\d+)\.[^.]+$")


def image_index(path: Path) -> int:
    match = INDEX_RE.search(path.name)
    return int(match.group(1)) if match else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config.yaml")
    parser.add_argument(
        "--out", type=Path, default=REPO_ROOT / "data" / "share" / "tokopedia_dataset.zip"
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=0,
        help="cap images per product (0 = all). Use 1 for a much smaller archive",
    )
    parser.add_argument("--no-images", action="store_true")
    args = parser.parse_args(argv)

    cfg = Config.load(args.config)
    csv_path = cfg.storage.export_dir / "products_slim_ready.csv"
    jsonl_path = cfg.storage.export_dir / "products_slim_ready.jsonl"
    card_path = cfg.storage.export_dir / "DATASET.md"

    if not csv_path.exists():
        print(
            f"error: {csv_path} not found.\n"
            f"Run: python main.py export --slim --ready "
            f"--csv-single-line --format csv jsonl",
            file=sys.stderr,
        )
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)

    # data/images/ holds every product that reached stage 2, but the ready-only
    # CSV drops the ones with no usable description. Shipping their images would
    # put folders in the archive that no row points at.
    csv.field_size_limit(10_000_000)
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        wanted = {row["product_id"] for row in csv.DictReader(handle)}

    # Grouped by product folder so --max-images keeps the first N of each
    # product rather than the first N of the whole set.
    per_product: dict[str, list[Path]] = {}
    if not args.no_images and cfg.images.dir.exists():
        for folder in cfg.images.dir.iterdir():
            if not folder.is_dir() or folder.name not in wanted:
                continue
            files = sorted((f for f in folder.iterdir() if f.is_file()), key=image_index)
            if args.max_images > 0:
                files = files[: args.max_images]
            if files:
                per_product[folder.name] = files

    total_images = sum(len(v) for v in per_product.values())
    total_bytes = sum(f.stat().st_size for v in per_product.values() for f in v)
    print(f"csv     : {csv_path.name}  ({csv_path.stat().st_size / 1024**2:.1f} MB)")
    print(f"baris   : {len(wanted):,}")
    print(f"produk  : {len(per_product):,} punya gambar")
    print(f"gambar  : {total_images:,}  ({total_bytes / 1024**3:.2f} GB)")
    print(f"tujuan  : {args.out}\n", flush=True)

    written = 0
    with zipfile.ZipFile(
        args.out, "w", compression=zipfile.ZIP_STORED, allowZip64=True
    ) as archive:
        archive.write(csv_path, "products.csv")
        # The JSONL keeps the descriptions exactly as the sellers wrote them.
        # The CSV is flattened to one line per record for tooling that cannot
        # cope with quoted newlines, so paragraph breaks only survive here.
        if jsonl_path.exists():
            archive.write(jsonl_path, "products.jsonl")
        if card_path.exists():
            archive.write(card_path, "DATASET.md")

        for product_id, files in sorted(per_product.items()):
            for file in files:
                archive.write(file, f"images/{product_id}/{file.name}")
                written += 1
                if written % 10_000 == 0:
                    print(f"  {written:,}/{total_images:,} gambar...", flush=True)

    size = args.out.stat().st_size
    print(f"\nselesai: {args.out}")
    print(f"  {written:,} gambar + products.csv + products.jsonl + DATASET.md")
    print(f"  {size / 1024**3:.2f} GB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
