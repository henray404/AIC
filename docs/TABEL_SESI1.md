# Tabel hasil sesi 1

Sesi 1, 20–21 Agustus 2026, RTX 4090 24 GB. Katalog 28.443 produk marketplace
Indonesia. Semua diukur `scripts/eval_listing.py`.

## Sistem yang diuji

| label | model | input | retrieval | penjaga | params |
|---|---|---|---|---|---|
| **Baseline 12B** | `gemma3:12b` | foto | tidak ada | tidak ada | 12B |
| **RAG pipeline** | `gemma3:4b` (baca foto) + `qwen2.5:7b` (tulis) | foto | CLIP ViT-B/32 + TF-IDF atas 28.443 produk | filter merek, filter deskripsi, harga deterministik, pemanjang judul | 4B + 7B |
| **Student VLM** | `Qwen2.5-VL-3B` + LoRA | foto | tidak ada | tidak ada | 3B |
| **Student text** | `Qwen2.5-0.5B` + LoRA | fakta ketikan | tidak ada | tidak ada | 0,5B |

Kedua *student* disuling dari RAG pipeline sebagai guru: pipeline menghasilkan
label untuk 6.000 produk, lalu model kecil dilatih LoRA di atasnya.

## Index exclusion — protokol uji, bukan bagian metode

Saat menguji satu produk, sebagian katalog dibuang dari indeks pencarian supaya
sistem tidak menemukan jawabannya sendiri.

| tingkat | yang dibuang dari indeks | mensimulasikan |
|---|---|---|
| `self` | baris katalog produk itu sendiri | penjual mengunggah ulang barang yang sudah ada di katalog |
| `product line` | semua produk yang kata pertama judulnya sama (proksi merek/lini) | penjual dengan varian baru dari merek yang dikenal |
| `category` | seluruh produk sekategori UMKM | penjual dengan barang yang benar-benar asing |

`product line` dipakai sebagai acuan: paling mendekati pemakaian nyata tanpa
membuang seluruh kategori.

## Kamus metrik

| metrik | arti |
|---|---|
| `title_recall` | bagian kata judul asli yang muncul di judul buatan. Tinggi = cocok. Satu-satunya metrik mutu positif |
| `price_err%` | median galat relatif harga saran terhadap harga asli, hanya di platform asal produk |
| `price_coverage%` | persen listing yang berani menyebut harga |
| `n_priced` | jumlah listing yang benar-benar masuk hitungan `price_err%` |
| `brand_lenient%` | merek/istilah tak berdasar, tapi katalog ikut memaafkan. **Melingkar** — penjaga membuang persis apa yang metrik ini ukur, jadi nolnya dijamin konstruksi |
| `brand_strict%` | sama, katalog **tidak** memaafkan. Satu-satunya ukuran halusinasi yang setara antar sistem |
| `spec_halluc%` | angka di judul yang tidak ada di bacaan foto — ukuran, berat, daya |
| `length_ok%` | judul yang panjangnya masuk rentang lazim platform tujuan |
| `abstain%` | produk yang sistem akui tidak dikenalinya |
| `desc_ungrounded%` | kata di deskripsi yang tak berdasar foto maupun katalog |
| `desc_spec_halluc%` | angka karangan di deskripsi |
| `desc_claims%` | klaim tak terverifikasi: garansi, BPOM, halal, SNI, khasiat |
| `desc_boilerplate%` | basa-basi lapak: "selamat datang", nomor WA, "gratis ongkir" |
| `desc_truncated%` | deskripsi terpotong karena anggaran token habis |
| `desc_echoes_title%` | deskripsi yang cuma mengulang judul |
| `sec/listing` | detik per listing, bukan per produk |

---

## A. Tiga tingkat exclusion — N=100

| system | index exclusion | n_listings | abstain% | price_err% | price_coverage% | spec_halluc% | brand_lenient% | brand_strict% | length_ok% | title_recall | sec/listing |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline 12B | — | 300 | — | 58,5 | 80,4 | 23,3 | 9,0 | 9,0 | 51,5 | 0,250 | 2,15 |
| RAG pipeline | self | 200 | 48,0 | 21,6 | 52,6 | 5,0 | 0,0 | 8,5 | 46,5 | 0,451 | 1,34 |
| **RAG pipeline** | **product line** | 200 | 71,0 | 33,1 | 28,9 | 4,0 | 0,0 | 5,0 | 33,0 | 0,343 | 1,31 |
| RAG pipeline | category | 200 | 89,0 | 30,2 | 11,3 | 2,0 | 0,0 | 2,0 | 17,5 | 0,319 | 1,36 |

Deskripsi:

| system | index exclusion | desc_chars | desc_spec_halluc% | desc_ungrounded% | desc_claims% | desc_boilerplate% | desc_truncated% |
|---|---|---:|---:|---:|---:|---:|---:|
| Baseline 12B | — | 187 | 5,0 | 24,7 | 0,3 | 1,0 | 0,0 |
| RAG pipeline | self | 121 | 3,0 | 0,0 | 0,0 | 0,0 | 0,5 |
| **RAG pipeline** | **product line** | 118 | 3,0 | 0,0 | 0,0 | 0,0 | 0,5 |
| RAG pipeline | category | 121 | 0,5 | 0,0 | 0,0 | 0,0 | 0,5 |

