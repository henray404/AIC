#!/usr/bin/env python
"""One-off migration: hash filenames -> <product_id>_<NN>.<ext>.

Images used to be stored under a content hash, which made ownership invisible
as soon as a file left its folder. New downloads already use the labelled name;
this renames the ones already on disk instead of fetching 12 GB again.

    python scripts/rename_images.py --dry-run     # show the plan, touch nothing
    python scripts/rename_images.py               # do it

Safe to re-run: files already carrying the right name are left alone.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from tokopedia_scraper.config import Config  # noqa: E402
from tokopedia_scraper.image_downloader import image_filename  # noqa: E402
from tokopedia_scraper.storage import Storage  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config.yaml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    cfg = Config.load(args.config)
    renamed = already = missing = collided = 0
    products_touched = 0

    with Storage(cfg.storage.db_path) as storage:
        rows = storage.conn.execute(
            "SELECT product_id, local_image_paths, image_urls FROM products "
            "WHERE local_image_paths IS NOT NULL "
            "AND local_image_paths NOT IN ('', '[]')"
        ).fetchall()
        print(f"{len(rows):,} products have downloaded images\n")

        for row in rows:
            product_id = row["product_id"]
            try:
                paths = json.loads(row["local_image_paths"])
                urls = json.loads(row["image_urls"] or "[]")
            except json.JSONDecodeError:
                continue

            new_paths: list[str] = []
            changed = False

            for index, stored in enumerate(paths, start=1):
                old = cfg.root / stored
                # Extension comes from the URL when we still have it, otherwise
                # from the name already on disk.
                url = urls[index - 1] if index - 1 < len(urls) else old.name
                new_name = image_filename(product_id, url, index)
                new = old.parent / new_name

                if old.name == new_name:
                    already += 1
                    new_paths.append(stored)
                    continue

                if not old.exists():
                    missing += 1
                    # If the file is already there under the new name, point the
                    # record at it; otherwise leave the record untouched.
                    if new.exists():
                        new_paths.append(new.relative_to(cfg.root).as_posix())
                        changed = True
                    else:
                        new_paths.append(stored)
                    continue

                if new.exists():
                    collided += 1
                    new_paths.append(new.relative_to(cfg.root).as_posix())
                    changed = True
                    continue

                if not args.dry_run:
                    old.rename(new)
                renamed += 1
                changed = True
                new_paths.append(new.relative_to(cfg.root).as_posix())

            if changed:
                products_touched += 1
                if not args.dry_run:
                    storage.set_local_images(product_id, new_paths)

    verb = "would rename" if args.dry_run else "renamed"
    print(f"{verb:<18}{renamed:>8,}")
    print(f"{'already named':<18}{already:>8,}")
    print(f"{'file missing':<18}{missing:>8,}")
    print(f"{'target existed':<18}{collided:>8,}")
    print(f"{'products updated':<18}{products_touched:>8,}")

    if args.dry_run:
        print("\nDry run — nothing changed. Re-run without --dry-run to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
