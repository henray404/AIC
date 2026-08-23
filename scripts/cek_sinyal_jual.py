"""Ukur cakupan sinyal penjualan (`sold_count`, `rating`, `review_count`) di dataset gabungan.

Latar: kolom-kolom ini ADA di skema `merged.parquet` tapi kosong untuk seluruh
18.443 baris tokopedia, karena ekspornya slim 8 kolom — bukan hilang saat merge
(lihat `docs/DATASET.md` §"tokopedia_dataset"). Aslinya masih utuh di
`data/products.db`, jadi ini pekerjaan JOIN, bukan scraping ulang.

Skrip ini menjawab satu pertanyaan keputusan: **setelah join, berapa persen dari
28.443 baris benar-benar punya angka terjual, dan berapa yang eksak vs bucket?**
Angka itu yang menentukan apakah sinyal penjualan layak jadi dasar penentuan
posisi harga (menggantikan `MARGIN_DEFAULT`) atau cuma pelengkap.

    python scripts/cek_sinyal_jual.py              # ukur + tulis hasil join
    python scripts/cek_sinyal_jual.py --tanpa-tulis  # ukur saja
    python scripts/cek_sinyal_jual.py --selfcheck    # uji logika pada data sintetis

Keluaran:
    data_drive/merged/merged_sinyal.parquet   merged + kolom sinyal terisi
    data_drive/merged/sinyal_report.json      angka cakupan untuk dikutip di paper

Catatan penting soal `sold_count` — jangan diperlakukan sebagai permintaan:
  - angkanya KUMULATIF seumur listing, bukan laju; tanpa umur listing, dua produk
    tidak sebanding;
  - di stage 1 nilainya DIBUCKET ("750+ terjual", lihat `parsers.py:123`). Hanya
    baris `pdp_fetched = 1` yang eksak;
  - harga dan kuantitas yang teramati adalah titik keseimbangan, bukan kurva
    permintaan. Regresi naif terjual-atas-harga menghasilkan estimasi bias.
Yang sah diklaim: asosiasi antara posisi harga relatif dan volume terjual.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parent.parent
SUMBER = PROJECT / "data_drive" / "merged" / "merged_local.parquet"
DB = PROJECT / "data" / "products.db"
TUJUAN = PROJECT / "data_drive" / "merged" / "merged_sinyal.parquet"
LAPORAN = PROJECT / "data_drive" / "merged" / "sinyal_report.json"

SINYAL = ["sold_count", "rating", "review_count"]

# Ambang keputusan. Di bawah ini sinyal penjualan tidak cukup tebal untuk jadi
# dasar penentuan posisi harga; ia turun jadi fitur pelengkap.
AMBANG_LAYAK = 0.40


def gabung_sinyal(df: pd.DataFrame, extra: pd.DataFrame,
                  sumber_db: str = "tokopedia") -> tuple[pd.DataFrame, int]:
    """Isi kolom sinyal yang kosong dari tabel `products`, jangan timpa yang sudah ada.

    Join dibatasi ke baris ber-`source == sumber_db`. Alasannya bukan kerapian:
    `products.db` hanya berisi produk tokopedia, sementara `product_id_asli`
    blibli hidup di ruang ID yang berbeda dan bisa bertabrakan secara numerik.
    Tanpa batas ini, baris blibli bisa mewarisi `pdp_fetched` — bahkan nilai
    sinyal — milik produk tokopedia yang kebetulan ber-ID sama.

    Baris blibli dan tokopedia2025 yang sudah membawa nilainya sendiri dibiarkan
    apa adanya. Returns (df, n_terisi).
    """
    df = df.copy()
    for kol in SINYAL:
        if kol not in df.columns:
            df[kol] = pd.NA
    # Menandai asal nilai. Tanpa ini, "eksak" tidak bisa dibedakan dari
    # "tidak diketahui": pdp_fetched hanya bermakna untuk nilai dari products.db.
    df["sinyal_dari_db"] = False
    df["pdp_fetched"] = pd.NA

    extra = extra.copy()
    extra["_pid"] = extra["_pid"].astype(str)
    extra = extra.drop_duplicates("_pid", keep="first").set_index("_pid")

    boleh = df["source"].astype(str).eq(sumber_db) if "source" in df.columns else \
        pd.Series(True, index=df.index)
    pid = df["product_id_asli"].astype(str).where(boleh)
    ketemu = boleh & pid.isin(extra.index)

    sebelum = int(df["sold_count"].notna().sum())
    for kol in SINYAL:
        if kol not in extra.columns:
            continue
        # Nilai lama menang; hanya sel kosong yang diisi.
        kosong = ketemu & df[kol].isna()
        df.loc[kosong, kol] = pid[kosong].map(extra[kol])
    if "pdp_fetched" in extra.columns:
        df.loc[ketemu, "pdp_fetched"] = pid[ketemu].map(extra["pdp_fetched"])
    df.loc[ketemu, "sinyal_dari_db"] = True

    sesudah = int(df["sold_count"].notna().sum())
    return df, sesudah - sebelum


def ringkas(df: pd.DataFrame) -> dict:
    """Hitung angka cakupan yang jadi dasar keputusan."""
    n = len(df)
    harga = pd.to_numeric(df.get("price"), errors="coerce")
    terjual = pd.to_numeric(df.get("sold_count"), errors="coerce")
    pdp = pd.to_numeric(df.get("pdp_fetched"), errors="coerce").fillna(0).astype(int)

    dari_db = df.get("sinyal_dari_db", pd.Series(False, index=df.index)).fillna(False)

    ada_terjual = terjual.notna()
    # `pdp_fetched` hanya bermakna untuk nilai yang datang dari products.db.
    # Nilai bawaan blibli/tokopedia2025 tidak punya penanda eksak sama sekali —
    # jangan diam-diam dihitung sebagai eksak.
    eksak = ada_terjual & dari_db & (pdp == 1)
    bucket = ada_terjual & dari_db & (pdp != 1)
    tak_diketahui = ada_terjual & ~dari_db
    pasangan = ada_terjual & harga.notna() & (harga > 0)

    per_sumber = []
    if "source" in df.columns:
        for src, g in df.groupby("source"):
            t = pd.to_numeric(g["sold_count"], errors="coerce")
            p = pd.to_numeric(g.get("pdp_fetched"), errors="coerce").fillna(0).astype(int)
            d = g.get("sinyal_dari_db", pd.Series(False, index=g.index)).fillna(False)
            per_sumber.append({
                "source": str(src),
                "baris": len(g),
                "ada_sold_count": int(t.notna().sum()),
                "pct": round(100 * t.notna().mean(), 1),
                "eksak": int((t.notna() & d & (p == 1)).sum()),
                "ada_rating": int(pd.to_numeric(
                    g.get("rating"), errors="coerce").notna().sum()),
            })

    hasil = {
        "dihitung_pada": datetime.now(timezone.utc).isoformat(),
        "baris_total": n,
        "ada_sold_count": int(ada_terjual.sum()),
        "cakupan_sold_count": round(float(ada_terjual.mean()), 4),
        "eksak_dari_pdp": int(eksak.sum()),
        "cakupan_eksak": round(float(eksak.mean()), 4),
        "bucket_dari_stage1": int(bucket.sum()),
        "ketepatan_tak_diketahui": int(tak_diketahui.sum()),
        "pasangan_harga_terjual": int(pasangan.sum()),
        "sold_count_nol": int((terjual == 0).sum()),
        "ambang_layak": AMBANG_LAYAK,
        "layak_jadi_dasar_posisi_harga": bool(ada_terjual.mean() >= AMBANG_LAYAK),
        "per_sumber": per_sumber,
    }
    if ada_terjual.any():
        q = terjual.dropna().quantile([0.25, 0.5, 0.75, 0.95])
        hasil["sold_count_kuantil"] = {
            "p25": float(q.loc[0.25]), "median": float(q.loc[0.50]),
            "p75": float(q.loc[0.75]), "p95": float(q.loc[0.95]),
        }
    return hasil


def cetak(r: dict) -> None:
    n = r["baris_total"]
    print(f"\nbaris total                : {n:,}")
    print(f"punya sold_count           : {r['ada_sold_count']:,} "
          f"({100 * r['cakupan_sold_count']:.1f}%)")
    print(f"  eksak (PDP tokopedia)    : {r['eksak_dari_pdp']:,} "
          f"({100 * r['cakupan_eksak']:.1f}%)")
    print(f"  bucket '750+ terjual'    : {r['bucket_dari_stage1']:,}")
    print(f"  ketepatan tak diketahui  : {r['ketepatan_tak_diketahui']:,} "
          f"(bawaan blibli/tokopedia2025)")
    print(f"pasangan harga+terjual     : {r['pasangan_harga_terjual']:,}")
    print(f"sold_count bernilai 0      : {r['sold_count_nol']:,}")
    if "sold_count_kuantil" in r:
        q = r["sold_count_kuantil"]
        print(f"sebaran sold_count         : p25={q['p25']:.0f} "
              f"median={q['median']:.0f} p75={q['p75']:.0f} p95={q['p95']:.0f}")

    if r["per_sumber"]:
        print("\nper sumber:")
        print(f"  {'source':<16}{'baris':>8}{'sold':>8}{'%':>7}{'eksak':>8}{'rating':>8}")
        for s in r["per_sumber"]:
            print(f"  {s['source']:<16}{s['baris']:>8,}{s['ada_sold_count']:>8,}"
                  f"{s['pct']:>7.1f}{s['eksak']:>8,}{s['ada_rating']:>8,}")

    print()
    if r["layak_jadi_dasar_posisi_harga"]:
        print(f"VERDIKT: cakupan {100 * r['cakupan_sold_count']:.1f}% >= "
              f"{100 * AMBANG_LAYAK:.0f}% — sinyal penjualan cukup tebal untuk jadi")
        print("         dasar penentuan posisi harga (kandidat pengganti MARGIN_DEFAULT).")
    else:
        print(f"VERDIKT: cakupan {100 * r['cakupan_sold_count']:.1f}% < "
              f"{100 * AMBANG_LAYAK:.0f}% — belum cukup jadi dasar posisi harga.")
        print("         Pakai sebagai fitur pelengkap saja, dan cari sumber lain dulu.")
    print("\nIngat: sold_count kumulatif, sebagian dibucket, dan pasangan harga-kuantitas")
    print("adalah keseimbangan pasar. Klaim yang sah = ASOSIASI, bukan elastisitas.")


def selfcheck() -> None:
    """Uji logika penggabungan tanpa menyentuh data asli."""
    df = pd.DataFrame({
        "product_id":     ["a", "b", "c", "d"],
        "product_id_asli": ["1", "2", "3", "4"],
        "source":          ["tokopedia", "tokopedia", "blibli", "tokopedia2025"],
        "price":           [10_000, 20_000, 30_000, 0],
        # blibli sudah bawa nilainya sendiri; tokopedia kosong (ekspor slim)
        "sold_count":      [None, None, 99.0, None],
        "rating":          [None, None, 4.5, None],
        "review_count":    [None, None, 12.0, None],
    })
    extra = pd.DataFrame({
        "_pid":         ["1", "2", "3"],
        "sold_count":   [750.0, 5.0, 111.0],
        "rating":       [4.8, 4.1, 3.0],
        "review_count": [30.0, 2.0, 7.0],
        "pdp_fetched":  [1, 0, 1],
    })

    out, terisi = gabung_sinyal(df, extra)
    assert terisi == 2, f"harus mengisi 2 sel kosong (a, b), dapat {terisi}"
    assert out.loc[out["product_id"] == "a", "sold_count"].iloc[0] == 750.0
    # 'c' blibli ber-product_id_asli '3' yang KEBETULAN sama dengan produk
    # tokopedia di DB. Nilainya tidak boleh tersentuh, dan ia tidak boleh
    # mewarisi pdp_fetched=1 milik produk lain itu.
    baris_c = out.loc[out["product_id"] == "c"].iloc[0]
    assert baris_c["sold_count"] == 99.0, "tabrakan ID lintas sumber menimpa nilai"
    assert not bool(baris_c["sinyal_dari_db"]), "baris blibli tidak boleh ditandai dari DB"
    assert pd.isna(out.loc[out["product_id"] == "d", "sold_count"].iloc[0]), \
        "baris tanpa pasangan di DB harus tetap kosong"

    r = ringkas(out)
    assert r["baris_total"] == 4
    assert r["ada_sold_count"] == 3, r["ada_sold_count"]
    # 'a' pdp=1 -> eksak; 'b' pdp=0 -> bucket; 'c' bawaan blibli -> tak diketahui
    assert r["eksak_dari_pdp"] == 1, r["eksak_dari_pdp"]
    assert r["bucket_dari_stage1"] == 1, r["bucket_dari_stage1"]
    assert r["ketepatan_tak_diketahui"] == 1, r["ketepatan_tak_diketahui"]
    # 'd' harganya 0 -> bukan pasangan yang bisa dipakai
    assert r["pasangan_harga_terjual"] == 3, r["pasangan_harga_terjual"]
    assert r["layak_jadi_dasar_posisi_harga"] is True

    # duplikat product_id di DB tidak boleh menggandakan baris
    dup = pd.concat([extra, extra], ignore_index=True)
    out2, _ = gabung_sinyal(df, dup)
    assert len(out2) == len(df), "join tidak boleh menambah baris"

    cetak(r)
    print("\nselfcheck OK")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sumber", default=str(SUMBER))
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--tanpa-tulis", action="store_true",
                    help="ukur saja, jangan tulis parquet hasil join")
    ap.add_argument("--selfcheck", action="store_true",
                    help="uji logika pada data sintetis, tidak menyentuh data asli")
    args = ap.parse_args()

    if args.selfcheck:
        selfcheck()
        return

    sumber, db = Path(args.sumber), Path(args.db)
    if not sumber.exists():
        raise SystemExit(f"tidak ada {sumber} — jalankan scripts/localize_merged.py dulu")
    df = pd.read_parquet(sumber)
    print(f"{len(df):,} baris dari {sumber.name}")

    if db.exists():
        con = sqlite3.connect(db)
        extra = pd.read_sql(
            "select product_id as _pid, sold_count, rating, review_count, pdp_fetched "
            "from products", con)
        con.close()
        print(f"{len(extra):,} baris dari products.db "
              f"({int(extra['sold_count'].notna().sum()):,} punya sold_count)")
        df, terisi = gabung_sinyal(df, extra)
        print(f"terisi dari join           : {terisi:,} sel sold_count")
    else:
        # Bukan kegagalan: cakupan bawaan tetap terukur, dan angkanya adalah
        # LANTAI — join products.db hanya bisa menaikkannya.
        print(f"\n!! {db} TIDAK ADA. Sinyal tokopedia tidak bisa dipulihkan di mesin ini.")
        print("   Angka di bawah = cakupan BAWAAN merged, yaitu batas bawah.")
        kosong = pd.DataFrame(columns=["_pid"] + SINYAL + ["pdp_fetched"])
        df, _ = gabung_sinyal(df, kosong)

    r = ringkas(df)
    cetak(r)

    if not args.tanpa_tulis:
        TUJUAN.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(TUJUAN, index=False)
        LAPORAN.write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n-> {TUJUAN}")
        print(f"-> {LAPORAN}")


if __name__ == "__main__":
    main()
