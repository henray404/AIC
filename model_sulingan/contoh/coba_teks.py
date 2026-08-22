"""Coba murid teks 0,5B: keterangan produk ketikan -> judul + deskripsi.

    python coba_teks.py
    python coba_teks.py "jenis: Kopi | merek: Kapal Api | ukuran: 165gr | harga: 12000"
    python coba_teks.py "jenis: Tas | kategori: fashion_perawatan" --platform blibli

Tanpa argumen, empat contoh bawaan dijalankan. Bobot dasarnya diunduh otomatis
dari HuggingFace saat pertama kali (~1 GB).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ADAPTER = Path(__file__).resolve().parent.parent / "murid_teks_0.5b"
DASAR = "Qwen/Qwen2.5-0.5B-Instruct"

# Persis prompt yang dipakai saat melatih. Menyimpang darinya membuat
# keluarannya kacau -- model 0,5B tidak punya kelenturan untuk itu.
SISTEM = ("Kamu penulis listing marketplace Indonesia. Dari fakta produk, "
          "tulis judul dan deskripsi. Jangan sebut apa pun yang tidak ada di "
          "fakta — tidak ada ukuran, berat, garansi, izin, atau klaim khasiat "
          "yang dikarang.")

CONTOH = [
    "jenis: Minyak | merek: Sunco | ukuran: 2Liter | kategori: bumbu_masak | harga: 60000",
    "jenis: Sepatu | merek: Keeping | kategori: fashion_perawatan | harga: 177550",
    "jenis: Keripik | ukuran: 250gr | kategori: camilan_olahan | harga: 15000",
    "jenis: Speaker | merek: JBL | kategori: lainnya | harga: 247603",
]


def muat():
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not ADAPTER.exists():
        sys.exit(f"adapter tidak ditemukan: {ADAPTER}")
    perangkat = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"memuat {DASAR} di {perangkat} ...", flush=True)
    tok = AutoTokenizer.from_pretrained(ADAPTER)
    model = AutoModelForCausalLM.from_pretrained(
        DASAR, dtype=torch.bfloat16, device_map=perangkat)
    model = PeftModel.from_pretrained(model, str(ADAPTER)).eval()
    print("siap\n", flush=True)
    return tok, model, torch


def jalankan(tok, model, torch, fakta: str, platform: str) -> None:
    mulai = time.time()
    pesan = [{"role": "system", "content": SISTEM},
             {"role": "user", "content": f"platform: {platform} | {fakta}"}]
    teks = tok.apply_chat_template(pesan, tokenize=False, add_generation_prompt=True)
    ids = tok(teks, return_tensors="pt").to(model.device)
    with torch.no_grad():
        keluar = model.generate(**ids, max_new_tokens=220, do_sample=False,
                                pad_token_id=tok.pad_token_id or tok.eos_token_id)
    jawab = tok.decode(keluar[0][ids.input_ids.shape[1]:], skip_special_tokens=True)

    print("=" * 74)
    print("MASUKAN  :", fakta)
    print("PLATFORM :", platform)
    try:
        h = json.loads(jawab)
        print("JUDUL    :", h.get("judul"))
        print("DESKRIPSI:", h.get("deskripsi"))
    except json.JSONDecodeError:
        # jarang, tapi mungkin -- model kadang membungkus JSON dengan pagar kode
        print("JSON tidak sah, keluaran mentah:")
        print(jawab[:400])
    print(f"           {time.time() - mulai:.1f} detik")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fakta", nargs="*",
                    help="keterangan produk; kosong = pakai contoh bawaan")
    ap.add_argument("--platform", default="tokopedia",
                    choices=("tokopedia", "blibli", "shopee", "umum"))
    args = ap.parse_args()

    tok, model, torch = muat()
    for fakta in (args.fakta or CONTOH):
        jalankan(tok, model, torch, fakta, args.platform)

    if not args.fakta:
        print()
        print("Perhatikan: merek di masukan sering HILANG dari judul, dan warna,")
        print("rasa, atau bentuk kemasan sering DIKARANG. Dua kegagalan berbeda,")
        print("keduanya terukur -- lihat README di murid_teks_0.5b/.")


if __name__ == "__main__":
    main()
