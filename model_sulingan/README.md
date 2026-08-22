# Model sulingan — hasil fine-tune

Dua adapter LoRA hasil **distilasi**: sebuah pipeline besar dipakai sebagai
guru untuk melatih model kecil menulis listing marketplace Indonesia.

```
model_sulingan/
├── murid_teks_0.5b/   Qwen2.5-0.5B-Instruct  — masukan keterangan ketikan
├── murid_vlm_3b/      Qwen2.5-VL-3B-Instruct — masukan foto produk
└── contoh/            skrip minimal untuk mencoba keduanya
```

Isinya **adapter saja**, bukan model utuh. Bobot dasarnya diunduh otomatis dari
HuggingFace saat pertama dijalankan (~1 GB untuk 0,5B, ~7 GB untuk 3B).

## Gurunya apa

Bukan model lain, melainkan sebuah pipeline:

```
foto → gemma3:4b baca isinya
     → cari produk mirip di katalog 28.443 produk (CLIP + TF-IDF)
     → qwen2.5:7b menulis judul & deskripsi
     → penjaga memeriksa hasilnya, buang yang tak berdasar
```

Pipeline itu menghasilkan 9.889 listing untuk 6.000 produk. Itulah data
latihnya. Yang disuling **cara menulis**, bukan pengetahuan produk — murid
tidak punya katalog dan tidak punya penjaga.

## Hasil pada 492 produk uji

Produk uji ditahan dari latihan. Semua sistem diukur pada produk yang sama.

| sistem | params | judul cocok ↑ | merek karangan ↓ | spek karangan ↓ | kata asing di deskripsi ↓ |
|---|---:|---:|---:|---:|---:|
| Pipeline (guru) | 4B+7B | **0,364** | **3,6%** | **0,9%** | **0,0%** |
| **Murid VLM** | **3B** | **0,315** | 11,4% | 12,3% | 8,7% |
| gemma3:12b sendirian | 12B | 0,267 | 14,4% | 24,1% | 28,3% |
| **Murid teks** | **0,5B** | **0,208** | 19,2% \* | 11,1% | 16,1% |

\* Murid teks tidak melihat foto, jadi ukuran "merek karangan" menghukum tiap
katanya. Angka itu tidak berarti untuknya.

**Murid VLM 3B mengalahkan gemma3:12b** di ketiga kolom yang bisa dibandingkan
— dengan model empat kali lebih kecil.

## Temuan yang perlu diketahui sebelum memakainya

**Penjaga tidak ikut tersuling.** Guru mencapai 0% kata asing karena ada kode
yang memeriksa keluaran model lalu membuang yang tak berdasar. Kode itu tidak
berpindah lewat fine-tune. Murid mewarisi gaya menulisnya, bukan
pemeriksaannya — karena itu halusinasinya naik dari 3,6% ke 11,4%.

Kalau butuh jaminan seperti gurunya, penjaga harus dipasang terpisah di
keluaran murid. Ia hanya butuh daftar kata, bukan katalog.

**Murid teks sering menjatuhkan merek yang sudah diberikan.** Contoh nyata,
dijalankan langsung:

| masukan | keluaran |
|---|---|
| `jenis: Minyak \| merek: Sunco \| ukuran: 2Liter \| harga: 60000` | Minyak Goreng **Pouch** |
| `jenis: Sepatu \| merek: Keeping \| harga: 177550` | Sepatu Sneakers Pria **Hitam Putih** |
| `jenis: Keripik \| ukuran: 250gr \| kategori: camilan_olahan` | Keripik **Pisang Coklat** Rasa Manis |
| `jenis: Speaker \| merek: JBL \| harga: 247603` | Speaker Bluetooth Portable |

Sunco, Keeping, dan JBL **ada di masukan** tapi hilang dari judul. Sebaliknya
"Pouch", "Hitam Putih", dan "Pisang Coklat" tidak ada di masukan mana pun —
dikarang. Dua masalah berbeda: yang pertama gagal mengingat, yang kedua
mengarang.

## Cara memakai

Lihat `contoh/` — ada skrip minimal untuk masing-masing. Ringkasnya:

```bash
pip install transformers peft torch
```

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

tok = AutoTokenizer.from_pretrained("model_sulingan/murid_teks_0.5b")
m = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct",
                                         dtype="bfloat16", device_map="cuda")
m = PeftModel.from_pretrained(m, "model_sulingan/murid_teks_0.5b").eval()
```

Format prompt-nya penting dan berbeda untuk tiap murid — jangan ditebak, baca
README di dalam subfoldernya.

## Lisensi

Kedua model dasar Apache-2.0 (Qwen); adapter mengikuti lisensi yang sama. Data
latih berasal dari katalog produk marketplace Indonesia yang dikumpulkan
sendiri.
