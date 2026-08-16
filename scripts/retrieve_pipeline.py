"""Pipeline dua tahap: foto -> fakta terlihat -> cari di dataset -> judul + deskripsi.

Datasetnya dipakai **saat model bekerja**, bukan dilebur jadi bobot lewat latihan.
Uji sebelumnya menunjukkan model dasar sudah 90% benar menyebut jenis barang tapi
sering salah merek. Merek tidak bisa ditebak dari foto buram — tapi ada di 28 ribu
judul milikmu. Jadi: model melihat, dataset mengingat.

    python scripts/retrieve_pipeline.py --n 20
    python scripts/retrieve_pipeline.py --hanya-cari "sunscreen tube biru"

Indeksnya TF-IDF murni numpy/pandas — tanpa unduhan, tanpa GPU tambahan.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
import re
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd
import requests
from PIL import Image

from build_train_pairs import clean_title

PROJECT = Path(__file__).resolve().parent.parent
SUMBER = PROJECT / "data_drive" / "merged" / "merged_local.parquet"
KELUARAN = PROJECT / "data_drive" / "eval" / "pipeline_demo.jsonl"
OLLAMA = "http://localhost:11434/api/generate"

# gemma3 dipilih setelah diadu di 100 gambar yang sama: skor inti 0,483 lawan 0,371,
# dan nol keluaran yang bocor jadi teks penalaran (qwen3-vl bocor 11 dari 100).
MODEL_VISI = "gemma3:4b"
MODEL_TEKS = "qwen2.5:7b"

# "Langsung ke jawaban" perlu: gemma3 suka membuka dengan "Berikut adalah barang
# yang ada di foto tersebut:" dan menghabiskan anggaran sebelum sampai ke isinya.
PROMPT_VISI = ("Barang apa di foto ini? Sebut jenis dan mereknya saja, satu baris, "
               "langsung ke jawaban tanpa kalimat pembuka.")

# blok basa-basi toko yang tidak boleh dicontoh gayanya
SAMPAH = re.compile(
    r"(?i)selamat datang|happy shopping|budayakan membaca|wajib baca|mohon dibaca|"
    r"tidak menerima komplain|no complain|bukan tanggung jawab|gratis ongkir|"
    r"ongkos kirim|bubble wrap|harga dapat berubah|chat admin|whatsapp|0[0-9]{9,12}"
)
STOP = {"dan", "untuk", "yang", "dengan", "atau", "the", "for", "with", "pcs", "set"}


def token(teks) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", str(teks).lower())
            if len(w) >= 3 and w not in STOP]


class Indeks:
    """TF-IDF ringkas di atas judul produk. 28 ribu judul pendek — cukup dict."""

    def __init__(self, judul: list[str]):
        self.n = len(judul)
        self.inverted: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.panjang = []
        for i, j in enumerate(judul):
            t = token(j)
            self.panjang.append(math.sqrt(len(t)) or 1.0)
            hitung: dict[str, int] = defaultdict(int)
            for w in t:
                hitung[w] += 1
            for w, c in hitung.items():
                self.inverted[w].append((i, c))
        self.idf = {w: math.log(1 + self.n / len(post))
                    for w, post in self.inverted.items()}

    def cari(self, kueri: str, k: int = 5) -> list[tuple[int, float]]:
        skor: dict[int, float] = defaultdict(float)
        for w in set(token(kueri)):
            if w not in self.inverted:
                continue
            bobot = self.idf[w]
            for i, c in self.inverted[w]:
                skor[i] += bobot * (1 + math.log(c)) / self.panjang[i]
        return sorted(skor.items(), key=lambda x: -x[1])[:k]


def bersih_deskripsi(teks: str, maks: int = 320) -> str:
    kalimat = [s.strip() for s in re.split(r"[.\n]+", str(teks)) if s.strip()]
    baik = [s for s in kalimat if not SAMPAH.search(s)]
    return " ".join(baik)[:maks]


def muat_gambar(path: Path, sisi_maks: int = 640) -> str:
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((sisi_maks, sisi_maks))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def panggil(model: str, prompt: str, images=None, timeout=300, num_predict=500,
            minta_json=False) -> str:
    body = {"model": model, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.2, "num_predict": num_predict}}
    if images:
        body["images"] = images
    if minta_json:
        body["format"] = "json"
    r = requests.post(OLLAMA, timeout=timeout, json=body)
    r.raise_for_status()
    j = r.json()
    jawab = (j.get("response") or "").strip()
    if not jawab:
        # model thinking kehabisan anggaran: isinya masih ada di `thinking`
        jawab = (j.get("thinking") or "").strip()[-300:]
    return jawab


ANGKA = re.compile(r"\d+(?:[.,]\d+)?\s*(?:ml|l|gr|g|kg|liter|pcs|cm|mm|inch|watt|w)?\b",
                   re.IGNORECASE)


def samar_angka(teks: str) -> str:
    """Buang angka dan satuan dari contoh gaya, supaya tidak ikut tersalin."""
    return ANGKA.sub("…", str(teks))


def ringkas_konteks(tetangga: pd.DataFrame) -> str:
    """Ringkasan katalog: kosakata, kategori, kisaran harga — BUKAN judul utuh.

    Versi pertama menyodorkan judul tetangga apa adanya, dan model menyalin
    varian serta nomor model dari produk lain ("Sabun 5 Liter Lemongrass" untuk
    foto sabun blueberry). Yang boleh menular hanya kosakata dan harga.
    """
    harga = pd.to_numeric(tetangga["price"], errors="coerce").dropna()
    kat = tetangga["kategori_umkm"].mode()
    istilah: dict[str, int] = defaultdict(int)
    for j in tetangga["title_bersih"]:
        for w in token(j):
            if not any(c.isdigit() for c in w):
                istilah[w] += 1
    # Syarat muncul di >=2 tetangga. Nama merek khas hampir selalu muncul sekali,
    # jadi tersaring sendiri; kosakata umum ("keripik", "pisang") tetap lolos.
    # Tanpa ini merek tetangga menular: foto madu -> "Beverage Almaidani Nutrindo".
    umum = [w for w, c in sorted(istilah.items(), key=lambda x: -x[1])[:12] if c >= 2]
    gaya = [samar_angka(bersih_deskripsi(d, 130))
            for d in tetangga["description"].head(2) if str(d).strip()]

    bagian = [f"Kategori lazim: {kat.iloc[0] if len(kat) else 'tidak jelas'}"]
    if len(harga):
        bagian.append(
            f"Kisaran harga pasar untuk barang serupa: Rp{int(harga.quantile(0.25)):,} "
            f"- Rp{int(harga.quantile(0.75)):,} (tengah Rp{int(harga.median()):,})")
    bagian.append(f"Istilah yang lazim dipakai penjual: {', '.join(umum)}")
    if gaya:
        bagian.append("Contoh nada kalimat penjual (tiru nadanya saja, JANGAN salin isinya): "
                      + " | ".join(gaya))
    return "\n".join(bagian)


ATURAN = (
    "Tulis listing untuk produk di foto. Aturan:\n"
    "- Judul maksimal 12 kata, sebut jenis barang lebih dulu.\n"
    "- Deskripsi 2-3 kalimat, menarik tapi hanya menyebut hal yang terlihat.\n"
    "- DILARANG menyebut ukuran, isi, berat, rasa, varian, atau nomor model "
    "kecuali benar-benar terbaca di foto.\n"
    "- Jangan mengarang garansi, izin BPOM, atau klaim khasiat.\n"
    "- Kalau merek tidak terbaca di foto, jangan sebut merek apa pun.\n\n"
    'Jawab JSON: {"judul": "...", "deskripsi": "...", "kategori": "...", '
    '"perkiraan_harga": 0}'
)


def susun_prompt(fakta: str, tetangga: pd.DataFrame | None) -> str:
    kepala = ("Kamu penulis listing marketplace Indonesia.\n\n"
              f"Yang terlihat di foto produk: {fakta}\n\n")
    if tetangga is None or not len(tetangga):
        # tetangga terlalu jauh: lebih baik keluaran umum daripada salah meyakinkan
        return kepala + ATURAN
    return (kepala + "Rujukan dari katalog produk nyata (hanya untuk kosakata, "
            "kategori, dan harga — bukan untuk menyalin spesifikasi):\n"
            + ringkas_konteks(tetangga) + "\n\n" + ATURAN)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--k", type=int, default=5, help="berapa tetangga diambil")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--min-skor", type=float, default=2.0,
                    help="di bawah ini konteks katalog tidak dipakai sama sekali")
    ap.add_argument("--hanya-cari", default=None,
                    help="lewati model, cuma tunjukkan hasil pencarian untuk teks ini")
    args = ap.parse_args()

    df = pd.read_parquet(SUMBER)
    df = df[df["n_gambar_lokal"] > 0].reset_index(drop=True)
    df["title_bersih"] = [clean_title(t) for t in df["title"].astype(str)]
    df["description"] = df["description"].astype("object").fillna("").astype(str)
    print(f"katalog: {len(df):,} produk")

    indeks = Indeks(df["title_bersih"].tolist())
    print(f"indeks: {len(indeks.inverted):,} istilah unik")

    if args.hanya_cari:
        for i, s in indeks.cari(args.hanya_cari, args.k):
            r = df.iloc[i]
            print(f"  {s:6.2f}  {r['title_bersih'][:70]}  | {r['kategori_umkm']} | "
                  f"Rp{int(r['price']):,}")
        return

    sampel = df.sample(args.n, random_state=args.seed)
    KELUARAN.parent.mkdir(parents=True, exist_ok=True)
    hasil = []
    with KELUARAN.open("w", encoding="utf-8") as f:
        for i, (idx, r) in enumerate(sampel.iterrows(), 1):
            mulai = time.time()
            try:
                fakta = panggil(MODEL_VISI, PROMPT_VISI,
                                images=[muat_gambar(Path(r["local_image_paths"][0]))])
                cocok = indeks.cari(fakta, args.k + 1)
                # buang dirinya sendiri kalau kebetulan terambil
                cocok = [(j, s) for j, s in cocok if j != idx][:args.k]
                skor_teratas = cocok[0][1] if cocok else 0.0
                # tetangga terlalu jauh -> jangan beri konteks sama sekali
                pakai = skor_teratas >= args.min_skor
                tetangga = df.iloc[[j for j, _ in cocok]] if pakai else df.iloc[[]]
                mentah = panggil(MODEL_TEKS, susun_prompt(fakta, tetangga if pakai else None),
                                 num_predict=400, minta_json=True)
                try:
                    keluar = json.loads(mentah)
                except json.JSONDecodeError:
                    keluar = {"_mentah": mentah[:300]}
                galat = ""
            except Exception as e:
                fakta, tetangga, keluar = "", df.iloc[[]], {}
                skor_teratas, pakai = 0.0, False
                galat = f"{type(e).__name__}: {e}"[:150]

            rec = {
                "product_id": r["product_id"], "source": r["source"],
                "judul_asli": r["title_bersih"], "harga_asli": int(r["price"]),
                "kategori_asli": r["kategori_umkm"], "vlm": fakta,
                "skor_teratas": round(float(skor_teratas), 2), "pakai_konteks": bool(pakai),
                "tetangga": tetangga["title_bersih"].tolist() if len(tetangga) else [],
                "hasil": keluar, "detik": round(time.time() - mulai, 1), "galat": galat,
            }
            hasil.append(rec)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{i}/{len(sampel)}] {rec['detik']}s  {r['title_bersih'][:45]}")

    h = pd.DataFrame(hasil)
    print(f"\n{len(h)} produk, {h['detik'].mean():.1f} detik/produk, "
          f"{int((h['galat'] != '').sum())} galat")
    print(f"-> {KELUARAN}")


if __name__ == "__main__":
    main()
