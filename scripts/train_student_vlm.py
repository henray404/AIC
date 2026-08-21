"""Suling pipeline jadi SATU model penglihatan: foto masuk, listing keluar.

Ini tujuan akhir proyek. Guru adalah pipeline penuh — gemma3:4b melihat,
qwen2.5:7b menulis, retrieval katalog, penjaga leksikon: dua model dan satu
indeks. Murid satu VLM ~3B yang menerima foto yang sama dan langsung menjawab,
tanpa katalog dan tanpa penjaga.

Bedanya dengan `train_student.py`: di sana muridnya model teks yang menerima
fakta ketikan penjual. Lebih murah dilatih, tapi kehilangan input foto, jadi
klaimnya bukan lagi "menggantikan pipeline".

    python scripts/train_student_vlm.py --latih
    python scripts/train_student_vlm.py --infer --keluaran data_drive/eval/murid_vlm.jsonl

Bawaannya Qwen2.5-VL-3B-Instruct: Apache-2.0, tidak bergerbang, langsung unduh.
`google/gemma-3-4b-it` bisa dipakai lewat --dasar, tapi bobotnya bergerbang
lisensi dan butuh token HF; versi Ollama-nya GGUF Q4_K_M yang tidak bisa di-LoRA.

BELUM PERNAH DIJALANKAN. Ditulis tanpa GPU untuk mengujinya — `--selfcheck`
hanya memeriksa bentuk percakapan dan penyusunan batch, bukan latihannya.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data_drive" / "merged"
ADAPTER = PROJECT / "data_drive" / "murid_vlm_lora"
DASAR = "Qwen/Qwen2.5-VL-3B-Instruct"

PERINTAH = ("Lihat foto produk ini. Tulis listing untuk platform {platform}. "
            "Jawab JSON dengan kunci judul dan deskripsi. Jangan sebut ukuran, "
            "berat, garansi, izin, merek, atau khasiat yang tidak terlihat.")


def muat_contoh(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]


def pesan_murid(platform: str, jawaban: str | None) -> list[dict]:
    """Bentuk percakapan. `jawaban` None saat inferensi."""
    pesan = [{"role": "user", "content": [
        {"type": "image"},
        {"type": "text", "text": PERINTAH.format(platform=platform)}]}]
    if jawaban is not None:
        pesan.append({"role": "assistant",
                      "content": [{"type": "text", "text": jawaban}]})
    return pesan


class FotoListing(Dataset):
    """Satu contoh: foto produk -> listing satu platform.

    Rugi dihitung hanya di bagian jawaban. Token gambar jumlahnya ratusan dan
    isinya bukan sesuatu yang perlu diramalkan; melatihnya di situ membuang
    kapasitas dan membuat rugi terlihat turun tanpa jawabannya membaik.
    """

    def __init__(self, path: Path, prosesor, maks: int = 1024):
        self.baris = muat_contoh(path)
        self.prosesor, self.maks = prosesor, maks

    def __len__(self):
        return len(self.baris)

    def __getitem__(self, i):
        from PIL import Image

        b = self.baris[i]
        gambar = Image.open(b["gambar"]).convert("RGB")
        gambar.thumbnail((512, 512))       # kekang jumlah token penglihatan

        penuh = self.prosesor.apply_chat_template(
            pesan_murid(b["platform"], b["jawaban"]), tokenize=False)
        awal = self.prosesor.apply_chat_template(
            pesan_murid(b["platform"], None), tokenize=False,
            add_generation_prompt=True)

        enc = self.prosesor(text=[penuh], images=[gambar], return_tensors="pt",
                            truncation=True, max_length=self.maks)
        n_awal = len(self.prosesor.tokenizer(awal).input_ids)
        ids = enc["input_ids"][0]
        label = ids.clone()
        label[:min(n_awal, len(label))] = -100
        label[ids == self.prosesor.tokenizer.pad_token_id] = -100
        keluar = {k: (v[0] if torch.is_tensor(v) and v.dim() > 1 else v)
                  for k, v in enc.items()}
        keluar["labels"] = label
        return keluar


def susun(batch, pad_id):
    """Empuk kanan. Kunci penglihatan disatukan menurut baris, bukan ditumpuk."""
    n = max(len(b["input_ids"]) for b in batch)
    keluar: dict = {}
    ids, lab, mask = [], [], []
    for b in batch:
        sisa = n - len(b["input_ids"])
        ids.append(torch.cat([b["input_ids"], torch.full((sisa,), pad_id)]))
        lab.append(torch.cat([b["labels"], torch.full((sisa,), -100)]))
        mask.append(torch.cat([torch.ones(len(b["input_ids"])), torch.zeros(sisa)]))
    keluar["input_ids"] = torch.stack(ids).long()
    keluar["labels"] = torch.stack(lab).long()
    keluar["attention_mask"] = torch.stack(mask).long()
    for k in batch[0]:
        if k in ("input_ids", "labels", "attention_mask"):
            continue
        nilai = [b[k] for b in batch]
        # pixel_values Qwen2.5-VL berbentuk (petak, fitur): petak tiap gambar
        # disambung memanjang, bukan diberi dimensi batch baru.
        keluar[k] = (torch.cat(nilai, dim=0) if torch.is_tensor(nilai[0])
                     else nilai)
    return keluar


def _muat(args, latih: bool):
    from transformers import AutoModelForImageTextToText, AutoProcessor

    prosesor = AutoProcessor.from_pretrained(args.dasar)
    if prosesor.tokenizer.pad_token_id is None:
        prosesor.tokenizer.pad_token = prosesor.tokenizer.eos_token
    model = AutoModelForImageTextToText.from_pretrained(
        args.dasar, torch_dtype=torch.bfloat16, device_map="cuda")
    if latih:
        from peft import LoraConfig, get_peft_model

        # Hanya proyeksi bahasa yang dilatih. Menara penglihatan dibekukan:
        # 10k contoh terlalu sedikit untuk menggeser encoder gambar tanpa
        # merusaknya, dan yang perlu dipindahkan dari guru adalah cara MENULIS,
        # bukan cara melihat.
        model = get_peft_model(model, LoraConfig(
            r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"]))
        model.print_trainable_parameters()
    return prosesor, model


def latih(args):
    prosesor, model = _muat(args, latih=True)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()

    ds = FotoListing(DATA / "vlm_latih.jsonl", prosesor)
    dl = DataLoader(ds, batch_size=args.batch, shuffle=True,
                    collate_fn=lambda b: susun(b, prosesor.tokenizer.pad_token_id))
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                            lr=args.lr)
    total = max((len(dl) * args.epoch) // args.akumulasi, 1)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr,
                                                total_steps=total, pct_start=0.03)
    print(f"{len(ds):,} contoh, batch {args.batch} x akumulasi {args.akumulasi}, "
          f"{total:,} langkah optimasi")

    model.train()
    n, t0, jalan = 0, time.time(), 0.0
    for ep in range(args.epoch):
        for i, batch in enumerate(dl, 1):
            batch = {k: (v.to("cuda") if torch.is_tensor(v) else v)
                     for k, v in batch.items()}
            rugi = model(**batch).loss / args.akumulasi
            rugi.backward()
            jalan += rugi.item() * args.akumulasi
            if i % args.akumulasi:
                continue
            torch.nn.utils.clip_grad_norm_(
                [p for p in model.parameters() if p.requires_grad], 1.0)
            opt.step()
            sched.step()
            opt.zero_grad(set_to_none=True)
            n += 1
            if n % 25 == 0:
                print(f"[{n}/{total}] rugi {jalan / (25 * args.akumulasi):.4f}  "
                      f"{(time.time() - t0) / 60:.1f} mnt", flush=True)
                jalan = 0.0
        print(f"epoch {ep + 1} selesai")

    ADAPTER.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(ADAPTER)
    prosesor.save_pretrained(ADAPTER)
    print(f"-> {ADAPTER}")


def infer(args):
    from peft import PeftModel
    from PIL import Image

    prosesor, model = _muat(args, latih=False)
    model = PeftModel.from_pretrained(model, ADAPTER).eval()

    uji = muat_contoh(DATA / "vlm_uji.jsonl")
    # Satu baris keluaran per PRODUK memuat semua platform sekaligus — bentuk
    # yang sama dengan retrieve_pipeline.py, supaya eval_listing.py menilainya
    # dengan metrik yang persis sama.
    per_produk: dict[str, list[dict]] = {}
    for b in uji:
        per_produk.setdefault(b["product_id"], []).append(b)

    keluaran = Path(args.keluaran)
    keluaran.parent.mkdir(parents=True, exist_ok=True)
    with keluaran.open("w", encoding="utf-8") as f:
        for i, (pid, kelompok) in enumerate(per_produk.items(), 1):
            mulai = time.time()
            gambar = Image.open(kelompok[0]["gambar"]).convert("RGB")
            gambar.thumbnail((512, 512))
            hasil = {}
            for b in kelompok:
                teks = prosesor.apply_chat_template(
                    pesan_murid(b["platform"], None), tokenize=False,
                    add_generation_prompt=True)
                enc = prosesor(text=[teks], images=[gambar],
                               return_tensors="pt").to("cuda")
                with torch.no_grad():
                    keluar = model.generate(**enc, max_new_tokens=220,
                                            do_sample=False)
                jawab = prosesor.tokenizer.decode(
                    keluar[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
                try:
                    hasil[b["platform"]] = json.loads(jawab)
                except json.JSONDecodeError:
                    hasil[b["platform"]] = {"_mentah": jawab[:300]}

            r = kelompok[0]
            f.write(json.dumps({
                "product_id": pid, "source": r.get("source", ""),
                "judul_asli": r.get("judul_asli", ""),
                "harga_asli": int(r.get("harga_asli") or 0),
                "kategori_asli": r.get("kategori_asli", ""),
                # Murid melihat foto tapi tidak menuliskan bacaannya. vlm diisi
                # bacaan guru atas foto yang SAMA supaya merek_ketat% punya dasar;
                # tetangga tetap kosong karena murid memang tidak diberi katalog.
                "vlm": r.get("vlm", ""), "tetangga": [],
                "platform": [b["platform"] for b in kelompok], "hasil": hasil,
                "detik": round(time.time() - mulai, 2), "galat": "",
            }, ensure_ascii=False) + "\n")
            if i % 25 == 0:
                print(f"[{i}/{len(per_produk)}]", flush=True)
    print(f"-> {keluaran}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--latih", action="store_true")
    ap.add_argument("--infer", action="store_true")
    ap.add_argument("--dasar", default=DASAR)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--akumulasi", type=int, default=8)
    ap.add_argument("--epoch", type=int, default=1)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--keluaran",
                    default=str(PROJECT / "data_drive" / "eval" / "murid_vlm.jsonl"))
    args = ap.parse_args()
    if args.latih:
        latih(args)
    elif args.infer:
        infer(args)
    else:
        ap.error("pilih --latih atau --infer")


def _selfcheck():
    """Uji bentuk percakapan dan penyusunan batch. Tidak menyentuh GPU."""
    p = pesan_murid("tokopedia", None)
    assert len(p) == 1 and p[0]["role"] == "user"
    assert p[0]["content"][0]["type"] == "image"
    assert "tokopedia" in p[0]["content"][1]["text"]
    p = pesan_murid("blibli", '{"judul": "x"}')
    assert len(p) == 2 and p[1]["role"] == "assistant"

    def contoh(n_ids, n_tutup, n_petak):
        ids = torch.arange(1, n_ids + 1)
        lab = ids.clone()
        lab[:n_tutup] = -100
        return {"input_ids": ids, "labels": lab,
                "pixel_values": torch.zeros(n_petak, 3)}

    b = susun([contoh(6, 2, 4), contoh(3, 1, 4)], pad_id=0)
    assert b["input_ids"].shape == (2, 6), b["input_ids"].shape
    assert b["labels"].shape == b["input_ids"].shape
    # baris pendek diempukkan, dan empuknya tidak ikut dihitung rugi
    assert b["attention_mask"][1].tolist() == [1, 1, 1, 0, 0, 0]
    assert b["labels"][1].tolist()[3:] == [-100, -100, -100]
    assert b["labels"][1][0].item() == -100          # tutup prompt tetap ada
    # petak gambar disambung memanjang, bukan diberi dimensi batch baru
    assert b["pixel_values"].shape == (8, 3), b["pixel_values"].shape
    print("selfcheck ok")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        main()
