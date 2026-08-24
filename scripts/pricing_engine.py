"""Pricing engine — Market-First: pasar menentukan harga, HPP menentukan untung.

Menggabungkan data biaya platform (diverifikasi Agustus 2026), pajak UMKM
(PP 20/2026), dan benchmark harga dari 28.443 produk katalog untuk
merekomendasikan harga jual yang kompetitif bagi UMKM.

    # pakai langsung dari CLI
    python scripts/pricing_engine.py --hpp 25000 --platform tokopedia "kaos polos pria"

    # dari pipeline (impor sebagai modul)
    from pricing_engine import PricingEngine
    engine = PricingEngine()
    result = engine.hitung("kaos polos pria hitam", hpp_per_unit=25000,
                           platform="tokopedia")

Lihat docs/MODEL_HARGA.md untuk penjelasan lengkap formula dan keputusan desain.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)

PROJECT = Path(__file__).resolve().parent.parent
SUMBER = PROJECT / "data_drive" / "merged" / "merged_local.parquet"

# ─── Biaya Platform (diverifikasi Agustus 2026) ──────────────────────────────

BIAYA_PLATFORM: dict[str, dict] = {
    "tokopedia": {
        # Sumber primer: PDF tarif resmi "Tokopedia non Mall Tarif - Mulai
        # 20 Februari 2025", di-parse ke docs/tarif_tokopedia_nonmall.csv
        # (3.779 baris, 43 kategori) oleh scripts/parse_tarif_tokopedia.py.
        # Tiap angka di bawah = median tarif efektif baris daun kategori
        # Tokopedia yang dipetakan, dilahirkan ulang dengan:
        #     python scripts/parse_tarif_tokopedia.py --ringkas
        # "Efektif" = diskon komisi 20% atas subkategori bertarif 10% sudah
        # dipotong (10,00% -> 8,00%), berlaku sejak 16 September 2024.
        "komisi_pct": {
            "fashion_perawatan":   8.0,
            "elektronik_gadget":   5.75,
            "makanan_minuman":     5.75,
            "skincare_kecantikan": 8.0,
            "dapur_rumah":         8.0,
            "kesehatan_olahraga":  8.0,
            "kriya_rumah":         8.0,
            "minuman_herbal":      7.5,
            "lainnya":             8.0,
        },
        "gratis_ongkir_pct": 0.0,   # sudah termasuk di komisi dinamis
        # Dua angka di bawah TIDAK ada di PDF tarif dan belum ditemukan sumber
        # primernya; keduanya warisan dari versi sebelumnya. Jangan dikutip di
        # paper sebelum diverifikasi. Lihat docs/MODEL_HARGA.md Subbab 2.2.
        "biaya_proses": 1250,        # [BELUM DIVERIFIKASI] Rp1.250/pesanan
        "fee_cap": 80_000,           # [BELUM DIVERIFIKASI] maks komisi per item
        "label": "Tokopedia",
    },
    "shopee": {
        # Biaya Admin per 2026 — sama untuk Non-Star, Star, dan Star+
        "komisi_pct": {
            "fashion_perawatan":  10.0,
            "elektronik_gadget":   6.5,
            "makanan_minuman":    10.0,
            "skincare_kecantikan": 9.5,
            "dapur_rumah":        10.0,
            "kesehatan_olahraga":  9.0,
            "kriya_rumah":        10.0,
            "minuman_herbal":      6.5,
            "lainnya":             9.0,
        },
        "gratis_ongkir_pct": 6.0,   # Gratis Ongkir XTRA (4-9%, rata-rata 6%)
        "biaya_proses": 1250,
        "fee_cap": None,
        "label": "Shopee",
    },
    "blibli": {
        # Seller Regular 2025-2026
        "komisi_pct": {
            "fashion_perawatan":  10.0,
            "elektronik_gadget":   4.25,
            "makanan_minuman":     5.75,
            "skincare_kecantikan": 8.0,
            "dapur_rumah":         7.5,
            "kesehatan_olahraga":  7.5,
            "kriya_rumah":         8.0,
            "minuman_herbal":      5.75,
            "lainnya":             7.5,
        },
        "gratis_ongkir_pct": 0.0,
        "biaya_proses": 0,
        "fee_cap": None,
        "label": "Blibli",
    },
}

# Pajak — PP 20/2026, PMK 37/2025, PMK 131/2024
#
# pph_final_pct dipakai untuk dua hal sekaligus, dan besarannya kebetulan sama:
#   - PPh Final UMKM 0,5% atas omzet bruto (PP 20/2026)
#   - PPh Pasal 22 0,5% yang DIPUNGUT MARKETPLACE di muka (PMK 37/2025),
#     yang jadi kredit atas PPh Final di atas. Bukan beban tambahan, jadi tidak
#     dijumlahkan dua kali. Ambang pemicunya juga sama: Rp500 juta.
#
# ppn_pct = 11,0 bukan 12,0. Tarif nominal memang 12%, tapi untuk barang
# non-mewah dikalikan DPP nilai lain 11/12 sehingga tarif efektifnya 11%
# (PMK 131/2024). Barang tergolong mewah kena 12% penuh — di luar cakupan
# model ini, yang menyasar produk UMKM.
PAJAK = {
    "pph_final_pct": 0.5,         # 0,5% dari omzet bruto
    "bebas_omzet": 500_000_000,   # Rp500 juta pertama BEBAS pajak
    "ppn_pct": 11.0,              # efektif, hanya kalau PKP (omzet > Rp4,8M)
}

# ─── Kosakata Kategori ───────────────────────────────────────────────────────
#
# Diturunkan dari data, bukan dari taksonomi bayangan. Diukur 20 Agustus 2026 atas
# merged.parquet (28.443 baris) dengan `df["kategori_umkm"].value_counts()`:
#
#   lainnya 10.738 | fashion_perawatan 7.566 | kriya_rumah 3.594 | pokok_tani 1.847
#   minuman_herbal 1.796 | bumbu_masak 1.543 | camilan_olahan 1.359
#
# Sebelum ini tabel biaya dan margin memakai kunci karangan (`makanan_minuman`,
# `skincare_kecantikan`, `elektronik_gadget`, `dapur_rumah`, `kesehatan_olahraga`)
# yang muncul NOL kali di data, sementara tiga kategori pangan nyata jatuh diam-diam
# ke `lainnya` lewat `.get(kategori, ...)` — 16,7% katalog, tanpa satu pun peringatan.

KATEGORI_DATA: tuple[str, ...] = (
    "bumbu_masak", "camilan_olahan", "fashion_perawatan",
    "kriya_rumah", "lainnya", "minuman_herbal", "pokok_tani",
)

# Label internal -> kategori tarif platform. Tarifnya sendiri (§BIAYA_PLATFORM)
# diverifikasi Agustus 2026 dan memakai taksonomi platform, bukan taksonomi kita;
# pemetaan ini yang menjembatani keduanya. Ketiga kategori pangan memakai tarif
# kelompok makanan/minuman karena itu kelompok tarif tempat mereka jatuh di
# ketiga marketplace.
KE_TARIF: dict[str, str] = {
    "bumbu_masak":       "makanan_minuman",
    "camilan_olahan":    "makanan_minuman",
    "pokok_tani":        "makanan_minuman",
    "minuman_herbal":    "minuman_herbal",
    "fashion_perawatan": "fashion_perawatan",
    "kriya_rumah":       "kriya_rumah",
    "lainnya":           "lainnya",
}


def kategori_tarif(kategori: str) -> str:
    """Petakan label kategori ke kategori tarif platform.

    Kategori tak dikenal TIDAK didiamkan. Jatuh ke `lainnya` tetap terjadi supaya
    pipeline tidak mati di tengah batch, tapi selalu disertai peringatan — persis
    yang absen waktu 4.749 produk pangan lewat tanpa jejak.
    """
    if kategori in KE_TARIF:
        return KE_TARIF[kategori]
    log.warning(
        "kategori %r tidak dikenal; memakai tarif dan margin 'lainnya'. "
        "Kosakata yang sah: %s. Kalau ini kategori baru dari data, "
        "tambahkan ke KATEGORI_DATA dan KE_TARIF, jangan biarkan jatuh diam-diam.",
        kategori, ", ".join(KATEGORI_DATA),
    )
    return "lainnya"


# ─── Margin Default per Kategori ─────────────────────────────────────────────
#
# PERINGATAN: angka-angka ini BELUM DIUKUR — disusun dari perkiraan, bukan dari
# katalog maupun sumber luar. Lihat docs/RISET_MODEL_HARGA.md §4.1 untuk rencana
# penggantiannya dengan dispersi harga empiris per kategori.
#
# Terukur 20 Agu 2026 atas 299 produk contoh: tabel ini dibaca 299 kali dan
# nilainya dipakai NOL kali, karena zona TIDAK_ADA_DATA tidak pernah aktif ketika
# retrieval selalu menemukan tetangga. Ia baru menentukan harga saat retrieval
# gagal — yaitu untuk produk yang benar-benar baru.

MARGIN_DEFAULT: dict[str, dict[str, float]] = {
    "fashion_perawatan":   {"lo": 0.50, "mid": 0.80, "hi": 1.50},
    "elektronik_gadget":   {"lo": 0.10, "mid": 0.20, "hi": 0.30},
    "makanan_minuman":     {"lo": 0.30, "mid": 0.50, "hi": 0.80},
    "minuman_herbal":      {"lo": 0.40, "mid": 0.60, "hi": 1.00},
    "skincare_kecantikan": {"lo": 0.40, "mid": 0.70, "hi": 1.20},
    "dapur_rumah":         {"lo": 0.25, "mid": 0.40, "hi": 0.60},
    "kesehatan_olahraga":  {"lo": 0.30, "mid": 0.45, "hi": 0.70},
    "kriya_rumah":         {"lo": 0.50, "mid": 1.00, "hi": 2.00},
    "lainnya":             {"lo": 0.30, "mid": 0.50, "hi": 0.80},
    # Tiga kategori pangan nyata. Sebelumnya tidak ada di sini sama sekali.
    "bumbu_masak":         {"lo": 0.30, "mid": 0.50, "hi": 0.80},
    "camilan_olahan":      {"lo": 0.30, "mid": 0.50, "hi": 0.80},
    "pokok_tani":          {"lo": 0.25, "mid": 0.40, "hi": 0.60},
}

# Satuan konversi grosir → eceran
KONVERSI_SATUAN: dict[str, int] = {
    "lusin": 12, "kodi": 20, "gross": 144,
    "bal": 12, "dus": 24, "pack": 6,
}

# ─── §3.4 Unit Modal: satuan lazim per kategori ───────────────────────
#
# Mesin ini TIDAK menebak satuan modal. "Modal Rp50.000" bisa berarti per pcs,
# per kg bahan, atau per lusin — salah tebak menggeser harga berkali-kali lipat.
# Tabel ini cuma dipakai untuk MENYODORKAN pilihan yang relevan dengan barang
# yang terdeteksi dari foto; jawabannya tetap harus datang dari penjual, dan
# kalau ia diam, `PricingRequest` mundur ke asumsi teraman (1 unit jual).
#
# Kuncinya memakai kosakata nyata (KATEGORI_DATA). docs/MODEL_HARGA.md §3.4
# menulis tabel ini dengan kunci karangan (`makanan_minuman`,
# `skincare_kecantikan`, `elektronik_gadget`, `dapur_rumah`) yang muncul nol kali
# di katalog — cacat yang sama yang sudah dibereskan untuk komisi dan margin.
# Empat kategori pangan kami memetakan ke entri "makanan/minuman" doc, dan
# `fashion_perawatan` menggabungkan entri fashion dan skincare doc karena di
# kosakata kami keduanya memang satu kategori.

UNIT_LAZIM: dict[str, dict[str, Any]] = {
    "camilan_olahan": {
        "satuan_beli": ["kg", "liter", "karung", "bal", "dus"],
        "satuan_jual": ["pcs", "bungkus", "sachet", "botol", "cup"],
        "pertanyaan": "Modal Rp{hpp:,} ini untuk beli berapa banyak bahan, "
                      "dan jadi berapa kemasan siap jual?",
    },
    "bumbu_masak": {
        "satuan_beli": ["kg", "liter", "karung", "bal", "dus"],
        "satuan_jual": ["pcs", "bungkus", "sachet", "botol"],
        "pertanyaan": "Modal Rp{hpp:,} ini untuk beli berapa banyak bahan, "
                      "dan jadi berapa kemasan siap jual?",
    },
    "pokok_tani": {
        "satuan_beli": ["kg", "karung", "dus"],
        "satuan_jual": ["pcs", "bungkus", "kg"],
        "pertanyaan": "Modal Rp{hpp:,} ini untuk berapa kg, "
                      "dan dijual per kemasan berapa?",
    },
    "minuman_herbal": {
        "satuan_beli": ["kg", "liter", "dus", "bal"],
        "satuan_jual": ["botol", "sachet", "cup", "pcs"],
        "pertanyaan": "Modal Rp{hpp:,} ini untuk berapa banyak bahan, "
                      "dan jadi berapa botol/sachet?",
    },
    "fashion_perawatan": {
        "satuan_beli": ["pcs", "lusin (12)", "kodi (20)", "meter (kain)",
                        "liter (isi ulang)"],
        "satuan_jual": ["pcs", "botol", "tube", "sachet"],
        "pertanyaan": "Modal Rp{hpp:,} ini untuk berapa banyak barang?",
    },
    "kriya_rumah": {
        "satuan_beli": ["pcs", "meter (kain)", "gulung (benang)", "lembar"],
        "satuan_jual": ["pcs", "set"],
        "pertanyaan": "Modal Rp{hpp:,} ini bahan untuk berapa produk jadi?",
    },
    "lainnya": {
        "satuan_beli": ["pcs", "lusin (12)", "kodi (20)", "kg", "dus"],
        "satuan_jual": ["pcs"],
        "pertanyaan": "Modal Rp{hpp:,} ini untuk berapa banyak barang?",
    },
}

# ─── §3.5 Variasi: faktor harga per ukuran ───────────────────────────
#
# PERINGATAN, setara dengan yang menempel di MARGIN_DEFAULT: angka-angka ini
# BELUM DIUKUR dari katalog. Mereka disalin apa adanya dari docs/MODEL_HARGA.md
# §3.5, yang menyebutnya "diturunkan dari pola marketplace" tanpa menunjukkan
# pengukurannya. Perlakukan sebagai parameter yang di-set tangan.
#
# Dispatch-nya lewat SATUAN di label, bukan lewat kategori: "250g" selalu pakai
# kurva berat, "30ml" selalu pakai kurva volume. Itu kebetulan persis pemakaian
# di doc (makanan diukur gram, skincare diukur ml) tapi tidak ikut rusak kalau
# kategori salah tebak — dan kategori memang sering salah (37,8% `lainnya`).
#
# Nilai = harga relatif terhadap ukuran dasar tabel, sudah memuat diskon volume:
# 500g bukan 10× harga 50g melainkan 7×, karena harga per gram turun seiring
# kemasan membesar.

ANCHOR_UKURAN: dict[str, dict[float, float]] = {
    # gram — docs/MODEL_HARGA.md §3.5, tabel "makanan_minuman"
    "berat":  {50: 1.00, 100: 1.85, 150: 2.60, 250: 4.00, 500: 7.00, 1000: 12.00},
    # mililiter — docs/MODEL_HARGA.md §3.5, tabel "skincare_kecantikan"
    "volume": {15: 1.00, 30: 1.80, 60: 3.20, 100: 4.80},
}

# Konvensi marketplace Indonesia: XS–XL satu harga, XXL ke atas kena tambahan
# karena bahannya lebih banyak.
ATURAN_UKURAN_FASHION: dict[str, float] = {
    "xs": 1.00, "s": 1.00, "m": 1.00, "l": 1.00, "xl": 1.00,
    "xxl": 1.05, "2xl": 1.05,
    "3xl": 1.10, "xxxl": 1.10,
    "4xl": 1.15,
    "5xl": 1.20,
}

# Variasi material/grade — HPP-nya beda, jadi tidak bisa proporsional. Dipakai
# HANYA sebagai estimasi ketika penjual cuma punya satu HPP; kalau ia mengisi
# `hpp_per_grade`, tabel ini tidak dibaca sama sekali.
#
# Doc §3.5 memberi tiga baris saja (fashion 1,5×; makanan 1,8×; kriya 2,5×).
# `lainnya` — 37,8% katalog — tidak ada di doc; dipakai 1,5×, yang terkecil dari
# ketiganya, supaya estimasi tidak melambung untuk kategori yang paling tidak
# kita kenali.
RASIO_GRADE: dict[str, dict[str, float]] = {
    "fashion_perawatan": {"reguler": 1.0, "premium": 1.5},
    "camilan_olahan":    {"reguler": 1.0, "premium": 1.8},
    "bumbu_masak":       {"reguler": 1.0, "premium": 1.8},
    "pokok_tani":        {"reguler": 1.0, "premium": 1.8},
    "minuman_herbal":    {"reguler": 1.0, "premium": 1.8},
    "kriya_rumah":       {"reguler": 1.0, "premium": 2.5},
    "lainnya":           {"reguler": 1.0, "premium": 1.5},
}

STOP = {"dan", "untuk", "yang", "dengan", "atau", "the", "for", "with", "pcs", "set"}


# ─── Data Classes ────────────────────────────────────────────────────────────

@dataclass
class PricingRequest:
    """Input untuk kalkulasi harga."""
    deskripsi_produk: str         # teks deskripsi (dari VLM atau user langsung)
    hpp_total: int                # total modal yang dikeluarkan (Rupiah)
    platform: str = "tokopedia"   # "tokopedia" | "shopee" | "blibli"
    hpp_satuan: str = "pcs"       # satuan modal: "pcs", "kg", "lusin", dll
    hpp_jumlah: float = 1.0       # berapa satuan yang didapat dari modal itu
    jual_per_unit: float | None = None   # isi per kemasan jual
    jual_satuan: str | None = None       # satuan kemasan jual ("g", "ml", dll)
    biaya_packing: int = 0
    biaya_produksi: int = 0
    omzet_tahunan: int = 0        # untuk cek pajak (default 0 = bebas)
    is_ppn: bool = False

    # ── §3.4 jalur langsung: penjual tahu hasil jadinya, tanpa konversi satuan ──
    # "beli pisang 5 kg Rp50.000, jadi 20 bungkus" → jumlah_unit_jual=20.
    # Diprioritaskan di atas konversi satuan karena ini jawaban eksplisit penjual,
    # bukan hasil terjemahan tabel.
    jumlah_unit_jual: float | None = None
    satuan_jual: str = "pcs"      # nama unit yang dijual: pcs, bungkus, botol

    # ── §3.5 Variasi ──
    variasi_warna: list[str] | None = None    # ["Hitam", "Putih", "Navy"]
    variasi_ukuran: list[str] | None = None   # ["S","M","L","XL"] atau ["100g","250g"]
    hpp_per_ukuran: dict[str, int] | None = None   # {"S": 25000, "XXL": 30000}
    variasi_grade: list[str] | None = None    # ["Reguler", "Premium"]
    hpp_per_grade: dict[str, int] | None = None    # {"Reguler": 25000, "Premium": 40000}

    @property
    def hpp_per_unit(self) -> int:
        """Konversi modal grosir → HPP per 1 unit jual."""
        if self.jumlah_unit_jual:
            return hitung_hpp_per_unit(
                self.hpp_total, self.jumlah_unit_jual,
                self.biaya_packing + self.biaya_produksi)

        jumlah = self.hpp_jumlah * KONVERSI_SATUAN.get(self.hpp_satuan, 1)

        if self.jual_per_unit and self.jual_satuan:
            GRAM = {"g": 1, "gr": 1, "kg": 1000}
            ML = {"ml": 1, "l": 1000, "liter": 1000}
            if self.hpp_satuan == "kg" and self.jual_satuan in GRAM:
                total = self.hpp_jumlah * 1000
                jumlah = total / (self.jual_per_unit * GRAM[self.jual_satuan])
            elif self.hpp_satuan in ("l", "liter") and self.jual_satuan in ML:
                total = self.hpp_jumlah * 1000
                jumlah = total / (self.jual_per_unit * ML[self.jual_satuan])

        hpp_bahan = self.hpp_total / max(jumlah, 1)
        return int(hpp_bahan + self.biaya_packing + self.biaya_produksi)


@dataclass
class VariantPrice:
    """Harga untuk satu varian spesifik (§5.2)."""
    label: str                     # "XXL", "250g", "Premium", "Hitam"
    jenis: str                     # "warna" | "ukuran" | "grade"
    harga_minimum: int             # BEP varian ini
    harga_rekomendasi: int
    harga_agresif: int
    harga_premium: int
    hpp_unit: int                  # HPP per unit untuk varian ini
    margin_persen: float
    komponen: dict[str, int]       # breakdown varian ini
    catatan: str | None = None     # dari mana faktor harganya datang


@dataclass
class PricingResult:
    """Output dari kalkulasi harga."""
    # Harga utama
    harga_minimum: int             # BEP — di bawah ini rugi
    harga_rekomendasi: int         # harga jual yang disarankan
    harga_agresif: int             # harga kompetitif (margin rendah)
    harga_premium: int             # harga premium

    # Zona & status
    zona: str                      # "BAGUS" | "WAJAR" | "KETAT" | "BAHAYA" | "TIDAK_ADA_DATA"
    zona_emoji: str                # emoji untuk zona
    peringatan: str | None         # peringatan kalau zona KETAT/BAHAYA
    saran: list[str]               # saran konkret

    # Pasar
    harga_pasar_p25: int
    harga_pasar_median: int
    harga_pasar_p75: int
    jumlah_kompetitor: int

    # Info
    hpp_per_unit: int
    margin_persen: float           # margin dari harga rekomendasi
    kategori: str
    platform: str
    total_potongan_pct: float      # total biaya platform + pajak

    # Breakdown per unit terjual
    breakdown: dict[str, int]      # {hpp, komisi, ongkir, proses, pajak, laba}

    # Konteks
    produk_serupa: list[dict]      # 5 produk terdekat

    # Perbandingan platform
    perbandingan_platform: list[dict] = field(default_factory=list)

    # ── §3.5 Harga per varian; kosong kalau produk tidak punya variasi ──
    varian: list[VariantPrice] = field(default_factory=list)

    # Nama unit yang dijual — "pcs", "bungkus", "botol". Semua angka harga di
    # atas berlaku PER SATU unit ini, bukan per kg bahan yang dibeli penjual.
    satuan_jual: str = "pcs"

    # Variasi yang lazim dipakai produk serupa, diukur dari judul tetangga
    variasi_disarankan: dict[str, Any] = field(default_factory=dict)

    # Narasi bahasa Indonesia: kenapa harganya segitu
    penjelasan: str = ""

    def cetak(self) -> str:
        """Format hasil untuk tampilan terminal."""
        garis = "═" * 58
        baris = [
            f"╔{garis}╗",
            f"║  {'Hasil Rekomendasi Harga':^54}  ║",
            f"╠{garis}╣",
            f"║  Kategori: {self.kategori:<44}  ║",
            f"║  Platform: {self.platform:<44}  ║",
            f"╠{garis}╣",
        ]

        # Zona
        baris.append(f"║  {self.zona_emoji} Zona: {self.zona:<48}  ║")
        if self.peringatan:
            # word-wrap peringatan
            for line in _wrap(self.peringatan, 54):
                baris.append(f"║  {line:<54}  ║")
        baris.append(f"╠{garis}╣")

        # Harga
        baris.append(f"║  HPP per unit:      Rp{self.hpp_per_unit:>12,}              ║")
        baris.append(f"║  Harga BEP:         Rp{self.harga_minimum:>12,}              ║")
        baris.append(f"║  ─────────────────────────────────────────────────  ║")
        baris.append(f"║  🔥 Agresif:         Rp{self.harga_agresif:>12,}              ║")
        baris.append(f"║  ✅ Rekomendasi:     Rp{self.harga_rekomendasi:>12,}              ║")
        baris.append(f"║  💎 Premium:         Rp{self.harga_premium:>12,}              ║")
        baris.append(f"║  ─────────────────────────────────────────────────  ║")
        margin_str = f"{self.margin_persen:+.1f}%"
        baris.append(f"║  Margin (rekom):     {margin_str:<35}║")
        baris.append(f"╠{garis}╣")

        # Pasar
        pasar_header = f"📈 Harga Pasar ({self.jumlah_kompetitor} produk serupa):"
        baris.append(f"║  {pasar_header:<54}  ║")
        baris.append(f"║     P25 (murah):    Rp{self.harga_pasar_p25:>12,}              ║")
        baris.append(f"║     Median:         Rp{self.harga_pasar_median:>12,}              ║")
        baris.append(f"║     P75 (premium):  Rp{self.harga_pasar_p75:>12,}              ║")
        baris.append(f"╠{garis}╣")

        # Breakdown
        bd_header = f"📋 Breakdown per unit terjual Rp{self.harga_rekomendasi:,}:"
        baris.append(f"║  {bd_header:<54}  ║")
        for label, val in self.breakdown.items():
            pct = val / max(self.harga_rekomendasi, 1) * 100
            isi = f"{label:<20} Rp{val:>9,}  ({pct:>5.1f}%)"
            baris.append(f"║     {isi:<51}  ║")

        # Saran
        if self.saran:
            baris.append(f"╠{garis}╣")
            baris.append(f"║  💡 Saran:{'':>46}║")
            for i, s in enumerate(self.saran, 1):
                for line in _wrap(f"{i}. {s}", 54):
                    baris.append(f"║  {line:<54}  ║")

        # Perbandingan platform
        if self.perbandingan_platform:
            baris.append(f"╠{garis}╣")
            baris.append(f"║  🏪 Perbandingan Platform:{'':>30}║")
            for p in self.perbandingan_platform:
                isi = (f"     {p['platform']:<12} BEP Rp{p['bep']:>9,}"
                       f"  biaya {p['total_pct']:.1f}%")
                baris.append(f"║  {isi:<54}  ║")

        # Harga per varian (§3.5)
        if self.varian:
            baris.append(f"╠{garis}╣")
            baris.append(f"║  📋 Daftar Harga per Varian:{'':>28}║")

            warna = [v for v in self.varian if v.jenis == "warna"]
            ukuran = [v for v in self.varian if v.jenis == "ukuran"]
            grade = [v for v in self.varian if v.jenis == "grade"]

            if ukuran:
                baris.append(f"║     Ukuran/isi (harga berbeda):{'':>25}║")
                for v in ukuran:
                    isi = (f"{v.label:<10} Rp{v.harga_rekomendasi:>9,}"
                           f"   BEP Rp{v.harga_minimum:>8,}  {v.margin_persen:>6.0f}%")
                    baris.append(f"║       {isi:<49}  ║")
            if warna:
                # Satu baris untuk semua: justru itu poinnya, harganya sama.
                nama = ", ".join(v.label for v in warna)
                baris.append(f"║     Warna/motif (harga sama):{'':>27}║")
                for line in _wrap(f"Rp{warna[0].harga_rekomendasi:,} — {nama}", 49):
                    baris.append(f"║       {line:<49}  ║")
            if grade:
                baris.append(f"║     Grade/material (harga berbeda):{'':>21}║")
                for v in grade:
                    tanda = " [estimasi]" if v.catatan and "ESTIMASI" in v.catatan else ""
                    isi = f"{v.label:<12} Rp{v.harga_rekomendasi:>9,}{tanda}"
                    baris.append(f"║       {isi:<49}  ║")

        # Variasi yang lazim di katalog (§3.5)
        saran_var = self.variasi_disarankan.get("saran") if self.variasi_disarankan else None
        if saran_var:
            baris.append(f"╠{garis}╣")
            n = self.variasi_disarankan.get("dari_n", 0)
            judul_var = f"💡 Varian yang lazim (dari {n} produk serupa):"
            baris.append(f"║  {judul_var:<54}  ║")
            for sv in saran_var:
                for line in _wrap(f"• {sv}", 54):
                    baris.append(f"║  {line:<54}  ║")

        # Narasi (§5.2)
        if self.penjelasan:
            baris.append(f"╠{garis}╣")
            baris.append(f"║  📝 Penjelasan:{'':>41}║")
            for line in _wrap(self.penjelasan, 54):
                baris.append(f"║  {line:<54}  ║")

        baris.append(f"╚{garis}╝")
        return "\n".join(baris)


def _wrap(text: str, width: int) -> list[str]:
    """Sederhana: pecah teks panjang ke beberapa baris."""
    words = text.split()
    lines, current = [], ""
    for w in words:
        if len(current) + len(w) + 1 > width:
            lines.append(current)
            current = w
        else:
            current = f"{current} {w}".strip()
    if current:
        lines.append(current)
    return lines or [""]


# ─── TF-IDF Index (sama dengan retrieve_pipeline.py) ─────────────────────────

def _token(teks: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", str(teks).lower())
            if len(w) >= 3 and w not in STOP]


class Indeks:
    """TF-IDF ringkas di atas judul produk."""

    def __init__(self, judul: list[str]):
        self.n = len(judul)
        self.inverted: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.panjang: list[float] = []
        for i, j in enumerate(judul):
            t = _token(j)
            self.panjang.append(math.sqrt(len(t)) or 1.0)
            hitung: dict[str, int] = defaultdict(int)
            for w in t:
                hitung[w] += 1
            for w, c in hitung.items():
                self.inverted[w].append((i, c))
        self.idf = {w: math.log(1 + self.n / len(post))
                    for w, post in self.inverted.items()}

    def cari(self, kueri: str, k: int = 10) -> list[tuple[int, float]]:
        skor: dict[int, float] = defaultdict(float)
        for w in set(_token(kueri)):
            if w not in self.inverted:
                continue
            bobot = self.idf[w]
            for i, c in self.inverted[w]:
                skor[i] += bobot * (1 + math.log(c)) / self.panjang[i]
        return sorted(skor.items(), key=lambda x: -x[1])[:k]


# ─── Fungsi Utilitas ─────────────────────────────────────────────────────────

def bulatkan_psikologis(harga: int) -> int:
    """Bulatkan ke angka psikologis terdekat."""
    if harga <= 0:
        return 0
    if harga < 10_000:
        h = round(harga / 500) * 500 - 100
    elif harga < 100_000:
        h = round(harga / 1_000) * 1_000 - 100
    elif harga < 1_000_000:
        h = round(harga / 5_000) * 5_000 - 100
    else:
        h = round(harga / 10_000) * 10_000 - 100
    return max(h, 100)  # minimal Rp100


def hitung_bep(hpp_per_unit: int, platform: str, kategori: str,
               omzet_tahunan: int = 0, is_ppn: bool = False) -> tuple[float, float, int]:
    """Hitung break-even price. Returns (bep, total_potongan_pct, biaya_flat)."""
    biaya = BIAYA_PLATFORM.get(platform, BIAYA_PLATFORM["tokopedia"])
    komisi = biaya["komisi_pct"][kategori_tarif(kategori)]
    ongkir = biaya["gratis_ongkir_pct"]
    biaya_flat = biaya["biaya_proses"]

    total_pct = komisi + ongkir
    if omzet_tahunan >= PAJAK["bebas_omzet"]:
        total_pct += PAJAK["pph_final_pct"]
    if is_ppn:
        total_pct += PAJAK["ppn_pct"]

    bep = (hpp_per_unit + biaya_flat) / (1 - total_pct / 100)

    # Tokopedia membatasi komisi per item (Rp80.000, Juli 2026). Di atas batas itu
    # komisi berhenti tumbuh, jadi BEP proporsional di atas melebih-lebihkan biaya.
    # Sebelumnya `fee_cap` didefinisikan tapi tidak pernah dibaca.
    cap = biaya.get("fee_cap")
    if cap and bep * komisi / 100 > cap:
        bep = (hpp_per_unit + biaya_flat + cap) / (1 - (total_pct - komisi) / 100)

    return bep, total_pct, biaya_flat


def tentukan_zona(bep: float, p25: float, median: float, p75: float) -> str:
    """Tentukan zona kompetitif berdasarkan BEP vs harga pasar."""
    if bep > p75:
        return "BAHAYA"
    elif bep > median:
        return "KETAT"
    elif bep > p25:
        return "WAJAR"
    else:
        return "BAGUS"


ZONA_EMOJI = {
    "BAGUS": "🟢",
    "WAJAR": "🟡",
    "KETAT": "🟠",
    "BAHAYA": "🔴",
    "TIDAK_ADA_DATA": "⚪",
}


# ─── §3.4 Unit Modal ─────────────────────────────────────────────────────────

def hitung_hpp_per_unit(modal_total: int, jumlah_unit: float,
                        biaya_produksi_per_unit: int = 0) -> int:
    """Konversi modal grosir → HPP per unit jual, ketika penjual tahu jumlahnya.

    Jalur paling sederhana dari §3.4, untuk kasus di mana penjual bisa langsung
    menyebut hasil jadinya ("beli pisang 5 kg Rp50.000, jadi 20 bungkus") tanpa
    perlu konversi satuan sama sekali. Jalur satuan (kg→g, lusin→pcs) ada di
    `PricingRequest.hpp_per_unit`.

        >>> hitung_hpp_per_unit(50_000, 20, 1_500)   # + kemasan Rp1.500
        4000
    """
    if jumlah_unit <= 0:
        raise ValueError(f"jumlah_unit harus > 0, dapat {jumlah_unit}")
    return int(modal_total / jumlah_unit + biaya_produksi_per_unit)


def pertanyaan_unit(kategori: str, hpp_total: int) -> dict[str, Any] | None:
    """Pertanyaan klarifikasi satuan modal, disesuaikan jenis barang.

    Mengembalikan `None` kalau kategori itu praktis selalu dijual per pcs
    sehingga bertanya cuma menambah gesekan. Pemanggilnya (UI/pipeline) yang
    memutuskan mau menampilkan atau tidak — mesin ini tidak pernah menebak
    jawabannya sendiri.
    """
    entri = UNIT_LAZIM.get(kategori_tarif_unit(kategori))
    if entri is None or not entri.get("pertanyaan"):
        return None
    return {
        "pertanyaan": entri["pertanyaan"].format(hpp=hpp_total),
        "satuan_beli": list(entri["satuan_beli"]),
        "satuan_jual": list(entri["satuan_jual"]),
        "default": ("Kalau dilewati: dianggap modal untuk 1 unit jual — "
                    "asumsi teraman, harga bisa kemahalan tapi tidak akan rugi."),
    }


def kategori_tarif_unit(kategori: str) -> str:
    """Kategori yang dipakai untuk UNIT_LAZIM/RASIO_GRADE — divalidasi, tidak diam."""
    if kategori in UNIT_LAZIM:
        return kategori
    log.warning(
        "kategori %r tidak ada di UNIT_LAZIM/RASIO_GRADE; memakai 'lainnya'. "
        "Kosakata yang sah: %s.", kategori, ", ".join(KATEGORI_DATA),
    )
    return "lainnya"


# ─── §3.5 Variasi Produk ─────────────────────────────────────────────────────

_RE_UKURAN = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|gr|gram|g|ml|liter|lt|l)\b",
                        re.IGNORECASE)


def _parse_ukuran(label: str) -> tuple[float, str] | None:
    """"250g" → (250.0, "berat"); "1kg" → (1000.0, "berat"); "30ml" → (30.0, "volume")."""
    m = _RE_UKURAN.search(str(label))
    if not m:
        return None
    qty = float(m.group(1).replace(",", "."))
    satuan = m.group(2).lower()
    if satuan == "kg":
        return qty * 1000, "berat"
    if satuan in ("g", "gr", "gram"):
        return qty, "berat"
    if satuan in ("l", "lt", "liter"):
        return qty * 1000, "volume"
    return qty, "volume"   # ml


def _faktor_dari_anchor(qty: float, tabel: dict[float, float]) -> float:
    """Interpolasi log-log antar titik jangkar; di luar rentang, ekstrapolasi
    memakai eksponen segmen terdekat.

    Log-log dipilih karena diskon volume memang berperilaku pangkat: pada tabel
    berat §3.5 eksponennya 0,83–0,89 di seluruh rentang, bukan konstanta aditif.
    Di titik jangkar hasilnya persis sama dengan angka doc.
    """
    titik = sorted(tabel.items())
    if qty <= titik[0][0]:
        (x0, y0), (x1, y1) = titik[0], titik[1]
    elif qty >= titik[-1][0]:
        (x0, y0), (x1, y1) = titik[-2], titik[-1]
    else:
        (x0, y0), (x1, y1) = titik[0], titik[1]
        for i in range(len(titik) - 1):
            if titik[i][0] <= qty <= titik[i + 1][0]:
                (x0, y0), (x1, y1) = titik[i], titik[i + 1]
                break
    alpha = math.log(y1 / y0) / math.log(x1 / x0)
    return y0 * (qty / x0) ** alpha


def faktor_ukuran(label: str) -> tuple[float, str]:
    """Faktor harga relatif ukuran dasar tabelnya. Returns (faktor, jenis).

    jenis: "berat" | "volume" | "fashion" | "tetap" (label tidak dikenali).
    Dispatch lewat satuan di label, bukan lewat kategori — lihat catatan di
    ANCHOR_UKURAN.
    """
    ukur = _parse_ukuran(label)
    if ukur:
        qty, dimensi = ukur
        return _faktor_dari_anchor(qty, ANCHOR_UKURAN[dimensi]), dimensi

    kunci = str(label).strip().lower().replace(" ", "").replace("-", "")
    if kunci in ATURAN_UKURAN_FASHION:
        return ATURAN_UKURAN_FASHION[kunci], "fashion"

    log.warning(
        "label ukuran %r tidak dikenali (bukan berat/volume, bukan ukuran "
        "fashion); harga varian ini disamakan dengan varian dasar.", label)
    return 1.0, "tetap"


def faktor_relatif(label: str, dasar: str) -> float:
    """Faktor harga varian `label` relatif varian `dasar` (yang HPP-nya diketahui).

    Rasio antar dua ukuran = f(label)/f(dasar), jadi hasilnya tidak bergantung
    pada ukuran mana yang jadi dasar tabel. Contoh §3.5: dasar 100g, varian 250g
    → 4,00/1,85 = 2,16×.
    """
    f_var, jenis_var = faktor_ukuran(label)
    f_dasar, jenis_dasar = faktor_ukuran(dasar)
    if jenis_var != jenis_dasar:
        log.warning(
            "varian %r (%s) dan varian dasar %r (%s) beda jenis ukuran; "
            "rasionya tidak bermakna, dipakai 1,0.",
            label, jenis_var, dasar, jenis_dasar)
        return 1.0
    return f_var / max(f_dasar, 1e-9)


def variasi_kosmetik(harga_dasar: int, varian: list[str]) -> dict[str, Any]:
    """Warna/motif → harga sama untuk semua varian.

    Dipisah jadi fungsinya sendiri karena inilah kesalahan yang paling sering:
    membuat listing terpisah per warna, sehingga review dan rating penjualan
    terpecah ke belasan listing yang masing-masing terlihat sepi.
    """
    return {
        "harga": harga_dasar,
        "varian": list(varian),
        "catatan": f"Harga sama untuk semua {len(varian)} varian warna/motif",
        "saran": ("Buat 1 listing dengan pilihan varian, bukan listing terpisah "
                  "per warna — supaya rating dan jumlah terjual menumpuk di satu "
                  "tempat."),
    }


def rasio_grade(kategori: str, grade: str) -> float:
    """Rasio harga grade relatif 'reguler'. 1,0 kalau grade tak dikenal."""
    tabel = RASIO_GRADE[kategori_tarif_unit(kategori)]
    kunci = str(grade).strip().lower()
    if kunci in tabel:
        return tabel[kunci]
    log.warning(
        "grade %r tidak ada di RASIO_GRADE[%s] (yang ada: %s); dipakai 1,0. "
        "Untuk grade di luar reguler/premium, isi `hpp_per_grade` — menebak "
        "rasionya bukan urusan mesin ini.",
        grade, kategori, ", ".join(tabel))
    return 1.0


# Deteksi variasi lazim dari katalog. docs/MODEL_HARGA.md §3.5 mengandaikan
# kolom `specs` berisi "Warna"/"Ukuran"; kolom itu TIDAK ADA di
# merged.parquet (25 kolom, tak satu pun `specs`). Jadi deteksinya dari judul —
# lebih lemah, dan persentasenya dihitung ulang atas tetangga yang benar-benar
# ditemukan, bukan disalin dari tabel doc yang sumbernya tidak bisa dilacak.
_POLA_VARIASI: dict[str, re.Pattern] = {
    "warna": re.compile(
        r"\b(hitam|putih|merah|biru|hijau|kuning|coklat|cokelat|abu|navy|"
        r"maroon|pink|ungu|krem|gold|silver|tosca|mocca|warna)\b", re.IGNORECASE),
    "ukuran": re.compile(
        r"\b(all\s?size|allsize|ukuran|size|xs|xl|xxl|2xl|3xl|4xl|5xl)\b",
        re.IGNORECASE),
    "berat_isi": re.compile(r"\d+\s*(kg|gr|gram|g|ml|liter|lt|l)\b", re.IGNORECASE),
    "rasa": re.compile(r"\b(rasa|varian rasa|flavor)\b", re.IGNORECASE),
    "kapasitas": re.compile(r"\d+\s*(gb|tb)\b", re.IGNORECASE),
}

_LABEL_VARIASI = {
    "warna": ("Warna/motif", "harga sama untuk semua varian"),
    "ukuran": ("Ukuran (S/M/L/XL)", "S–XL biasanya satu harga, XXL ke atas naik"),
    "berat_isi": ("Berat/isi kemasan", "harga berbeda, ikut diskon volume"),
    "rasa": ("Rasa", "harga sama untuk semua varian"),
    "kapasitas": ("Kapasitas", "harga berbeda per kapasitas"),
}


def deteksi_variasi_katalog(judul: list[str], minimal_pct: float = 20.0) -> dict[str, Any]:
    """Variasi apa yang lazim dipakai produk serupa di katalog.

    Dihitung atas judul tetangga yang ditemukan retrieval. `dari_n` ikut
    dikembalikan supaya pemanggil bisa jujur: 3 dari 5 tetangga bukan "60% pasar".
    """
    n = len(judul)
    if not n:
        return {"dari_n": 0, "pola": [], "saran": []}

    pola = []
    for nama, rx in _POLA_VARIASI.items():
        cocok = sum(1 for j in judul if rx.search(str(j)))
        if not cocok:
            continue
        label, efek = _LABEL_VARIASI[nama]
        pola.append({
            "jenis": nama,
            "label": label,
            "efek_harga": efek,
            "jumlah": cocok,
            "persen": round(cocok / n * 100, 1),
        })
    pola.sort(key=lambda p: -p["jumlah"])

    saran = [f"{p['label']} — {p['persen']:.0f}% produk serupa punya ini "
             f"({p['efek_harga']})"
             for p in pola if p["persen"] >= minimal_pct]
    return {"dari_n": n, "pola": pola, "saran": saran}


# ─── §3.3 Keputusan Harga per Zona ───────────────────────────────────────────

def putuskan_harga(bep: float, p25: float, median: float, p75: float,
                   kategori: str, hpp_per_unit: int, platform: str,
                   omzet_tahunan: int = 0, is_ppn: bool = False) -> dict[str, Any]:
    """Zona kompetitif → harga rekomendasi/agresif/premium + peringatan + saran.

    Dipisah dari `PricingEngine.hitung()` supaya harga per varian (§3.5) memakai
    logika yang PERSIS sama, bukan jalur kedua yang lama-lama menyimpang. Varian
    memanggilnya dengan BEP dan kuantil pasar yang sudah diskalakan ke ukuran
    varian itu.
    """
    # ── Zona ──
    # `median <= 0` menggantikan `not len(harga)` versi method: di `hitung()`
    # ketiga kuantil memang di-set 0,0 persis ketika tetangga tidak cukup, jadi
    # syaratnya setara — tanpa menyeret Series pandas ke dalam fungsi murni ini.
    if median <= 0:
        zona = "TIDAK_ADA_DATA"
    else:
        zona = tentukan_zona(bep, p25, median, p75)

    # ── Harga berdasarkan zona ──
    peringatan: str | None = None
    saran: list[str] = []
    margin_tabel = MARGIN_DEFAULT.get(kategori, MARGIN_DEFAULT["lainnya"])

    if zona == "BAHAYA":
        harga_rekom = bulatkan_psikologis(int(p75))
        peringatan = (
            f"⚠️ Modal terlalu tinggi! BEP Rp{int(bep):,} > harga tertinggi "
            f"pasar Rp{int(p75):,}. Produk serupa rata-rata Rp{int(median):,}."
        )
        # Hitung BEP di platform lain untuk saran
        bep_lain = []
        for plat_lain in BIAYA_PLATFORM:
            if plat_lain == platform:
                continue
            bep_l, pct_l, _ = hitung_bep(hpp_per_unit, plat_lain, kategori,
                                          omzet_tahunan, is_ppn)
            bep_lain.append((plat_lain, bep_l, pct_l))
        bep_lain.sort(key=lambda x: x[1])

        saran = ["Cari supplier lebih murah untuk turunkan HPP"]
        for pl, bl, pl_pct in bep_lain:
            label = BIAYA_PLATFORM[pl]["label"]
            if bl < p75:
                saran.append(f"Pindah ke {label} (biaya {pl_pct:.1f}%) → "
                             f"BEP Rp{int(bl):,}, masih bisa untung")
            else:
                saran.append(f"{label} (biaya {pl_pct:.1f}%) → "
                             f"BEP Rp{int(bl):,}, masih terlalu tinggi")
        saran.extend([
            "Tambah value: kemasan premium, bundling, bonus",
            "Jual langsung (Instagram/WhatsApp) tanpa biaya platform",
        ])

    elif zona == "KETAT":
        rekom = max(bep * 1.15, median)
        rekom = min(rekom, p75)
        harga_rekom = bulatkan_psikologis(int(rekom))
        peringatan = (
            f"💡 Margin tipis. BEP Rp{int(bep):,} mendekati median pasar "
            f"Rp{int(median):,}. Pertimbangkan turunkan HPP."
        )
        saran = ["Cari supplier lebih murah",
                  "Naikkan volume penjualan untuk turunkan biaya per unit"]

    elif zona == "WAJAR":
        rekom = max(median, bep * 1.20)
        rekom = min(rekom, p75)
        harga_rekom = bulatkan_psikologis(int(rekom))

    elif zona == "BAGUS":
        harga_rekom = bulatkan_psikologis(int(median))

    else:  # TIDAK_ADA_DATA
        harga_rekom = bulatkan_psikologis(int(bep * (1 + margin_tabel["mid"])))
        peringatan = "Tidak ada data produk serupa. Harga berdasarkan estimasi margin."
        saran = ["Coba deskripsi yang lebih spesifik untuk hasil lebih akurat"]

    # Pastikan selalu >= BEP
    harga_rekom = max(harga_rekom, bulatkan_psikologis(int(bep)) + 100)

    # ── Tiga opsi ──
    if zona != "TIDAK_ADA_DATA" and p25 > 0:
        harga_agresif = bulatkan_psikologis(int(max(p25, bep * 1.10)))
        harga_premium = bulatkan_psikologis(int(min(p75 * 1.1, bep * 2.5)))
    else:
        harga_agresif = bulatkan_psikologis(int(bep * (1 + margin_tabel["lo"])))
        harga_premium = bulatkan_psikologis(int(bep * (1 + margin_tabel["hi"])))

    harga_agresif = max(harga_agresif, bulatkan_psikologis(int(bep)) + 100)
    harga_premium = max(harga_premium, harga_rekom)


    return {
        "zona": zona,
        "harga_rekomendasi": harga_rekom,
        "harga_agresif": harga_agresif,
        "harga_premium": harga_premium,
        "peringatan": peringatan,
        "saran": saran,
    }


def rincian_biaya(harga: int, hpp_per_unit: int, platform: str, kategori: str,
                  omzet_tahunan: int = 0, is_ppn: bool = False) -> dict[str, int]:
    """Breakdown per unit terjual pada satu harga: HPP, komisi, ongkir, pajak, laba."""
    harga_rekom = harga        # nama lokal warisan, dipertahankan agar logikanya utuh
    # ── Breakdown ──
    biaya_cfg = BIAYA_PLATFORM.get(platform, BIAYA_PLATFORM["tokopedia"])
    komisi_pct = biaya_cfg["komisi_pct"][kategori_tarif(kategori)]
    ongkir_pct = biaya_cfg["gratis_ongkir_pct"]
    komisi_nom = int(harga_rekom * komisi_pct / 100)
    cap_cfg = biaya_cfg.get("fee_cap")
    if cap_cfg:
        komisi_nom = min(komisi_nom, cap_cfg)
    ongkir_nom = int(harga_rekom * ongkir_pct / 100)
    proses_nom = biaya_cfg["biaya_proses"]

    pajak_pct_eff = 0.0
    if omzet_tahunan >= PAJAK["bebas_omzet"]:
        pajak_pct_eff = PAJAK["pph_final_pct"]
    pajak_nom = int(harga_rekom * pajak_pct_eff / 100)

    # PPN ikut menaikkan BEP di hitung_bep(), jadi ia harus ikut mengurangi
    # laba di sini juga. Sebelumnya tidak: BEP naik 11% tapi "Laba bersih"
    # tetap dihitung seolah PPN tidak ada, sehingga penjual PKP melihat laba
    # yang lebih besar dari kenyataan.
    ppn_nom = int(harga_rekom * PAJAK["ppn_pct"] / 100) if is_ppn else 0

    laba = (harga_rekom - hpp_per_unit - komisi_nom - ongkir_nom
            - proses_nom - pajak_nom - ppn_nom)
    breakdown = {
        "HPP": hpp_per_unit,
        f"Komisi {biaya_cfg['label']} ({komisi_pct}%)": komisi_nom,
    }
    if ongkir_nom > 0:
        breakdown[f"Gratis Ongkir ({ongkir_pct}%)"] = ongkir_nom
    if proses_nom > 0:
        breakdown["Biaya proses"] = proses_nom
    if pajak_nom > 0:
        breakdown[f"PPh Final ({pajak_pct_eff}%)"] = pajak_nom
    if ppn_nom > 0:
        breakdown[f"PPN ({PAJAK['ppn_pct']}%)"] = ppn_nom
    breakdown["Laba bersih"] = laba


    return breakdown


# ─── §3.5 Harga per Varian ───────────────────────────────────────────────────

def hitung_varian(hpp_dasar: int, harga_dasar: int, p25: float, median: float,
                  p75: float, kategori: str, platform: str,
                  variasi_warna: list[str] | None = None,
                  variasi_ukuran: list[str] | None = None,
                  hpp_per_ukuran: dict[str, int] | None = None,
                  variasi_grade: list[str] | None = None,
                  hpp_per_grade: dict[str, int] | None = None,
                  omzet_tahunan: int = 0, is_ppn: bool = False) -> list[VariantPrice]:
    """Daftar harga per varian, mengikuti tiga perlakuan berbeda di §3.5.

    - **Warna/motif** → harga SAMA. Tidak ada perhitungan ulang sama sekali.
    - **Ukuran/isi** → harga BERBEDA proporsional, memakai kurva diskon volume
      (`ANCHOR_UKURAN`) atau konvensi ukuran fashion (`ATURAN_UKURAN_FASHION`).
    - **Material/grade** → harga BERBEDA tidak proporsional. Kalau penjual mengisi
      `hpp_per_grade`, dihitung penuh dari HPP-nya sendiri; kalau tidak, hanya
      diestimasi dari `RASIO_GRADE` dan varian itu ditandai sebagai estimasi.

    Varian pertama di `variasi_ukuran` dianggap varian DASAR — yaitu ukuran yang
    HPP-nya dilaporkan penjual. Varian lain diskalakan relatif terhadapnya.

    Asumsi yang perlu ikut dibaca: kuantil pasar ikut diskalakan dengan faktor
    yang sama. Retrieval tidak sadar ukuran, jadi P25/median/P75 mewakili campuran
    ukuran apa adanya; kita memperlakukannya seolah mewakili ukuran dasar. Tanpa
    retrieval yang sadar ukuran, tidak ada dasar yang lebih baik — tapi ini
    asumsi, bukan hasil pengukuran.
    """
    varian: list[VariantPrice] = []

    def _rakit(label: str, jenis: str, hpp_v: int, harga_v: int,
               bep_v: float, catatan: str | None) -> VariantPrice:
        return VariantPrice(
            label=label,
            jenis=jenis,
            harga_minimum=int(bep_v),
            harga_rekomendasi=harga_v,
            harga_agresif=0,
            harga_premium=0,
            hpp_unit=hpp_v,
            margin_persen=round((harga_v - hpp_v) / max(hpp_v, 1) * 100, 1),
            komponen=rincian_biaya(harga_v, hpp_v, platform, kategori,
                                   omzet_tahunan, is_ppn),
            catatan=catatan,
        )

    # ── Ukuran/isi ──
    if variasi_ukuran:
        dasar = variasi_ukuran[0]
        for label in variasi_ukuran:
            if hpp_per_ukuran and label in hpp_per_ukuran:
                hpp_v = int(hpp_per_ukuran[label])
                rasio = hpp_v / max(hpp_dasar, 1)
                catatan = "HPP diisi penjual"
            else:
                rasio = faktor_relatif(label, dasar)
                hpp_v = int(hpp_dasar * rasio)
                catatan = (f"faktor {rasio:.2f}× dari varian dasar {dasar} "
                           f"(estimasi, lihat ANCHOR_UKURAN)")

            bep_v, _, _ = hitung_bep(hpp_v, platform, kategori, omzet_tahunan, is_ppn)
            putusan = putuskan_harga(bep_v, p25 * rasio, median * rasio, p75 * rasio,
                                     kategori, hpp_v, platform, omzet_tahunan, is_ppn)
            v = _rakit(label, "ukuran", hpp_v, putusan["harga_rekomendasi"],
                       bep_v, catatan)
            v.harga_agresif = putusan["harga_agresif"]
            v.harga_premium = putusan["harga_premium"]
            varian.append(v)

    # ── Warna/motif: satu harga untuk semua ──
    if variasi_warna:
        info = variasi_kosmetik(harga_dasar, variasi_warna)
        bep_v, _, _ = hitung_bep(hpp_dasar, platform, kategori, omzet_tahunan, is_ppn)
        for label in variasi_warna:
            varian.append(_rakit(label, "warna", hpp_dasar, harga_dasar, bep_v,
                                 info["catatan"]))

    # ── Material/grade ──
    if variasi_grade:
        for label in variasi_grade:
            if hpp_per_grade and label in hpp_per_grade:
                hpp_v = int(hpp_per_grade[label])
                bep_v, _, _ = hitung_bep(hpp_v, platform, kategori,
                                         omzet_tahunan, is_ppn)
                # Pasar TIDAK diskalakan di sini: grade premium memang mestinya
                # laku lebih mahal, tapi katalog tidak punya label grade sehingga
                # tidak ada angka untuk menskalakannya. Konsekuensinya jujur —
                # grade ber-HPP tinggi akan jatuh ke zona KETAT/BAHAYA, dan itu
                # memang informasi yang perlu dilihat penjual.
                putusan = putuskan_harga(bep_v, p25, median, p75, kategori, hpp_v,
                                         platform, omzet_tahunan, is_ppn)
                v = _rakit(label, "grade", hpp_v, putusan["harga_rekomendasi"],
                           bep_v, "HPP diisi penjual")
                v.harga_agresif = putusan["harga_agresif"]
                v.harga_premium = putusan["harga_premium"]
            else:
                rasio = rasio_grade(kategori, label)
                harga_v = bulatkan_psikologis(int(harga_dasar * rasio))
                bep_v, _, _ = hitung_bep(hpp_dasar, platform, kategori,
                                         omzet_tahunan, is_ppn)
                v = _rakit(label, "grade", hpp_dasar, harga_v, bep_v,
                           f"ESTIMASI {rasio:.2f}× harga reguler; HPP dianggap "
                           f"tidak berubah, jadi margin di baris ini terlalu "
                           f"optimis. Isi hpp_per_grade untuk angka sebenarnya.")
            varian.append(v)

    return varian


def susun_penjelasan(zona: str, kategori: str, satuan_jual: str, platform_label: str,
                     hpp_per_unit: int, bep: float, harga_rekom: int,
                     p25: float, median: float, p75: float, jumlah_kompetitor: int,
                     margin_persen: float, breakdown: dict[str, int]) -> str:
    """Narasi bahasa Indonesia: kenapa harganya segitu (§5.2 `penjelasan`).

    Ditulis untuk dibaca penjual, bukan untuk log. Setiap angka yang disebut di
    sini berasal dari hasil hitung yang sama, tidak ada yang dikarang ulang.
    """
    laba = breakdown.get("Laba bersih", 0)
    potongan = sum(v for k, v in breakdown.items() if k not in ("HPP", "Laba bersih"))

    if zona == "TIDAK_ADA_DATA":
        return (
            f"Belum ada produk serupa di katalog untuk dijadikan pembanding, jadi "
            f"harga Rp{harga_rekom:,} per {satuan_jual} ini dihitung dari modal "
            f"kamu saja: HPP Rp{hpp_per_unit:,} ditambah biaya {platform_label} "
            f"sampai balik modal di Rp{int(bep):,}, lalu ditambah margin bawaan "
            f"kategori '{kategori}'. Angka margin bawaan itu belum diukur dari "
            f"data — perlakukan harga ini sebagai titik awal, lalu sesuaikan "
            f"setelah lihat harga pesaing sendiri."
        )

    dasar = {
        "BAGUS": (f"Modal kamu rendah dibanding pasar, jadi harga diambil dari "
                  f"median pasar Rp{int(median):,} — bukan dari modal. Kamu bisa "
                  f"ikut harga yang sudah biasa dibayar pembeli dan tetap untung besar."),
        "WAJAR": (f"Posisi kamu kompetitif. Harga diambil dari median pasar "
                  f"Rp{int(median):,}, dengan jaminan tetap di atas titik balik "
                  f"modal Rp{int(bep):,}."),
        "KETAT": (f"Titik balik modal kamu Rp{int(bep):,} sudah melewati median "
                  f"pasar Rp{int(median):,}, jadi harga didorong ke atas sedikit "
                  f"dan marginnya tipis."),
        "BAHAYA": (f"Titik balik modal kamu Rp{int(bep):,} lebih tinggi dari "
                   f"harga termahal di pasar Rp{int(p75):,}. Di harga pasar mana "
                   f"pun kamu tidak untung, jadi angka di bawah ini bukan "
                   f"rekomendasi — ia batas atas pasar, ditampilkan supaya kamu "
                   f"tahu jaraknya."),
    }[zona]

    return (
        f"Produk ini masuk kategori '{kategori}' dan dibandingkan dengan "
        f"{jumlah_kompetitor} produk serupa di katalog, yang harganya berkisar "
        f"Rp{int(p25):,}–Rp{int(p75):,} (median Rp{int(median):,}). {dasar} "
        f"Dari harga Rp{harga_rekom:,} per {satuan_jual}, modal kamu "
        f"Rp{hpp_per_unit:,} dan potongan {platform_label} Rp{potongan:,}, "
        f"sisanya laba bersih Rp{laba:,} ({margin_persen:.1f}% dari modal). "
        f"Di bawah Rp{int(bep):,} kamu rugi."
    )


# ─── Pricing Engine ──────────────────────────────────────────────────────────

class PricingEngine:
    """Mesin penentuan harga market-first.

    Muat dataset sekali, lalu panggil .hitung() berulang kali.
    """

    def __init__(self, sumber: Path | None = None):
        src = sumber or SUMBER
        if not src.exists():
            raise FileNotFoundError(
                f"Dataset tidak ditemukan: {src}\n"
                "Jalankan scripts/localize_merged.py dulu, atau arahkan --sumber ke parquet yang ada."
            )
        self.df = pd.read_parquet(src)
        # Pastikan kolom yang dibutuhkan ada
        if "title" not in self.df.columns:
            raise ValueError(f"Kolom 'title' tidak ditemukan di {src}")

        # Bersihkan judul untuk indexing
        self.df["_judul"] = self.df["title"].astype(str).str.strip()
        self.df["_harga"] = pd.to_numeric(self.df["price"], errors="coerce")

        self.indeks = Indeks(self.df["_judul"].tolist())
        print(f"PricingEngine: {len(self.df):,} produk, "
              f"{len(self.indeks.inverted):,} istilah unik")

    def hitung(self, deskripsi: str, hpp_per_unit: int, platform: str = "tokopedia",
               k: int = 10, min_skor: float = 2.0,
               omzet_tahunan: int = 0, is_ppn: bool = False,
               satuan_jual: str = "pcs",
               variasi_warna: list[str] | None = None,
               variasi_ukuran: list[str] | None = None,
               hpp_per_ukuran: dict[str, int] | None = None,
               variasi_grade: list[str] | None = None,
               hpp_per_grade: dict[str, int] | None = None) -> PricingResult:
        """Hitung harga rekomendasi dengan logika market-first.

        Args:
            deskripsi: teks deskripsi produk (dari VLM atau langsung user)
            hpp_per_unit: HPP per 1 unit jual (sudah dikonversi)
            platform: "tokopedia" | "shopee" | "blibli"
            k: berapa tetangga terdekat diambil
            min_skor: skor minimum untuk menggunakan data tetangga
            omzet_tahunan: estimasi omzet per tahun (untuk cek pajak)
            is_ppn: apakah sudah PKP (wajib PPN)?
            satuan_jual: nama unit yang dijual ("pcs", "bungkus", "botol")
            variasi_warna: daftar warna/motif — harga sama untuk semua (§3.5)
            variasi_ukuran: daftar ukuran/isi — harga proporsional; elemen
                pertama dianggap ukuran yang HPP-nya dilaporkan penjual
            hpp_per_ukuran: HPP asli per ukuran, kalau penjual tahu
            variasi_grade: daftar grade/material — harga tidak proporsional
            hpp_per_grade: HPP asli per grade, kalau penjual tahu
        """
        # ── Cari produk serupa ──
        cocok = self.indeks.cari(deskripsi, k)
        skor_teratas = cocok[0][1] if cocok else 0.0
        pakai = skor_teratas >= min_skor

        if pakai:
            idx_tetangga = [i for i, _ in cocok]
            tetangga = self.df.iloc[idx_tetangga]
        else:
            tetangga = self.df.iloc[[]]

        # ── Kategori ──
        kategori = "lainnya"
        if pakai and len(tetangga) and "kategori_umkm" in tetangga.columns:
            modus = tetangga["kategori_umkm"].mode()
            if len(modus):
                kategori = str(modus.iloc[0])

        # ── Harga pasar (filter outlier) ──
        if pakai and len(tetangga):
            harga = pd.to_numeric(tetangga["price"], errors="coerce").dropna()
            harga = harga[harga > 0]
            if len(harga) >= 4:
                q05, q95 = harga.quantile(0.05), harga.quantile(0.95)
                harga = harga[(harga >= q05) & (harga <= q95)]
        else:
            harga = pd.Series(dtype=float)

        if len(harga) >= 2:
            p25 = float(harga.quantile(0.25))
            median = float(harga.median())
            p75 = float(harga.quantile(0.75))
        else:
            p25, median, p75 = 0.0, 0.0, 0.0

        # ── BEP ──
        bep, total_pct, biaya_flat = hitung_bep(
            hpp_per_unit, platform, kategori, omzet_tahunan, is_ppn)

        # ── Zona & harga (§3.3) ──
        putusan = putuskan_harga(bep, p25, median, p75, kategori, hpp_per_unit,
                                 platform, omzet_tahunan, is_ppn)
        zona = putusan["zona"]
        harga_rekom = putusan["harga_rekomendasi"]
        harga_agresif = putusan["harga_agresif"]
        harga_premium = putusan["harga_premium"]
        peringatan = putusan["peringatan"]
        saran = putusan["saran"]
        # ── Margin ──
        margin_persen = (harga_rekom - hpp_per_unit) / max(hpp_per_unit, 1) * 100

        # ── Breakdown ──
        breakdown = rincian_biaya(harga_rekom, hpp_per_unit, platform, kategori,
                                  omzet_tahunan, is_ppn)
        # ── Produk serupa ──
        produk_serupa = []
        if pakai and len(tetangga):
            for _, r in tetangga.head(5).iterrows():
                produk_serupa.append({
                    "judul": str(r.get("title", ""))[:60],
                    "harga": int(r.get("price", 0)),
                    "source": str(r.get("source", "")),
                })

        # ── Perbandingan platform ──
        perbandingan = []
        for plat_nama in BIAYA_PLATFORM:
            bep_p, pct_p, _ = hitung_bep(hpp_per_unit, plat_nama, kategori,
                                          omzet_tahunan, is_ppn)
            perbandingan.append({
                "platform": BIAYA_PLATFORM[plat_nama]["label"],
                "bep": int(bep_p),
                "total_pct": round(pct_p, 1),
                "bisa_untung": bep_p < p75 if p75 > 0 else True,
            })
        perbandingan.sort(key=lambda x: x["bep"])

        # ── §3.5 Harga per varian ──
        varian = hitung_varian(
            hpp_dasar=hpp_per_unit, harga_dasar=harga_rekom,
            p25=p25, median=median, p75=p75,
            kategori=kategori, platform=platform,
            variasi_warna=variasi_warna, variasi_ukuran=variasi_ukuran,
            hpp_per_ukuran=hpp_per_ukuran, variasi_grade=variasi_grade,
            hpp_per_grade=hpp_per_grade,
            omzet_tahunan=omzet_tahunan, is_ppn=is_ppn,
        )

        # ── §3.5 Variasi yang lazim dipakai produk serupa ──
        variasi_disarankan = deteksi_variasi_katalog(
            tetangga["_judul"].tolist() if pakai and len(tetangga) else [])

        # ── §5.2 Narasi ──
        penjelasan = susun_penjelasan(
            zona=zona, kategori=kategori, satuan_jual=satuan_jual,
            platform_label=BIAYA_PLATFORM.get(platform, {}).get("label", platform),
            hpp_per_unit=hpp_per_unit, bep=bep, harga_rekom=harga_rekom,
            p25=p25, median=median, p75=p75, jumlah_kompetitor=len(harga),
            margin_persen=margin_persen, breakdown=breakdown,
        )

        return PricingResult(
            harga_minimum=int(bep),
            harga_rekomendasi=harga_rekom,
            harga_agresif=harga_agresif,
            harga_premium=harga_premium,
            zona=zona,
            zona_emoji=ZONA_EMOJI.get(zona, "⚪"),
            peringatan=peringatan,
            saran=saran,
            harga_pasar_p25=int(p25),
            harga_pasar_median=int(median),
            harga_pasar_p75=int(p75),
            jumlah_kompetitor=len(harga),
            hpp_per_unit=hpp_per_unit,
            margin_persen=round(margin_persen, 1),
            kategori=kategori,
            platform=BIAYA_PLATFORM.get(platform, {}).get("label", platform),
            total_potongan_pct=round(total_pct, 1),
            breakdown=breakdown,
            produk_serupa=produk_serupa,
            perbandingan_platform=perbandingan,
            varian=varian,
            satuan_jual=satuan_jual,
            variasi_disarankan=variasi_disarankan,
            penjelasan=penjelasan,
        )

    def hitung_dari(self, req: PricingRequest, k: int = 10,
                    min_skor: float = 2.0) -> PricingResult:
        """Jalur `PricingRequest` → `PricingResult` seperti di §5.1–5.2.

        `hitung()` menerima HPP yang sudah jadi; method ini yang mengerjakan
        konversi satuan dan meneruskan seluruh field variasi, supaya pemanggil
        tidak perlu tahu urutan argumennya.
        """
        return self.hitung(
            deskripsi=req.deskripsi_produk,
            hpp_per_unit=req.hpp_per_unit,
            platform=req.platform,
            k=k, min_skor=min_skor,
            omzet_tahunan=req.omzet_tahunan,
            is_ppn=req.is_ppn,
            satuan_jual=req.satuan_jual,
            variasi_warna=req.variasi_warna,
            variasi_ukuran=req.variasi_ukuran,
            hpp_per_ukuran=req.hpp_per_ukuran,
            variasi_grade=req.variasi_grade,
            hpp_per_grade=req.hpp_per_grade,
        )


# ─── CLI ─────────────────────────────────────────────────────────────────────

def _daftar(teks: str | None) -> list[str] | None:
    """--warna "Hitam,Putih,Navy" → ["Hitam", "Putih", "Navy"]"""
    if not teks:
        return None
    isi = [x.strip() for x in teks.split(",") if x.strip()]
    return isi or None


def _peta(teks: str | None) -> dict[str, int] | None:
    """--hpp-ukuran "S=25000,XXL=30000" → {"S": 25000, "XXL": 30000}"""
    if not teks:
        return None
    out: dict[str, int] = {}
    for bagian in teks.split(","):
        bagian = bagian.strip()
        if not bagian:
            continue
        if "=" not in bagian:
            raise SystemExit(f"format salah: {bagian!r}, harusnya LABEL=HARGA")
        label, nilai = bagian.split("=", 1)
        out[label.strip()] = int(nilai.strip())
    return out or None


def main():
    ap = argparse.ArgumentParser(
        description="Rekomendasi harga jual e-commerce untuk UMKM (market-first).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Contoh:
  python scripts/pricing_engine.py "kaos polos pria" --hpp 25000
  python scripts/pricing_engine.py "keripik pisang 250g" --hpp 50000 --satuan kg --jumlah 5 --jual-per 250 --jual-satuan g
  python scripts/pricing_engine.py "serum niacinamide 30ml" --hpp 30000 --platform shopee
  python scripts/pricing_engine.py "tas kulit handmade" --hpp 150000 --platform shopee

Variasi (§3.5) dan satuan modal (§3.4):
  # warna: satu harga untuk semua
  python scripts/pricing_engine.py "kaos polos pria" --hpp 25000 \\
      --warna "Hitam,Putih,Navy" --ukuran "M,L,XL,XXL,3XL"
  # isi kemasan: harga proporsional, ikut diskon volume
  python scripts/pricing_engine.py "keripik pisang" --hpp 50000 --jumlah-unit 20 \\
      --packing 1500 --ukuran "100g,250g,500g" --satuan-jual bungkus
  # grade dengan HPP masing-masing
  python scripts/pricing_engine.py "tas rajut" --hpp 60000 \\
      --grade "Reguler,Premium" --hpp-grade "Reguler=60000,Premium=95000"
  # tanya balik satuan modal sebelum menghitung
  python scripts/pricing_engine.py "keripik pisang" --hpp 50000 --tanya-unit
""")
    ap.add_argument("deskripsi", help="deskripsi produk (seperti yang ditulis VLM)")
    ap.add_argument("--hpp", type=int, required=True, help="modal / HPP total (Rupiah)")
    ap.add_argument("--platform", default="tokopedia",
                    choices=list(BIAYA_PLATFORM.keys()),
                    help="platform tujuan (default: tokopedia)")
    ap.add_argument("--satuan", default="pcs", help="satuan HPP: pcs, kg, lusin, dll")
    ap.add_argument("--jumlah", type=float, default=1.0, help="berapa satuan dari HPP")
    ap.add_argument("--jual-per", type=float, default=None,
                    help="isi per kemasan jual (misal: 250 untuk 250g)")
    ap.add_argument("--jual-satuan", default=None,
                    help="satuan kemasan jual (g, ml, dll)")
    ap.add_argument("--packing", type=int, default=0, help="biaya packing per unit")
    ap.add_argument("--produksi", type=int, default=0,
                    help="biaya produksi per unit (selain bahan)")
    ap.add_argument("--omzet", type=int, default=0,
                    help="estimasi omzet tahunan (untuk cek pajak)")
    ap.add_argument("--ppn", action="store_true",
                    help="penjual sudah PKP, harga kena PPN efektif 11%%")
    ap.add_argument("--jumlah-unit", type=float, default=None,
                    help="modal itu jadi berapa unit jual (§3.4; "
                         "menang atas --satuan/--jumlah)")
    ap.add_argument("--satuan-jual", default="pcs",
                    help="nama unit yang dijual: pcs, bungkus, botol")
    ap.add_argument("--warna", default=None,
                    help='variasi warna/motif, dipisah koma — harga SAMA '
                         '(contoh: "Hitam,Putih,Navy")')
    ap.add_argument("--ukuran", default=None,
                    help='variasi ukuran/isi, dipisah koma — harga BERBEDA. '
                         'Elemen pertama = ukuran yang HPP-nya kamu isi '
                         '(contoh: "100g,250g,500g" atau "M,L,XL,XXL")')
    ap.add_argument("--hpp-ukuran", default=None,
                    help='HPP asli per ukuran (contoh: "S=25000,XXL=30000")')
    ap.add_argument("--grade", default=None,
                    help='variasi grade/material (contoh: "Reguler,Premium")')
    ap.add_argument("--hpp-grade", default=None,
                    help='HPP asli per grade (contoh: "Reguler=25000,Premium=40000")')
    ap.add_argument("--tanya-unit", action="store_true",
                    help="tampilkan pertanyaan klarifikasi satuan modal (§3.4) "
                         "lalu berhenti, tanpa menghitung harga")
    ap.add_argument("--sumber", default=None, help="path ke parquet dataset")
    ap.add_argument("--json", action="store_true", help="output JSON, bukan tabel")
    ap.add_argument("--semua-platform", action="store_true",
                    help="hitung untuk semua platform sekaligus")
    args = ap.parse_args()

    req = PricingRequest(
        deskripsi_produk=args.deskripsi,
        hpp_total=args.hpp,
        platform=args.platform,
        hpp_satuan=args.satuan,
        hpp_jumlah=args.jumlah,
        jual_per_unit=args.jual_per,
        jual_satuan=args.jual_satuan,
        biaya_packing=args.packing,
        biaya_produksi=args.produksi,
        omzet_tahunan=args.omzet,
        is_ppn=args.ppn,
        jumlah_unit_jual=args.jumlah_unit,
        satuan_jual=args.satuan_jual,
        variasi_warna=_daftar(args.warna),
        variasi_ukuran=_daftar(args.ukuran),
        hpp_per_ukuran=_peta(args.hpp_ukuran),
        variasi_grade=_daftar(args.grade),
        hpp_per_grade=_peta(args.hpp_grade),
    )

    sumber = Path(args.sumber) if args.sumber else None
    engine = PricingEngine(sumber)

    if args.tanya_unit:
        # Kategori ditebak dari tetangga terdekat — cuma untuk memilih pertanyaan
        # mana yang relevan, bukan untuk menghitung apa pun.
        pratinjau = engine.hitung(args.deskripsi, hpp_per_unit=1,
                                  platform=args.platform)
        tanya = pertanyaan_unit(pratinjau.kategori, args.hpp)
        print(f"\nBarang dikenali sebagai kategori: {pratinjau.kategori}")
        if tanya is None:
            print("Kategori ini praktis selalu dijual per pcs — "
                  "tidak perlu klarifikasi satuan.\n")
            return
        print(f"\n  {tanya['pertanyaan']}")
        print(f"    Satuan beli yang lazim: {', '.join(tanya['satuan_beli'])}")
        print(f"    Satuan jual yang lazim: {', '.join(tanya['satuan_jual'])}")
        print(f"\n  {tanya['default']}")
        print("\n  Jawab lewat flag: --jumlah-unit N   (atau --satuan/--jumlah)\n")
        return

    hpp = req.hpp_per_unit
    print(f"\nHPP per unit jual: Rp{hpp:,} "
          f"(dari Rp{req.hpp_total:,} / {req.hpp_jumlah} {req.hpp_satuan}"
          f"{f' → {req.jual_per_unit}{req.jual_satuan}/kemasan' if req.jual_per_unit else ''})\n")

    platforms = list(BIAYA_PLATFORM.keys()) if args.semua_platform else [args.platform]

    for plat in platforms:
        req.platform = plat
        result = engine.hitung_dari(req)

        if args.json:
            out = asdict(result)
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print(result.cetak())
            print()

        if result.produk_serupa:
            print("  Produk serupa di katalog:")
            for p in result.produk_serupa:
                print(f"    Rp{p['harga']:>9,}  {p['source']:<12} {p['judul']}")
            print()


if __name__ == "__main__":
    main()
