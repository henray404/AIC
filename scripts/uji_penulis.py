"""Ablasi penulis: qwen2.5:7b lawan template, dengan bacaan foto yang SAMA.

Pertanyaannya bukan "apakah pipeline mengalahkan template" -- itu sudah
dijawab uji_tradisional.py, tapi tidak adil, karena di sana template
menerima fakta yang diekstrak dari judul emas sedangkan pipeline harus
membaca foto.

Di sini keduanya berangkat dari medan `vlm` yang sama persis: teks yang
gemma3:4b hasilkan saat melihat foto produk, sudah tersimpan di berkas
hasil. Jadi yang dibandingkan murni langkah PENULISAN.

Kalau selisihnya kecil, qwen2.5:7b -- 7 miliar parameter, ~1,5 detik per
listing -- tidak membayar ongkosnya, dan pipeline memang overkill di
bagian itu. Kalau besar, penulis LLM memang bekerja.

Tanpa GPU: bacaan foto dibaca dari berkas, tidak dihasilkan ulang.
"""
import json
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
import eval_listing as ev
import retrieve_pipeline as rp

uji = [json.loads(l) for l in Path("hasil_sesi2/S3_pipeline_lini.jsonl").open(encoding="utf-8")
       if l.strip()]
lex = rp.muat_lexicon()
umum, merek_set = lex.get("umum", set()), lex.get("merek", set())

UK = re.compile(r"(?i)\b(\d+(?:[.,]\d+)?\s*(?:gr?|kg|ml|lt?r?|liter|w|cm|pcs))\b")


def fakta_dari_foto(r):
    """Slot diisi dari bacaan foto -- sumber yang sama dengan yang dipakai
    pipeline, bukan dari judul emas."""
    baca = str(r.get("vlm") or "")
    kata = re.sub(r"[^\w\s.\-/&+,']", " ", baca).split()
    merek = next((w for w in kata if w.lower() in merek_set), "")
    jenis = next((w for w in kata
                  if w.lower() in umum and w.lower() not in merek_set and len(w) > 2), "")
    uk = UK.search(baca)
    return jenis, merek, (re.sub(r"\s+", "", uk.group(1)) if uk else "")


def judul_template(r):
    return " ".join(x for x in fakta_dari_foto(r) if x)


def judul_pipeline(r, plat):
    h = (r.get("hasil") or {}).get(plat) or {}
    return str(h.get("judul") or "")


def ukur(judul, r):
    emas, kj = ev.kata(r.get("judul_asli", "")), ev.kata(judul)
    if not emas or not kj:
        return None
    f1 = 2 * len(emas & kj) / (len(emas) + len(kj))
    # Halusinasi diukur terhadap bacaan foto -- kata di judul yang tidak
    # terlihat di foto. Definisi yang sama dengan kata_asing di eval_listing.
    return f1, bool(kj - ev.kata(str(r.get("vlm") or ""))), len(judul.split())


PLAT = ["blibli", "tokopedia", "shopee"]
print(f"{len(uji)} produk, bacaan foto identik, yang berbeda hanya PENULIS\n")
print(f"  {'penulis':34} {'inti_f1':>9} {'kata_asing':>12} {'kata':>6}")

for nama, fn in (("template (nol model, CPU)", lambda r, p: judul_template(r)),
                 ("qwen2.5:7b (pipeline)", judul_pipeline)):
    f1s, hal, pj = [], [], []
    for r in uji:
        for p in PLAT:
            j = fn(r, p)
            m = ukur(j, r)
            if m:
                f1s.append(m[0]); hal.append(m[1]); pj.append(m[2])
    print(f"  {nama:34} {st.mean(f1s):9.3f} {100*st.mean(hal):11.1f}% {st.mean(pj):6.1f}")

# Berapa banyak bacaan foto yang bahkan tidak menghasilkan satu slot pun?
kosong = sum(1 for r in uji if not judul_template(r).strip())
print(f"\n  template gagal total (nol slot terisi): {kosong}/{len(uji)}"
      f" = {100*kosong/len(uji):.1f}%")
print("  -- pada produk ini template tidak mengeluarkan apa pun,")
print("     sementara pipeline tetap menulis judul.")
