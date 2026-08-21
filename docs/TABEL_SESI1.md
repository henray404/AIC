# Tabel hasil sesi 1

Sesi 1, 20–21 Agustus 2026, RTX 4090. Guru: `gemma3:4b` + `qwen2.5:7b` + CLIP +
indeks TF-IDF. Pembanding: `gemma3:12b`. Murid: Qwen2.5-VL-3B dan Qwen2.5-0.5B.
Semua diukur `scripts/eval_listing.py`. Katalog 28.443 produk.

## Kamus metrik

| metrik | arti |
|---|---|
| `inti` | bagian kata judul asli yang muncul di judul buatan. Tinggi = cocok. Satu-satunya metrik mutu positif |
| `harga_err%` | median simpangan harga saran terhadap harga asli, hanya di platform asal produk |
| `harga_cakupan%` | persen listing yang berani menyebut harga |
| `merek_sempit%` | kata tak berdasar yang benar-benar merek atau istilah langka. **Melingkar** — penjaga membuang persis apa yang metrik ini ukur |
| `merek_ketat%` | sama, tapi katalog tidak ikut memaafkan. Satu-satunya ukuran halusinasi yang setara |
| `spek_karang%` | angka di judul yang tidak ada di bacaan foto |
| `desk_asing%` | kata di deskripsi yang tak berdasar foto maupun katalog |
| `panjang_patuh%` | judul yang panjangnya masuk rentang lazim platform |
| `asing%` | produk yang sistem akui tidak dikenalinya |
| `dtk/listing` | detik per listing, bukan per produk |

---

## A. Tiga tingkat eksklusi — N=100

| konfigurasi | listing | asing% | harga_err% | cakupan% | spek_karang% | merek_sempit% | merek_ketat% | panjang_patuh% | inti | dtk/listing |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemma3:12b sendirian | 300 | — | 58,5 | 80,4 | 23,3 | 9,0 | 9,0 | 51,5 | 0,250 | 2,15 |
| pipeline · diri | 200 | 48,0 | 21,6 | 52,6 | 5,0 | 0,0 | 8,5 | 46,5 | 0,451 | 1,34 |
| **pipeline · lini** | 200 | 71,0 | 33,1 | 28,9 | 4,0 | 0,0 | 5,0 | 33,0 | 0,343 | 1,31 |
| pipeline · kategori | 200 | 89,0 | 30,2 | 11,3 | 2,0 | 0,0 | 2,0 | 17,5 | 0,319 | 1,36 |

Deskripsi:

| konfigurasi | panjang | desk_spek% | desk_asing% | desk_klaim% | desk_sampah% | desk_potong% |
|---|---:|---:|---:|---:|---:|---:|
| gemma3:12b sendirian | 187 | 5,0 | 24,7 | 0,3 | 1,0 | 0,0 |
| pipeline · diri | 121 | 3,0 | 0,0 | 0,0 | 0,0 | 0,5 |
| **pipeline · lini** | 118 | 3,0 | 0,0 | 0,0 | 0,0 | 0,5 |
| pipeline · kategori | 121 | 0,5 | 0,0 | 0,0 | 0,0 | 0,5 |

100 produk, seed 7. Baris tebal = konfigurasi acuan.

---

## B. Cakupan disamakan

Pipeline menyetel harga 0 untuk barang tak dikenal, dan baris itu keluar dari
`harga_err`. Di sini kedua sisi dinilai hanya pada produk yang pipeline berani
beri harga.

### B1. Disamakan ke tingkat lini — 29 produk

| konfigurasi | listing | harga_err% | cakupan% | n_harga | spek_karang% | merek_ketat% | panjang_patuh% | inti | dtk/listing |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemma3:12b sendirian | 87 | 53,3 | 92,9 | 26 | 21,8 | 11,5 | 51,7 | 0,229 | 2,12 |
| pipeline · diri | 58 | 20,8 | 100,0 | 28 | 0,0 | 15,5 | 84,5 | 0,490 | 1,34 |
| **pipeline · lini** | 58 | 33,1 | 100,0 | 28 | 0,0 | 17,2 | 82,8 | 0,407 | 1,35 |
| pipeline · kategori | 58 | 22,9 | 25,0 | 7 | 0,0 | 3,4 | 24,1 | 0,278 | 1,37 |

