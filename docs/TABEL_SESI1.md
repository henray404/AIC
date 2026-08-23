# Tabel hasil

Semua angka diukur pada **himpunan uji yang sama**: 492 produk yang ditahan dari
latihan model sulingan. Katalog 28.443 produk marketplace Indonesia. Diukur
`scripts/eval_listing.py`, dibatasi ke platform `blibli` dan `tokopedia` supaya
tiap sistem menghasilkan jumlah listing yang sama.

## Dari mana tiap angka berasal

Kode berubah setelah sesi 3, dan tidak semua konfigurasi sempat dijalankan ulang.
Ini harus dibaca lebih dulu supaya tabel di bawah tidak salah kutip.

| label | kode | dijalankan |
|---|---|---|
| **S4** | terkini — kategori ditambatkan, pemanjang judul ketat | 22 Agu 2026, laptop |
| **S3** | sesi 3, sebelum perbaikan kategori dan judul | 21–22 Agu 2026, RTX 4090 sewaan |

`S3_baseline_12b` **tetap sah dibandingkan dengan S4**: `baseline_besar.py` tidak
ikut berubah — yang disunting hanya cara memilih produk uji, bukan cara
menghasilkan listing.

Ablasi ambang dan pemanjang judul (bagian C dan D) masih S3. Angkanya benar
untuk kode saat itu, tapi **jangan disandingkan lintas bagian** dengan S4.

Waktu tidak sebanding antara S3 dan S4 — mesinnya berbeda.

## Sistem yang diuji

| label | model | input | retrieval | penjaga | params |
|---|---|---|---|---|---|
| **RAG pipeline** | `gemma3:4b` (baca foto) + `qwen2.5:7b` (tulis) | foto | CLIP ViT-B/32 + TF-IDF atas 28.443 produk | filter merek, filter deskripsi, harga deterministik, penambat kategori, pemanjang judul | 4B + 7B |
| **Baseline 12B** | `gemma3:12b` | foto | — | — | 12B |
| **Student VLM** | `Qwen2.5-VL-3B` + LoRA | foto | — | — | 3B |
| **Student text** | `Qwen2.5-0.5B` + LoRA | keterangan ketikan | — | — | 0,5B |

Kedua *student* disuling dari RAG pipeline sebagai guru: pipeline menghasilkan
9.889 label untuk 6.000 produk, lalu model kecil dilatih LoRA di atasnya.

## Index exclusion — protokol uji, bukan bagian metode

| tingkat | yang dibuang dari indeks | mensimulasikan |
|---|---|---|
| `self` | baris katalog produk itu sendiri | penjual mengunggah ulang barang yang sudah ada |
| `product line` | semua produk yang kata pertama judulnya sama | penjual dengan varian baru dari merek yang dikenal |
| `category` | seluruh produk sekategori UMKM | penjual dengan barang yang benar-benar asing |

`product line` dipakai sebagai acuan di seluruh dokumen ini.

## Kamus metrik

| metrik | arti |
|---|---|
| `title_recall` | bagian kata judul asli yang muncul di judul buatan. Tinggi = cocok |
| `price_err%` | median galat relatif harga. **Asimetris** — menebak 100rb untuk barang 20rb tercatat 400%, sebaliknya cuma 80% |
| `price_logerr` | median dari nilai mutlak log(tebakan/asli). Simetris. 0,69 = meleset tepat 2× |
| `price_within2x%` | porsi tebakan antara setengah sampai dua kali harga asli |
| `price_coverage%` | porsi listing yang berani menyebut harga |
| `abstain%` | porsi produk yang sistem akui tidak dikenalinya |
| `category_valid%` | kategori yang benar-benar ada di taksonomi UMKM (7 nilai) |
| `category_correct%` | kategori yang sama dengan kategori produk aslinya |
| `brand_lenient%` | merek tak berdasar, katalog ikut memaafkan. **Melingkar** — penjaga membuang persis apa yang metrik ini ukur |
| `brand_strict%` | sama, katalog **tidak** memaafkan. Satu-satunya ukuran halusinasi yang setara antar sistem |
| `spec_halluc%` | angka di judul yang tidak ada di bacaan foto |
| `desc_ungrounded%` | kata di deskripsi yang tak berdasar foto maupun katalog |
| `length_ok%` | judul yang panjangnya masuk rentang lazim platform |

