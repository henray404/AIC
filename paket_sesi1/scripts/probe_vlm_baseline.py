"""Uji model vision bawaan: seberapa jauh ia sudah mengenali produk dari fotonya.

Menjawab satu pertanyaan sebelum melatih apa pun: **perlu fine-tune atau tidak?**
Kalau model dasar sudah menyebut bendanya dengan benar, fine-tune untuk pengenalan
itu mubazir — sisa pekerjaannya tinggal gaya bahasa, dan itu urusan prompt.

    python scripts/probe_vlm_baseline.py --n 100
    python scripts/probe_vlm_baseline.py --model qwen3-vl:4b --n 30

Berjalan lewat Ollama lokal, jadi gambar tidak pernah keluar dari mesin ini.
Skornya proksi otomatis (berapa kata isi dari judul yang muncul di jawaban model),
bukan penilaian manusia — hasil per baris ditulis supaya bisa diperiksa sendiri.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import re
import time
from pathlib import Path

import pandas as pd
import requests
from PIL import Image

PROJECT = Path(__file__).resolve().parent.parent
SUMBER = PROJECT / "data_drive" / "merged" / "train_pairs.parquet"
KELUARAN = PROJECT / "data_drive" / "eval" / "baseline_vlm.jsonl"
OLLAMA = "http://localhost:11434/api/generate"

# Prompt sengaja pendek. qwen3-vl model thinking: begitu diminta format terstruktur
# atau instruksi panjang, ia menalar tanpa henti sampai anggaran token habis dan
# `response` keluar kosong. Pertanyaan pendek konsisten menghasilkan jawaban.
PROMPT = "Barang apa di foto ini? Sebut jenis dan mereknya, singkat."

# kata yang tidak menandakan pengenalan benda
STOP = {
    "dan", "untuk", "yang", "dengan", "atau", "the", "for", "with", "of", "in",
    "pcs", "pack", "set", "isi", "pria", "wanita", "anak", "size", "all",
}


def kata_urut(teks) -> list[str]:
    """Kata isi, urutan asli dipertahankan (untuk mengambil inti judul)."""
    kata = re.findall(r"[a-zA-Z0-9]+", str(teks).lower())
    keluar = []
    for w in kata:
        if len(w) >= 3 and w not in STOP and w not in keluar:
            keluar.append(w)
    return keluar


def kata_isi(teks) -> set[str]:
    return set(kata_urut(teks))


def muat_gambar(path: Path, sisi_maks: int = 640) -> str:
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((sisi_maks, sisi_maks))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


BLOK_JSON = re.compile(r"\{.*\}", re.DOTALL)


def tanya(model: str, b64: str, timeout: int) -> dict:
    # Tanpa format="json": qwen3-vl model thinking, dan dengan format terkunci
    # seluruh keluarannya nyangkut di field `thinking` sementara `response` kosong.
    # Minta JSON lewat prompt saja, lalu parse longgar.
    r = requests.post(OLLAMA, timeout=timeout, json={
        "model": model,
        "prompt": PROMPT,
        "images": [b64],
        # JANGAN pasang think=False: Ollama lalu membuang isi penalaran, padahal
        # model tetap menghabiskan anggaran token di sana -> response DAN thinking
        # sama-sama kosong. Dibiarkan menyala supaya cadangan di bawah bisa dipakai.
        "stream": False,
        "options": {"temperature": 0, "num_predict": 500},
    })
    r.raise_for_status()
    j = r.json()
    mentah = (j.get("response") or "").strip()
    dari_thinking = False
    if not mentah:
        # model kehabisan anggaran saat menalar; isi pengenalannya tetap ada di
        # `thinking`, jadi dipakai sebagai cadangan dan ditandai
        mentah = (j.get("thinking") or "").strip()[-300:]
        dari_thinking = bool(mentah)

    blok = BLOK_JSON.search(mentah)
    if blok:
        try:
            hasil = json.loads(blok.group())
            hasil["_dari_thinking"] = dari_thinking
            return hasil
        except json.JSONDecodeError:
            pass
    return {"teks": mentah[:300], "_dari_thinking": dari_thinking}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="qwen3-vl:4b")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    df = pd.read_parquet(SUMBER)
    # jatah per sumber supaya tokopedia2025 yang kecil tetap terwakili
    jatah = {"tokopedia": 0.5, "blibli": 0.35, "tokopedia2025": 0.15}
    bagian = []
    for src, porsi in jatah.items():
        g = df[df["source"] == src]
        if len(g):
            bagian.append(g.sample(min(int(args.n * porsi) or 1, len(g)), random_state=args.seed))
    sampel = pd.concat(bagian)
    print(f"menguji {len(sampel)} gambar dengan {args.model}", flush=True)

    KELUARAN.parent.mkdir(parents=True, exist_ok=True)
    baris = []
    with KELUARAN.open("w", encoding="utf-8") as f:
        for i, (_, r) in enumerate(sampel.iterrows(), 1):
            p = Path(r["gambar"])
            mulai = time.time()
            try:
                jawab = tanya(args.model, muat_gambar(p), args.timeout)
                galat = ""
            except Exception as e:
                jawab, galat = {}, f"{type(e).__name__}: {e}"[:150]
            detik = time.time() - mulai

            teks_jawab = " ".join(str(v) for k, v in jawab.items()
                                  if v and not k.startswith("_"))
            urut = kata_urut(r["title_bersih"])
            emas, tebak = set(urut), kata_isi(teks_jawab)
            skor = len(emas & tebak) / len(emas) if emas else 0.0
            # 4 kata pertama judul ~ jenis barang + merek; sisanya ekor SEO,
            # jadi recall penuh menghukum judul panjang secara tidak adil
            inti = set(urut[:4])
            skor_inti = len(inti & tebak) / len(inti) if inti else 0.0
            kepala = str(r["title_bersih"]).split()[0].lower() if r["title_bersih"] else ""
            kepala_kena = bool(kepala) and kepala in tebak

            rec = {
                "product_id": r["product_id"], "source": r["source"],
                "gambar": str(p), "judul": r["title_bersih"],
                "kategori": r["kategori_umkm"], "keluaran": jawab,
                "skor": round(skor, 3), "skor_inti": round(skor_inti, 3),
                "kepala_kena": kepala_kena,
                "dari_thinking": bool(jawab.get("_dari_thinking")),
                "detik": round(detik, 2), "galat": galat,
            }
            baris.append(rec)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if i % 10 == 0:
                print(f"  [{i}/{len(sampel)}] skor rata-rata sejauh ini "
                      f"{sum(b['skor'] for b in baris) / len(baris):.2f}", flush=True)

    hasil = pd.DataFrame(baris)
    print()
    print(hasil.groupby("source").agg(
        n=("skor", "size"), skor_penuh=("skor", "mean"), skor_inti=("skor_inti", "mean"),
        kepala_kena=("kepala_kena", "mean"), detik=("detik", "mean"),
        galat=("galat", lambda s: int((s != "").sum())),
    ).round(3).to_string())
    print(f"\nkeseluruhan: skor inti {hasil['skor_inti'].mean():.3f}, "
          f"skor penuh {hasil['skor'].mean():.3f}, "
          f"kata kepala kena {100 * hasil['kepala_kena'].mean():.0f}%, "
          f"skor inti nol {int((hasil['skor_inti'] == 0).sum())}/{len(hasil)}, "
          f"jawaban benar-benar kosong "
          f"{int(hasil['keluaran'].map(lambda d: not str(d.get('teks', '')).strip()).sum())}, "
          f"{hasil['detik'].mean():.1f} detik/gambar")
    print(f"-> {KELUARAN}")


if __name__ == "__main__":
    main()
