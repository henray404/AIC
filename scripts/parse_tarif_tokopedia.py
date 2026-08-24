"""Ubah PDF tarif resmi Tokopedia non-Mall menjadi tabel yang bisa dipakai ulang.

Sumber: "Tokopedia non Mall Tarif - Mulai 20 Februari 2025.pdf", diunduh dari
halaman bantuan Tokopedia. PDF-nya dokumen pihak ketiga dan tidak ikut di-commit
(lihat .gitignore); yang di-commit adalah hasil parse-nya di
`docs/tarif_tokopedia_nonmall.csv`, supaya setiap angka tarif pada
`docs/MODEL_HARGA.md` dan `scripts/pricing_engine.py` bisa dilacak ke barisnya.

    python scripts/parse_tarif_tokopedia.py --pdf ~/Downloads/"Tokopedia non Mall Tarif - Mulai 20 Februari 2025.pdf"
    python scripts/parse_tarif_tokopedia.py --ringkas      # tarif per kategori_umkm
    python scripts/parse_tarif_tokopedia.py --selfcheck    # uji dari CSV, tanpa PDF

Dua hal yang perlu diketahui sebelum memakai angkanya:

1. **Diskon 20% untuk tarif 10%.** Sejak 16 September 2024 semua subkategori
   bertarif 10,00% mendapat diskon komisi 20%, sehingga tarif efektifnya 8,00%.
   Kolom `tarif_efektif_pct` sudah memperhitungkan ini; kolom `tarif_pct` tidak.

2. **Baris 0,00% ada dua jenis.** Pada kategori barang segar (Sayur & Buah Segar,
   Daging & Seafood, dan sejenisnya) seluruh pohon sampai daun bernilai 0,00% —
   itu tarif sungguhan. Tapi pada sebagian baris agregat (contoh: "Buku > Buku
   Ekonomi & Bisnis" 0,00% padahal seluruh anaknya 10,00%) nol itu sel kosong
   yang terbaca 0. Karena itu ringkasan per kategori dihitung dari **baris daun
   saja** — baris yang punya sub sub-kategori — bukan dari baris agregat.
"""

from __future__ import annotations

import argparse
import csv
import re
import statistics
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
TUJUAN = PROJECT / "docs" / "tarif_tokopedia_nonmall.csv"
PDF_DEFAULT = Path.home() / "Downloads" / "Tokopedia non Mall Tarif - Mulai 20 Februari 2025.pdf"

BERLAKU = "20 Februari 2025"
DISKON_SEJAK = "16 September 2024"

BARIS_TARIF = re.compile(r"^(.*?)\s*(\d+\.\d{2})%$")

# Kategori Tokopedia yang mewakili tiap nilai `kategori_umkm` pada dataset kita.
# Pemetaan ini penilaian manusia, bukan hasil pengukuran — ditulis terbuka di
# sini supaya bisa diperdebatkan, bukan disembunyikan di dalam konstanta.
PETA_KATEGORI: dict[str, list[str]] = {
    "bumbu_masak":         ["Bumbu Masakan"],
    "camilan_olahan":      ["Snack & Es Krim", "Makanan & Minuman"],
    "fashion_perawatan":   ["Fashion Wanita", "Fashion Pria", "Fashion Muslim",
                            "Fashion Anak & Bayi", "Perawatan Tubuh", "Kecantikan"],
    "kriya_rumah":         ["Rumah Tangga"],
    "minuman_herbal":      ["Minuman", "Kesehatan"],
    "pokok_tani":          ["Sayur & Buah Segar", "Beras & Makanan Kering",
                            "Daging & Seafood", "Telur & Olahan Susu"],
    "makanan_minuman":     ["Makanan & Minuman", "Snack & Es Krim", "Minuman",
                            "Makanan Beku & Olahan", "Makanan Sarapan",
                            "Mie, Pasta & Bihun"],
    "elektronik_gadget":   ["Elektronik", "Handphone & Tablet", "Komputer & Laptop",
                            "Audio, Kamera & Elektronik Lainnya", "Gadget & Elektronik"],
    "skincare_kecantikan": ["Kecantikan", "Perawatan Tubuh"],
    "dapur_rumah":         ["Dapur", "Rumah Tangga"],
    "kesehatan_olahraga":  ["Kesehatan", "Olahraga"],
    "lainnya":             [],   # kosong = seluruh kategori
}


