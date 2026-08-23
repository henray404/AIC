"""Penjaga pricing engine — terutama kosakata kategori.

Latar: sampai 20 Agustus 2026, `MARGIN_DEFAULT` dan `komisi_pct` memakai kunci
karangan (`makanan_minuman`, `skincare_kecantikan`, `elektronik_gadget`,
`dapur_rumah`, `kesehatan_olahraga`) yang muncul NOL kali di katalog, sementara
tiga kategori pangan nyata — `pokok_tani`, `bumbu_masak`, `camilan_olahan`,
16,7% dari 28.443 produk — jatuh diam-diam ke `lainnya` lewat `.get(kategori, ...)`.

Tidak ada yang menangkapnya karena satu-satunya pemeriksa pricing yang jalan
tanpa data (`scripts/pricing_demo_offline.py`) mengarang datanya sendiri memakai
kosakata karangan yang sama. Berkas ini memutus lingkaran itu.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pricing_engine import (  # noqa: E402
    BIAYA_PLATFORM,
    KATEGORI_DATA,
    KE_TARIF,
    MARGIN_DEFAULT,
    bulatkan_psikologis,
    hitung_bep,
    kategori_tarif,
    tentukan_zona,
)


# ─── Kosakata kategori ───────────────────────────────────────────────────────

def test_setiap_kategori_data_punya_margin():
    """Tidak boleh ada kategori nyata yang tidak punya baris margin sendiri."""
    hilang = [k for k in KATEGORI_DATA if k not in MARGIN_DEFAULT]
    assert not hilang, f"kategori nyata tanpa margin: {hilang}"


def test_setiap_kategori_data_punya_tarif_di_semua_platform():
    for kategori in KATEGORI_DATA:
        tarif = kategori_tarif(kategori)
        for platform, cfg in BIAYA_PLATFORM.items():
            assert tarif in cfg["komisi_pct"], \
                f"{kategori} -> {tarif} tidak ada di komisi_pct {platform}"


def test_pemetaan_tarif_menutup_seluruh_kosakata():
    assert set(KATEGORI_DATA) == set(KE_TARIF), \
        "KATEGORI_DATA dan KE_TARIF harus persis sama isinya"


def test_kategori_pangan_tidak_jatuh_ke_lainnya():
    """Inti bug lamanya: pangan diam-diam ditarifkan sebagai 'lainnya'."""
    for kategori in ("pokok_tani", "bumbu_masak", "camilan_olahan"):
        assert kategori_tarif(kategori) == "makanan_minuman", kategori


def test_kategori_tak_dikenal_memperingatkan(caplog):
    """Boleh mundur ke 'lainnya', tapi tidak boleh diam."""
    with caplog.at_level("WARNING"):
        assert kategori_tarif("kategori_yang_tidak_ada") == "lainnya"
    assert any("tidak dikenal" in r.message for r in caplog.records), \
        "fallback kategori wajib meninggalkan jejak di log"


def test_demo_offline_memakai_kosakata_nyata():
    """Demo tidak boleh mengarang kategorinya sendiri lagi."""
    import re

    teks = (Path(__file__).resolve().parent.parent
            / "scripts" / "pricing_demo_offline.py").read_text(encoding="utf-8")
    dipakai = set(re.findall(r'"kategori_umkm":\s*"([a-z_]+)"', teks))
    assert dipakai, "tidak menemukan kategori di data contoh demo"
    asing = dipakai - set(KATEGORI_DATA)
    assert not asing, f"demo memakai kategori yang tidak ada di data: {sorted(asing)}"


# ─── Aritmetika ──────────────────────────────────────────────────────────────

def test_bep_di_atas_hpp():
    bep, pct, flat = hitung_bep(25_000, "tokopedia", "lainnya")
    assert bep > 25_000 + flat
    assert 0 < pct < 100


def test_fee_cap_tokopedia_menahan_bep():
    """Komisi Tokopedia dibatasi Rp80.000/item; BEP tidak boleh tumbuh seolah tidak."""
    hpp = 5_000_000
    bep, _, _ = hitung_bep(hpp, "tokopedia", "lainnya")
    komisi_efektif = bep - hpp - BIAYA_PLATFORM["tokopedia"]["biaya_proses"]
    cap = BIAYA_PLATFORM["tokopedia"]["fee_cap"]
    assert komisi_efektif <= cap + 1, \
        f"komisi efektif Rp{komisi_efektif:,.0f} melebihi cap Rp{cap:,}"


def test_fee_cap_tidak_mengganggu_harga_kecil():
    """Di bawah batas, perilakunya harus persis seperti sebelum cap ada."""
    hpp = 25_000
    bep, pct, flat = hitung_bep(hpp, "tokopedia", "lainnya")
    assert bep == pytest.approx((hpp + flat) / (1 - pct / 100))


def test_platform_tanpa_cap_tidak_terpengaruh():
    hpp = 5_000_000
    bep, pct, flat = hitung_bep(hpp, "shopee", "lainnya")
    assert bep == pytest.approx((hpp + flat) / (1 - pct / 100))


@pytest.mark.parametrize("bep,zona", [
    (10, "BAGUS"), (30, "WAJAR"), (60, "KETAT"), (200, "BAHAYA"),
])
def test_zona_mengikuti_posisi_bep(bep, zona):
    assert tentukan_zona(bep, p25=25, median=50, p75=75) == zona


def test_pembulatan_psikologis_tidak_pernah_negatif():
    # Kontraknya: nol/negatif tetap 0 (tidak ada harga), sisanya minimal Rp100.
    assert bulatkan_psikologis(0) == 0
    assert bulatkan_psikologis(-5_000) == 0
    for harga in (1, 99, 500, 9_999, 55_500, 1_234_567):
        assert bulatkan_psikologis(harga) >= 100, harga


def test_pembulatan_psikologis_dekat_dengan_asalnya():
    for harga in (12_400, 55_500, 240_000):
        hasil = bulatkan_psikologis(harga)
        assert abs(hasil - harga) / harga < 0.06, (harga, hasil)
