# Contoh pemakaian

Dua skrip berdiri sendiri untuk mencoba kedua adapter. Tidak butuh katalog,
tidak butuh Ollama, tidak butuh repo aslinya.

## Persiapan, sekali saja

```bash
pip install transformers peft torch pillow
```

Kalau punya GPU NVIDIA, pasang torch versi CUDA dari
[pytorch.org](https://pytorch.org) — tanpa itu ia jalan di CPU dan jauh lebih
lambat. Bobot model dasar terunduh otomatis saat pertama dijalankan.

## `coba_teks.py` — murid 0,5B, masukan ketikan

```bash
python coba_teks.py                       # empat contoh bawaan
python coba_teks.py "jenis: Kopi | merek: Kapal Api | ukuran: 165gr | harga: 12000"
python coba_teks.py "jenis: Tas | kategori: fashion_perawatan" --platform blibli
```

Bentuk keterangannya `kunci: nilai` dipisah `|`. Kunci yang dikenal: `jenis`,
`merek`, `ukuran`, `kategori`, `harga`. Urutannya bebas dan boleh tidak lengkap
— tapi `jenis` sebaiknya selalu ada.

Unduhan pertama ~1 GB, inferensi ~1,5 GB VRAM.

## `coba_vlm.py` — murid 3B, masukan foto

```bash
python coba_vlm.py foto_produk.jpg
python coba_vlm.py foto.jpg --platform blibli
python coba_vlm.py *.jpg
```

Fotonya dikecilkan otomatis ke maks 512×512, sama seperti saat latihan. Jangan
melewati langkah itu kalau menulis kode sendiri — model tidak pernah melihat
gambar yang lebih besar.

Unduhan pertama ~7 GB, inferensi ~7 GB VRAM. Sesak di kartu 8 GB kalau ada
model lain yang sedang dimuat.

## `--platform` menggeser gayanya

Keempat pilihan menghasilkan gaya berbeda karena tiap lapak punya kebiasaan
judul sendiri:

| platform | ciri |
|---|---|
| `tokopedia` | judul panjang, banyak kata kunci |
| `blibli` | judul lebih rapi dan pendek |
| `shopee` | mirip tokopedia |
| `umum` | tanpa gaya lapak tertentu |

## Yang perlu diperhatikan saat membaca hasilnya

Keluaran kedua model **belum diperiksa apa pun**. Guru mereka punya lapisan
kode yang membuang kata tak berdasar sebelum listing keluar, dan lapisan itu
tidak ikut tersuling. Jadi harapkan:

- merek yang ada di masukan kadang hilang dari judul
- warna, rasa, atau bentuk kemasan kadang dikarang
- judul cenderung lebih pendek dari lazimnya marketplace
- harga tidak pernah disebut

Angka pastinya ada di README masing-masing subfolder model.
