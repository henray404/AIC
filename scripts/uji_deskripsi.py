"""Ukur pendekatan tradisional untuk DESKRIPSI, masukan teks, tanpa neural.

Deskripsi asli median 140 kata prosa pemasaran. F1 kata terhadap itu tidak
berarti -- yang penting bukan menebak kalimat pemasaran penjual, tapi:
  (a) apakah fakta produk tersampaikan (jenis/merek/ukuran muncul),
  (b) apakah ada KLAIM yang dikarang -- angka atau merek yang tidak ada
      di keterangan. Ini risiko sebenarnya: "500ml", "BPOM", "original".
"""
import json
import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, "scripts")
import eval_listing as ev
import retrieve_pipeline as rp

uji = [json.loads(l) for l in Path("hasil_sesi2/S3_pipeline_lini.jsonl").open(encoding="utf-8")
       if l.strip()]
lex = rp.muat_lexicon()
merek_set = lex.get("merek", set())

df = pd.read_parquet("data_drive/merged/merged_local.parquet",
                     columns=["product_id", "title", "description"])
df["product_id"] = df["product_id"].astype(str)
desk_pid = dict(zip(df["product_id"], df["description"].fillna("").astype(str)))
judul_katalog = [rp.clean_title(t) for t in df["title"].astype(str)]
desk_katalog = list(df["description"].fillna("").astype(str))
indeks = rp.Indeks(judul_katalog)

baris_pid = {p: i for i, p in enumerate(df["product_id"])}
lini_baris = defaultdict(list)
for i, j in enumerate(judul_katalog):
    if j:
        lini_baris[j.split()[0].lower()].append(i)

UK = re.compile(r"(?i)\b(\d+(?:[.,]\d+)?\s*(?:gr?|kg|ml|lt?r?|liter|w|cm|pcs))\b")
# Hanya angka BERSATUAN yang klaim yang bisa diperiksa. Angka telanjang di
# prosa ("lima tahap", "3 kali saring") bukan klaim produk -- versi pertama
# metrik ini menghitungnya dan menandai 88% deskripsi ASLI penjual sebagai
# karangan, yang jelas keliru.
ANGKA = re.compile(r"(?i)\b\d+(?:[.,]\d+)?\s*(?:gr|gram|kg|ml|l|ltr|liter|"
                   r"cm|mm|m|w|watt|pcs|pack|inch|inci)\b")

# Leksikon merek dibangun otomatis dari judul, jadi memuat kata umum yang
# kebetulan sering jadi awalan nama toko. Tanpa saringan ini kata "toko" di
# template membuat setiap keluaran tampak mengarang merek.
BUKAN_MEREK = {"toko", "grosir", "pusat", "agen", "murah", "original", "asli",
               "resmi", "baru", "premium", "super", "jaya", "mandiri", "sumber"}


def fakta_dari(r):
    judul = str(r.get("judul_asli", ""))
    kata = re.sub(r"[^\w\s.\-/&+,']", " ", judul).split()
    umum = lex.get("umum", set())
    merek = next((w for w in kata[:4] if w.lower() in merek_set), "")
    jenis = next((w for w in kata
                  if w.lower() in umum and w.lower() not in merek_set and len(w) > 2), "")
    uk = UK.search(judul)
    return {"jenis": jenis, "merek": merek,
            "ukuran": re.sub(r"\s+", "", uk.group(1)) if uk else "",
            "kategori": str(r.get("kategori_asli", ""))}


def klaim_karang(teks, f):
    """Angka atau merek di deskripsi yang tidak ada di keterangan."""
    dasar = " ".join(str(v) for v in f.values()).lower()
    norm = lambda x: re.sub(r"\s+", "", x.lower())
    angka_dasar = {norm(a) for a in ANGKA.findall(dasar)}
    if any(norm(a) not in angka_dasar for a in ANGKA.findall(teks)):
        return True
    return any(w.lower() in merek_set and w.lower() not in BUKAN_MEREK
               and w.lower() not in dasar
               for w in re.findall(r"[A-Za-z]{3,}", teks))


def fakta_tersampaikan(teks, f):
    """Berapa bagian fakta wajib yang muncul di deskripsi."""
    isi = [v for k, v in f.items() if v and k != "kategori"]
    if not isi:
        return None
    t = teks.lower()
    return sum(1 for v in isi if v.lower() in t) / len(isi)


def blokir_untuk(r):
    i = baris_pid.get(str(r.get("product_id")))
    blok = {i} if i is not None else set()
    if i is not None and judul_katalog[i]:
        blok |= set(lini_baris[judul_katalog[i].split()[0].lower()])
    return blok


def m_template(r):
    """Empat kalimat berkerangka tetap, slot diisi fakta. Nol latihan."""
    f = fakta_dari(r)
    nama = " ".join(x for x in (f["merek"], f["jenis"]) if x) or "Produk ini"
    uk = f" Tersedia dalam ukuran {f['ukuran']}." if f["ukuran"] else ""
    kat = f["kategori"].replace("_", " ") if f["kategori"] else "kebutuhan harian"
    return (f"{nama} siap kirim dari toko kami.{uk} "
            f"Cocok untuk kebutuhan {kat} sehari-hari. "
            f"Barang dikemas rapi dan aman sebelum dikirim. "
            f"Silakan chat penjual bila ada pertanyaan sebelum memesan.")


def m_retrieval(r):
    """Salin deskripsi tetangga terdekat."""
    kueri = " ".join(str(v) for v in fakta_dari(r).values())
    cocok = indeks.cari(kueri, 1, blokir=blokir_untuk(r))
    return desk_katalog[cocok[0][0]] if cocok else ""


def m_retrieval_potong(r):
    """Deskripsi tetangga, tapi kalimat yang memuat angka/merek asing dibuang."""
    f = fakta_dari(r)
    kal = re.split(r"(?<=[.!?])\s+|\n+", m_retrieval(r))
    aman = [k for k in kal if k.strip() and not klaim_karang(k, f)]
    return " ".join(aman[:5])


METODE = [
    ("template berkerangka", m_template),
    ("salin deskripsi tetangga", m_retrieval),
    ("tetangga + potong klaim asing", m_retrieval_potong),
]

print(f"{len(uji)} produk uji, DESKRIPSI dari masukan teks\n")
print(f"  {'metode':32} {'fakta_sampai':>13} {'klaim_karang':>13} {'kata':>6}")
for nama, fn in METODE:
    fk, kk, pj = [], [], []
    for r in uji:
        t = fn(r)
        f = fakta_dari(r)
        v = fakta_tersampaikan(t, f)
        if v is not None:
            fk.append(v)
        kk.append(klaim_karang(t, f))
        pj.append(len(t.split()))
    print(f"  {nama:32} {st.mean(fk):13.3f} {100*st.mean(kk):12.1f}% {st.mean(pj):6.1f}")

# Pembanding: deskripsi asli penjual, dinilai dengan ukuran yang sama
fk, kk, pj = [], [], []
for r in uji:
    t = desk_pid.get(str(r["product_id"]), "")
    f = fakta_dari(r)
    v = fakta_tersampaikan(t, f)
    if v is not None:
        fk.append(v)
    kk.append(klaim_karang(t, f))
    pj.append(len(t.split()))
print(f"\n  {'deskripsi ASLI penjual (acuan)':32} {st.mean(fk):13.3f} "
      f"{100*st.mean(kk):12.1f}% {st.mean(pj):6.1f}")
