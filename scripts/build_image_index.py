"""Sandikan gambar utama tiap produk jadi vektor CLIP, simpan sebagai indeks.

Pencarian teks sudah menemukan jenis barang yang benar, tapi salah kelas harga:
gaun Eprise Rp479.800 ditetanggai gaun pasar, sepatu Zedruz Rp116.899 dapat
tetangga sneakers murah. Teks tidak bisa membedakan barang premium dari barang
biasa kalau kata-katanya sama. Kemiripan visual bisa.

    python scripts/build_image_index.py                 # semua produk bergambar
    python scripts/build_image_index.py --batas 2000     # coba sebagian dulu

Keluaran: data_drive/merged/image_index.npz (emb float16 + pid)
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

PROJECT = Path(__file__).resolve().parent.parent
SUMBER = PROJECT / "data_drive" / "merged" / "merged_local.parquet"
TUJUAN = PROJECT / "data_drive" / "merged" / "image_index.npz"

MODEL = "ViT-B-32"
BOBOT = "laion2b_s34b_b79k"


def muat_model(device: str):
    import open_clip
    model, _, preprocess = open_clip.create_model_and_transforms(
        MODEL, pretrained=BOBOT, device=device)
    model.eval()
    return model, preprocess


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--batas", type=int, default=0, help="hanya proses N produk pertama")
    ap.add_argument("--batch", type=int, default=64)
    args = ap.parse_args()

    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"perangkat: {device}"
          + (f" ({torch.cuda.get_device_name(0)})" if device == "cuda" else ""))

    df = pd.read_parquet(SUMBER, columns=["product_id", "local_image_paths", "n_gambar_lokal"])
    df = df[df["n_gambar_lokal"] > 0].reset_index(drop=True)
    if args.batas:
        df = df.head(args.batas)
    # satu gambar utama per produk: galeri tokopedia rata-rata 7 berkas, dan
    # memakai semuanya membuat produk itu 7x lebih mungkin terpilih jadi tetangga
    jalur = [Path(p[0]) for p in df["local_image_paths"]]
    print(f"{len(jalur):,} produk bergambar")

    model, preprocess = muat_model(device)

    vektor, pid, gagal = [], [], 0
    mulai = time.time()
    for i in range(0, len(jalur), args.batch):
        potong = jalur[i:i + args.batch]
        gambar, ids = [], []
        for p, produk in zip(potong, df["product_id"].iloc[i:i + args.batch]):
            try:
                with Image.open(p) as im:
                    gambar.append(preprocess(im.convert("RGB")))
                ids.append(produk)
            except Exception:
                gagal += 1
        if not gambar:
            continue
        with torch.no_grad():
            batch = torch.stack(gambar).to(device)
            emb = model.encode_image(batch)
            emb = emb / emb.norm(dim=-1, keepdim=True)   # cosine jadi dot product
        vektor.append(emb.cpu().numpy().astype("float16"))
        pid.extend(ids)
        if (i // args.batch) % 20 == 0 and i:
            laju = (i + len(potong)) / (time.time() - mulai)
            print(f"  {i + len(potong):,}/{len(jalur):,}  {laju:.0f} gambar/detik  "
                  f"sisa ~{(len(jalur) - i) / laju / 60:.1f} menit", flush=True)

    emb = np.vstack(vektor)
    np.savez_compressed(TUJUAN, emb=emb, pid=np.array(pid))
    print(f"\n{len(pid):,} vektor {emb.shape[1]} dimensi, {gagal} gambar gagal dibaca")
    print(f"{time.time() - mulai:.0f} detik total")
    print(f"-> {TUJUAN}  ({TUJUAN.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