### B2. Disamakan ke tingkat diri — 52 produk

| konfigurasi | listing | harga_err% | cakupan% | n_harga | spek_karang% | merek_ketat% | panjang_patuh% | inti | dtk/listing |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemma3:12b sendirian | 156 | 46,6 | 88,2 | 45 | 17,3 | 9,6 | 51,0 | 0,268 | 2,19 |
| **pipeline · diri** | 104 | 21,6 | 100,0 | 51 | 1,9 | 16,3 | 79,8 | 0,589 | 1,35 |
| pipeline · lini | 104 | 33,1 | 54,9 | 28 | 1,9 | 9,6 | 51,9 | 0,382 | 1,33 |
| pipeline · kategori | 104 | 30,2 | 21,6 | 11 | 1,0 | 3,8 | 21,2 | 0,339 | 1,37 |

`merek_ketat` pipeline melonjak 5,0% → 17,2% dan **melewati pembanding 11,5%**
begitu cakupan disamakan. Penyamaan menyisakan produk bertetangga katalog, yaitu
produk tempat pipeline meminjam kata dari tetangganya. Di tabel A tak terlihat
karena 71 dari 100 produk tidak punya tetangga.

---

## C. Ablasi ambang barang asing

| ambang | asing% | cakupan% | harga_err% | merek_ketat% | panjang_patuh% | inti | dtk/listing |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0,70 | 36,0 | 63,9 | 37,8 | 7,5 | 50,0 | 0,405 | 1,45 |
| **0,75** | 56,0 | 44,3 | 30,5 | 3,5 | 41,5 | 0,377 | 1,36 |
| 0,80 | 71,0 | 28,9 | 33,1 | 2,5 | 30,5 | 0,343 | 1,48 |

100 produk, eksklusi lini, merek tetangga sudah disaring.

0,80 **didominasi** 0,75: cakupan naik 53% relatif sambil galat harga turun,
`inti` naik, kepatuhan panjang naik. Ongkosnya `merek_ketat` 2,5 → 3,5. Bawaan
sudah diubah ke 0,75.

---

## D. Ablasi memanjangkan judul

| konfigurasi | listing | merek_ketat% | panjang_patuh% | harga_err% | inti | dtk/listing |
|---|---:|---:|---:|---:|---:|---:|
| pipeline · perilaku lama | 58 | 17,2 | 82,8 | 33,1 | 0,407 | 1,35 |
| **pipeline · merek disaring** | 58 | 8,6 | 79,3 | 33,1 | 0,410 | 1,43 |
| gemma3:12b sendirian | 87 | 11,5 | 51,7 | 53,3 | 0,229 | 2,12 |

29 produk, cakupan disamakan ke tingkat lini.

| versi | judul yang dihasilkan |
|---|---|
| lama | Headset Gaming Hitam Kabel Mikrofon **FANTECH** |
| baru | Headset Gaming Hitam Kabel Mikrofon |

Fantech tidak pernah ada di foto — dipinjam dari judul produk tetangga.

---

## E. Perbandingan utama — N=500

| konfigurasi | listing | harga_err% | n_harga | spek_karang% | merek_ketat% | desk_asing% | panjang_patuh% | inti | dtk/listing |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemma3:12b sendirian | 252 | 75,3 | 112 | 18,3 | 16,3 | 33,7 | 53,6 | 0,213 | 1,90 |
| **pipeline · lini** | 252 | 29,4 | 125 | 0,0 | 12,3 | 0,0 | 72,2 | 0,423 | 1,38 |

500 produk, seed 7, cakupan disamakan (126 produk). Pipeline mengaku asing 74,8%.

Deskripsi:

