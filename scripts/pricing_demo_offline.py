"""Demo pricing engine offline — bisa jalan tanpa dataset parquet.

Script ini membuat dataset sintetis kecil untuk menguji logika pricing engine
tanpa perlu data asli. Cocok untuk demo/presentasi atau development.

    python scripts/pricing_demo_offline.py
    python scripts/pricing_demo_offline.py --interaktif


Kategori pada data contoh WAJIB memakai kosakata nyata dari katalog
(`pricing_engine.KATEGORI_DATA`). Sebelumnya berkas ini mengarang kategorinya
sendiri dengan kosakata yang sama-sama karangan seperti di engine, jadi demo
ini tidak mungkin mendeteksi bahwa kosakata itu tidak ada di data — lingkaran
tertutup. `tests/test_pricing.py` sekarang menjaganya.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ─── Buat Dataset Sintetis ────────────────────────────────────────────────────

def buat_dataset_sintetis() -> Path:
    """Buat parquet kecil dengan produk contoh untuk demo."""
    produk = [
        # Fashion
        {"title": "Kaos Polos Pria Lengan Pendek Hitam Katun Premium", "price": 35000, "kategori_umkm": "fashion_perawatan", "source": "tokopedia"},
        {"title": "Kaos Polos Wanita Putih Cotton Combed 30s", "price": 42000, "kategori_umkm": "fashion_perawatan", "source": "tokopedia"},
        {"title": "Kaos Polos Pria Oversize Abu-Abu", "price": 55000, "kategori_umkm": "fashion_perawatan", "source": "shopee"},
        {"title": "Kaos Polos Premium Unisex Basic Tee", "price": 49000, "kategori_umkm": "fashion_perawatan", "source": "blibli"},
        {"title": "Kaos Oblong Pria Dewasa Murah Grosir", "price": 28000, "kategori_umkm": "fashion_perawatan", "source": "tokopedia"},
        {"title": "T-shirt Polos Pria Katun Reguler Fit", "price": 38000, "kategori_umkm": "fashion_perawatan", "source": "shopee"},
        {"title": "Kaos Lengan Pendek Pria Polos Warna Warni", "price": 32000, "kategori_umkm": "fashion_perawatan", "source": "tokopedia"},
        {"title": "Baju Kaos Pria Polos O-Neck Hitam Premium", "price": 65000, "kategori_umkm": "fashion_perawatan", "source": "blibli"},
        {"title": "Kemeja Flanel Pria Kotak Lengan Panjang", "price": 85000, "kategori_umkm": "fashion_perawatan", "source": "tokopedia"},
        {"title": "Kemeja Flannel Pria Premium Motif Tartan", "price": 120000, "kategori_umkm": "fashion_perawatan", "source": "blibli"},
        {"title": "Kemeja Flanel Kotak Kotak Pria Wanita Unisex", "price": 75000, "kategori_umkm": "fashion_perawatan", "source": "shopee"},
        {"title": "Kemeja Flanel Casual Pria Lengan Panjang Slim", "price": 95000, "kategori_umkm": "fashion_perawatan", "source": "tokopedia"},

        # Tas
        {"title": "Tas Selempang Kulit Wanita Handmade Premium", "price": 180000, "kategori_umkm": "fashion_perawatan", "source": "blibli"},
        {"title": "Tas Tote Bag Kulit Sintetis Wanita Korean Style", "price": 89000, "kategori_umkm": "fashion_perawatan", "source": "shopee"},
        {"title": "Tas Wanita Kulit Asli Handmade Vintage", "price": 250000, "kategori_umkm": "fashion_perawatan", "source": "tokopedia"},
        {"title": "Tas Selempang Wanita Mini Bag Kulit PU", "price": 65000, "kategori_umkm": "fashion_perawatan", "source": "shopee"},
        {"title": "Tas Kulit Wanita Branded Lokal Premium", "price": 350000, "kategori_umkm": "fashion_perawatan", "source": "blibli"},
        {"title": "Sling Bag Kulit Wanita Handmade Artisan", "price": 195000, "kategori_umkm": "fashion_perawatan", "source": "tokopedia"},

        # Makanan
        {"title": "Keripik Pisang Renyah Manis 250g", "price": 18000, "kategori_umkm": "camilan_olahan", "source": "tokopedia"},
        {"title": "Keripik Pisang Lampung Coklat 200g", "price": 15000, "kategori_umkm": "camilan_olahan", "source": "shopee"},
        {"title": "Keripik Pisang Original Gurih 300g", "price": 22000, "kategori_umkm": "camilan_olahan", "source": "blibli"},
        {"title": "Keripik Pisang Aneka Rasa 250g Premium", "price": 25000, "kategori_umkm": "camilan_olahan", "source": "tokopedia"},
        {"title": "Kripik Pisang Keju 150g Homemade", "price": 12000, "kategori_umkm": "camilan_olahan", "source": "shopee"},
        {"title": "Keripik Pisang Pedas Crispy 250g", "price": 20000, "kategori_umkm": "camilan_olahan", "source": "tokopedia"},

        # Skincare
        {"title": "Serum Niacinamide 10% Brightening 30ml", "price": 55000, "kategori_umkm": "fashion_perawatan", "source": "shopee"},
        {"title": "Serum Wajah Niacinamide Glowing 20ml", "price": 35000, "kategori_umkm": "fashion_perawatan", "source": "tokopedia"},
        {"title": "Niacinamide Serum Whitening 30ml Premium", "price": 89000, "kategori_umkm": "fashion_perawatan", "source": "blibli"},
        {"title": "Face Serum Niacinamide + Zinc 30ml", "price": 45000, "kategori_umkm": "fashion_perawatan", "source": "shopee"},
        {"title": "Serum Pencerah Wajah Niacinamide 15ml", "price": 28000, "kategori_umkm": "fashion_perawatan", "source": "tokopedia"},
        {"title": "Brightening Serum Niacinamide 30ml BPOM", "price": 75000, "kategori_umkm": "fashion_perawatan", "source": "blibli"},

        # Sabun
        {"title": "Sabun Mandi Herbal Alami Zaitun 100g", "price": 12000, "kategori_umkm": "minuman_herbal", "source": "tokopedia"},
        {"title": "Sabun Batang Natural Herbal Aroma Terapi", "price": 15000, "kategori_umkm": "minuman_herbal", "source": "shopee"},
        {"title": "Sabun Herbal Alami Madu Propolis 80g", "price": 18000, "kategori_umkm": "minuman_herbal", "source": "blibli"},
        {"title": "Natural Soap Bar Herbal Handmade", "price": 25000, "kategori_umkm": "minuman_herbal", "source": "tokopedia"},
        {"title": "Sabun Mandi Batang Herbal Lavender", "price": 10000, "kategori_umkm": "minuman_herbal", "source": "shopee"},
        {"title": "Sabun Alami Herbal Sereh 100g", "price": 14000, "kategori_umkm": "minuman_herbal", "source": "tokopedia"},

        # Elektronik
        {"title": "Earphone Bluetooth TWS Wireless Stereo", "price": 89000, "kategori_umkm": "lainnya", "source": "shopee"},
        {"title": "Headset Bluetooth 5.0 TWS Mini In-Ear", "price": 65000, "kategori_umkm": "lainnya", "source": "tokopedia"},
        {"title": "TWS Earbuds Bluetooth Premium Bass", "price": 120000, "kategori_umkm": "lainnya", "source": "blibli"},
        {"title": "Wireless Earphone Bluetooth 5.3 TWS", "price": 150000, "kategori_umkm": "lainnya", "source": "tokopedia"},
    ]

    df = pd.DataFrame(produk)
    df["product_id"] = [f"DEMO_{i:04d}" for i in range(len(df))]
    df["n_gambar_lokal"] = 1
    df["local_image_paths"] = [["demo.jpg"]] * len(df)
    df["description"] = ""

    path = Path(tempfile.mkdtemp()) / "demo_products.parquet"
    df.to_parquet(path, index=False)
    print(f"📦 Dataset sintetis: {len(df)} produk → {path}")
    return path


# ─── Skenario Uji ────────────────────────────────────────────────────────────

SKENARIO = [
    {
        "nama": "1. ZONA BAGUS — Keripik Pisang di Blibli",
        "desc": "HPP rendah → margin besar, harga ikut pasar",
        "deskripsi": "keripik pisang renyah kemasan 250g",
        "hpp": 4000,   # sudah per unit (dari 5kg @ 50rb = 20 bungkus, + kemasan 1500)
        "platform": "blibli",
    },
    {
        "nama": "2. ZONA WAJAR — Kaos Polos di Tokopedia",
        "desc": "Posisi normal, anchor ke median pasar",
        "deskripsi": "kaos polos pria lengan pendek hitam katun",
        "hpp": 27000,   # 25rb + 2rb packing
        "platform": "tokopedia",
    },
    {
        "nama": "3. ZONA KETAT/WAJAR — Serum Skincare di Shopee",
        "desc": "HPP mendekati median, margin tipis di Shopee (biaya 15,5%)",
        "deskripsi": "serum niacinamide wajah 30ml",
        "hpp": 33000,   # 30rb + 3rb packing
        "platform": "shopee",
    },
    {
        "nama": "4. ZONA BAHAYA — Tas Kulit Handmade di Shopee ⚠️",
        "desc": "HPP terlalu tinggi → BEP > P75 pasar → PERINGATAN",
        "deskripsi": "tas kulit wanita handmade premium",
        "hpp": 155000,  # 150rb + 5rb packing
        "platform": "shopee",
    },
    {
        "nama": "5. Grosir — Sabun 1 Lusin di Tokopedia",
        "desc": "Beli grosir, HPP sudah dikonversi ke per pcs",
        "deskripsi": "sabun mandi batang herbal alami",
        "hpp": 5500,    # 60rb / 12 + 500 packing
        "platform": "tokopedia",
    },
]


def main():
    from pricing_engine import PricingEngine, BIAYA_PLATFORM

    # Buat dataset sintetis
    parquet_path = buat_dataset_sintetis()
    engine = PricingEngine(parquet_path)

    print("\n" + "=" * 62)
    print("  🏪 DEMO PRICING ENGINE — Market-First (Offline)")
    print("  Data sintetis, logika nyata")
    print("=" * 62)

    ringkasan = []

    for s in SKENARIO:
        print(f"\n{'─' * 62}")
        print(f"  📋 {s['nama']}")
        print(f"     {s['desc']}")
        print(f"{'─' * 62}")

        result = engine.hitung(
            deskripsi=s["deskripsi"],
            hpp_per_unit=s["hpp"],
            platform=s["platform"],
        )

        print(f"\n  Input: \"{s['deskripsi']}\"")
        print(f"  HPP/unit: Rp{s['hpp']:,}, Platform: {s['platform']}")
        print()
        print(result.cetak())

        if result.produk_serupa:
            print("\n  📦 Produk serupa:")
            for p in result.produk_serupa:
                print(f"     Rp{p['harga']:>9,}  {p['source']:<12} {p['judul']}")

        ringkasan.append({
            "nama": s["nama"][:35],
            "zona": result.zona,
            "bep": result.harga_minimum,
            "rekom": result.harga_rekomendasi,
            "margin": result.margin_persen,
            "platform": s["platform"],
        })

    # Ringkasan
    print(f"\n\n{'=' * 75}")
    print("  📊 RINGKASAN SEMUA SKENARIO")
    print(f"{'=' * 75}")
    print(f"  {'Skenario':<36} {'Zona':<10} {'BEP':>10} {'Rekom':>10} {'Margin':>8}")
    print(f"  {'─'*36} {'─'*10} {'─'*10} {'─'*10} {'─'*8}")
    for r in ringkasan:
        print(f"  {r['nama']:<36} {r['zona']:<10} "
              f"Rp{r['bep']:>8,} Rp{r['rekom']:>8,} {r['margin']:>+6.1f}%")

    # Bonus: perbandingan platform untuk skenario 4 (Bahaya)
    print(f"\n{'─' * 75}")
    print("  🏪 Skenario 4 — Perbandingan Platform (Tas Kulit Rp155.000)")
    print(f"{'─' * 75}")
    for plat in BIAYA_PLATFORM:
        r = engine.hitung("tas kulit wanita handmade premium", hpp_per_unit=155000,
                          platform=plat)
        status = "✅" if r.zona != "BAHAYA" else "❌"
        print(f"  {status} {r.platform:<12}  Zona: {r.zona:<10} "
              f"BEP: Rp{r.harga_minimum:>9,}  Rekom: Rp{r.harga_rekomendasi:>9,}  "
              f"Margin: {r.margin_persen:>+.1f}%")

    # Interaktif?
    print(f"\n{'─' * 75}")
    try:
        jawab = input("\n  Mau coba mode interaktif? (y/n): ").strip().lower()
    except EOFError:
        # dijalankan tanpa terminal (CI, pipe, penilai yang me-redirect stdout):
        # skenario di atas sudah tercetak, jadi cukup keluar rapi
        print("\n  (stdin tidak tersedia — mode interaktif dilewati)\n")
        return
    if jawab == "y":
        print("\n  Ketik 'q' untuk keluar.\n")
        while True:
            desc = input("  📸 Deskripsi produk: ").strip()
            if desc.lower() in ("q", "quit", "exit"):
                break
            try:
                hpp = int(input("  💰 HPP per unit (Rp): ").strip().replace(".", "").replace(",", ""))
            except ValueError:
                print("  ⚠️  HPP harus angka.")
                continue
            plat = input("  🏪 Platform [tokopedia/shopee/blibli]: ").strip() or "tokopedia"
            r = engine.hitung(desc, hpp_per_unit=hpp, platform=plat)
            print()
            print(r.cetak())
            if r.produk_serupa:
                print("\n  📦 Produk serupa:")
                for p in r.produk_serupa:
                    print(f"     Rp{p['harga']:>9,}  {p['source']:<12} {p['judul']}")
            print()

    print("\n✅ Demo selesai!")


if __name__ == "__main__":
    main()
