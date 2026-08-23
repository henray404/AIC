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
> Kode di `main` sudah berubah sejak itu. Perbaikannya sudah diukur, tapi baru
> pada satu konfigurasi, jadi tidak dicampurkan ke sini supaya keenam bagian di
> bawah tetap sebanding satu sama lain. Lihat
> **[PERBAIKAN_SETELAH_S3.md](PERBAIKAN_SETELAH_S3.md)**.

> ## Metrik halusinasi: yang lama gugur, yang baru tervalidasi
>
> Penilaian manusia (51 listing, buta, 23 Agustus 2026) membantah tiga metrik
> yang selama ini jadi klaim terkuat:
>
> | metrik | recall | presisi | putusan |
> |---|---:|---:|---|
> | `brand_strict%` | 6,7% | 100% | **gugur** — melewatkan 93% |
> | `spec_halluc%` | 0,0% | — | **gugur** — tak menangkap satu pun |
> | `desc_ungrounded%` | 9,1% | 100% | **gugur** — melewatkan 91% |
> | **`ungrounded_words%`** | **93,3%** | **35%** | **dipakai sekarang** |
>
> Ketiga yang gugur hanya mencari nama merek dan istilah langka. Yang
> dilewatkan warna, aroma, rasa, dan sifat produk — semuanya kata Indonesia
> lazim:
>
> ```
> "Sepatu Lari Pria Hitam"             foto: sepatu Puma Future
> "Sabun Mandi Aroma Citrus Segar"     foto: sabun cuci beras SEZA
> "Cheek & Lip Tint Warna Merah Muda"  foto: Implora liptint
> ```
>
> `ungrounded_words%` (kolom `kata_asing%` di keluaran) memakai aturan paling
> sederhana: ada kata di judul yang tidak muncul di bacaan foto. Empat varian
> lain diuji dan kalah, termasuk daftar atribut warna/rasa/bahan buatan tangan.
>
> **Presisinya 35%** — dua dari tiga tuduhan sebenarnya sah, karena kata jenis
> dan kata jualan ikut terhukum. Jadi angka mutlaknya tidak berarti "sekian
> persen listing berhalusinasi"; yang bermakna **selisih antar sistem**, karena
> semuanya dihukum dengan cara yang sama.
>
> Metrik lain tidak terpengaruh: `title_recall`, `price_logerr`,
> `price_within2x%`, `category_valid%` punya definisi objektif.
>
> Rinciannya di [`PENILAIAN_MANUSIA.md`](PENILAIAN_MANUSIA.md).

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
| `ungrounded_words%` | judul yang memuat kata tak ada di bacaan foto. **Satu-satunya ukuran halusinasi yang tervalidasi manusia** (recall 93,3%, presisi 35%). Bandingkan selisihnya, bukan nilai mutlaknya |
| ~~`brand_strict%`~~ | **GUGUR** — recall 6,7%, hanya mencari nama merek dan istilah langka |
| ~~`spec_halluc%`~~ | **GUGUR** — recall 0,0% |
| ~~`desc_ungrounded%`~~ | **GUGUR** — recall 9,1% |
| ~~`brand_lenient%`~~ | **GUGUR** — melingkar, penjaga membuang persis apa yang ia ukur |
| `length_ok%` | judul yang panjangnya masuk rentang lazim platform |
| `sec/listing` | detik per listing, bukan per produk |

---

## A. Tiga tingkat exclusion

| system | exclusion | abstain% | price_err% | price_logerr | price_within2x% | price_coverage% | **ungrounded_words%** | length_ok% | title_recall | sec/listing |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| RAG pipeline | self | 30,7 | 23,7 | 0,258 | 74,0 | 70,3 | 90,3 | 56,2 | 0,444 | 1,41 |
| **RAG pipeline** | **product line** | 56,1 | 29,9 | 0,300 | 72,4 | 44,5 | **85,4** | 39,7 | 0,364 | 1,39 |
| RAG pipeline | category | 81,3 | 38,8 | 0,409 | 62,6 | 18,9 | **83,7** | 22,8 | 0,319 | 1,37 |
| Baseline 12B | — | — | 76,6 | 0,788 | 45,5 | 85,0 | 99,4 | 55,4 | 0,267 | 1,91 |

Kolom halusinasi lama (`spec_halluc%`, `brand_strict%`) dibuang dari tabel ini —
keduanya gugur. Angka lamanya masih bisa direproduksi dengan `git checkout
sesi-3`.

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

| system | exclusion | price_err% | price_logerr | price_within2x% | price_coverage% | **ungrounded_words%** | length_ok% | title_recall |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| RAG pipeline | self | 23,0 | 0,248 | 78,0 | 100,0 | 96,5 | 77,3 | 0,488 |
| **RAG pipeline** | **product line** | 29,9 | 0,300 | 72,4 | 100,0 | **95,8** | 78,2 | 0,446 |
| RAG pipeline | category | 35,9 | 0,350 | 67,6 | 31,8 | **88,7** | 32,6 | 0,334 |
| Baseline 12B | — | 104,1 | 0,964 | 40,5 | 91,1 | 99,3 | 55,1 | 0,272 |

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