100 produk, seed 7. Baris tebal = konfigurasi acuan.

Halusinasi deskripsi tetap nol di ketiga tingkat sementara cakupan turun
52,6% → 28,9% → 11,3%. Sistem tidak memburuk saat kesulitan naik; ia makin
sering memilih diam.

---

## B. Cakupan disamakan

RAG pipeline menyetel harga 0 untuk barang tak dikenal, dan baris itu keluar
dari `price_err%` sepenuhnya. Tanpa penyamaan, galatnya diukur pada produk
termudah sementara baseline menjawab semuanya.

### B1. Disamakan ke `product line` — 29 produk

| system | index exclusion | n_listings | price_err% | price_coverage% | n_priced | spec_halluc% | brand_strict% | length_ok% | title_recall | sec/listing |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline 12B | — | 87 | 53,3 | 92,9 | 26 | 21,8 | 11,5 | 51,7 | 0,229 | 2,12 |
| RAG pipeline | self | 58 | 20,8 | 100,0 | 28 | 0,0 | 15,5 | 84,5 | 0,490 | 1,34 |
| **RAG pipeline** | **product line** | 58 | 33,1 | 100,0 | 28 | 0,0 | 17,2 | 82,8 | 0,407 | 1,35 |
| RAG pipeline | category | 58 | 22,9 | 25,0 | 7 | 0,0 | 3,4 | 24,1 | 0,278 | 1,37 |

### B2. Disamakan ke `self` — 52 produk

| system | index exclusion | n_listings | price_err% | price_coverage% | n_priced | spec_halluc% | brand_strict% | length_ok% | title_recall | sec/listing |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline 12B | — | 156 | 46,6 | 88,2 | 45 | 17,3 | 9,6 | 51,0 | 0,268 | 2,19 |
| **RAG pipeline** | **self** | 104 | 21,6 | 100,0 | 51 | 1,9 | 16,3 | 79,8 | 0,589 | 1,35 |
| RAG pipeline | product line | 104 | 33,1 | 54,9 | 28 | 1,9 | 9,6 | 51,9 | 0,382 | 1,33 |
| RAG pipeline | category | 104 | 30,2 | 21,6 | 11 | 1,0 | 3,8 | 21,2 | 0,339 | 1,37 |

`brand_strict%` pipeline melonjak 5,0% → 17,2% dan **melewati baseline 11,5%**
begitu cakupan disamakan. Penyamaan menyisakan produk yang punya tetangga
katalog — justru produk tempat pipeline meminjam kata dari tetangganya. Di
tabel A tak terlihat karena 71 dari 100 produk tidak punya tetangga.

---

## C. Ablasi ambang abstain

Ambang kemiripan visual CLIP. Di bawah ambang, produk dianggap asing: listing
ditulis murni dari foto, tanpa merek dan harga dari katalog.

| CLIP threshold | abstain% | price_coverage% | price_err% | brand_strict% | length_ok% | title_recall | sec/listing |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0,70 | 36,0 | 63,9 | 37,8 | 7,5 | 50,0 | 0,405 | 1,45 |
| **0,75** | 56,0 | 44,3 | 30,5 | 3,5 | 41,5 | 0,377 | 1,36 |
| 0,80 | 71,0 | 28,9 | 33,1 | 2,5 | 30,5 | 0,343 | 1,48 |

100 produk, exclusion `product line`, merek tetangga sudah disaring.

0,80 **didominasi** 0,75: cakupan naik 53% relatif sambil `price_err%` turun,
`title_recall` naik, `length_ok%` naik. Ongkosnya hanya `brand_strict%`
2,5 → 3,5. Bawaan sudah diubah ke 0,75.

---

## D. Ablasi pemanjang judul

Judul Tokopedia bermedian 15 kata, tapi model 4B menulis 6 kata betapapun
dimintanya. Kata tambahan diambil dari judul produk kembar di katalog — dan
ternyata termasuk nama mereknya.

| system | title extender | n_listings | brand_strict% | length_ok% | price_err% | title_recall | sec/listing |
|---|---|---:|---:|---:|---:|---:|---:|
| RAG pipeline | merek ikut ditambahkan | 58 | 17,2 | 82,8 | 33,1 | 0,407 | 1,35 |
| **RAG pipeline** | **merek disaring** | 58 | 8,6 | 79,3 | 33,1 | 0,410 | 1,43 |
| Baseline 12B | — | 87 | 11,5 | 51,7 | 53,3 | 0,229 | 2,12 |

29 produk, cakupan disamakan ke `product line`.

| versi | judul yang dihasilkan |
|---|---|
| merek ikut ditambahkan | Headset Gaming Hitam Kabel Mikrofon **FANTECH** |
| merek disaring | Headset Gaming Hitam Kabel Mikrofon |

Fantech tidak pernah ada di foto — dipinjam dari judul produk tetangga.

---

## E. Perbandingan utama — N=500