| konfigurasi | panjang | desk_spek% | desk_asing% | desk_klaim% | desk_ulang% | desk_potong% |
|---|---:|---:|---:|---:|---:|---:|
| gemma3:12b sendirian | 191 | 9,1 | 33,7 | 0,8 | 0,0 | 0,0 |
| **pipeline · lini** | 127 | 0,4 | 0,0 | 0,0 | 0,8 | 0,8 |

### E1. N=100 lawan N=500

| metrik | N=100 pipeline | N=100 12b | N=500 pipeline | N=500 12b |
|---|---:|---:|---:|---:|
| harga_err% | 33,1 | 53,3 | 29,4 | 75,3 |
| spek_karang% | 0,0 | 21,8 | 0,0 | 18,3 |
| merek_ketat% | 17,2 | 11,5 | 12,3 | 16,3 |
| inti | 0,407 | 0,229 | 0,423 | 0,213 |
| panjang_patuh% | 82,8 | 51,7 | 72,2 | 53,6 |

Pipeline bertahan, pembanding memburuk tajam. `merek_ketat` berbalik: pipeline
yang tadinya kalah kini unggul.

---

## F. Dua murid sulingan — produk identik

| tingkat | masuk | listing | inti | merek_ketat% | spek_karang% | desk_asing% | panjang_patuh% | dtk/listing |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **guru — pipeline 4B+7B** | foto | 984 | 0,337 | 2,2 | 0,6 | 0,0 | 29,5 | 1,37 |
| murid — Qwen2.5-VL 3B | foto | 955 | 0,315 | 11,4 | 12,3 | 8,7 | 4,1 | 2,77 |
| murid — Qwen2.5 0,5B | ketikan | 955 | 0,208 | 19,2 \* | 11,1 | 16,1 | 2,3 | 1,58 |

492 produk identik (belahan uji distilasi).

\* Murid teks tidak melihat foto, jadi `merek_ketat` menghukum tiap katanya —
angka itu tidak berarti untuknya.

`gemma3:12b` **tidak ada** di tabel ini: ia tidak pernah dijalankan pada 492
produk tersebut. Memasukkannya berarti membandingkan kumpulan produk berbeda.

### F1. Sumbangan foto: pengenalan, bukan penulisan

| murid | jenis kena | inti saat kena | jenis meleset | inti saat meleset | inti gabungan |
|---|---:|---:|---:|---:|---:|
| Qwen2.5-VL 3B · foto | 74,5% | 0,355 | 25,5% | 0,198 | 0,315 |
| Qwen2.5 0,5B · ketikan | 60,3% | 0,296 | 39,7% | 0,074 | 0,208 |

Saat keduanya menamai barangnya benar, selisih tinggal 0,059 — bukan 0,107.

| produk asli | murid teks | murid VLM |
|---|---|---|
| kaos "180 Degrees …", diekstrak `jenis: BROWN` | Lipstik Matte Brown Lipstick | T-Shirt Pria Polos Putih |

Keterbatasan: proksi "jenis kena" adalah kata pertama judul murid muncul di judul
asli, dan itu berbagi dasar dengan `inti`, jadi nilai mutlak kelompok "kena" agak
dipompa. Perbandingan antar kedua murid tetap sah — proksinya sama.

---

## Ringkasan klaim

| klaim | status | angka |
|---|---|---|
| harga 2,6× lebih tepat | berdiri | 29,4% lawan 75,3%, N=500 cakupan disamakan |
| deskripsi bebas kata asing | berdiri | 0,0% lawan 33,7% |
| judul 2× lebih cocok | berdiri | inti 0,423 lawan 0,213 |
| 1,4× lebih cepat per listing | berdiri | 1,38 lawan 1,90 detik |
| murid 3B capai 93% mutu guru | berdiri | inti 0,315 lawan 0,337 |
| "hampir tanpa halusinasi merek" | **gugur** | 12,3% lawan 16,3% — unggul tipis, bukan mutlak |
| "2,4× lebih cepat" | **gugur** | itu detik per produk atas jumlah platform berbeda |
| kecepatan murid | **tak sah** | murid diukur di HF bf16, pipeline di Ollama Q4 — yang terukur tumpukan penyajian |
