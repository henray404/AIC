"""Latih murid kecil dari label guru, lalu jalankan untuk dinilai.

Guru: pipeline penuh — gemma3:4b melihat foto, qwen2.5:7b menulis, retrieval
katalog, penjaga leksikon. Murid: satu model teks ~0,5B tanpa foto, tanpa
katalog, tanpa penjaga. Bukan pengetahuan yang disuling, melainkan gaya menulis
yang sudah lolos penjaga.

    python scripts/train_student.py --latih
    python scripts/train_student.py --infer --keluaran data_drive/eval/murid.jsonl

Sengaja tidak memakai TRL: API-nya bergeser antar versi minor, dan lingkaran
LoRA di sini cukup pendek untuk ditulis langsung dengan transformers + peft.
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
ADAPTER = PROJECT / "data_drive" / "murid_lora"
DASAR = "Qwen/Qwen2.5-0.5B-Instruct"


class Percakapan(Dataset):
    """Token penuh, tapi rugi hanya dihitung di bagian jawaban.

    Tanpa penopengan, model menghabiskan kapasitas menghafal templat prompt yang
    sama di tiap contoh, dan pada model 0,5B kapasitas itu tidak berlebih.
    """

    def __init__(self, path: Path, tok, maks: int = 640):
        self.baris = [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]
        self.tok, self.maks = tok, maks

    def __len__(self):
        return len(self.baris)

    def __getitem__(self, i):
        pesan = self.baris[i]["messages"]
        penuh = self.tok.apply_chat_template(pesan, tokenize=False)
        awal = self.tok.apply_chat_template(pesan[:-1], tokenize=False,
                                            add_generation_prompt=True)
        ids = self.tok(penuh, truncation=True, max_length=self.maks).input_ids
        n_awal = len(self.tok(awal, truncation=True, max_length=self.maks).input_ids)
        label = list(ids)
        label[:n_awal] = [-100] * min(n_awal, len(label))
        return {"input_ids": ids, "labels": label}


def susun(batch, pad_id):
    n = max(len(b["input_ids"]) for b in batch)
    ids, lab, mask = [], [], []
    for b in batch:
        sisa = n - len(b["input_ids"])
        ids.append(b["input_ids"] + [pad_id] * sisa)
        lab.append(b["labels"] + [-100] * sisa)
        mask.append([1] * len(b["input_ids"]) + [0] * sisa)
    t = torch.tensor
    return {"input_ids": t(ids), "labels": t(lab), "attention_mask": t(mask)}


def latih(args):
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(args.dasar)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.dasar, torch_dtype=torch.bfloat16, device_map="cuda")
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"]))
    model.print_trainable_parameters()
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()

    ds = Percakapan(DATA / "distill_latih.jsonl", tok)
    dl = DataLoader(ds, batch_size=args.batch, shuffle=True,
                    collate_fn=lambda b: susun(b, tok.pad_token_id))
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr)
    total = len(dl) * args.epoch
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=total,
                                                pct_start=0.03)
    print(f"{len(ds):,} contoh, {len(dl):,} langkah/epoch, {total:,} langkah total")

    model.train()
    langkah, t0, jalan = 0, time.time(), 0.0
    for ep in range(args.epoch):
        for batch in dl:
            batch = {k: v.to("cuda") for k, v in batch.items()}
            rugi = model(**batch).loss
            rugi.backward()
            torch.nn.utils.clip_grad_norm_(
                [p for p in model.parameters() if p.requires_grad], 1.0)
            opt.step()
            sched.step()
            opt.zero_grad(set_to_none=True)
            jalan += rugi.item()
            langkah += 1
            if langkah % 50 == 0:
                print(f"[{langkah}/{total}] rugi {jalan / 50:.4f}  "
                      f"{(time.time() - t0) / 60:.1f} mnt", flush=True)
                jalan = 0.0
        print(f"epoch {ep + 1} selesai")

    ADAPTER.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(ADAPTER)
    tok.save_pretrained(ADAPTER)
    print(f"-> {ADAPTER}")


def infer(args):
    import pandas as pd
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(ADAPTER)
    model = AutoModelForCausalLM.from_pretrained(
        args.dasar, torch_dtype=torch.bfloat16, device_map="cuda")
    model = PeftModel.from_pretrained(model, ADAPTER).eval()

    uji = [json.loads(l) for l in
           (DATA / "distill_uji.jsonl").open(encoding="utf-8") if l.strip()]
    inp = pd.read_parquet(DATA / "text_pairs.parquet")
    asal = {r.input: r for r in inp.itertuples()}

    keluaran = Path(args.keluaran)
    keluaran.parent.mkdir(parents=True, exist_ok=True)
    with keluaran.open("w", encoding="utf-8") as f:
        for i, b in enumerate(uji, 1):
            mulai = time.time()
            pesan = b["messages"][:-1]
            teks = tok.apply_chat_template(pesan, tokenize=False,
                                           add_generation_prompt=True)
            ids = tok(teks, return_tensors="pt").to("cuda")
            with torch.no_grad():
                keluar = model.generate(**ids, max_new_tokens=220, do_sample=False,
                                        pad_token_id=tok.pad_token_id)
            jawab = tok.decode(keluar[0][ids.input_ids.shape[1]:],
                               skip_special_tokens=True)
            try:
                h = json.loads(jawab)
            except json.JSONDecodeError:
                h = {"_mentah": jawab[:300]}

            # Bentuk keluaran disamakan dengan retrieve_pipeline.py supaya
            # eval_listing.py menilainya dengan metrik yang sama persis.
            masuk = pesan[-1]["content"]
            plat = masuk.split("|")[0].replace("platform:", "").strip()
            r = asal.get(masuk.split("|", 1)[1].strip())
            f.write(json.dumps({
                "product_id": getattr(r, "product_id", f"uji{i}"),
                "source": getattr(r, "source", ""),
                "judul_asli": getattr(r, "title", ""),
                "harga_asli": int(getattr(r, "price", 0) or 0),
                "kategori_asli": getattr(r, "kategori_umkm", ""),
                # Murid tidak melihat foto dan tidak punya katalog; kedua kolom
                # ini memang kosong, dan itu membuat merek_ketat% menghukum tiap
                # katanya. Nilai murid lewat inti dan desk_*, bukan merek_ketat%.
                "vlm": "", "tetangga": [],
                "platform": [plat], "hasil": {plat: h},
                "detik": round(time.time() - mulai, 2), "galat": "",
            }, ensure_ascii=False) + "\n")
            if i % 50 == 0:
                print(f"[{i}/{len(uji)}]", flush=True)
    print(f"-> {keluaran}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--latih", action="store_true")
    ap.add_argument("--infer", action="store_true")
    ap.add_argument("--dasar", default=DASAR)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--epoch", type=int, default=2)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--keluaran",
                    default=str(PROJECT / "data_drive" / "eval" / "murid.jsonl"))
    args = ap.parse_args()
    if args.latih:
        latih(args)
    elif args.infer:
        infer(args)
    else:
        ap.error("pilih --latih atau --infer")


def _selfcheck():
    """Uji penopengan label tanpa mengunduh model: tokenizer palsu sudah cukup."""
    import tempfile

    class TokPalsu:
        pad_token_id = 0

        def apply_chat_template(self, pesan, tokenize=False, add_generation_prompt=False):
            t = "".join(f"<{m['role']}>{m['content']}" for m in pesan)
            return t + "<assistant>" if add_generation_prompt else t

        def __call__(self, teks, truncation=False, max_length=None):
            ids = [ord(c) % 97 for c in teks]
            return type("O", (), {"input_ids": ids[:max_length]})()

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.jsonl"
        p.write_text(json.dumps({"messages": [
            {"role": "system", "content": "S"},
            {"role": "user", "content": "U"},
            {"role": "assistant", "content": "JAWAB"}]}), encoding="utf-8")
        ds = Percakapan(p, TokPalsu())
        b = ds[0]
        assert len(b["input_ids"]) == len(b["labels"])
        n_tutup = sum(1 for x in b["labels"] if x == -100)
        assert 0 < n_tutup < len(b["labels"]), (n_tutup, len(b["labels"]))
        # yang dilatih harus persis ekor jawaban, bukan templat prompt
        assert b["labels"][n_tutup:] == b["input_ids"][n_tutup:]
        batch = susun([ds[0], {"input_ids": [1, 2], "labels": [-100, 2]}], 0)
        assert batch["input_ids"].shape == batch["labels"].shape
        assert batch["attention_mask"][1].sum().item() == 2   # sisanya empuk
    print("selfcheck ok")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        main()