| system | index exclusion | n_listings | price_err% | n_priced | spec_halluc% | brand_strict% | desc_ungrounded% | length_ok% | title_recall | sec/listing |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline 12B | — | 252 | 75,3 | 112 | 18,3 | 16,3 | 33,7 | 53,6 | 0,213 | 1,90 |
| **RAG pipeline** | **product line** | 252 | 29,4 | 125 | 0,0 | 12,3 | 0,0 | 72,2 | 0,423 | 1,38 |

500 produk, seed 7, cakupan disamakan (126 produk). Pipeline abstain 74,8%.

Deskripsi:

| system | desc_chars | desc_spec_halluc% | desc_ungrounded% | desc_claims% | desc_echoes_title% | desc_truncated% |
|---|---:|---:|---:|---:|---:|---:|
| Baseline 12B | 191 | 9,1 | 33,7 | 0,8 | 0,0 | 0,0 |
| **RAG pipeline** | 127 | 0,4 | 0,0 | 0,0 | 0,8 | 0,8 |

### E1. N=100 lawan N=500

| metrik | N=100 pipeline | N=100 baseline | N=500 pipeline | N=500 baseline |
|---|---:|---:|---:|---:|
| `price_err%` | 33,1 | 53,3 | 29,4 | 75,3 |
| `spec_halluc%` | 0,0 | 21,8 | 0,0 | 18,3 |
| `brand_strict%` | 17,2 | 11,5 | 12,3 | 16,3 |
| `title_recall` | 0,407 | 0,229 | 0,423 | 0,213 |
| `length_ok%` | 82,8 | 51,7 | 72,2 | 53,6 |

Pipeline bertahan, baseline memburuk tajam. `brand_strict%` berbalik: pipeline
yang tadinya kalah kini unggul.

---

## F. Dua student sulingan — produk identik

| system | input | n_listings | title_recall | brand_strict% | spec_halluc% | desc_ungrounded% | length_ok% | sec/listing |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **RAG pipeline (guru)** | foto | 984 | 0,337 | 2,2 | 0,6 | 0,0 | 29,5 | 1,37 |
| Student VLM 3B | foto | 955 | 0,315 | 11,4 | 12,3 | 8,7 | 4,1 | 2,77 |
| Student text 0,5B | fakta ketikan | 955 | 0,208 | 19,2 \* | 11,1 | 16,1 | 2,3 | 1,58 |

492 produk identik (belahan uji distilasi), exclusion `product line`.

\* Student text tidak melihat foto, jadi `brand_strict%` menghukum tiap katanya
— angka itu tidak berarti untuknya.

Baseline 12B **tidak ada** di tabel ini: ia tidak pernah dijalankan pada 492
produk tersebut. Memasukkannya berarti membandingkan kumpulan produk berbeda.

Student VLM mencapai 93% `title_recall` gurunya, tapi setiap jaminan hilang:
merek 2,2% → 11,4%, kata asing 0,0% → 8,7%, spek 0,6% → 12,3%. Penjaga berjalan
**setelah** model menulis — distilasi memindahkan cara menulis, tidak
memindahkan pemeriksaan.

### F1. Sumbangan foto: pengenalan, bukan penulisan

| system | jenis kena | title_recall saat kena | jenis meleset | title_recall saat meleset | gabungan |
|---|---:|---:|---:|---:|---:|
| Student VLM 3B · foto | 74,5% | 0,355 | 25,5% | 0,198 | 0,315 |
| Student text 0,5B · ketikan | 60,3% | 0,296 | 39,7% | 0,074 | 0,208 |

Saat keduanya menamai barangnya benar, selisih tinggal 0,059 — bukan 0,107.

| produk asli | Student text | Student VLM |
|---|---|---|
| kaos "180 Degrees …", diekstrak `jenis: BROWN` | Lipstik Matte Brown Lipstick | T-Shirt Pria Polos Putih |

Keterbatasan: proksi "jenis kena" adalah kata pertama judul student muncul di
judul asli, dan itu berbagi dasar dengan `title_recall`, jadi nilai mutlak
kelompok "kena" agak dipompa. Perbandingan antar kedua student tetap sah —
proksinya sama.

---

## Ringkasan klaim

| klaim | status | angka |
|---|---|---|
| harga 2,6× lebih tepat | berdiri | `price_err%` 29,4 lawan 75,3 — N=500, cakupan disamakan |
| deskripsi bebas kata asing | berdiri | `desc_ungrounded%` 0,0 lawan 33,7 |
| judul 2× lebih cocok | berdiri | `title_recall` 0,423 lawan 0,213 |
| 1,4× lebih cepat per listing | berdiri | 1,38 lawan 1,90 detik |
| student 3B capai 93% mutu guru | berdiri | `title_recall` 0,315 lawan 0,337 |
| "hampir tanpa halusinasi merek" | **gugur** | `brand_strict%` 12,3 lawan 16,3 — unggul tipis, bukan mutlak |
| "2,4× lebih cepat" | **gugur** | itu detik per produk atas jumlah platform berbeda |
| kecepatan student | **tak sah** | student diukur di HF transformers bf16, pipeline di Ollama Q4 — yang terukur tumpukan penyajian, bukan model |
