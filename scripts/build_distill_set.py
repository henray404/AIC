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


def contoh(fakta_str: str, platform: str, h: dict) -> dict:
    masuk = f"platform: {platform} | {fakta_str}"
    keluar = json.dumps({"judul": str(h["judul"]).strip(),
                         "deskripsi": str(h["deskripsi"]).strip()},
                        ensure_ascii=False)
    return {"messages": [{"role": "system", "content": SISTEM},
                         {"role": "user", "content": masuk},
                         {"role": "assistant", "content": keluar}]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default=str(KELUARAN / "text_pairs.parquet"))
    ap.add_argument("--guru", required=True, help="jsonl keluaran retrieve_pipeline.py")
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
                per_produk.setdefault(pid, []).append(contoh(peta[pid], plat, h))
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


def _selfcheck():
    assert layak({"judul": "Botol Minum Tritan", "deskripsi": "A" * 50 + "."})
    assert not layak({"_mentah": "..."})
    assert not layak({"judul": "Botol", "deskripsi": "A" * 50 + "."})      # judul pendek
    assert not layak({"judul": "Botol Minum Tritan", "deskripsi": "pendek."})
    assert not layak({"judul": "Botol Minum Tritan", "deskripsi": "A" * 50})  # terpotong
    c = contoh("jenis: Botol", "tokopedia",
               {"judul": "Botol Minum", "deskripsi": "Praktis."})
    assert c["messages"][1]["content"].startswith("platform: tokopedia | jenis:")
    assert json.loads(c["messages"][2]["content"])["judul"] == "Botol Minum"
    print("selfcheck ok")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        main()
