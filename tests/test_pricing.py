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


# ─────────────────────────────────────────────────────────────────────────────
# §3.4 Unit modal dan §3.5 Variasi produk
#
# Latar: keduanya sudah ditulis lengkap di docs/MODEL_HARGA.md sejak awal tapi
# tidak pernah ada di kode, sehingga doc menjanjikan penanganan satuan grosir dan
# harga per varian yang sebenarnya tidak dikerjakan siapa pun. Berkas uji ini
# mengikat implementasinya ke angka yang tertulis di doc, supaya keduanya tidak
# bisa lagi menyimpang diam-diam.
# ─────────────────────────────────────────────────────────────────────────────

from pricing_engine import (  # noqa: E402
    ANCHOR_UKURAN,
    ATURAN_UKURAN_FASHION,
    RASIO_GRADE,
    UNIT_LAZIM,
    PricingRequest,
    deteksi_variasi_katalog,
    faktor_relatif,
    faktor_ukuran,
    hitung_hpp_per_unit,
    hitung_varian,
    pertanyaan_unit,
    putuskan_harga,
    rasio_grade,
    rincian_biaya,
    susun_penjelasan,
    variasi_kosmetik,
)


# ─── Kosakata tabel baru ─────────────────────────────────────────────────────

@pytest.mark.parametrize("tabel,nama", [(UNIT_LAZIM, "UNIT_LAZIM"),
                                        (RASIO_GRADE, "RASIO_GRADE")])
def test_tabel_baru_menutup_seluruh_kosakata(tabel, nama):
    """Cacat yang sama seperti MARGIN_DEFAULT dulu: kunci karangan di doc §3.4/§3.5."""
    hilang = [k for k in KATEGORI_DATA if k not in tabel]
    assert not hilang, f"{nama} tidak punya baris untuk kategori nyata: {hilang}"


def test_tabel_baru_tidak_punya_kunci_karangan():
    for nama, tabel in (("UNIT_LAZIM", UNIT_LAZIM), ("RASIO_GRADE", RASIO_GRADE)):
        asing = set(tabel) - set(KATEGORI_DATA)
        assert not asing, f"{nama} memakai kategori di luar data: {sorted(asing)}"


# ─── §3.4 Konversi HPP per unit ──────────────────────────────────────────────

def test_hpp_per_unit_contoh_doc():
    """docs/MODEL_HARGA.md §3.4: 5 kg pisang Rp50.000 → 20 bungkus + kemasan Rp1.500."""
    assert hitung_hpp_per_unit(50_000, 20, 1_500) == 4_000


def test_hpp_per_unit_menolak_jumlah_nol():
    """Pembagian nol harus jadi error yang jelas, bukan harga tak hingga."""
    with pytest.raises(ValueError):
        hitung_hpp_per_unit(50_000, 0)


def test_jumlah_unit_jual_menang_atas_konversi_satuan():
    """Jawaban eksplisit penjual mengalahkan terjemahan tabel satuan."""
    req = PricingRequest(deskripsi_produk="keripik", hpp_total=50_000,
                         hpp_satuan="lusin", jumlah_unit_jual=20,
                         biaya_packing=1_500)
    assert req.hpp_per_unit == 4_000     # bukan 50.000/12 + 1.500


def test_default_aman_ketika_satuan_tidak_dijawab():
    """§3.4: kalau user diam, asumsi 1 unit jual — salah ke atas, bukan ke bawah."""
    req = PricingRequest(deskripsi_produk="kaos", hpp_total=50_000)
    assert req.hpp_per_unit == 50_000


def test_pertanyaan_unit_relevan_dengan_kategori():
    tanya = pertanyaan_unit("camilan_olahan", 50_000)
    assert tanya is not None
    assert "50,000" in tanya["pertanyaan"]
    assert "kg" in tanya["satuan_beli"]
    assert "bungkus" in tanya["satuan_jual"]


def test_pertanyaan_unit_kategori_asing_tidak_meledak(caplog):
    with caplog.at_level("WARNING"):
        assert pertanyaan_unit("kategori_ngawur", 10_000) is not None
    assert any("tidak ada di UNIT_LAZIM" in r.message for r in caplog.records)


# ─── §3.5 Faktor ukuran ──────────────────────────────────────────────────────

