---
base_model: Qwen/Qwen2.5-VL-3B-Instruct
library_name: peft
pipeline_tag: image-text-to-text
language: [id]
tags:
- lora
- marketplace
- indonesian
- vision-language
---

# Murid VLM 3B

Adapter LoRA di atas **Qwen2.5-VL-3B-Instruct**. Menerima **foto produk**,
menghasilkan judul dan deskripsi listing dalam bahasa Indonesia.

Ini murid yang lebih penting dari keduanya: masukannya sama dengan pipeline
guru, jadi ia benar-benar bisa menggantikannya.

## Format masukan — wajib persis begini

```
user      : [gambar] + "Lihat foto produk ini. Tulis listing untuk platform
            {platform}. Jawab JSON dengan kunci judul dan deskripsi. Jangan
            sebut ukuran, berat, garansi, izin, merek, atau khasiat yang tidak
            terlihat."
assistant : {"judul": "...", "deskripsi": "..."}
```

`platform` yang dikenal: `tokopedia`, `blibli`, `shopee`, `umum`.

**Fotonya dikecilkan ke maksimal 512×512** saat latihan. Memberi gambar jauh
lebih besar menghasilkan jumlah token penglihatan yang tidak pernah ia temui —
kecilkan dulu dengan `thumbnail((512, 512))`.

## Hasil pada 492 produk uji

Produk uji ditahan dari latihan. Semua sistem diukur pada produk yang sama.

| sistem | params | judul cocok ↑ | merek karangan ↓ | spek karangan ↓ | kata asing ↓ |
|---|---:|---:|---:|---:|---:|
| Pipeline (guru) | 4B+7B | 0,364 | 3,6% | 0,9% | 0,0% |
| **Murid VLM (ini)** | **3B** | **0,315** | 11,4% | 12,3% | 8,7% |
| gemma3:12b sendirian | 12B | 0,267 | 14,4% | 24,1% | 28,3% |

**Mengalahkan gemma3:12b di ketiganya** dengan model empat kali lebih kecil.
Mencapai 87% mutu judul gurunya sambil menanggalkan katalog 28.443 produk,
CLIP, dan seluruh lapisan penjaga.

## Batasan yang terukur

**Jaminan gurunya tidak ikut pindah.** Guru mencapai 0% kata asing karena ada
kode yang memeriksa keluarannya lalu membuang yang tak berdasar — bukan karena
modelnya lebih pintar. Kode itu tidak berpindah lewat fine-tune:

```
merek karangan   3,6%  →  11,4%
kata asing       0,0%  →   8,7%
spek karangan    0,9%  →  12,3%
```

Kalau butuh jaminan setara gurunya, pasang penjaganya terpisah di keluaran
model ini. Ia hanya butuh daftar kata, bukan katalog — jauh lebih ringan
daripada pipeline penuh.

**Judulnya pendek.** Hanya 4,1% judul masuk rentang panjang lazim platform,
lawan 55,4% milik gemma3:12b. Guru mencapainya lewat langkah terpisah yang
menambahkan kata dari produk kembar di katalog, dan langkah itu juga tidak
tersuling. Untuk Tokopedia yang bermedian 15 kata, judul model ini akan terasa
terlalu ringkas.

**Tidak menyebut harga.** Guru menghitung harga dari tetangga katalog; murid
tidak punya katalog, jadi tidak pernah dilatih memprediksinya.

## Cara menjalankan

```bash
pip install transformers peft torch pillow
```

```python
import json, torch
from PIL import Image
from peft import PeftModel
from transformers import AutoModelForImageTextToText, AutoProcessor

ADAPTER = "model_sulingan/murid_vlm_3b"
PERINTAH = ("Lihat foto produk ini. Tulis listing untuk platform {platform}. "
            "Jawab JSON dengan kunci judul dan deskripsi. Jangan sebut ukuran, "
            "berat, garansi, izin, merek, atau khasiat yang tidak terlihat.")

pro = AutoProcessor.from_pretrained(ADAPTER)
model = AutoModelForImageTextToText.from_pretrained(
    "Qwen/Qwen2.5-VL-3B-Instruct", dtype=torch.bfloat16, device_map="cuda")
model = PeftModel.from_pretrained(model, ADAPTER).eval()

gambar = Image.open("produk.jpg").convert("RGB")
gambar.thumbnail((512, 512))            # penting — sama seperti saat latihan

pesan = [{"role": "user", "content": [
    {"type": "image"},
    {"type": "text", "text": PERINTAH.format(platform="tokopedia")}]}]
teks = pro.apply_chat_template(pesan, tokenize=False, add_generation_prompt=True)
enc = pro(text=[teks], images=[gambar], return_tensors="pt").to(model.device)

with torch.no_grad():
    keluar = model.generate(**enc, max_new_tokens=220, do_sample=False)
jawab = pro.tokenizer.decode(keluar[0][enc["input_ids"].shape[1]:],
                             skip_special_tokens=True)
print(json.loads(jawab))
```

VRAM saat inferensi ~7 GB. Sesak di kartu 8 GB kalau ada model lain yang
sedang dimuat.

## Cara melatihnya

| | |
|---|---|
| metode | LoRA, `r=16`, `alpha=32`, `dropout=0.05` |
| modul target | `q_proj k_proj v_proj o_proj gate_proj up_proj down_proj` |
| menara penglihatan | **dibekukan** |
| epoch | 1 |
| batch | 1, akumulasi gradien 8 |
| learning rate | 1e-4, OneCycleLR, warmup 3% |
| ukuran gambar | dikecilkan ke maks 512×512 |
| rugi | hanya di bagian jawaban; prompt dan token gambar ditutup `-100` |

Menara penglihatan dibekukan dengan sengaja: 6.000 contoh terlalu sedikit untuk
menggeser encoder gambar tanpa merusaknya, dan yang perlu dipindahkan dari guru
adalah cara **menulis**, bukan cara melihat.

Skripnya `scripts/train_student_vlm.py` di repo asal.