def efektif(pct: float) -> float:
    """Diskon komisi 20% berlaku hanya untuk subkategori bertarif 10%."""
    return 8.0 if pct == 10.0 else pct


def _prefiks(nama: str, kandidat: list[str]) -> tuple[str | None, str | None]:
    """Cocokkan `nama` ke prefiks terpanjang di `kandidat`.

    Ekstraksi teks PDF kadang menempelkan dua kolom tanpa spasi
    ("...Elektronik LainnyaAksesoris Kamera"), jadi bentuk tanpa spasi ikut
    dicoba selama huruf sesudahnya kapital.
    """
    terbaik = None
    for k in kandidat:
        if nama == k:
            return k, ""
        if nama.startswith(k + " "):
            sisa = nama[len(k):].strip()
        elif nama.startswith(k) and len(nama) > len(k) and nama[len(k)].isupper():
            sisa = nama[len(k):].strip()
        else:
            continue
        if terbaik is None or len(k) > len(terbaik[0]):
            terbaik = (k, sisa)
    return terbaik if terbaik else (None, None)


def parse_pdf(pdf: Path) -> list[dict]:
    """Bangun kembali hierarki tiga tingkat dari teks PDF yang sudah datar.

    PDF-nya urut: baris induk selalu muncul sebelum anaknya, jadi hierarki bisa
    disusun ulang dengan pencocokan prefiks tanpa perlu koordinat sel.
    """
    from pypdf import PdfReader

    baris_mentah: list[str] = []
    for halaman in PdfReader(str(pdf)).pages:
        baris_mentah.extend((halaman.extract_text() or "").split("\n"))

    kategori: list[str] = []
    subkategori: dict[str, list[str]] = {}
    hasil: list[dict] = []

    for baris in baris_mentah:
        cocok = BARIS_TARIF.match(baris.strip())
        if not cocok or not cocok.group(1).strip():
            continue
        nama, pct = cocok.group(1).strip(), float(cocok.group(2))

        kat, sisa = _prefiks(nama, kategori)
        if kat is None:
            kategori.append(nama)
            subkategori[nama] = []
            kat, sub, subsub = nama, "", ""
        elif not sisa:
            sub, subsub = "", ""
        else:
            s, ss = _prefiks(sisa, subkategori[kat])
            if s is None:
                subkategori[kat].append(sisa)
                sub, subsub = sisa, ""
            else:
                sub, subsub = s, ss

        hasil.append({
            "kategori": kat,
            "subkategori": sub,
            "sub_subkategori": subsub,
            "tarif_pct": f"{pct:.2f}",
            "tarif_efektif_pct": f"{efektif(pct):.2f}",
        })
    return hasil


def tulis_csv(baris: list[dict], tujuan: Path = TUJUAN) -> None:
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    with tujuan.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(baris[0].keys()))
        w.writeheader()
        w.writerows(baris)


def baca_csv(sumber: Path = TUJUAN) -> list[dict]:
    with sumber.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def daun(baris: list[dict], kategori: list[str] | None = None) -> list[float]:
    """Tarif efektif baris daun — baris yang punya sub sub-kategori.

    Baris agregat dilewati karena sebagiannya bernilai 0,00% hanya sebab selnya
    kosong di PDF; lihat catatan 2 pada docstring modul.
    """
    return [
        float(b["tarif_efektif_pct"]) for b in baris
        if b["sub_subkategori"] and (kategori is None or b["kategori"] in kategori)
    ]


