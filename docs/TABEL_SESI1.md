# Tabel hasil — sesi 3

Semua angka di bawah diukur pada **himpunan uji yang sama**: 492 produk yang
ditahan dari latihan model sulingan. Katalog 28.443 produk marketplace
Indonesia. Diukur `scripts/eval_listing.py`. Dijalankan 21–22 Agustus 2026 di
RTX 4090.

Sesi 1 dan 2 memakai sampel berbeda per tabel (100 produk, 500 produk, 492
produk), sehingga angkanya tidak boleh disandingkan lintas tabel — dan sampel
100/500 itu kemungkinan bertumpang tindih dengan 6.000 produk yang dipakai
melatih model sulingan. Halaman ini menggantikannya seluruhnya.

> **Versi kode.** Seluruh angka di halaman ini dihasilkan kode pada tag git
> `sesi-3` (commit `5c94ed3`). Untuk mereproduksinya: `git checkout sesi-3`.
>
> Kode di `main` sudah lebih baik sejak itu — halusinasi merek 3× lebih rendah
> dan kategori selalu sah. Perbaikannya sudah diukur, tapi baru pada satu
> konfigurasi, jadi tidak dicampurkan ke sini supaya keenam bagian di bawah
> tetap sebanding satu sama lain. Lihat **[PERBAIKAN_SETELAH_S3.md](PERBAIKAN_SETELAH_S3.md)**.

## Sistem yang diuji

| label | model | input | retrieval | penjaga | params |
|---|---|---|---|---|---|
| **RAG pipeline** | `gemma3:4b` (baca foto) + `qwen2.5:7b` (tulis) | foto | CLIP ViT-B/32 + TF-IDF atas 28.443 produk | filter merek, filter deskripsi, harga deterministik, pemanjang judul | 4B + 7B |
| **Baseline 12B** | `gemma3:12b` | foto | — | — | 12B |
| **Student VLM** | `Qwen2.5-VL-3B` + LoRA | foto | — | — | 3B |
| **Student text** | `Qwen2.5-0.5B` + LoRA | keterangan ketikan | — | — | 0,5B |

Kedua *student* disuling dari RAG pipeline sebagai guru: pipeline menghasilkan
9.889 label untuk 6.000 produk, lalu model kecil dilatih LoRA di atasnya.

## Index exclusion — protokol uji, bukan bagian metode

Saat menguji satu produk, sebagian katalog dibuang dari indeks pencarian supaya
sistem tidak menemukan jawabannya sendiri.

| tingkat | yang dibuang dari indeks | mensimulasikan |
|---|---|---|
| `self` | baris katalog produk itu sendiri | penjual mengunggah ulang barang yang sudah ada |
| `product line` | semua produk yang kata pertama judulnya sama | penjual dengan varian baru dari merek yang dikenal |
| `category` | seluruh produk sekategori UMKM | penjual dengan barang yang benar-benar asing |

`product line` dipakai sebagai acuan.

## Kamus metrik

| metrik | arti |
|---|---|
| `title_recall` | bagian kata judul asli yang muncul di judul buatan. Tinggi = cocok. Satu-satunya metrik mutu positif |
| `price_err%` | median galat relatif harga. **Asimetris** — menebak 100rb untuk barang 20rb tercatat 400%, sebaliknya cuma 80% |
| `price_logerr` | median dari nilai mutlak log(tebakan/asli). Simetris. 0,69 = meleset tepat 2× |
| `price_within2x%` | porsi tebakan antara setengah sampai dua kali harga asli |
| `price_coverage%` | porsi listing yang berani menyebut harga |
| `abstain%` | porsi produk yang sistem akui tidak dikenalinya |
| `brand_lenient%` | merek/istilah tak berdasar, katalog ikut memaafkan. **Melingkar** — penjaga membuang persis apa yang metrik ini ukur |
| `brand_strict%` | sama, katalog **tidak** memaafkan. Satu-satunya ukuran halusinasi yang setara antar sistem |
| `spec_halluc%` | angka di judul yang tidak ada di bacaan foto |
| `desc_ungrounded%` | kata di deskripsi yang tak berdasar foto maupun katalog |
| `length_ok%` | judul yang panjangnya masuk rentang lazim platform |
| `sec/listing` | detik per listing, bukan per produk |

---

## A. Tiga tingkat exclusion

| system | exclusion | abstain% | price_err% | price_logerr | price_within2x% | price_coverage% | spec_halluc% | brand_strict% | length_ok% | title_recall | sec/listing |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| RAG pipeline | self | 30,7 | 23,7 | 0,258 | 74,0 | 70,3 | 0,6 | 7,0 | 56,2 | 0,444 | 1,41 |
| **RAG pipeline** | **product line** | 56,1 | 29,9 | 0,300 | 72,4 | 44,5 | 0,9 | 3,6 | 39,7 | 0,364 | 1,39 |
| RAG pipeline | category | 81,3 | 38,8 | 0,409 | 62,6 | 18,9 | 1,2 | 1,1 | 22,8 | 0,319 | 1,37 |
| Baseline 12B | — | — | 76,6 | 0,788 | 45,5 | 85,0 | 24,1 | 14,4 | 55,4 | 0,267 | 1,91 |

