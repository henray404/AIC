"""Demo & pengujian pricing engine — jalankan tanpa perlu Ollama/VLM.

Menguji berbagai skenario harga dari docs/MODEL_HARGA.md untuk memastikan
logika zona (BAGUS/WAJAR/KETAT/BAHAYA) bekerja dengan benar.

    python scripts/pricing_demo.py
    python scripts/pricing_demo.py --interaktif
    python scripts/pricing_demo.py --deskripsi "tas kulit handmade" --hpp 150000 --platform shopee
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# pastikan scripts/ ada di sys.path agar bisa impor pricing_engine
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pricing_engine import PricingEngine, PricingRequest, BIAYA_PLATFORM


# ─── Skenario Uji ────────────────────────────────────────────────────────────

SKENARIO = [
    {
        "nama": "Skenario 1: ZONA BAGUS — Keripik Pisang di Blibli",
        "deskripsi": "keripik pisang renyah kemasan 250g",
        "hpp_total": 50_000,
        "hpp_satuan": "kg",
        "hpp_jumlah": 5,
        "jual_per": 250,
        "jual_satuan": "g",
        "packing": 1500,
        "platform": "blibli",
        "zona_harapan": "BAGUS",
    },
    {
        "nama": "Skenario 2: ZONA WAJAR — Kaos Polos Pria di Tokopedia",
        "deskripsi": "kaos polos pria lengan pendek hitam katun",
        "hpp_total": 25_000,
        "hpp_satuan": "pcs",
        "hpp_jumlah": 1,
        "packing": 2000,
        "platform": "tokopedia",
        "zona_harapan": "WAJAR",
    },
    {
        "nama": "Skenario 3: ZONA KETAT — Serum Skincare UMKM di Shopee",
        "deskripsi": "serum niacinamide wajah 30ml",
        "hpp_total": 30_000,
        "hpp_satuan": "pcs",
        "hpp_jumlah": 1,
        "packing": 3000,
        "platform": "shopee",
        "zona_harapan": "KETAT",
    },
    {
        "nama": "Skenario 4: ZONA BAHAYA — Tas Kulit Handmade di Shopee",
        "deskripsi": "tas kulit wanita handmade premium",
        "hpp_total": 150_000,
        "hpp_satuan": "pcs",
        "hpp_jumlah": 1,
        "packing": 5000,
        "platform": "shopee",
        "zona_harapan": "BAHAYA",
    },
    {
        "nama": "Skenario 5: Grosir — Sabun 1 Lusin jual di Tokopedia",
        "deskripsi": "sabun mandi batang herbal alami",
        "hpp_total": 60_000,
        "hpp_satuan": "lusin",
        "hpp_jumlah": 1,
        "packing": 500,
        "platform": "tokopedia",
        "zona_harapan": None,  # tergantung data
    },
    {
        "nama": "Skenario 6: Perbandingan Platform — Baju sama di 3 platform",
        "deskripsi": "kemeja flanel pria kotak kotak lengan panjang",
        "hpp_total": 45_000,
        "hpp_satuan": "pcs",
        "hpp_jumlah": 1,
        "packing": 2500,
        "platform": "all",     # special: hitung untuk semua platform
        "zona_harapan": None,
    },
]


def jalankan_skenario(engine: PricingEngine, skenario: list[dict]):
    """Jalankan semua skenario dan tampilkan hasil."""
    print("=" * 62)
    print("  DEMO PRICING ENGINE — Market-First")
    print("=" * 62)

    ringkasan = []

    for s in skenario:
        print(f"\n{'─' * 62}")
        print(f"  📋 {s['nama']}")
        print(f"{'─' * 62}")

        req = PricingRequest(
            deskripsi_produk=s["deskripsi"],
            hpp_total=s["hpp_total"],
            platform=s.get("platform", "tokopedia"),
            hpp_satuan=s.get("hpp_satuan", "pcs"),
            hpp_jumlah=s.get("hpp_jumlah", 1.0),
            jual_per_unit=s.get("jual_per"),
            jual_satuan=s.get("jual_satuan"),
            biaya_packing=s.get("packing", 0),
        )

        hpp = req.hpp_per_unit
        print(f"  Input: \"{s['deskripsi']}\"")
        print(f"  Modal: Rp{s['hpp_total']:,} ({s['hpp_jumlah']} {s['hpp_satuan']})"
              f" → HPP/unit: Rp{hpp:,}")

        if s.get("platform") == "all":
            # Hitung untuk semua platform
            for plat in BIAYA_PLATFORM:
                result = engine.hitung(
                    deskripsi=s["deskripsi"],
                    hpp_per_unit=hpp,
                    platform=plat,
                )
                print(f"\n  [{BIAYA_PLATFORM[plat]['label']}]")
                print(result.cetak())
                ringkasan.append({
                    "skenario": s["nama"],
                    "platform": plat,
                    "zona": result.zona,
                    "bep": result.harga_minimum,
                    "rekomendasi": result.harga_rekomendasi,
                    "margin": result.margin_persen,
                })
        else:
            result = engine.hitung(
                deskripsi=s["deskripsi"],
                hpp_per_unit=hpp,
                platform=s["platform"],
            )
            print()
            print(result.cetak())

            # Cek zona kalau ada harapan
            harapan = s.get("zona_harapan")
            if harapan:
                status = "✅" if result.zona == harapan else "❌"
                print(f"\n  {status} Zona harapan: {harapan}, "
                      f"Zona aktual: {result.zona}")
            else:
                print(f"\n  ℹ️  Zona: {result.zona}")

            ringkasan.append({
                "skenario": s["nama"],
                "platform": s["platform"],
                "zona": result.zona,
                "bep": result.harga_minimum,
                "rekomendasi": result.harga_rekomendasi,
                "margin": result.margin_persen,
            })

            # Tampilkan produk serupa kalau ada
            if result.produk_serupa:
                print("\n  📦 Produk serupa di katalog:")
                for p in result.produk_serupa:
                    print(f"     Rp{p['harga']:>9,}  {p['source']:<12} {p['judul']}")

    # Ringkasan akhir
    print(f"\n\n{'=' * 62}")
    print("  RINGKASAN SEMUA SKENARIO")
    print(f"{'=' * 62}")
    print(f"  {'Skenario':<40} {'Zona':<10} {'BEP':>10} {'Rekom':>10} {'Margin':>8}")
    print(f"  {'─'*40} {'─'*10} {'─'*10} {'─'*10} {'─'*8}")
    for r in ringkasan:
        label = r["skenario"][:38]
        if r["platform"] != "all":
            label += f" ({r['platform'][:4]})"
        print(f"  {label:<40} {r['zona']:<10} "
              f"Rp{r['bep']:>8,} Rp{r['rekomendasi']:>8,} {r['margin']:>+6.1f}%")


def mode_interaktif(engine: PricingEngine):
    """Loop interaktif: user ketik deskripsi dan HPP, dapat rekomendasi."""
    print("\n" + "=" * 62)
    print("  MODE INTERAKTIF — ketik 'q' untuk keluar")
    print("=" * 62)

    while True:
        print()
        deskripsi = input("📸 Deskripsi produk: ").strip()
        if deskripsi.lower() in ("q", "quit", "exit"):
            break

        try:
            hpp_str = input("💰 HPP per unit (Rp): ").strip().replace(".", "").replace(",", "")
            hpp = int(hpp_str)
        except ValueError:
            print("  ⚠️  HPP harus angka bulat.")
            continue

        platform = input("🏪 Platform [tokopedia/shopee/blibli, default=tokopedia]: ").strip()
        if not platform:
            platform = "tokopedia"
        if platform not in BIAYA_PLATFORM:
            print(f"  ⚠️  Platform tidak dikenal: {platform}")
            continue

        result = engine.hitung(
            deskripsi=deskripsi,
            hpp_per_unit=hpp,
            platform=platform,
        )
        print()
        print(result.cetak())

        if result.produk_serupa:
            print("\n  📦 Produk serupa:")
            for p in result.produk_serupa:
                print(f"     Rp{p['harga']:>9,}  {p['source']:<12} {p['judul']}")

        # Tunjukkan perbandingan platform
        if result.perbandingan_platform:
            print("\n  🏪 Kalau jual di platform lain:")
            for p in result.perbandingan_platform:
                ok = "✅" if p["bisa_untung"] else "❌"
                print(f"     {ok} {p['platform']:<12} BEP Rp{p['bep']:>9,}  "
                      f"biaya {p['total_pct']:.1f}%")


def main():
    ap = argparse.ArgumentParser(
        description="Demo & pengujian pricing engine LAPAKIN.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--interaktif", "-i", action="store_true",
                    help="mode interaktif: ketik produk dan HPP, dapat rekomendasi")
    ap.add_argument("--deskripsi", "-d", default=None,
                    help="deskripsi produk untuk satu query langsung")
    ap.add_argument("--hpp", type=int, default=None,
                    help="HPP per unit untuk query langsung")
    ap.add_argument("--platform", "-p", default="tokopedia",
                    help="platform tujuan (default: tokopedia)")
    ap.add_argument("--sumber", default=None, help="path ke parquet dataset")
    args = ap.parse_args()

    sumber = Path(args.sumber) if args.sumber else None
    engine = PricingEngine(sumber)

    if args.deskripsi and args.hpp:
        # Single query
        result = engine.hitung(
            deskripsi=args.deskripsi,
            hpp_per_unit=args.hpp,
            platform=args.platform,
        )
        print()
        print(result.cetak())
        if result.produk_serupa:
            print("\n  📦 Produk serupa:")
            for p in result.produk_serupa:
                print(f"     Rp{p['harga']:>9,}  {p['source']:<12} {p['judul']}")
    elif args.interaktif:
        mode_interaktif(engine)
    else:
        jalankan_skenario(engine, SKENARIO)


if __name__ == "__main__":
    main()