def ringkas(baris: list[dict]) -> dict[str, dict]:
    """Tarif wakil per `kategori_umkm`: median tarif efektif baris daun."""
    out = {}
    for kat_kami, kat_toped in PETA_KATEGORI.items():
        nilai = daun(baris, kat_toped or None)
        if not nilai:
            continue
        out[kat_kami] = {
            "median": round(statistics.median(nilai), 2),
            "min": round(min(nilai), 2),
            "max": round(max(nilai), 2),
            "n_daun": len(nilai),
        }
    return out


def cetak_ringkas(baris: list[dict]) -> None:
    print(f"Tarif layanan Tokopedia non-Mall, berlaku {BERLAKU}")
    print(f"Tarif efektif sudah memperhitungkan diskon 20% atas tarif 10% (sejak {DISKON_SEJAK}).\n")
    print(f"{'kategori_umkm':22s} {'median':>7s} {'min':>6s} {'max':>6s} {'daun':>7s}")
    print("-" * 52)
    for kat, s in ringkas(baris).items():
        print(f"{kat:22s} {s['median']:>6.2f}% {s['min']:>5.2f}% {s['max']:>5.2f}% {s['n_daun']:>7d}")


def selfcheck(baris: list[dict]) -> int:
    """Uji tanpa jaringan atas nilai yang bisa dibaca langsung di PDF."""
    gagal = 0

    def cek(nama: str, dapat, harap):
        nonlocal gagal
        tanda = "ok  " if dapat == harap else "GAGAL"
        if dapat != harap:
            gagal += 1
        print(f"  [{tanda}] {nama}: {dapat!r} (harap {harap!r})")

    cek("jumlah baris", len(baris), 3779)
    cek("jumlah kategori", len({b["kategori"] for b in baris}), 43)

    def tarif(kat, sub="", subsub=""):
        for b in baris:
            if (b["kategori"], b["subkategori"], b["sub_subkategori"]) == (kat, sub, subsub):
                return b["tarif_pct"], b["tarif_efektif_pct"]
        return None

    cek("Rumah Tangga (kategori)", tarif("Rumah Tangga"), ("7.95", "7.95"))
    cek("Elektronik (kategori)", tarif("Elektronik"), ("4.25", "4.25"))
    cek("Fashion Wanita — diskon 10%→8%", tarif("Fashion Wanita"), ("10.00", "8.00"))
    cek("Sayur & Buah Segar > Buah > Apel", tarif("Sayur & Buah Segar", "Buah", "Apel"), ("0.00", "0.00"))
    cek("Rumah Tangga > Dekorasi > Lukisan", tarif("Rumah Tangga", "Dekorasi", "Lukisan"), ("7.50", "7.50"))
    cek("tarif tertinggi", max(float(b["tarif_pct"]) for b in baris), 10.0)

    print("\nGAGAL" if gagal else "\nSemua uji lulus.")
    return gagal


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", type=Path, default=PDF_DEFAULT,
                    help="PDF tarif resmi Tokopedia non-Mall")
    ap.add_argument("--ringkas", action="store_true",
                    help="cetak tarif wakil per kategori_umkm")
    ap.add_argument("--selfcheck", action="store_true",
                    help="uji hasil parse terhadap nilai yang diketahui")
    a = ap.parse_args()

    if (a.ringkas or a.selfcheck) and not a.pdf.exists():
        if not TUJUAN.exists():
            print(f"PDF tidak ada di {a.pdf} dan CSV belum dibuat.")
            return 1
        baris = baca_csv()
        print(f"PDF tidak ada; memakai {TUJUAN.relative_to(PROJECT)}\n")
    else:
        if not a.pdf.exists():
            print(f"PDF tidak ditemukan: {a.pdf}")
            return 1
        baris = parse_pdf(a.pdf)
        tulis_csv(baris)
        print(f"{len(baris)} baris ditulis ke {TUJUAN.relative_to(PROJECT)}\n")

    if a.selfcheck:
        return 1 if selfcheck(baris) else 0
    if a.ringkas:
        cetak_ringkas(baris)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
