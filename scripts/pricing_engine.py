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
        # Komisi Dinamis per 18 Mei 2026 (sudah termasuk pajak)
        "komisi_pct": {
            "fashion_perawatan":   8.0,
            "elektronik_gadget":   3.5,
            "makanan_minuman":     6.5,
            "skincare_kecantikan": 7.0,
            "dapur_rumah":         8.0,
            "kesehatan_olahraga":  6.5,
            "kriya_rumah":         8.0,
            "minuman_herbal":      6.5,
            "lainnya":             6.5,
        },
        "gratis_ongkir_pct": 0.0,   # sudah termasuk di komisi dinamis
        "biaya_proses": 1250,        # Rp1.250/pesanan (flat)
        "fee_cap": 80_000,           # maks komisi per item (Juli 2026)
        "label": "Tokopedia",
    },
    "shopee": {
        # Biaya Admin Star/Star+ per 2 Mei 2026
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

# Pajak — PP 20/2026
PAJAK = {
    "pph_final_pct": 0.5,         # 0,5% dari omzet bruto
    "bebas_omzet": 500_000_000,   # Rp500 juta pertama BEBAS pajak
    "ppn_pct": 12.0,              # hanya kalau PKP (omzet > Rp4,8M)
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

    @property
    def hpp_per_unit(self) -> int:
        """Konversi modal grosir → HPP per 1 unit jual."""
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
               omzet_tahunan: int = 0, is_ppn: bool = False) -> PricingResult:
        """Hitung harga rekomendasi dengan logika market-first.

        Args:
            deskripsi: teks deskripsi produk (dari VLM atau langsung user)
            hpp_per_unit: HPP per 1 unit jual (sudah dikonversi)
            platform: "tokopedia" | "shopee" | "blibli"
            k: berapa tetangga terdekat diambil
            min_skor: skor minimum untuk menggunakan data tetangga
            omzet_tahunan: estimasi omzet per tahun (untuk cek pajak)
            is_ppn: apakah sudah PKP (wajib PPN)?
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

        # ── Zona ──
        if not len(harga) or median <= 0:
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

        # ── Margin ──
        margin_persen = (harga_rekom - hpp_per_unit) / max(hpp_per_unit, 1) * 100

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

        laba = harga_rekom - hpp_per_unit - komisi_nom - ongkir_nom - proses_nom - pajak_nom
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
        breakdown["Laba bersih"] = laba

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
        )


# ─── CLI ─────────────────────────────────────────────────────────────────────

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
    )

    sumber = Path(args.sumber) if args.sumber else None
    engine = PricingEngine(sumber)

    hpp = req.hpp_per_unit
    print(f"\nHPP per unit jual: Rp{hpp:,} "
          f"(dari Rp{req.hpp_total:,} / {req.hpp_jumlah} {req.hpp_satuan}"
          f"{f' → {req.jual_per_unit}{req.jual_satuan}/kemasan' if req.jual_per_unit else ''})\n")

    platforms = list(BIAYA_PLATFORM.keys()) if args.semua_platform else [args.platform]

    for plat in platforms:
        result = engine.hitung(
            deskripsi=args.deskripsi,
            hpp_per_unit=hpp,
            platform=plat,
            omzet_tahunan=args.omzet,
            is_ppn=req.is_ppn,
        )

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
