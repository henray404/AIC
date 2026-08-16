"""Ubah path gambar Colab di `merged.parquet` jadi path lokal yang benar-benar ada.

Path di dataset gabungan menunjuk ke `/content/drive/MyDrive/IAC/...` (mesin Colab).
Skrip ini memetakannya ke folder lokal, memeriksa berkasnya satu per satu, lalu
menulis salinan yang siap diolah:

    python scripts/localize_merged.py
    python scripts/localize_merged.py --keep-missing   # simpan path hilang, jangan dibuang
    python scripts/localize_merged.py --selfcheck      # uji pemetaan path saja

Keluaran `merged_local.parquet` menambah dua kolom:

    n_gambar_lokal      jumlah berkas yang benar-benar ada di mesin ini
    gambar_hilang       jumlah path yang tidak ketemu berkasnya

Baris tidak pernah dibuang. Produk tanpa gambar tetap ada dengan `n_gambar_lokal = 0`,
supaya model teks tetap bisa memakainya.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parent.parent
DRIVE = PROJECT / "data_drive"
SUMBER = DRIVE / "merged" / "merged.parquet"
TUJUAN = DRIVE / "merged" / "merged_local.parquet"
LAPORAN = DRIVE / "merged" / "path_report.json"

# akar Colab -> akar lokal
ROOT_MAP = {
    "/content/drive/MyDrive/IAC/blibli": DRIVE / "blibli",
    "/content/drive/MyDrive/IAC/data/external/tokopedia2025": DRIVE / "data" / "external" / "tokopedia2025",
    # tokopedia tidak ikut diunduh dari Drive: gambarnya sudah ada di repo ini
    "/content/drive/MyDrive/IAC/tokopedia_dataset": PROJECT / "data",
}


def remap(p: str) -> Path | None:
    p = str(p).replace("\\", "/")
    for akar, lokal in ROOT_MAP.items():
        akar = akar.rstrip("/")
        if p.startswith(akar + "/"):
            return Path(lokal) / p[len(akar) + 1:]
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep-missing", action="store_true",
                    help="tetap tulis path yang berkasnya tidak ada")
    ap.add_argument("--sumber", default=str(SUMBER))
    args = ap.parse_args()

    src = Path(args.sumber)
    if not src.exists():
        raise SystemExit(f"tidak ada {src} — jalankan scripts/fetch_drive_iac.py dulu")

    df = pd.read_parquet(src)
    print(f"{src.name}: {len(df):,} baris")

    ada_cache: dict[str, bool] = {}   # path sama bisa muncul di banyak baris

    def periksa(paths):
        if not isinstance(paths, (list, tuple, np.ndarray)):
            return [], 0, 0
        hidup, hilang = [], 0
        for p in paths:
            lokal = remap(p)
            if lokal is None:
                hilang += 1
                if args.keep_missing:
                    hidup.append(str(p))
                continue
            kunci = str(lokal)
            if kunci not in ada_cache:
                ada_cache[kunci] = lokal.exists()
            if ada_cache[kunci]:
                hidup.append(kunci)
            else:
                hilang += 1
                if args.keep_missing:
                    hidup.append(kunci)
        n_ada = len(hidup) - (hilang if args.keep_missing else 0)
        return hidup, n_ada, hilang

    hasil = [periksa(v) for v in df["local_image_paths"]]
    df["local_image_paths"] = [h[0] for h in hasil]
    df["n_gambar_lokal"] = [h[1] for h in hasil]
    df["gambar_hilang"] = [h[2] for h in hasil]

    ringkas = df.groupby("source").agg(
        baris=("product_id", "size"),
        gambar_ada=("n_gambar_lokal", "sum"),
        gambar_hilang=("gambar_hilang", "sum"),
        baris_tanpa_gambar=("n_gambar_lokal", lambda s: int((s == 0).sum())),
    )
    ringkas["persen_baris_bergambar"] = (
        100 * (1 - ringkas["baris_tanpa_gambar"] / ringkas["baris"])).round(1)
    print()
    print(ringkas.to_string())

    df.to_parquet(TUJUAN, index=False)
    print(f"\n-> {TUJUAN}")

    LAPORAN.write_text(json.dumps({
        "sumber": str(src),
        "keluaran": str(TUJUAN),
        "waktu": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "keep_missing": bool(args.keep_missing),
        "per_sumber": {k: {kk: int(vv) for kk, vv in v.items()}
                       for k, v in ringkas.to_dict(orient="index").items()},
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print("->", LAPORAN)


def _selfcheck():
    assert remap("/content/drive/MyDrive/IAC/blibli/images/A/A_01.webp") == \
        DRIVE / "blibli" / "images" / "A" / "A_01.webp"
    assert remap("/content/drive/MyDrive/IAC/data/external/tokopedia2025/images/x~.jpeg") == \
        DRIVE / "data" / "external" / "tokopedia2025" / "images" / "x~.jpeg"
    assert remap("/content/drive/MyDrive/IAC/tokopedia_dataset/images/1/1_01.jpeg") == \
        PROJECT / "data" / "images" / "1" / "1_01.jpeg"
    assert remap("/tidak/dikenal/x.jpg") is None
    print("selfcheck ok")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        main()