@pytest.mark.parametrize("label,harapan", [
    ("50g", 1.00), ("100g", 1.85), ("150g", 2.60),
    ("250g", 4.00), ("500g", 7.00), ("1kg", 12.00),
    ("15ml", 1.00), ("30ml", 1.80), ("60ml", 3.20), ("100ml", 4.80),
])
def test_faktor_ukuran_persis_seperti_tabel_doc(label, harapan):
    """Di titik jangkar, interpolasi log-log harus mengembalikan angka doc apa adanya."""
    faktor, _ = faktor_ukuran(label)
    assert faktor == pytest.approx(harapan, rel=1e-9)


def test_faktor_ukuran_contoh_relatif_doc():
    """§3.5: HPP 100g → 250g naik 2,15× (doc membulatkan; rasio pastinya 4,00/1,85)."""
    assert faktor_relatif("250g", "100g") == pytest.approx(2.162, abs=0.005)


def test_diskon_volume_selalu_berlaku():
    """Inti tabelnya: kemasan 2× besar TIDAK boleh berharga 2× lipat."""
    for kecil, besar in (("100g", "200g"), ("250g", "500g"), ("30ml", "60ml")):
        assert 1.0 < faktor_relatif(besar, kecil) < 2.0


def test_faktor_ukuran_monoton_naik():
    urut = ["50g", "100g", "150g", "250g", "500g", "1kg"]
    nilai = [faktor_ukuran(u)[0] for u in urut]
    assert nilai == sorted(nilai)


def test_ukuran_di_luar_jangkar_diekstrapolasi_wajar():
    """2kg tidak ada di tabel; harus di atas 1kg tapi tidak melompat linear (24×)."""
    faktor, dimensi = faktor_ukuran("2kg")
    assert dimensi == "berat"
    assert 12.0 < faktor < 24.0


@pytest.mark.parametrize("label", ["XS", "S", "M", "L", "XL", "xl", " m "])
def test_ukuran_fashion_standar_satu_harga(label):
    """Konvensi marketplace Indonesia: XS–XL tidak beda harga."""
    assert faktor_ukuran(label) == (1.00, "fashion")


@pytest.mark.parametrize("label,harapan", [("XXL", 1.05), ("2XL", 1.05),
                                           ("3XL", 1.10), ("4XL", 1.15),
                                           ("5XL", 1.20)])
def test_ukuran_jumbo_kena_markup(label, harapan):
    assert faktor_ukuran(label)[0] == pytest.approx(harapan)


def test_label_ukuran_tak_dikenal_tidak_diam(caplog):
    """Boleh mundur ke 1,0, tapi harus meninggalkan jejak — bukan diam seperti bug lama."""
    with caplog.at_level("WARNING"):
        assert faktor_ukuran("jumbo banget")[0] == 1.0
    assert any("tidak dikenali" in r.message for r in caplog.records)


def test_beda_jenis_ukuran_tidak_dirasiokan(caplog):
    """"XL" berbanding "250g" tidak punya arti; jangan dikarang angkanya."""
    with caplog.at_level("WARNING"):
        assert faktor_relatif("XL", "250g") == 1.0
    assert any("beda jenis ukuran" in r.message for r in caplog.records)


# ─── §3.5 Warna dan grade ────────────────────────────────────────────────────

def test_variasi_warna_harganya_sama():
    hasil = variasi_kosmetik(54_900, ["Hitam", "Putih", "Navy", "Abu"])
    assert hasil["harga"] == 54_900
    assert len(hasil["varian"]) == 4
    assert "1 listing" in hasil["saran"]


@pytest.mark.parametrize("kategori,harapan", [
    ("fashion_perawatan", 1.5), ("camilan_olahan", 1.8), ("kriya_rumah", 2.5),
])
def test_rasio_grade_seperti_doc(kategori, harapan):
    assert rasio_grade(kategori, "Premium") == pytest.approx(harapan)


def test_grade_tak_dikenal_tidak_ditebak(caplog):
    """Menebak rasio untuk grade di luar reguler/premium = mengarang; harus 1,0 + warning."""
    with caplog.at_level("WARNING"):
        assert rasio_grade("kriya_rumah", "Super Ultra") == 1.0
    assert any("tidak ada di RASIO_GRADE" in r.message for r in caplog.records)


