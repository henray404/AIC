"""Ukur pendekatan NLP tradisional untuk judul, tanpa model neural sama sekali.

Semua kandidat menerima MASUKAN TEKS (keterangan penjual), bukan foto -- jadi
pembandingnya student teks 0,5B, bukan pipeline penuh.

Dijalankan pada 492 produk uji yang sama, tanpa GPU.
"""
import json
import re
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, "scripts")
import eval_listing as ev
import retrieve_pipeline as rp

uji = [json.loads(l) for l in Path("hasil_sesi2/S3_pipeline_lini.jsonl").open(encoding="utf-8")
       if l.strip()]
lex = rp.muat_lexicon()

# Indeks TF-IDF atas judul katalog -- ini "modelnya", dibangun sekali dalam detik
df = pd.read_parquet("data_drive/merged/merged_local.parquet",
                     columns=["title", "product_id"])
judul_katalog = [rp.clean_title(t) for t in df["title"].astype(str)]
indeks = rp.Indeks(judul_katalog)

# WAJIB: produk uji ada di katalog ini. Tanpa eksklusi, retrieval menemukan
# produk itu sendiri dan menyalin judulnya -- skornya jadi hampir 1,0 dan
# tidak berarti apa-apa. Ini kebocoran yang sama yang sudah ditutup di
# pipeline lewat --eksklusi.
baris_pid = {str(p): i for i, p in enumerate(df["product_id"])}
lini_baris = defaultdict(list)
for i, j in enumerate(judul_katalog):
    if j:
        lini_baris[j.split()[0].lower()].append(i)

# n-gram statistik: kata apa yang biasa mengikuti kata apa di judul katalog
bigram = defaultdict(Counter)
for j in judul_katalog[:20000]:
    kata = j.split()
    for a, b in zip(kata, kata[1:]):
        bigram[a.lower()][b] += 1

UK = re.compile(r"(?i)\b(\d+(?:[.,]\d+)?\s*(?:gr?|kg|ml|lt?r?|liter|w|cm|pcs))\b")


def fakta_dari(r):
    """Susun keterangan teks dari judul asli -- meniru apa yang penjual ketik."""
    judul = str(r.get("judul_asli", ""))
    kata = re.sub(r"[^\w\s.\-/&+,']", " ", judul).split()
    umum = lex.get("umum", set())
    merek_set = lex.get("merek", set())
    merek = next((w for w in kata[:4] if w.lower() in merek_set), "")
    jenis = next((w for w in kata
                  if w.lower() in umum and w.lower() not in merek_set and len(w) > 2), "")
    uk = UK.search(judul)
    return {"jenis": jenis, "merek": merek,
            "ukuran": re.sub(r"\s+", "", uk.group(1)) if uk else "",
            "kategori": str(r.get("kategori_asli", ""))}


def skor(judul, r):
    emas = ev.kata(r.get("judul_asli", ""))
    kj = ev.kata(judul)
    if not emas or not kj:
        return None
    n = len(emas & kj)
    f1 = 2 * n / (len(emas) + len(kj))
    dasar = ev.kata(" ".join(str(v) for v in fakta_dari(r).values()))
    return f1, bool(kj - dasar)


def m_template(r):
    """Template slot: jenis + merek + ukuran. Nol latihan, nol model."""
    f = fakta_dari(r)
    return " ".join(x for x in (f["jenis"], f["merek"], f["ukuran"]) if x)


def blokir_untuk(r):
    """Eksklusi tingkat `product line`, sama dengan yang dipakai pipeline."""
    pid = str(r.get("product_id"))
    i = baris_pid.get(pid)
    blok = {i} if i is not None else set()
    if i is not None and judul_katalog[i]:
        blok |= set(lini_baris[judul_katalog[i].split()[0].lower()])
    return blok


def m_retrieval(r):
    """Salin judul tetangga terdekat. 'Model'-nya cuma indeks TF-IDF."""
    kueri = " ".join(str(v) for v in fakta_dari(r).values())
    cocok = indeks.cari(kueri, 1, blokir=blokir_untuk(r))
    return judul_katalog[cocok[0][0]] if cocok else ""


def m_retrieval_saring(r):
    """Judul tetangga, tapi kata tak berdasar keterangan dibuang."""
    judul = m_retrieval(r)
    dasar = ev.kata(" ".join(str(v) for v in fakta_dari(r).values()))
    umum = lex.get("umum", set())
    return " ".join(w for w in judul.split()
                    if w.lower() in dasar
                    or (w.lower() in umum and w.lower() not in lex["merek"]))


def m_template_bigram(r):
    """Template lalu diperpanjang dengan kata yang statistik katalog bilang
    lazim mengikuti -- Markov orde 1, murni hitungan."""
    kata = m_template(r).split()
    if not kata:
        return ""
    ada = {w.lower() for w in kata}
    for _ in range(4):
        pilih = next((w for w, _ in bigram.get(kata[-1].lower(), Counter()).most_common(6)
                      if w.lower() not in ada and w.isalpha() and len(w) > 2), None)
        if not pilih:
            break
        kata.append(pilih)
        ada.add(pilih.lower())
    return " ".join(kata)


METODE = [
    ("template slot", m_template),
    ("template + bigram katalog", m_template_bigram),
    ("retrieval tetangga terdekat", m_retrieval),
    ("retrieval + saring keterangan", m_retrieval_saring),
]

print(f"{len(uji)} produk uji, masukan TEKS (keterangan), tanpa foto\n")
print(f"  {'metode':32} {'inti_f1':>9} {'halusinasi':>12} {'kata':>6}")
for nama, fn in METODE:
    f1s, hal, panjang = [], [], []
    for r in uji:
        j = fn(r)
        s = skor(j, r)
        if s:
            f1s.append(s[0])
            hal.append(s[1])
            panjang.append(len(j.split()))
    print(f"  {nama:32} {st.mean(f1s):9.3f} {100*st.mean(hal):11.1f}% "
          f"{st.mean(panjang):6.1f}")

print(f"\n  {'-- pembanding neural --':32}")
for nama, v in (("Student teks 0,5B (LoRA)", 0.208),
                ("Baseline 12B (pakai foto)", 0.292),
                ("Student VLM 3B (pakai foto)", 0.393),
                ("RAG pipeline (pakai foto)", 0.405)):
    print(f"  {nama:32} {v:9.3f}")