---

## A. Perbandingan utama — S4 lawan baseline

492 produk, 984 listing tiap sisi, exclusion `product line`.

| system | title_recall | category_valid% | category_correct% | brand_strict% | spec_halluc% | desc_ungrounded% | price_logerr | price_within2x% | length_ok% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **RAG pipeline (S4)** | **0,346** | **100,0** | **65,9** | **1,2** | **1,0** | **0,0** | **0,300** | **72,4** | 25,6 |
| Baseline 12B (S3) | 0,267 | 0,0 | 0,0 | 14,4 | 24,1 | 28,3 | 0,788 | 45,5 | **55,4** |

Pipeline unggul di delapan dari sembilan kolom. Satu-satunya kekalahan
`length_ok%`, dan itu justru memburuk setelah perbaikan judul — lihat bagian E.

Deskripsi:

| system | desc_chars | desc_spec% | desc_ungrounded% | desc_claims% | desc_boilerplate% | desc_repeats% |
|---|---:|---:|---:|---:|---:|---:|
| **RAG pipeline (S4)** | 118 | **0,1** | **0,0** | **0,0** | **0,0** | 0,4 |
| Baseline 12B (S3) | 188 | 7,9 | 28,3 | 0,5 | 0,2 | 0,0 |

Pipeline abstain pada 56,1% produk (276 dari 492) dan menyebut harga pada 44,5%
listing; baseline menjawab semuanya.

### A1. Cakupan disamakan — 216 produk

Pipeline menyetel harga 0 untuk barang tak dikenal, dan baris itu keluar dari
`price_err` sepenuhnya. Di sini kedua sisi dinilai hanya pada produk yang
pipeline berani beri harga.

| system | price_err% | price_logerr | price_within2x% | category_correct% | brand_strict% | spec_halluc% | length_ok% | title_recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **RAG pipeline (S4)** | **28,8** | **0,300** | **72,4** | **86,3** | **2,8** | **0,7** | 46,3 | **0,417** |
| Baseline 12B (S3) | 104,1 | 0,964 | 40,5 | 0,0 | 13,7 | 22,5 | **55,1** | 0,272 |

`price_err%` baseline melar ke 104,1 di subset ini, tapi `price_logerr` cuma
bergerak 0,788 → 0,964. Keunggulan pipeline memang sedikit lebih besar di sini,
tapi jauh lebih kecil dari yang `price_err%` gambarkan — **3,2× nyata, bukan
3,6×**.

Sebabnya: baseline tidak menaksir harga, ia memilih dari menu angka bulat
(397 tebakan hanya 34 nilai unik) sementara 54% produk berharga di bawah
Rp 50rb. Galat relatif menghukum kelebihan jauh lebih berat daripada kekurangan.

`category_correct%` melonjak ke 86,3% di subset ini karena produk-produk inilah
yang punya tetangga katalog, dan tetangga itulah yang menambatkan kategorinya.

---

## B. Apa yang berubah dari S3 ke S4

Konfigurasi identik (`product line`, 492 produk yang sama), hanya kodenya beda.

| metrik | S3 | S4 | |
|---|---:|---:|---|
| `category_valid%` | 41,6 | **100,0** | prompt menyebut daftar sah + penambat |
| `category_correct%` | 36,4 | **65,9** | +81% relatif |
| `brand_strict%` | 3,6 | **1,2** | 3× lebih bersih |
| `price_err%` | 29,9 | **28,8** | |
| `price_logerr` | 0,300 | 0,300 | harga tidak disentuh |
| `abstain%` | 56,1 | 56,1 | tidak berubah |
| `title_recall` | 0,364 | 0,346 | −5% |
| `length_ok%` | 39,7 | 25,6 | **−35%** |

Tiga perubahan kode yang menghasilkannya:

1. **Kategori ditambatkan ke taksonomi.** Prompt menyebut ketujuh nilai sah,
   lalu keluarannya ditambatkan — nilai model kalau sudah sah, kalau tidak
   kategori tetangga katalog, kalau tidak kata penanda, kalau tidak `lainnya`.
