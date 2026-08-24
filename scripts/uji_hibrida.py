"""Hibrida: template slot sebagai lantai, diperpanjang dengan kata tetangga
yang lolos penjaga -- aturan suara mayoritas yang sama dengan panjangkan_judul
di pipeline, tapi tanpa model sama sekali.
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
umum, merek_set = lex.get("umum", set()), lex.get("merek", set())

df = pd.read_parquet("data_drive/merged/merged_local.parquet",
                     columns=["title", "product_id"])
judul_katalog = [rp.clean_title(t) for t in df["title"].astype(str)]
indeks = rp.Indeks(judul_katalog)
baris_pid = {str(p): i for i, p in enumerate(df["product_id"])}
lini_baris = defaultdict(list)
for i, j in enumerate(judul_katalog):
    if j:
        lini_baris[j.split()[0].lower()].append(i)

UK = re.compile(r"(?i)\b(\d+(?:[.,]\d+)?\s*(?:gr?|kg|ml|lt?r?|liter|w|cm|pcs))\b")


def fakta_dari(r):
    j = str(r.get("judul_asli", ""))
    kata = re.sub(r"[^\w\s.\-/&+,']", " ", j).split()
    merek = next((w for w in kata[:4] if w.lower() in merek_set), "")
    jenis = next((w for w in kata
                  if w.lower() in umum and w.lower() not in merek_set and len(w) > 2), "")
    uk = UK.search(j)
    return {"jenis": jenis, "merek": merek,
            "ukuran": re.sub(r"\s+", "", uk.group(1)) if uk else "",
            "kategori": str(r.get("kategori_asli", ""))}


def blokir_untuk(r):
    i = baris_pid.get(str(r.get("product_id")))
    b = {i} if i is not None else set()
    if i is not None and judul_katalog[i]:
        b |= set(lini_baris[judul_katalog[i].split()[0].lower()])
    return b


def hibrida(r, k=5, batas=8):
    """Template dulu, lalu tambah kata yang MAYORITAS tetangga sepakat.

    Aturan penjaga sama seperti pipeline: kandidat wajib alfabet (jadi angka
    dan satuan tidak pernah ikut), bukan merek (merek tetangga selalu milik
    produk lain), dan muncul di lebih dari separuh tetangga.
    """
    f = fakta_dari(r)
    judul = [x for x in (f["jenis"], f["merek"], f["ukuran"]) if x]
    ada = {x.lower() for x in judul}
    cocok = indeks.cari(" ".join(str(v) for v in f.values()), k, blokir=blokir_untuk(r))
    if not cocok:
        return " ".join(judul)
    suara = Counter()
    for idx, _ in cocok:
        for w in set(judul_katalog[idx].split()):
            if w.isalpha() and len(w) > 2 and w.lower() not in merek_set:
                suara[w] += 1
    n = len(cocok)
    for w, c in suara.most_common():
        if len(judul) >= batas:
            break
        if c * 2 > n and w.lower() not in ada:
            judul.append(w)
            ada.add(w.lower())
    return " ".join(judul)


def template(r):
    f = fakta_dari(r)
    return " ".join(x for x in (f["jenis"], f["merek"], f["ukuran"]) if x)


print(f"{len(uji)} produk uji, masukan TEKS\n")
print(f"  {'metode':34} {'inti_f1':>9} {'halusinasi':>12} {'kata':>6}")
for nama, fn in (("template slot", template),
                 ("hibrida: template + suara tetangga", hibrida)):
    f1s, hal, pj = [], [], []
    for r in uji:
        j = fn(r)
        emas, kj = ev.kata(r.get("judul_asli", "")), ev.kata(j)
        if not emas or not kj:
            continue
        f1s.append(2 * len(emas & kj) / (len(emas) + len(kj)))
        hal.append(bool(kj - ev.kata(" ".join(str(v) for v in fakta_dari(r).values()))))
        pj.append(len(j.split()))
    print(f"  {nama:34} {st.mean(f1s):9.3f} {100*st.mean(hal):11.1f}% {st.mean(pj):6.1f}")
