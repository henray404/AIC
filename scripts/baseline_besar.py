"""Baseline: satu model besar mengerjakan tugas listing sendirian.

Pembanding yang sah untuk pipeline. Tanpa retrieval, tanpa katalog, tanpa
penjaga — persis cara orang memakai VLM besar apa adanya. Keluarannya dibuat
sebentuk dengan `retrieve_pipeline.py` supaya bisa dinilai `eval_listing.py`
dengan metrik yang sama.

Pilihan modelnya sengaja gemma3:12b: satu keluarga dengan gemma3:4b yang dipakai
pipeline, tepat 3x parameternya. Kalau pembandingnya model keluarga lain, selisih
yang terukur bisa berasal dari perbedaan data latih, bukan dari ukuran.

    python scripts/baseline_besar.py --n 100 --model gemma3:12b
    python scripts/baseline_besar.py --n 10 --iris 0:5      # potong jadi beberapa jalan
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import time
from pathlib import Path

import pandas as pd
import requests
from PIL import Image

PROJECT = Path(__file__).resolve().parent.parent
SUMBER = PROJECT / "data_drive" / "merged" / "merged_local.parquet"
OLLAMA = "http://localhost:11434/api/generate"

PLATFORM = ("blibli", "tokopedia", "shopee")

PROMPT = """Kamu penulis listing marketplace Indonesia. Lihat foto produk ini.

Tulis listing untuk platform {platform}. Aturan:
- Judul maksimal 12 kata, sebut jenis barang lebih dulu.
- Deskripsi 2-3 kalimat, menarik tapi hanya menyebut hal yang terlihat.
- Jangan mengarang ukuran, berat, garansi, izin BPOM, atau klaim khasiat.
- Kalau merek tidak terbaca di foto, jangan sebut merek apa pun.

Jawab JSON: {{"judul": "...", "deskripsi": "...", "kategori": "...", "perkiraan_harga": 0}}"""


def muat_gambar(path: Path, sisi_maks: int = 640) -> str:
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((sisi_maks, sisi_maks))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def tanya(model: str, prompt: str, b64: str, timeout: int) -> dict:
    r = requests.post(OLLAMA, timeout=timeout, json={
        "model": model, "prompt": prompt, "images": [b64], "stream": False,
        "format": "json", "options": {"temperature": 0.2, "num_predict": 400},
    })
    r.raise_for_status()
    mentah = (r.json().get("response") or "").strip()
    try:
        return json.loads(mentah)
    except json.JSONDecodeError:
        return {"_mentah": mentah[:300]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="gemma3:12b")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--iris", default=None, help="proses sebagian sampel, mis. 0:25")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--keluaran", default=None)
    args = ap.parse_args()

    keluaran = Path(args.keluaran) if args.keluaran else (
        PROJECT / "data_drive" / "eval" / f"baseline_{args.model.replace(':', '_')}.jsonl")
    keluaran.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(SUMBER)
    df = df[df["n_gambar_lokal"] > 0].reset_index(drop=True)
    # seed dan n sama persis dengan retrieve_pipeline.py -> produk yang diuji identik
    sampel = df.sample(args.n, random_state=args.seed)
    mode = "w"
    if args.iris:
        a, b = (int(x) for x in args.iris.split(":"))
        sampel = sampel.iloc[a:b]
        mode = "a" if a > 0 else "w"
    print(f"{args.model}: {len(sampel)} produk x {len(PLATFORM)} platform")

    t0 = time.time()
    hasil = []
    with keluaran.open(mode, encoding="utf-8") as f:
        for i, (_, r) in enumerate(sampel.iterrows(), 1):
            mulai = time.time()
            keluar, galat = {}, ""
            try:
                b64 = muat_gambar(Path(r["local_image_paths"][0]))
                for plat in PLATFORM:
                    keluar[plat] = tanya(args.model, PROMPT.format(platform=plat),
                                         b64, args.timeout)
            except Exception as e:
                galat = f"{type(e).__name__}: {e}"[:150]

            rec = {
                "product_id": r["product_id"], "source": r["source"],
                "judul_asli": r["title"], "harga_asli": int(r["price"]),
                "kategori_asli": r["kategori_umkm"],
                # kolom ini kosong supaya eval memperlakukan baseline dengan adil:
                # ia memang tidak punya tahap penglihatan terpisah maupun katalog
                "vlm": "", "tetangga": [], "skor_teratas": 0.0,
                "pakai_konteks": False, "dikenal": None, "platform": list(PLATFORM),
                "hasil": keluar, "detik": round(time.time() - mulai, 1), "galat": galat,
            }
            hasil.append(rec)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{i}/{len(sampel)}] {rec['detik']}s  {str(r['title'])[:44]}", flush=True)

    h = pd.DataFrame(hasil)
    print(f"\n{len(h)} produk, {h['detik'].mean():.1f} detik/produk, "
          f"total {time.time() - t0:.0f}s, {int((h['galat'] != '').sum())} galat")
    print(f"-> {keluaran}")


if __name__ == "__main__":
    main()