2. **Pemanjang judul ikut suara mayoritas tetangga**, bukan "muncul di minimal
   dua". Kata yang disepakati mayoritas menggambarkan jenis barangnya; kata yang
   cuma dipunyai sebagian justru yang membedakan mereka satu sama lain.
3. **Satuan dibuang bersama angkanya.** "Minyak Goreng Sunco 1 Liter" yang
   ukurannya tak terbaca di foto dulu jadi "Minyak Goreng Sunco Liter".

---

## C. Ablasi ambang abstain — S3

**Kode lama.** Angkanya benar untuk kode saat itu, tapi jangan disandingkan
dengan bagian A.

| CLIP threshold | abstain% | price_coverage% | price_err% | price_logerr | brand_strict% | length_ok% | title_recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0,70 | 39,2 | 61,3 | 34,0 | 0,336 | 5,6 | 51,6 | 0,383 |
| **0,75** | 56,1 | 44,5 | 29,9 | 0,300 | 3,6 | 39,7 | 0,364 |
| 0,80 | 72,0 | 28,7 | 25,5 | 0,266 | 2,0 | 30,0 | 0,340 |

**Pertukaran murni, bukan parameter yang terbukti optimal.** Makin longgar
ambangnya, makin sering sistem menjawab dan makin sering pula ia meleset. Tidak
ada nilai yang mendominasi nilai lain di semua kolom.

Bawaan 0,75 dipilih atas dasar penilaian produk, bukan metrik: saran harga yang
meleset 30% masih berguna bagi penjual, sedangkan diam tidak berguna sama
sekali. Tulis sebagai pilihan di laporan, bukan sebagai temuan.

---

## D. Ablasi pemanjang judul — S3

**Kode lama**, ambang "muncul di minimal dua tetangga".

| system | title extender | brand_strict% | length_ok% | price_err% | title_recall |
|---|---|---:|---:|---:|---:|
| RAG pipeline | merek ikut ditambahkan | 10,5 | 41,9 | 29,9 | 0,371 |
| RAG pipeline | merek disaring | 3,6 | 39,7 | 29,9 | 0,364 |

| versi | judul yang dihasilkan |
|---|---|
| merek ikut ditambahkan | Headset Gaming Hitam Kabel Mikrofon **FANTECH** |
| merek disaring | Headset Gaming Hitam Kabel Mikrofon |

Fantech tidak pernah ada di foto — dipinjam dari judul produk tetangga.

Di S4 langkah ini diperketat lagi jadi suara mayoritas, dan `brand_strict%`
turun ke 1,2%.

---

## E. Ongkos perbaikan judul, dan kenapa tetap diambil

`length_ok%` turun 39,7 → 25,6, memperlebar kekalahan dari baseline (55,4%).

Kata yang berhenti ditambahkan diperiksa satu per satu pada 389 judul S3, tanpa
GPU, memakai tetangga yang sudah tersimpan:

| judul | kata yang tidak lagi ditambahkan | apa itu sebenarnya |
|---|---|---|
| Minyak Goreng Pouch Kunci Mas | solo, smg, jog | kota pengiriman |
| Minyak Goreng Pouch | sedaap | merek lain |
| Mie Instan K-Rose Premium | chicken, cheese | varian produk lain |
| Keripik Pisang Pandan Cokelat | manis | rasa produk lain |

Kedelapan contoh yang terambil tidak ada satu pun yang sah. Rata-rata kata
ditambahkan turun 2,39 → 1,44 per judul.

**`title_recall` nyaris tidak bergerak** (0,364 → 0,346) meski judulnya jauh
lebih pendek. Kalau kata-kata itu berguna, angka itu akan ikut jatuh. Tidak.

Kesimpulan yang jujur: `length_ok%` versi lama **sebagian palsu** — dipompa kata
yang tidak menggambarkan produknya. Angka 25,6 lebih rendah dan lebih benar.

---

## F. Dua student sulingan — S3

**Kode lama**, dan student tidak ikut dilatih ulang. Baris pipeline di sini juga
S3, jadi perbandingan di dalam tabel ini tetap sah satu sama lain.

