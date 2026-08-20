"""Turunkan profil gaya listing per platform dari data nyata.

Judul yang bagus di Tokopedia belum tentu bagus di blibli: judul blibli median
9 kata, Tokopedia 15, Shopee 11 dan gemar tanda "/". Harga pun berbeda tajam —
fashion di blibli median Rp105.000 lawan Rp35.562 di Tokopedia untuk kategori
yang sama. Profil ini yang membuat satu foto bisa menghasilkan listing berbeda
untuk tiap platform, tanpa melatih model apa pun.

    python scripts/build_platform_profiles.py
    python scripts/build_platform_profiles.py --selfcheck

Keluaran: data_drive/merged/platform_profiles.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parent.parent
DRIVE = PROJECT / "data_drive"
MERGED = DRIVE / "merged" / "merged_local.parquet"
SHOPEE = DRIVE / "data" / "external" / "shopee" / "data_products_id_small.csv"
LISTINGS = DRIVE / "data" / "external" / "tokopedia_listings" / "produk_tokopedia.csv"
TUJUAN = DRIVE / "merged" / "platform_profiles.json"

STOP = {"dan", "untuk", "yang", "dengan", "atau", "the", "for", "with", "pcs",
        "set", "isi", "pria", "wanita", "anak", "size", "all", "free", "new"}
MIN_HITUNG_KOSAKATA = 5
TOP_KOSAKATA = 12


def buang_varian(judul: str) -> str:
    """Ekor setelah ' - ' pada judul Tokopedia adalah varian dari PDP.

    Ditempelkan oleh scraper ini sendiri ("HITAM, M", "Black", "1 PCS"), bukan
    kebiasaan penjual. Tanpa dibuang, 83,9% judul Tokopedia tampak memakai
    pemisah ' - ' dan profilnya jadi mengajarkan artefak kita sendiri.
    """
    return judul.rsplit(" - ", 1)[0] if " - " in judul else judul


def token(teks) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", str(teks).lower())
            if len(w) >= 3 and w not in STOP]


def profil_judul(judul: pd.Series) -> dict:
    j = judul.astype(str)
    j = j[j.str.strip() != ""]
    kata = j.str.split().str.len()
    caps = j.map(lambda s: any(len(w) >= 4 and w.isupper() and w.isalpha() for w in s.split()))
    return {
        "median_char": int(j.str.len().median()),
        "median_kata": int(kata.median()),
        "p90_kata": int(kata.quantile(0.9)),
        "target_kata": [int(kata.quantile(0.25)), int(kata.quantile(0.75))],
        "pct_allcaps": round(100 * float(caps.mean()), 1),
        "pct_kurung": round(100 * float(j.str.contains(r"[\[\(]").mean()), 1),
        "pct_garis_miring": round(100 * float(j.str.contains("/").mean()), 1),
    }


def sebaran_harga(harga: pd.Series) -> dict | None:
    h = pd.to_numeric(harga, errors="coerce").dropna()
    h = h[h > 0]
    if len(h) < 20:
        return None
    return {"p25": int(h.quantile(0.25)), "median": int(h.median()),
            "p75": int(h.quantile(0.75)), "n": int(len(h))}


def kosakata_khas(judul_platform: pd.Series, judul_semua: pd.Series) -> list[str]:
    """Kata yang lebih sering muncul di platform ini dibanding rata-rata.

    Frekuensi mentah hanya akan mengembalikan "sepatu, kaos, jam" di semua
    platform. Yang dicari justru kata yang membedakan.
    """
    def hitung(s):
        c: dict[str, int] = defaultdict(int)
        for j in s:
            for w in set(token(j)):
                c[w] += 1
        return c

    ini, semua = hitung(judul_platform), hitung(judul_semua)
    n_ini, n_semua = max(len(judul_platform), 1), max(len(judul_semua), 1)
    skor = {}
    for w, c in ini.items():
        if c < MIN_HITUNG_KOSAKATA:
            continue
        skor[w] = (c / n_ini) / (semua.get(w, 0) / n_semua + 1e-9)
    return [w for w, _ in sorted(skor.items(), key=lambda x: -x[1])[:TOP_KOSAKATA]]


def bangun() -> dict:
    if not MERGED.exists():
        raise SystemExit(f"tidak ada {MERGED} — jalankan scripts/localize_merged.py dulu")

    df = pd.read_parquet(MERGED)
    df["judul"] = df["title"].astype(str)
    df.loc[df["source"] == "tokopedia", "judul"] = (
        df.loc[df["source"] == "tokopedia", "judul"].map(buang_varian))

    semua_judul = pd.Series(list(df["judul"]))
    profil: dict[str, dict] = {}

    for src, g in df.groupby("source"):
        desk = g["description"].astype("object").fillna("").astype(str)
        desk_isi = desk[desk.str.len() > 0]
        harga_kat, kosa_kat = {}, {}
        for kat, gk in g.groupby("kategori_umkm"):
            h = sebaran_harga(gk["price"])
            if h:
                harga_kat[str(kat)] = h
            if len(gk) >= 30:
                kosa_kat[str(kat)] = kosakata_khas(gk["judul"], semua_judul)
        profil[str(src)] = {
            "n": int(len(g)),
            "sumber": "hasil scraping sendiri" if src == "tokopedia" else "ekspor mitra",
            "judul": profil_judul(g["judul"]),
            "deskripsi": {
                "median_char": int(desk_isi.str.len().median()) if len(desk_isi) else None,
                "pct_ada_prosa": round(100 * len(desk_isi) / len(g), 1),
            },
            "harga_per_kategori": harga_kat,
            "kosakata_khas": kosa_kat,
            "catatan": [],
        }

    if "tokopedia" in profil:
        profil["tokopedia"]["catatan"].append(
            "Ekor ' - varian' dibuang sebelum dihitung; itu tempelan scraper, "
            "bukan gaya penjual.")

    if SHOPEE.exists():
        sh = pd.read_csv(SHOPEE)
        kosa = {}
        for kat, gk in sh.groupby("main_category"):
            if len(gk) >= 200:
                kosa[str(kat)] = kosakata_khas(gk["name"].astype(str), semua_judul)
        profil["shopee"] = {
            "n": int(len(sh)),
            "sumber": "ekspor mitra (judul saja)",
            "judul": profil_judul(sh["name"]),
            "deskripsi": {"median_char": None, "pct_ada_prosa": 0.0},
            "harga_per_kategori": {},
            "kosakata_khas": kosa,
            "catatan": ["Tanpa harga dan tanpa deskripsi — hanya bisa menyarankan judul."],
        }

    if LISTINGS.exists():
        tl = pd.read_csv(LISTINGS)
        h = sebaran_harga(tl["Harga (IDR)"])
        profil["tokopedia_listings"] = {
            "n": int(len(tl)),
            "sumber": "ekspor mitra (halaman listing)",
            "judul": profil_judul(tl["Nama Produk"]),
            "deskripsi": {"median_char": None, "pct_ada_prosa": 0.0},
            "harga_per_kategori": {"SEMUA": h} if h else {},
            "kosakata_khas": {},
            "catatan": [
                "Platform sama dengan 'tokopedia' tapi profil judulnya berbeda jauh "
                "karena diambil dari halaman listing, bukan halaman produk. "
                "Pilih salah satu, jangan digabung.",
            ],
        }
    return profil


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()

    profil = bangun()
    TUJUAN.write_text(json.dumps(profil, indent=2, ensure_ascii=False), encoding="utf-8")

    baris = [{
        "platform": nama, "n": p["n"],
        "median_kata": p["judul"]["median_kata"],
        "target_kata": f"{p['judul']['target_kata'][0]}-{p['judul']['target_kata'][1]}",
        "ALLCAPS%": p["judul"]["pct_allcaps"],
        "miring%": p["judul"]["pct_garis_miring"],
        "desk_char": p["deskripsi"]["median_char"],
        "kategori_berharga": len(p["harga_per_kategori"]),
    } for nama, p in profil.items()]
    print(pd.DataFrame(baris).to_string(index=False))
    print(f"\n-> {TUJUAN}")


def _selfcheck():
    assert buang_varian("Sepatu Lari Pria - HITAM, M") == "Sepatu Lari Pria"
    assert buang_varian("Minyak Goreng 2 Liter") == "Minyak Goreng 2 Liter"
    assert buang_varian("A - B - Black") == "A - B"
    j = pd.Series(["Sepatu Lari Pria Hitam", "KAOS POLOS PREMIUM", "Tas (Import) Wanita"])
    p = profil_judul(j)
    assert p["median_kata"] == 3 and p["pct_allcaps"] > 0 and p["pct_kurung"] > 0
    assert sebaran_harga(pd.Series([1] * 5)) is None          # sampel terlalu kecil
    assert sebaran_harga(pd.Series(range(1, 101)))["median"] == 50
    khas = kosakata_khas(pd.Series(["kopi arabika gayo"] * 6),
                         pd.Series(["sepatu lari"] * 100 + ["kopi arabika gayo"] * 6))
    assert "arabika" in khas
    print("selfcheck ok")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        main()
