"""Susun input terstruktur untuk model teks kecil (deskripsi singkat -> judul + deskripsi).

Bedanya dengan `build_train_pairs.py`: di sana input adalah foto. Di sini input
adalah beberapa fakta yang realistis diketik penjual — merek, jenis barang,
ukuran, kategori, harga — diekstrak dari judul memakai `lexicon.json`.

Labelnya TIDAK diambil dari kolom `description`. Cuma 34% deskripsi mentah yang
lolos filter kebersihan dasar, dan yang lolos pun masih penuh emoji dan basa-basi
lapak. Label dihasilkan terpisah oleh `retrieve_pipeline.py` sebagai guru.

    python scripts/build_text_pairs.py
    python scripts/build_text_pairs.py --n 10000
    python scripts/build_text_pairs.py --selfcheck

Keluaran `data_drive/merged/text_pairs.parquet` — kolom `fakta` (dict) dan
`input` (string siap pakai), plus `product_id` untuk disambung ke label guru.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parent.parent
SUMBER = PROJECT / "data_drive" / "merged" / "merged.parquet"
LEKSIKON = PROJECT / "data_drive" / "merged" / "lexicon.json"
TUJUAN = PROJECT / "data_drive" / "merged" / "text_pairs.parquet"

# angka + satuan yang benar-benar menggambarkan barang; "2" telanjang dibuang
# karena hampir selalu bagian nama varian, bukan ukuran.
UKURAN = re.compile(
    r"(?i)\b(\d+(?:[.,]\d+)?\s*(?:gr?|kg|ml|lt?r?|liter|w(?:att)?|cm|mm|m|inch|"
    r"in|pcs|pack|sachet|tablet|kapsul|butir|lembar|meter)\b)")
BAJU = re.compile(r"(?i)\b(all\s*size|[SML]|XS|XL|XXL|XXXL|[23]XL)\b")
BUKAN_KATA = re.compile(r"^[\d.,/-]+$")
# token promo/SEO tidak pernah jadi jenis barang
PROMO = {"baru", "new", "termurah", "murah", "promo", "diskon", "sale", "cod", "ready",
         "readystock", "stok", "grosir", "ecer", "original", "ori", "free", "gratis",
         "bestseller", "terlaris", "viral", "limited", "hot", "flash", "garansi",
         "resmi", "terbaik", "berkualitas", "kualitas", "premium", "asli", "paket"}
SIMBOL = re.compile(r"[^\w\s.\-/&+,']", flags=re.UNICODE)


def _kata(judul: str) -> list[str]:
    t = SIMBOL.sub(" ", str(judul))
    return [w for w in t.split() if w]


def _rentang_merek(kata, rendah, lex) -> tuple[int, int]:
    """Cari petak merek di kepala judul. Balikan (mulai, selesai) eksklusif.

    Leksikon hanya memuat satu kata per merek, padahal merek nyata sering
    beberapa kata ("La Roche Posay"). Petaknya dilebarkan ke kiri dan kanan
    selama tetangganya bukan kosakata katalog umum — kata yang tidak dikenal
    katalog di sebelah merek hampir selalu bagian dari merek itu.
    """
    for i in range(min(4, len(kata))):
        if rendah[i] in lex["merek"] and not BUKAN_KATA.match(rendah[i]):
            a, b = i, i + 1
            while a > 0 and rendah[a - 1] not in lex["umum"] and not BUKAN_KATA.match(rendah[a - 1]):
                a -= 1
            while (b < len(kata) and b < a + 3 and rendah[b] not in lex["umum"]
                   and not BUKAN_KATA.match(rendah[b])):
                b += 1
            return a, b
    return 0, 0


def ekstrak(judul: str, brand, kategori, harga, lex: dict) -> dict:
    """Tarik fakta yang wajar diketik penjual. Nilai kosong dibuang, bukan diisi '-'."""
    kata = _kata(judul)
    rendah = [w.lower() for w in kata]

    # Merek: kolom `brand` cuma terisi di blibli (31%); sisanya dari leksikon.
    # blibli mengisi 554 baris dengan "no brand" — itu bukan merek, itu ketiadaan merek
    KOSONG = {"nan", "none", "", "no brand", "nobrand", "oem", "tanpa merek", "-"}
    merek = str(brand).strip() if brand and str(brand).lower().strip() not in KOSONG else ""
    a, b = _rentang_merek(kata, rendah, lex)
    if not merek and b > a:
        merek = " ".join(kata[a:b])
    tokens_merek = set(rendah[a:b]) | {w.lower() for w in merek.split()}

    # Jenis: judul Indonesia head-initial, jadi kata pertama setelah merek.
    # Syaratnya ada di kosakata katalog `umum` — itu yang memisahkan jenis
    # nyata ("sabun", "sepatu") dari sisa nama merek ("posay", "infnix").
    # ponytail: heuristik posisi, bukan pengurai. Meleset pada judul yang
    # dibuka nama merek tak dikenal ("Sugar Bubble") atau kata tempat ("Korea
    # Eundan") — sekitar 1 dari 10. Kalau perlu lebih tajam, ganti dengan
    # pengurai judul terlatih atau daftar tipe produk yang dikurasi tangan.
    jenis = ""
    for w, r in zip(kata, rendah):
        if r in tokens_merek or r in PROMO or BUKAN_KATA.match(r) or len(w) < 3:
            continue
        if r in lex["umum"] and r not in lex["merek"]:
            jenis = w
            break

    ukuran = UKURAN.search(judul)
    ukuran = re.sub(r"\s+", "", ukuran.group(1)) if ukuran else ""
    if not ukuran:
        m = BAJU.search(judul)
        ukuran = m.group(1).upper() if m else ""

    fakta = {"jenis": jenis, "merek": merek, "ukuran": ukuran,
             "kategori": kategori if kategori and kategori != "lainnya" else "",
             "harga": int(harga) if harga and harga > 0 else 0}
    return {k: v for k, v in fakta.items() if v}


def jadi_input(fakta: dict) -> str:
    return " | ".join(f"{k}: {v}" for k, v in fakta.items())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=10000,
                    help="ukuran sampel akhir; 0 = pakai semua baris")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    lex = json.loads(LEKSIKON.read_text(encoding="utf-8"))
    lex = {k: set(v) for k, v in lex.items()}
    df = pd.read_parquet(SUMBER)
    print(f"{len(df):,} baris masuk")

    fakta = [
        ekstrak(r.title, r.brand, r.kategori_umkm, r.price, lex)
        for r in df.itertuples()
    ]
    df["fakta"] = fakta
    df["n_fakta"] = [len(f) for f in fakta]

    # Butuh minimal jenis + satu fakta lain; kalau tidak, input-nya terlalu
    # tipis untuk dinilai adil — model tidak diberi apa pun untuk dikerjakan.
    layak = df["fakta"].apply(lambda f: "jenis" in f) & (df["n_fakta"] >= 2)
    print(f"{layak.sum():,} baris punya fakta cukup ({layak.mean():.1%})")
    df = df[layak].copy()

    if args.n and args.n < len(df):
        # stratifikasi per platform x kategori supaya bauran uji tidak melenceng
        frac = args.n / len(df)
        # ambil indeksnya saja: groupby.apply pandas 3 membuang kolom kunci
        idx = (df.groupby(["source", "kategori_umkm"])
                 .apply(lambda g: g.sample(max(1, round(len(g) * frac)),
                                           random_state=args.seed).index.to_list()))
        df = df.loc[[i for lst in idx for i in lst]]
        print(f"sampel terstratifikasi -> {len(df):,} baris")

    df["input"] = df["fakta"].apply(jadi_input)
    kolom = ["product_id", "source", "kategori_umkm", "price", "title", "fakta", "input"]
    out = df[kolom].copy()
    out["fakta"] = out["fakta"].apply(json.dumps)   # parquet tidak suka dict campur
    out.to_parquet(TUJUAN, index=False)

    print("\ncakupan tiap fakta:")
    for k in ("jenis", "merek", "ukuran", "kategori", "harga"):
        ada = df["fakta"].apply(lambda f: k in f).mean()
        print(f"  {k:9} {ada:6.1%}")
    print("\ncontoh:")
    for _, r in out.sample(min(5, len(out)), random_state=1).iterrows():
        print(f"  in  : {r['input']}")
        print(f"  asli: {r['title'][:80]}")
    print(f"\n-> {TUJUAN}  ({len(out):,} baris)")


def _selfcheck():
    lex = {"merek": {"philips", "verve", "roche", "sunlight"},
           "jenis": set(),
           "umum": {"airfryer", "dress", "sabun", "cuci", "piring", "sepatu",
                    "keripik", "singkong", "toner", "acne", "mini", "watt", "low"}}
    f = ekstrak("Philips Airfryer Low Watt 500W", None, "lainnya", 450000, lex)
    assert f == {"jenis": "Airfryer", "merek": "Philips",
                 "ukuran": "500W", "harga": 450000}, f
    # merek dari kolom menang atas tebakan leksikon
    f = ekstrak("Dress Mini Coquette", "Verve", "fashion_perawatan", 0, lex)
    assert f["merek"] == "Verve" and f["jenis"] == "Dress" and "harga" not in f, f
    # jenis = kata pertama setelah merek, bukan kata leksikon pertama yang kebetulan cocok
    f = ekstrak("Sunlight Sabun Cuci Piring Cair 600 mL", None, None, 13100, lex)
    assert f["merek"] == "Sunlight" and f["jenis"] == "Sabun" and f["ukuran"] == "600mL", f
    # merek beberapa kata dilebarkan; sisa namanya tidak bocor jadi jenis
    f = ekstrak("LA ROCHE POSAY EFFACLAR Acne Toner 200ml", None, None, 621000, lex)
    assert f["merek"] == "LA ROCHE POSAY" and f["jenis"] == "Acne", f
    # tanpa merek dikenal, jenis tetap kata kepala
    f = ekstrak("Keripik Singkong Pedas 250gr", None, "camilan_olahan", 15000, lex)
    assert f["jenis"] == "Keripik" and f["ukuran"] == "250gr" and "merek" not in f, f
    # kata promo tidak boleh jadi jenis
    f = ekstrak("Original Sepatu Sneakers Pria", None, None, 0, lex)
    assert f["jenis"] == "Sepatu", f
    # judul kosong tidak boleh meledak
    assert ekstrak("", None, None, 0, lex) == {}
    print("selfcheck ok")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        main()
