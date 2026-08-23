"""Siapkan pasangan latih gambar -> teks tergrounding.

Targetnya **judul yang sudah dibersihkan**, bukan deskripsi: judul berisi jenis
produk, merek, varian, dan ukuran — hampir semuanya terlihat di foto. Deskripsi
justru penuh spesifikasi yang tidak terlihat (berat, garansi, isi karton).

    python scripts/build_train_pairs.py
    python scripts/build_train_pairs.py --selfcheck

Keluaran `data_drive/merged/train_pairs.parquet`, satu baris per produk bergambar.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parent.parent
SUMBER = PROJECT / "data_drive" / "merged" / "merged_local.parquet"
DB = PROJECT / "data" / "products.db"
TUJUAN = PROJECT / "data_drive" / "merged" / "train_pairs.parquet"

# token promo/SEO yang tidak menggambarkan bendanya
PROMO = {
    "baru", "new", "termurah", "murah", "promo", "diskon", "sale", "cod",
    "ready", "readystock", "stok", "grosir", "ecer", "original", "ori",
    "free", "gratis", "bestseller", "terlaris", "viral", "limited", "hot",
    "flash", "garansi", "resmi", "terbaik", "berkualitas", "kualitas", "premium",
}
KURUNG = re.compile(r"[\[\(\{][^\]\)\}]{0,40}[\]\)\}]")
SIMBOL = re.compile(r"[^\w\s\.\-/&%+,']", flags=re.UNICODE)
SPASI = re.compile(r"\s+")
MAKS_KATA = 14          # ekor di atas ini hampir selalu keyword stuffing


def clean_title(judul: str) -> str:
    """Buang promo, kurung, simbol, ALL CAPS, dan ekor keyword-stuffing."""
    if not judul:
        return ""
    t = KURUNG.sub(" ", str(judul))
    t = SIMBOL.sub(" ", t)
    t = SPASI.sub(" ", t).strip()

    kata = []
    for w in t.split():
        # ALL CAPS panjang -> Title Case, biar model tidak belajar berteriak.
        # isalpha() menjaga satuan dan kode varian: 500W, 12GB, XL tetap utuh.
        if len(w) >= 4 and w.isupper() and w.isalpha():
            w = w.capitalize()
        if w.lower().strip(".,-") in PROMO:
            continue
        kata.append(w)

    kata = kata[:MAKS_KATA]
    return " ".join(kata).strip(" .,-")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-kata", type=int, default=3,
                    help="buang baris yang judul bersihnya lebih pendek dari ini")
    args = ap.parse_args()

    if not SUMBER.exists():
        raise SystemExit(f"tidak ada {SUMBER} — jalankan scripts/localize_merged.py dulu")

    df = pd.read_parquet(SUMBER)
    df = df[df["n_gambar_lokal"] > 0].copy()
    print(f"{len(df):,} baris bergambar")

    df["gambar"] = [p[0] for p in df["local_image_paths"]]
    df["title_raw"] = df["title"].astype(str)
    df["title_bersih"] = [clean_title(t) for t in df["title_raw"]]
    df["n_kata_judul"] = df["title_bersih"].str.split().str.len()

    # specs + sinyal penjualan hanya ada di database tokopedia lokal
    if DB.exists():
        con = sqlite3.connect(DB)
        extra = pd.read_sql(
            "select product_id as pid, specs, sold_count, rating, review_count from products", con)
        con.close()
        extra["pid"] = extra["pid"].astype(str)
        df["pid"] = df["product_id_asli"].astype(str)
        df = df.merge(extra, on="pid", how="left", suffixes=("", "_db"))
        print(f"specs tersambung untuk {int(df['specs'].notna().sum()):,} baris")
    else:
        df["specs"] = None
        print(f"lewati specs — {DB} tidak ada")

    sebelum = len(df)
    df = df[df["n_kata_judul"] >= args.min_kata]
    print(f"buang {sebelum - len(df):,} baris berjudul terlalu pendek setelah dibersihkan")

    kolom = ["product_id", "source", "gambar", "title_raw", "title_bersih", "n_kata_judul",
             "kategori_umkm", "kategori_asal", "price", "specs", "sold_count",
             "rating", "review_count", "n_gambar_lokal", "url"]
    out = df[[c for c in kolom if c in df.columns]]
    out.to_parquet(TUJUAN, index=False)

    print()
    print(out.groupby("source").agg(
        baris=("product_id", "size"),
        median_kata_judul=("n_kata_judul", "median"),
        ada_specs=("specs", lambda s: int(s.notna().sum())),
    ).to_string())
    print()
    print("contoh pembersihan judul:")
    for _, r in out.sample(min(5, len(out)), random_state=0).iterrows():
        print("  -", r["title_raw"][:90])
        print("   ->", r["title_bersih"])
    print(f"\n-> {TUJUAN}  ({len(out):,} baris)")


def _selfcheck():
    kasus = [
        ("BARU! Philips Airfryer Low Watt 500W [GARANSI RESMI] TERMURAH",
         "Philips Airfryer Low Watt 500W"),
        ("Minyak Goreng Filma 2 Liter (Promo)", "Minyak Goreng Filma 2 Liter"),
        ("", ""),
    ]
    for masuk, harap in kasus:
        keluar = clean_title(masuk)
        assert keluar == harap, f"{masuk!r} -> {keluar!r}, diharap {harap!r}"
    panjang = clean_title(" ".join(f"kata{i}" for i in range(30)))
    assert len(panjang.split()) == MAKS_KATA
    print("selfcheck ok")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        main()