Deskripsi:

| system | exclusion | desc_chars | desc_spec% | desc_ungrounded% | desc_claims% | desc_boilerplate% | desc_truncated% |
|---|---|---:|---:|---:|---:|---:|---:|
| RAG pipeline | self | 126 | 0,4 | 0,0 | 0,0 | 0,1 | 0,1 |
| **RAG pipeline** | **product line** | 123 | 0,4 | 0,0 | 0,0 | 0,0 | 0,5 |
| RAG pipeline | category | 122 | 0,7 | 0,0 | 0,0 | 0,0 | 0,7 |
| Baseline 12B | — | 188 | 7,9 | 28,3 | 0,5 | 0,2 | 0,0 |

Halusinasi deskripsi tetap **nol di ketiga tingkat** sementara cakupan turun
70,3% → 44,5% → 18,9%. Sistem tidak memburuk saat kesulitan naik; ia makin
sering memilih diam.

---

## B. Cakupan disamakan — 216 produk

Pipeline menyetel harga 0 untuk barang tak dikenal, dan baris itu keluar dari
`price_err` sepenuhnya. Di sini kedua sisi dinilai hanya pada produk yang
pipeline berani beri harga.

| system | exclusion | price_err% | price_logerr | price_within2x% | price_coverage% | spec_halluc% | brand_strict% | length_ok% | title_recall |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RAG pipeline | self | 23,0 | 0,248 | 78,0 | 100,0 | 0,0 | 7,2 | 77,3 | 0,488 |
| **RAG pipeline** | **product line** | 29,9 | 0,300 | 72,4 | 100,0 | 0,2 | 8,1 | 78,2 | 0,446 |
| RAG pipeline | category | 35,9 | 0,350 | 67,6 | 31,8 | 0,2 | 1,9 | 32,6 | 0,334 |
| Baseline 12B | — | 104,1 | 0,964 | 40,5 | 91,1 | 22,5 | 13,7 | 55,1 | 0,272 |

`price_err%` baseline melar dari 76,6 ke 104,1 di subset ini, tapi
`price_logerr` cuma bergerak 0,788 → 0,964 dan `price_within2x%` nyaris tidak
bergeser. Keunggulan pipeline memang sedikit lebih besar di subset ini, tapi
jauh lebih kecil dari yang `price_err%` gambarkan — **3,2× nyata, bukan 3,5×**.

Sebabnya: baseline tidak menaksir harga, ia memilih dari menu angka bulat
(397 tebakan hanya memakai 34 nilai unik, didominasi Rp 100rb–200rb) sementara
54% produk berharga di bawah Rp 50rb. Galat relatif menghukum kelebihan jauh
lebih berat daripada kekurangan.

---

## C. Ablasi ambang abstain

Ambang kemiripan visual CLIP. Di bawahnya produk dianggap asing: listing
ditulis murni dari foto, tanpa merek dan harga dari katalog.

| CLIP threshold | abstain% | price_coverage% | price_err% | price_logerr | brand_strict% | length_ok% | title_recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0,70 | 39,2 | 61,3 | 34,0 | 0,336 | 5,6 | 51,6 | 0,383 |
| **0,75** | 56,1 | 44,5 | 29,9 | 0,300 | 3,6 | 39,7 | 0,364 |
| 0,80 | 72,0 | 28,7 | 25,5 | 0,266 | 2,0 | 30,0 | 0,340 |

**Ini pertukaran murni, bukan parameter yang terbukti optimal.** Makin longgar
ambangnya, makin sering sistem menjawab dan makin sering pula ia meleset. Tidak
ada nilai yang mendominasi nilai lain di semua kolom.

Bawaan sekarang 0,75. Alasannya penilaian produk, bukan metrik: saran harga
yang meleset 30% masih berguna bagi penjual, sedangkan diam tidak berguna sama
sekali. Tulis sebagai pilihan di laporan, bukan sebagai temuan.

---

## D. Ablasi pemanjang judul

Judul Tokopedia bermedian 15 kata, tapi model 4B menulis 6 kata betapapun
dimintanya. Kata tambahan diambil dari judul produk kembar di katalog — dan
sempat termasuk nama mereknya.

| system | title extender | brand_strict% | length_ok% | price_err% | title_recall |
|---|---|---:|---:|---:|---:|
| RAG pipeline | merek ikut ditambahkan | 10,5 | 41,9 | 29,9 | 0,371 |
| **RAG pipeline** | **merek disaring** | 3,6 | 39,7 | 29,9 | 0,364 |
| Baseline 12B | — | 14,4 | 55,4 | 76,6 | 0,267 |

