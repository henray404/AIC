"""Coba murid VLM 3B: foto produk -> judul + deskripsi.

    python coba_vlm.py foto.jpg
    python coba_vlm.py foto.jpg --platform blibli
    python coba_vlm.py *.jpg                    # beberapa foto sekaligus

Bobot dasarnya diunduh otomatis dari HuggingFace saat pertama kali (~7 GB).
Butuh VRAM sekitar 7 GB; di CPU jalan tapi lambat sekali.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ADAPTER = Path(__file__).resolve().parent.parent / "murid_vlm_3b"
DASAR = "Qwen/Qwen2.5-VL-3B-Instruct"

# Persis prompt yang dipakai saat melatih.
PERINTAH = ("Lihat foto produk ini. Tulis listing untuk platform {platform}. "
            "Jawab JSON dengan kunci judul dan deskripsi. Jangan sebut ukuran, "
            "berat, garansi, izin, merek, atau khasiat yang tidak terlihat.")


def muat():
    import torch
    from peft import PeftModel
    from transformers import AutoModelForImageTextToText, AutoProcessor

    if not ADAPTER.exists():
        sys.exit(f"adapter tidak ditemukan: {ADAPTER}")
    perangkat = "cuda" if torch.cuda.is_available() else "cpu"
    if perangkat == "cpu":
        print("PERINGATAN: tidak ada GPU, satu foto bisa memakan beberapa menit\n")
    print(f"memuat {DASAR} di {perangkat} ...", flush=True)
    pro = AutoProcessor.from_pretrained(ADAPTER)
    model = AutoModelForImageTextToText.from_pretrained(
        DASAR, dtype=torch.bfloat16, device_map=perangkat)
    model = PeftModel.from_pretrained(model, str(ADAPTER)).eval()
    print("siap\n", flush=True)
    return pro, model, torch


def jalankan(pro, model, torch, foto: Path, platform: str) -> None:
    from PIL import Image

    mulai = time.time()
    with Image.open(foto) as im:
        gambar = im.convert("RGB")
        # Wajib. Model dilatih pada gambar maks 512x512; yang lebih besar
        # menghasilkan jumlah token penglihatan yang tidak pernah ia temui.
        gambar.thumbnail((512, 512))
        pesan = [{"role": "user", "content": [
            {"type": "image"},
            {"type": "text", "text": PERINTAH.format(platform=platform)}]}]
        teks = pro.apply_chat_template(pesan, tokenize=False,
                                       add_generation_prompt=True)
        enc = pro(text=[teks], images=[gambar], return_tensors="pt").to(model.device)

    with torch.no_grad():
        keluar = model.generate(**enc, max_new_tokens=220, do_sample=False)
    jawab = pro.tokenizer.decode(keluar[0][enc["input_ids"].shape[1]:],
                                 skip_special_tokens=True)

    print("=" * 74)
    print("FOTO     :", foto.name)
    print("PLATFORM :", platform)
    try:
        h = json.loads(jawab)
        print("JUDUL    :", h.get("judul"))
        print("DESKRIPSI:", h.get("deskripsi"))
    except json.JSONDecodeError:
        print("JSON tidak sah, keluaran mentah:")
        print(jawab[:400])
    print(f"           {time.time() - mulai:.1f} detik")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("foto", nargs="+", help="satu atau beberapa berkas gambar")
    ap.add_argument("--platform", default="tokopedia",
                    choices=("tokopedia", "blibli", "shopee", "umum"))
    args = ap.parse_args()

    jalur = [Path(f) for f in args.foto]
    hilang = [p for p in jalur if not p.exists()]
    if hilang:
        sys.exit("berkas tidak ditemukan: " + ", ".join(str(p) for p in hilang))

    pro, model, torch = muat()
    for p in jalur:
        jalankan(pro, model, torch, p, args.platform)

    print()
    print("Model ini tidak menyebut harga -- gurunya menghitungnya dari katalog,")
    print("dan murid tidak punya katalog. Judulnya juga cenderung pendek.")
    print("Lihat README di murid_vlm_3b/ untuk batasan selengkapnya.")


if __name__ == "__main__":
    main()
