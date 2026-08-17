"""Panen kamus merek dan kata jenis barang dari katalog sendiri.

Uji tiga model menunjukkan cacat terakhir pipeline bukan soal kapasitas: menaikkan
VLM dari 4B ke 7B tidak mengurangi merek karangan ("tablet D-Vine, merek iBing").
Merek tercetak di kemasan dan terdaftar di 28 ribu judul milikmu — jadi masalahnya
mengingat, bukan melihat. Kamus ini mengubah menebak jadi mencocokkan.

    python scripts/build_lexicon.py
    python scripts/build_lexicon.py --selfcheck

Keluaran: data_drive/merged/lexicon.json
  merek  kandidat nama merek (dari kolom brand blibli + kata kepala judul)
  jenis  kata jenis barang ("sepatu", "kaos") supaya tidak ikut tersaring
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parent.parent
MERGED = PROJECT / "data_drive" / "merged" / "merged_local.parquet"
BLIBLI = PROJECT / "data_drive" / "blibli" / "products.parquet"
TUJUAN = PROJECT / "data_drive" / "merged" / "lexicon.json"

MIN_MEREK = 3        # merek harus muncul sebagai kata pertama di >=3 produk
MIN_JENIS = 40       # kata jenis muncul di banyak produk
MIN_KATEGORI = 4     # ...dan tersebar di >=4 kategori
MIN_UMUM = 20        # kata dianggap lazim kalau muncul di >=20 produk
RASIO_KEPALA = 0.5   # merek: >=50% kemunculannya sebagai kata pertama judul


def token(teks) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9\.\-]{2,}", str(teks).lower())


def bangun() -> dict:
    df = pd.read_parquet(MERGED)
    judul = df["title"].astype(str)

    # 1. merek eksplisit: kolom brand blibli, satu-satunya sumber berlabel
    merek = set()
    if BLIBLI.exists():
        b = pd.read_parquet(BLIBLI)["brand"].dropna().astype(str).str.strip().str.lower()
        merek |= {m for m in b if 2 < len(m) < 30}

    # 2. sebaran tiap kata: muncul di berapa produk, dan di berapa kategori
    per_kata_produk: dict[str, int] = defaultdict(int)
    per_kata_kategori: dict[str, set] = defaultdict(set)
    kepala: dict[str, int] = defaultdict(int)
    for j, kat in zip(judul, df["kategori_umkm"].astype(str)):
        t = token(j)
        if t:
            kepala[t[0]] += 1
        for w in set(t):
            per_kata_produk[w] += 1
            per_kata_kategori[w].add(kat)

    # kata jenis: sering muncul DAN tersebar lintas kategori -> bukan merek
    jenis = {w for w, n in per_kata_produk.items()
             if n >= MIN_JENIS and len(per_kata_kategori[w]) >= MIN_KATEGORI}

    # kandidat merek: sering jadi kata pertama judul, tapi bukan kata jenis
    # Merek hampir selalu jadi kata PERTAMA judul; kata deskriptif ("gaming",
    # "premium") muncul di mana saja. Tanpa syarat rasio ini, "gaming" ikut
    # terdaftar sebagai merek dan penjaga membuangnya dari judul yang sah.
    merek |= {w for w, n in kepala.items()
              if n >= MIN_MEREK and w not in jenis
              and n / max(per_kata_produk[w], 1) >= RASIO_KEPALA}
    merek -= jenis

    # Kata umum: apa pun yang muncul di >=20 produk. Dipakai penjaga merek untuk
    # membedakan "kata Indonesia biasa" dari "istilah asing yang dikarang".
    # Tanpa daftar ini penjaga membuang kata sah seperti "pesta" dan "jogging".
    umum = {w for w, n in per_kata_produk.items() if n >= MIN_UMUM}
    return {"merek": sorted(merek), "jenis": sorted(jenis), "umum": sorted(umum)}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    lex = bangun()
    TUJUAN.write_text(json.dumps(lex, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"merek : {len(lex['merek']):,} istilah")
    print(f"jenis : {len(lex['jenis']):,} istilah")
    print(f"umum  : {len(lex['umum']):,} istilah")
    print("contoh merek:", ", ".join(lex["merek"][:12]))
    print("contoh jenis:", ", ".join(lex["jenis"][:12]))
    print(f"\n-> {TUJUAN}")


def _selfcheck():
    assert token("SPEEDS Timbangan 040-15") == ["speeds", "timbangan", "040-15"]
    assert token("") == []
    assert token("A B") == []          # kata <3 huruf diabaikan
    print("selfcheck ok")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        main()
