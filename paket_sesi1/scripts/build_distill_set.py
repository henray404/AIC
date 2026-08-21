"""Sambungkan label guru ke sisi input, hasilkan berkas latih murid.

Guru = `retrieve_pipeline.py` (gemma3:4b lihat + qwen2.5:7b tulis + retrieval +
penjaga). Murid = satu model teks kecil tanpa gambar, tanpa katalog, tanpa
penjaga. Yang disuling bukan pengetahuannya, melainkan GAYA menulis yang sudah
lolos penjaga — murid tidak akan pernah punya katalog untuk diperiksa.

Sisi input dari `build_text_pairs.py`, label dari keluaran pipeline, disambung
lewat `product_id`. Satu contoh latih per platform, dan platformnya ikut masuk
ke input, supaya murid belajar membedakan gaya tiap lapak.

    python scripts/build_distill_set.py \
        --input  data_drive/merged/text_pairs.parquet \
        --guru   data_drive/eval/guru.jsonl

Keluaran `data_drive/merged/distill_{latih,uji}.jsonl` dalam bentuk pesan chat.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parent.parent
KELUARAN = PROJECT / "data_drive" / "merged"

SISTEM = ("Kamu penulis listing marketplace Indonesia. Dari fakta produk, "
          "tulis judul dan deskripsi. Jangan sebut apa pun yang tidak ada di "
          "fakta — tidak ada ukuran, berat, garansi, izin, atau klaim khasiat "
          "yang dikarang.")


def layak(h: dict) -> bool:
    """Buang label yang gurunya sendiri gagal menghasilkan dengan benar."""
    if not isinstance(h, dict) or "_mentah" in h:
        return False
    judul, desk = str(h.get("judul", "")).strip(), str(h.get("deskripsi", "")).strip()
    if len(judul.split()) < 3 or len(desk) < 40:
        return False
    # Kalimat terpotong berarti anggaran token guru habis di tengah. Melatih
    # murid pada potongan mengajarinya berhenti mendadak.
    return desk[-1] in ".!?"


def contoh(fakta_str: str, platform: str, h: dict, r: dict) -> dict:
    """Contoh latih, dengan metadata produknya disematkan di baris yang sama.

    Metadata ikut ditulis, bukan dicari lagi saat inferensi. Teks fakta TIDAK
    unik — 383 kelompok mencakup 870 dari 10.003 baris, misalnya sembilan kaos
    Cardinal berbeda yang semuanya menjadi "jenis: T-Shirt | merek: Cardinal |
    kategori: fashion_perawatan | harga: 217000". Memetakan teks fakta kembali
    ke produknya lewat dict membuat entri saling menimpa, dan 8,7% baris
    keluaran mencatat judul_asli milik produk lain — termasuk saat `inti`
    dihitung, jadi angkanya tidak bisa dipercaya.

    `Percakapan` di train_student.py hanya membaca kunci `messages`, jadi kunci
    tambahan ini tidak menyentuh latihannya.
    """
    masuk = f"platform: {platform} | {fakta_str}"
    keluar = json.dumps({"judul": str(h["judul"]).strip(),
                         "deskripsi": str(h["deskripsi"]).strip()},
                        ensure_ascii=False)
    return {"messages": [{"role": "system", "content": SISTEM},
                         {"role": "user", "content": masuk},
                         {"role": "assistant", "content": keluar}],
            "product_id": str(r.get("product_id")), "platform": platform,
            "source": r.get("source", ""), "judul_asli": r.get("judul_asli", ""),
            "harga_asli": r.get("harga_asli", 0),
            "kategori_asli": r.get("kategori_asli", "")}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default=str(KELUARAN / "text_pairs.parquet"))
    ap.add_argument("--guru", required=True, help="jsonl keluaran retrieve_pipeline.py")
    ap.add_argument("--vlm", action="store_true",
                    help="tulis juga bentuk penglihatan (foto -> listing) untuk "
                         "train_student_vlm.py, bukan hanya bentuk teks")
    ap.add_argument("--merged", default=str(KELUARAN / "merged_local.parquet"),
                    help="sumber jalur foto lokal untuk bentuk --vlm")
    ap.add_argument("--uji", type=float, default=0.05, help="porsi untuk berkas uji")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    inp = pd.read_parquet(args.input)
    peta = dict(zip(inp["product_id"].astype(str), inp["input"]))
    print(f"{len(peta):,} produk punya sisi input")

    baris = [json.loads(l) for l in Path(args.guru).open(encoding="utf-8") if l.strip()]
    print(f"{len(baris):,} baris label guru")

    per_produk: dict[str, list[dict]] = {}
    n_buang = 0
    for r in baris:
        pid = str(r.get("product_id"))
        if pid not in peta:
            continue
        for plat, h in (r.get("hasil") or {}).items():
            if layak(h):
                per_produk.setdefault(pid, []).append(contoh(peta[pid], plat, h, r))
            else:
                n_buang += 1
    print(f"{len(per_produk):,} produk tersambung, "
          f"{sum(len(v) for v in per_produk.values()):,} contoh, {n_buang:,} label dibuang")

    # Pisah per PRODUK, bukan per contoh. Satu produk menghasilkan beberapa
    # listing yang isinya nyaris sama; kalau dipisah per contoh, kembarannya
    # bocor ke berkas uji dan skornya jadi lebih bagus dari kenyataan.
    pid_semua = sorted(per_produk)
    random.Random(args.seed).shuffle(pid_semua)
    n_uji = max(1, int(len(pid_semua) * args.uji))
    pid_uji, pid_latih = set(pid_semua[:n_uji]), pid_semua[n_uji:]

    for nama, pids in (("latih", pid_latih), ("uji", sorted(pid_uji))):
        p = KELUARAN / f"distill_{nama}.jsonl"
        n = 0
        with p.open("w", encoding="utf-8") as f:
            for pid in pids:
                for c in per_produk[pid]:
                    f.write(json.dumps(c, ensure_ascii=False) + "\n")
                    n += 1
        print(f"  {nama}: {len(pids):,} produk, {n:,} contoh -> {p}")

    if args.vlm:
        tulis_vlm(baris, peta, args.merged, pid_latih, sorted(pid_uji))


def tulis_vlm(baris, peta, merged, pid_latih, pid_uji):
    """Bentuk kedua: foto -> listing, untuk train_student_vlm.py.

    Pemisahan latih/uji memakai daftar produk yang SAMA dengan bentuk teks,
    supaya kedua murid diuji pada produk yang sama dan skornya bisa disandingkan.
    """
    df = pd.read_parquet(merged, columns=["product_id", "local_image_paths",
                                          "n_gambar_lokal"])
    foto = {str(r.product_id): r.local_image_paths[0]
            for r in df.itertuples() if r.n_gambar_lokal > 0}
    print(f"{len(foto):,} produk punya foto lokal")

    per_produk: dict[str, list[dict]] = {}
    tanpa_foto = 0
    for r in baris:
        pid = str(r.get("product_id"))
        if pid not in peta:
            continue
        if pid not in foto:
            tanpa_foto += 1
            continue
        for plat, h in (r.get("hasil") or {}).items():
            if not layak(h):
                continue
            per_produk.setdefault(pid, []).append({
                "product_id": pid, "platform": plat, "gambar": foto[pid],
                "jawaban": json.dumps({"judul": str(h["judul"]).strip(),
                                       "deskripsi": str(h["deskripsi"]).strip()},
                                      ensure_ascii=False),
                # bacaan guru atas foto yang sama; dipakai eval_listing.py
                # sebagai bukti penglihatan saat menilai murid
                "vlm": r.get("vlm", ""), "source": r.get("source", ""),
                "judul_asli": r.get("judul_asli", ""),
                "harga_asli": r.get("harga_asli", 0),
                "kategori_asli": r.get("kategori_asli", ""),
            })
    if tanpa_foto:
        print(f"  {tanpa_foto:,} baris dilewati: tidak ada foto lokalnya")

    for nama, pids in (("latih", pid_latih), ("uji", pid_uji)):
        p = KELUARAN / f"vlm_{nama}.jsonl"
        n = 0
        with p.open("w", encoding="utf-8") as f:
            for pid in pids:
                for c in per_produk.get(pid, []):
                    f.write(json.dumps(c, ensure_ascii=False) + "\n")
                    n += 1
        print(f"  vlm {nama}: {n:,} contoh -> {p}")


def _selfcheck():
    assert layak({"judul": "Botol Minum Tritan", "deskripsi": "A" * 50 + "."})
    assert not layak({"_mentah": "..."})
    assert not layak({"judul": "Botol", "deskripsi": "A" * 50 + "."})      # judul pendek
    assert not layak({"judul": "Botol Minum Tritan", "deskripsi": "pendek."})
    assert not layak({"judul": "Botol Minum Tritan", "deskripsi": "A" * 50})  # terpotong
    c = contoh("jenis: Botol", "tokopedia",
               {"judul": "Botol Minum", "deskripsi": "Praktis."},
               {"product_id": "p1", "judul_asli": "Botol Minum Tritan 2 Liter",
                "harga_asli": 33000, "source": "tokopedia",
                "kategori_asli": "kriya_rumah"})
    assert c["messages"][1]["content"].startswith("platform: tokopedia | jenis:")
    assert json.loads(c["messages"][2]["content"])["judul"] == "Botol Minum"

    # Metadata harus menempel di barisnya. Dua produk berbeda boleh punya teks
    # fakta yang persis sama -- itu yang membuat pencarian balik lewat dict
    # menimpa entri dan menyilangkan judul_asli antar produk.
    assert c["product_id"] == "p1"
    assert c["judul_asli"] == "Botol Minum Tritan 2 Liter"
    kembar = contoh("jenis: Botol", "tokopedia",
                    {"judul": "Botol Minum", "deskripsi": "Praktis."},
                    {"product_id": "p2", "judul_asli": "Botol Minum Jumbo 1 Liter",
                     "harga_asli": 21000, "source": "blibli",
                     "kategori_asli": "kriya_rumah"})
    assert c["messages"][1] == kembar["messages"][1]      # input identik
    assert c["product_id"] != kembar["product_id"]        # produknya tidak
    assert c["judul_asli"] != kembar["judul_asli"]
    print("selfcheck ok")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        main()