# ─── §3.5 Perakitan varian ───────────────────────────────────────────────────

PASAR = dict(p25=35_000.0, median=45_000.0, p75=65_000.0)


def test_varian_warna_semuanya_satu_harga():
    varian = hitung_varian(hpp_dasar=27_000, harga_dasar=44_900,
                           kategori="fashion_perawatan", platform="tokopedia",
                           variasi_warna=["Hitam", "Putih", "Navy"], **PASAR)
    assert len(varian) == 3
    assert {v.harga_rekomendasi for v in varian} == {44_900}
    assert {v.jenis for v in varian} == {"warna"}


def test_varian_ukuran_fashion_hanya_jumbo_yang_naik():
    varian = hitung_varian(hpp_dasar=27_000, harga_dasar=44_900,
                           kategori="fashion_perawatan", platform="tokopedia",
                           variasi_ukuran=["M", "L", "XL", "XXL", "3XL"], **PASAR)
    harga = {v.label: v.harga_rekomendasi for v in varian}
    assert harga["M"] == harga["L"] == harga["XL"]
    assert harga["XXL"] > harga["XL"]
    assert harga["3XL"] > harga["XXL"]


def test_varian_ukuran_isi_naik_tapi_tidak_linear():
    varian = hitung_varian(hpp_dasar=4_000, harga_dasar=17_900,
                           kategori="camilan_olahan", platform="blibli",
                           variasi_ukuran=["100g", "200g"],
                           p25=9_000.0, median=17_000.0, p75=25_000.0)
    kecil, besar = varian[0].harga_rekomendasi, varian[1].harga_rekomendasi
    assert kecil < besar < kecil * 2


def test_hpp_per_ukuran_mengalahkan_estimasi():
    """Kalau penjual tahu HPP tiap ukuran, tabel jangkar tidak boleh ikut campur."""
    varian = hitung_varian(hpp_dasar=25_000, harga_dasar=44_900,
                           kategori="fashion_perawatan", platform="tokopedia",
                           variasi_ukuran=["M", "XXL"],
                           hpp_per_ukuran={"XXL": 40_000}, **PASAR)
    xxl = next(v for v in varian if v.label == "XXL")
    assert xxl.hpp_unit == 40_000
    assert xxl.catatan == "HPP diisi penjual"


def test_grade_tanpa_hpp_ditandai_estimasi():
    """Margin di baris ini memang terlalu optimis — wajib ada tandanya."""
    varian = hitung_varian(hpp_dasar=60_000, harga_dasar=76_900,
                           kategori="kriya_rumah", platform="tokopedia",
                           variasi_grade=["Premium"], **PASAR)
    assert "ESTIMASI" in varian[0].catatan
    assert varian[0].hpp_unit == 60_000


def test_grade_dengan_hpp_dihitung_penuh():
    varian = hitung_varian(hpp_dasar=60_000, harga_dasar=76_900,
                           kategori="kriya_rumah", platform="tokopedia",
                           variasi_grade=["Premium"],
                           hpp_per_grade={"Premium": 95_000}, **PASAR)
    assert varian[0].hpp_unit == 95_000
    assert varian[0].catatan == "HPP diisi penjual"
    assert varian[0].harga_rekomendasi >= varian[0].harga_minimum


def test_tanpa_variasi_daftar_varian_kosong():
    assert hitung_varian(hpp_dasar=27_000, harga_dasar=44_900,
                         kategori="fashion_perawatan", platform="tokopedia",
                         **PASAR) == []


def test_setiap_varian_tetap_di_atas_bep():
    """Jaminan yang sama dengan harga utama, tidak boleh bocor di jalur varian."""
    varian = hitung_varian(hpp_dasar=27_000, harga_dasar=44_900,
                           kategori="fashion_perawatan", platform="shopee",
                           variasi_warna=["Hitam"],
                           variasi_ukuran=["M", "XXL", "5XL"],
                           variasi_grade=["Reguler", "Premium"], **PASAR)
    for v in varian:
        assert v.harga_rekomendasi >= v.harga_minimum, v.label


# ─── Deteksi variasi dari katalog ────────────────────────────────────────────