| system | input | params | title_recall | brand_strict% | spec_halluc% | desc_ungrounded% | length_ok% |
|---|---|---:|---:|---:|---:|---:|---:|
| **RAG pipeline (S3)** | foto | 4B+7B | **0,364** | **3,6** | **0,9** | **0,0** | 39,7 |
| Student VLM | foto | 3B | 0,315 | 11,4 | 12,3 | 8,7 | 4,1 |
| Baseline 12B | foto | 12B | 0,267 | 14,4 | 24,1 | 28,3 | **55,4** |
| Student text | ketikan | 0,5B | 0,208 | 19,2 \* | 11,1 | 16,1 | 2,3 |

\* Student text tidak melihat foto, jadi `brand_strict%` menghukum tiap katanya.
Angka itu tidak berarti untuknya.

Kecepatan kedua student **tidak dilaporkan**: mereka diukur lewat HF
transformers bf16 tanpa batch sementara pipeline dan baseline lewat
Ollama/llama.cpp Q4. Yang terukur tumpukan penyajian, bukan model.

**Student VLM 3B mengalahkan Baseline 12B** di `title_recall`, `spec_halluc`,
dan `desc_ungrounded` — dengan model empat kali lebih kecil.

Tapi ia kalah dari gurunya di setiap kolom, dan pola kekalahannya seragam:
**penjaga itu kode, bukan gaya.** `saring_merek` dan `pelanggaran_deskripsi`
berjalan setelah model menulis; distilasi memindahkan cara menulis, tidak
memindahkan pemeriksaan.

Itu bukti positif, bukan kegagalan: kalau jaminan nol berasal dari bobot model,
student yang meniru gurunya akan ikut bersih. Ia tidak. Verifikasi eksternal
yang menekannya.

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
kelompok "kena" agak dipompa. Perbandingan antar kedua student tetap sah.

---

## Ringkasan klaim

Semua angka dari bagian A (S4 lawan baseline) kecuali yang ditandai.

| klaim | status | angka |
|---|---|---|
| harga 2,6× lebih tepat | berdiri | `price_logerr` 0,300 lawan 0,788 |
| deskripsi bebas kata asing | berdiri | 0,0% lawan 28,3% — dijamin penjaga |
| spesifikasi hampir tak pernah dikarang | berdiri | 1,0% lawan 24,1% |
| halusinasi merek 12× lebih jarang | berdiri | `brand_strict%` 1,2 lawan 14,4 |
| kategori selalu sah, 2/3 tepat | berdiri | 100% sah dan 65,9% benar, lawan 0% dan 0% |
| judul 1,3× lebih cocok | berdiri | `title_recall` 0,346 lawan 0,267 |
| student 3B mengalahkan 12B | berdiri *(S3)* | `title_recall` 0,315 lawan 0,267 |
| judul lebih patuh panjang platform | **gugur** | 25,6% lawan 55,4% — baseline menang telak |
| "ambang 0,75 optimal" | **gugur** | pertukaran murni, tak ada yang mendominasi |
| pipeline lebih cepat | **belum diukur ulang** | S3 mencatat 1,39 lawan 1,91 dtk/listing di 4090; S4 di laptop, tak sebanding |
| kecepatan student | **tak sah** | tumpukan penyajian berbeda |

## Berkas sumber

```
S4 (kode terkini)   data_drive/eval/S4_bersih.jsonl
S3 (kode sesi 3)    hasil_sesi2/S3_pipeline_diri.jsonl
                    hasil_sesi2/S3_pipeline_lini.jsonl
                    hasil_sesi2/S3_pipeline_kategori.jsonl
                    hasil_sesi2/S3_ambang_0.70.jsonl
                    hasil_sesi2/S3_ambang_0.80.jsonl
                    hasil_sesi2/S3_panjangkan_merek.jsonl
                    hasil_sesi2/S3_baseline_12b.jsonl
                    hasil_sesi2/murid_vlm.jsonl
                    hasil_sesi2/murid.jsonl
```

Belum dijalankan ulang dengan kode terkini: tingkat exclusion `self` dan
`category`, kedua ablasi ambang, ablasi pemanjang judul, dan kedua student.
Sekitar 8 jam GPU di laptop, atau ~1 jam di 4090 sewaan.
