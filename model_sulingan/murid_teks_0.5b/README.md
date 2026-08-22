---
base_model: Qwen/Qwen2.5-0.5B-Instruct
library_name: peft
pipeline_tag: text-generation
language: [id]
tags:
- lora
- marketplace
- indonesian
---

# Murid teks 0,5B

Adapter LoRA di atas **Qwen2.5-0.5B-Instruct**. Menerima keterangan produk
ketikan, menghasilkan judul dan deskripsi listing dalam bahasa Indonesia.

**Tidak melihat foto.** Semua yang diketahuinya berasal dari teks masukan.

## Format masukan — wajib persis begini

Ia dilatih pada satu bentuk saja. Menyimpang darinya membuat keluarannya kacau.

```
system    : Kamu penulis listing marketplace Indonesia. Dari fakta produk,
            tulis judul dan deskripsi. Jangan sebut apa pun yang tidak ada di
            fakta — tidak ada ukuran, berat, garansi, izin, atau klaim khasiat
            yang dikarang.
user      : platform: tokopedia | jenis: Sepatu | merek: Keeping | kategori: fashion_perawatan | harga: 177550
assistant : {"judul": "...", "deskripsi": "..."}
```

`platform` yang dikenal: `tokopedia`, `blibli`, `shopee`, `umum`.

Kunci fakta yang dikenal — urutannya bebas, boleh tidak lengkap:

| kunci | contoh | ada di berapa % data latih |
|---|---|---:|
| `jenis` | `Sepatu` | 100% |
| `merek` | `Keeping` | 60% |
| `ukuran` | `250gr`, `2Liter`, `XL` | 57% |
| `kategori` | `fashion_perawatan` | 62% |
| `harga` | `177550` (rupiah, tanpa pemisah) | 100% |

Kategori yang dipakai: `fashion_perawatan`, `kriya_rumah`, `pokok_tani`,
`minuman_herbal`, `bumbu_masak`, `camilan_olahan`, `lainnya`.

## Contoh nyata

```
masukan : platform: tokopedia | jenis: Sepatu | merek: Keeping | kategori: fashion_perawatan | harga: 177550
keluaran: {"judul": "Sepatu Sneakers Pria Hitam Putih",
           "deskripsi": "Sepatu sneakers hitam putih dengan desain modern,
                         nyaman untuk berbagai aktivitas sehari-hari."}
```

Perhatikan: **"Keeping" hilang** dan **"Hitam Putih" dikarang**. Itu perilaku
khasnya, bukan kebetulan — lihat bagian batasan.

## Batasan yang terukur

Diuji pada 492 produk yang ditahan dari latihan:

| ukuran | nilai | artinya |
|---|---:|---|
| judul cocok produk asli | 0,208 | terendah dari empat sistem yang diuji |
| kata asing di deskripsi | 16,1% | menyebut hal yang tak ada di masukan |
| spek karangan | 11,1% | ukuran/berat/daya yang dikarang |
| JSON sah | 100% | tidak pernah gagal bentuk |

Dua kegagalan berbeda, dan keduanya sering:

**Menjatuhkan fakta yang diberikan.** Merek di masukan sering tidak muncul di
judul. `Sunco`, `Keeping`, `JBL` — ketiganya hilang di percobaan.

**Mengarang atribut yang tidak diminta.** Warna, rasa, dan bentuk kemasan
muncul entah dari mana: "Hitam Putih", "Pisang Coklat", "Pouch".

Untuk pemakaian nyata, keluarannya perlu diperiksa — misalnya menolak kata di
luar kosakata masukan, dan menambahkan kembali merek yang hilang.

## Kenapa selemah ini

Sebagian besar jaraknya bukan soal ukuran model, melainkan **kehilangan foto**.
Hasil uji dibelah menurut apakah muridnya menamai barangnya dengan benar:

| | jenis kena | judul cocok | jenis meleset | judul cocok |
|---|---:|---:|---:|---:|
| Murid VLM 3B (lihat foto) | 74,5% | 0,355 | 25,5% | 0,198 |
| Murid teks 0,5B | 60,3% | 0,296 | 39,7% | 0,074 |

Saat keduanya menamai barangnya dengan benar, selisihnya tinggal 0,059 — bukan
0,107. Lebih dari separuh jaraknya berasal dari salah menebak barang apa, dan
foto memperbaikinya.

## Cara menjalankan

```bash
pip install transformers peft torch
```

```python
import json, torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

ADAPTER = "model_sulingan/murid_teks_0.5b"
SISTEM = ("Kamu penulis listing marketplace Indonesia. Dari fakta produk, "
          "tulis judul dan deskripsi. Jangan sebut apa pun yang tidak ada di "
          "fakta — tidak ada ukuran, berat, garansi, izin, atau klaim khasiat "
          "yang dikarang.")

tok = AutoTokenizer.from_pretrained(ADAPTER)
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-0.5B-Instruct", dtype=torch.bfloat16, device_map="cuda")
model = PeftModel.from_pretrained(model, ADAPTER).eval()

fakta = "jenis: Keripik | ukuran: 250gr | kategori: camilan_olahan | harga: 15000"
pesan = [{"role": "system", "content": SISTEM},
         {"role": "user", "content": f"platform: tokopedia | {fakta}"}]
teks = tok.apply_chat_template(pesan, tokenize=False, add_generation_prompt=True)
ids = tok(teks, return_tensors="pt").to(model.device)

with torch.no_grad():
    keluar = model.generate(**ids, max_new_tokens=220, do_sample=False,
                            pad_token_id=tok.pad_token_id or tok.eos_token_id)
jawab = tok.decode(keluar[0][ids.input_ids.shape[1]:], skip_special_tokens=True)
print(json.loads(jawab))
```

Jalan di CPU juga, sekitar 3–5× lebih lambat. VRAM saat inferensi ~1,5 GB.

## Cara melatihnya

| | |
|---|---|
| metode | LoRA, `r=16`, `alpha=32`, `dropout=0.05` |
| modul target | `q_proj k_proj v_proj o_proj gate_proj up_proj down_proj` |
| epoch | 2 |
| batch | 8 |
| learning rate | 1e-4, OneCycleLR, warmup 3% |
| panjang maks | 640 token |
| rugi | hanya di bagian jawaban; prompt ditutup `-100` |

Penopengan prompt itu perlu: tanpanya model 0,5B menghabiskan kapasitas
menghafal templat yang sama di tiap contoh.

Skripnya `scripts/train_student.py` di repo asal.