| CLIP threshold | abstain% | price_coverage% | price_err% | price_logerr | **ungrounded_words%** | length_ok% | title_recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0,70 | 39,2 | 61,3 | 34,0 | 0,336 | 87,2 | 51,6 | 0,383 |
| **0,75** | 56,1 | 44,5 | 29,9 | 0,300 | **85,4** | 39,7 | 0,364 |
| 0,80 | 72,0 | 28,7 | 25,5 | 0,266 | **82,8** | 30,0 | 0,340 |

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

| system | title extender | **ungrounded_words%** | length_ok% | price_err% | title_recall |
|---|---|---:|---:|---:|---:|
| RAG pipeline | merek ikut ditambahkan | 85,9 | 41,9 | 29,9 | 0,371 |
| **RAG pipeline** | **merek disaring** | **85,4** | 39,7 | 29,9 | 0,364 |
| Baseline 12B | — | 99,4 | 55,4 | 76,6 | 0,267 |

Dengan ukuran yang tervalidasi, ablasi ini nyaris tidak menggeser apa pun
(85,9 → 85,4). Metrik lama mencatat 10,5 → 3,6 dan terlihat seperti perbaikan
besar — itu karena ia hanya menghitung nama merek, dan menyaring merek memang
menghilangkan tepat apa yang ia ukur.

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

| system | input | params | title_recall | **ungrounded_words%** | length_ok% | sec/listing |
|---|---|---:|---:|---:|---:|---:|
| **RAG pipeline** | foto | 4B+7B | **0,364** | 85,4 | 39,7 | **1,39** |
| Student VLM | foto | 3B | 0,315 | **81,5** | 4,1 | 2,77 \* |
| Baseline 12B | foto | 12B | 0,267 | 99,4 | **55,4** | 1,91 |
| Student text | ketikan | 0,5B | 0,208 | 100,0 † | 2,3 | 1,58 \* |

\* Kedua student diukur lewat HF transformers bf16 tanpa batch, sementara
pipeline dan baseline lewat Ollama/llama.cpp Q4. Angka waktunya mengukur
tumpukan penyajian, bukan model — **jangan dipakai**.

† Student text tidak melihat foto sama sekali, jadi bacaan fotonya kosong dan
setiap kata otomatis terhitung asing. 100,0% di sini berarti "tidak bisa
diukur", bukan "selalu berhalusinasi".

**Student VLM sedikit lebih baik dari pipeline** di ukuran ini (81,5 lawan
85,4) — hal yang tidak terlihat sama sekali di metrik lama, yang mencatat 11,4
lawan 3,6 dan menyimpulkan sebaliknya. Selisih 3,9 poin itu kecil dan
sampelnya satu himpunan, jadi jangan diklaim sebagai kemenangan; yang penting
klaim lama "pipeline jauh lebih bersih dari student" tidak berdiri.

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
| judul 1,4× lebih cocok | berdiri | `title_recall` 0,364 lawan 0,267 |
| 1,4× lebih cepat per listing | berdiri | 1,39 lawan 1,91 detik |
| student 3B mengalahkan 12B | berdiri | `title_recall` 0,315 lawan 0,267 |
| judul lebih patuh panjang platform | **gugur** | 39,7% lawan 55,4% — baseline menang |
| "ambang 0,75 optimal" | **gugur** | pertukaran murni, tak ada yang mendominasi |
| lebih jarang mengarang dari baseline | berdiri, **tapi tipis** | `ungrounded_words%` 85,4 lawan 99,4 |
| kecepatan student | **tak sah** | tumpukan penyajian berbeda |
| ~~halusinasi merek 4× lebih jarang~~ | **gugur** | metriknya melewatkan 93% halusinasi |
| ~~spesifikasi hampir tak pernah dikarang~~ | **gugur** | metriknya menangkap 0% |
| ~~deskripsi bebas kata asing~~ | **gugur** | metriknya melewatkan 91% |

Ketiga klaim halusinasi lama gugur setelah penilaian manusia — bukan karena
sistemnya buruk melainkan karena **metriknya tidak mengukur apa yang namanya
janjikan**. Penggantinya, `ungrounded_words%`, masih menempatkan pipeline di
atas baseline (85,4 lawan 99,4) tapi selisihnya jauh lebih kecil daripada
"12× lebih bersih" yang dulu diklaim.

Dua hal yang harus ikut disebut kalau klaim ini dipakai:

1. **Presisi metriknya 35%.** Angka mutlaknya tidak berarti "85% listing
   berhalusinasi" — yang bermakna selisih antar sistem.
2. **Student VLM sedikit lebih baik dari pipeline** (81,5). Klaim "pipeline
   jauh lebih bersih dari student" tidak berdiri.

Penilaian manusia pada 51 listing bahkan mencatat pipeline **lebih sering**
mengarang judul daripada baseline (6/17 lawan 3/17) — berlawanan dengan metrik
otomatis. Sampelnya terlalu kecil untuk menyimpulkan, tapi cukup untuk menahan
klaim yang lebih berani. Lihat [`PENILAIAN_MANUSIA.md`](PENILAIAN_MANUSIA.md).

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