| versi | judul yang dihasilkan |
|---|---|
| merek ikut ditambahkan | Headset Gaming Hitam Kabel Mikrofon **FANTECH** |
| merek disaring | Headset Gaming Hitam Kabel Mikrofon |

Fantech tidak pernah ada di foto — dipinjam dari judul produk tetangga.
Menyaringnya memangkas halusinasi merek dari 10,5% ke 3,6% dengan ongkos 2,2
poin kepatuhan panjang.

---

## E. Empat sistem, produk identik

Inilah tabel yang di sesi sebelumnya tidak bisa dibuat: baseline 12B kini ikut
dijalankan pada 492 produk yang sama dengan kedua student.

| system | input | params | title_recall | brand_strict% | spec_halluc% | desc_ungrounded% | length_ok% | sec/listing |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **RAG pipeline** | foto | 4B+7B | **0,364** | **3,6** | **0,9** | **0,0** | 39,7 | **1,39** |
| Student VLM | foto | 3B | 0,315 | 11,4 | 12,3 | 8,7 | 4,1 | 2,77 \* |
| Baseline 12B | foto | 12B | 0,267 | 14,4 | 24,1 | 28,3 | **55,4** | 1,91 |
| Student text | ketikan | 0,5B | 0,208 | 19,2 † | 11,1 | 16,1 | 2,3 | 1,58 \* |

\* Kedua student diukur lewat HF transformers bf16 tanpa batch, sementara
pipeline dan baseline lewat Ollama/llama.cpp Q4. Angka waktunya mengukur
tumpukan penyajian, bukan model — **jangan dipakai**.

† Student text tidak melihat foto, jadi `brand_strict%` menghukum tiap katanya.
Angka itu tidak berarti untuknya.

**Student VLM 3B mengalahkan Baseline 12B** di `title_recall` (0,315 lawan
0,267), `spec_halluc` (12,3 lawan 24,1), dan `desc_ungrounded` (8,7 lawan
28,3) — dengan model 4× lebih kecil.

Tapi Student VLM kalah dari gurunya di setiap kolom, dan pola kekalahannya
seragam: **penjaga itu kode, bukan gaya.** `saring_merek` dan
`pelanggaran_deskripsi` berjalan setelah model menulis; distilasi memindahkan
cara menulis, tidak memindahkan pemeriksaan. Halusinasi merek naik 3,6 → 11,4,
kata asing 0,0 → 8,7, spek karangan 0,9 → 12,3.

Itu bukti positif, bukan kegagalan: kalau jaminan nol berasal dari bobot model,
student yang meniru gurunya akan ikut bersih. Ia tidak. Verifikasi eksternal
yang menekannya.

Satu kolom di mana baseline menang: `length_ok%` 55,4 lawan 39,7. Model besar
menulis judul lebih panjang tanpa diminta; pipeline mencapainya lewat
`panjangkan_judul`, dan itu hanya bekerja saat ada tetangga katalog — yaitu
pada 44% produk.

---

## Ringkasan klaim

| klaim | status | angka |
|---|---|---|
| harga 2,6× lebih tepat | berdiri | `price_logerr` 0,300 lawan 0,788 |
| deskripsi bebas kata asing | berdiri | 0,0% lawan 28,3% — dijamin penjaga |
| spesifikasi hampir tak pernah dikarang | berdiri | 0,9% lawan 24,1% |
| judul 1,4× lebih cocok | berdiri | `title_recall` 0,364 lawan 0,267 |
| halusinasi merek 4× lebih jarang | berdiri | `brand_strict%` 3,6 lawan 14,4 |
| 1,4× lebih cepat per listing | berdiri | 1,39 lawan 1,91 detik |
| student 3B mengalahkan 12B | berdiri | `title_recall` 0,315 lawan 0,267 |
| judul lebih patuh panjang platform | **gugur** | 39,7% lawan 55,4% — baseline menang |
| "ambang 0,75 optimal" | **gugur** | pertukaran murni, tak ada yang mendominasi |
| kecepatan student | **tak sah** | tumpukan penyajian berbeda |

## Berkas sumber

```
hasil_sesi2/S3_pipeline_diri.jsonl        S3_semua_v2.txt
hasil_sesi2/S3_pipeline_lini.jsonl        S3_cakupan_lini_v2.txt
hasil_sesi2/S3_pipeline_kategori.jsonl
hasil_sesi2/S3_ambang_0.70.jsonl
hasil_sesi2/S3_ambang_0.80.jsonl
hasil_sesi2/S3_panjangkan_merek.jsonl
hasil_sesi2/S3_baseline_12b.jsonl
hasil_sesi2/murid_vlm.jsonl               murid.jsonl
```