def test_deteksi_variasi_menghitung_dari_tetangga():
    judul = ["Kaos Polos Hitam Putih", "Kaos Oblong Navy",
             "Keripik Pisang 250g", "Sabun Batang"]
    hasil = deteksi_variasi_katalog(judul, minimal_pct=20.0)
    assert hasil["dari_n"] == 4
    jenis = {p["jenis"]: p["persen"] for p in hasil["pola"]}
    assert jenis["warna"] == 50.0
    assert jenis["berat_isi"] == 25.0


def test_deteksi_variasi_tanpa_tetangga_tidak_mengarang():
    hasil = deteksi_variasi_katalog([])
    assert hasil == {"dari_n": 0, "pola": [], "saran": []}


# ─── Keputusan harga (fungsi yang dipakai bersama varian) ────────────────────

@pytest.mark.parametrize("bep", [1_000, 20_000, 40_000, 50_000, 90_000, 200_000])
def test_putuskan_harga_tidak_pernah_di_bawah_bep(bep):
    """Satu-satunya jaminan keras model ini: penjual tidak boleh disuruh rugi."""
    putusan = putuskan_harga(bep, 35_000, 45_000, 65_000, "fashion_perawatan",
                             int(bep * 0.8), "tokopedia")
    assert putusan["harga_rekomendasi"] >= bep
    assert putusan["harga_agresif"] >= bep


def test_putuskan_harga_tanpa_pasar_jatuh_ke_tidak_ada_data():
    putusan = putuskan_harga(30_000, 0.0, 0.0, 0.0, "lainnya", 25_000, "tokopedia")
    assert putusan["zona"] == "TIDAK_ADA_DATA"
    assert putusan["peringatan"]


def test_zona_bahaya_menyertakan_saran_pindah_platform():
    putusan = putuskan_harga(186_012, 65_000, 120_000, 180_000,
                             "fashion_perawatan", 155_000, "shopee")
    assert putusan["zona"] == "BAHAYA"
    assert any("Tokopedia" in s for s in putusan["saran"])


# ─── Breakdown biaya ─────────────────────────────────────────────────────────

def test_rincian_biaya_sama_dengan_tabel_skenario_2_doc():
    """docs/MODEL_HARGA.md §7 Skenario 2: kaos polos, Tokopedia, harga Rp44.900."""
    bd = rincian_biaya(44_900, 27_000, "tokopedia", "fashion_perawatan")
    assert bd["HPP"] == 27_000
    assert bd["Komisi Tokopedia (8.0%)"] == 3_592
    assert bd["Biaya proses"] == 1_250
    assert bd["Laba bersih"] == 13_058


def test_rincian_biaya_penjual_pkp_kena_ppn():
    """PPN menaikkan BEP, jadi ia harus ikut memotong laba — bukan cuma di satu sisi."""
    biasa = rincian_biaya(100_000, 50_000, "tokopedia", "lainnya")
    pkp = rincian_biaya(100_000, 50_000, "tokopedia", "lainnya", is_ppn=True)
    assert pkp["Laba bersih"] < biasa["Laba bersih"]


# ─── Narasi ──────────────────────────────────────────────────────────────────

def test_penjelasan_menyebut_batas_rugi():
    bd = rincian_biaya(44_900, 27_000, "tokopedia", "fashion_perawatan")
    teks = susun_penjelasan("WAJAR", "fashion_perawatan", "pcs", "Tokopedia",
                            27_000, 30_706.0, 44_900, 35_000, 45_000, 65_000,
                            8, 66.3, bd)
    assert "30,706" in teks and "rugi" in teks


def test_penjelasan_tanpa_data_mengakui_ketiadaan_pembanding():
    """Zona TIDAK_ADA_DATA harus jujur bahwa harganya bersandar pada margin
    bawaan yang belum diukur — bukan disajikan seolah punya dasar pasar."""
    bd = rincian_biaya(40_000, 25_000, "tokopedia", "lainnya")
    teks = susun_penjelasan("TIDAK_ADA_DATA", "lainnya", "pcs", "Tokopedia",
                            25_000, 28_000.0, 40_000, 0, 0, 0, 0, 60.0, bd)
    assert "belum diukur" in teks.lower()
