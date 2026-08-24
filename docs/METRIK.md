# Metrik: definisi, validasi, dan batasannya

Dokumen acuan untuk menulis laporan. Tiap metrik dijelaskan: apa yang diukur,
bagaimana menghitungnya, apakah sudah divalidasi, dan apa yang **tidak boleh**
diklaim darinya.

Semuanya dihitung `scripts/eval_listing.py` dari berkas keluaran pipeline.
Jalankan tanpa argumen tambahan untuk melihat metrik yang sah; `--semua`
menampilkan yang sudah gugur.

---

## Ringkas: mana yang boleh dikutip

| status | metrik |
|---|---|
| **objektif** — definisinya tidak bisa diperdebatkan | `json_valid`, `harga_logerr`, `harga_2x`, `harga_cakupan`, `abstain`, `kategori_sah`, `panjang_patuh`, `desk_klaim`, `desk_sampah`, `desk_potong`, `detik_listing` |
| **tervalidasi manusia** — dengan syarat | `kata_asing` |
| **tahan manipulasi** — diuji dengan serangan | `inti_f1` |
| **batas bawah** — sebagian mengukur mutu label | `kategori_benar` |
| **rentan** — jangan dipakai sendirian | `inti`, `harga_err` |
| **GUGUR** — tidak mengukur yang dijanjikan | `merek_ketat`, `merek_sempit`, `spek_karang`, `desk_asing`, `desk_spek`, `harga_model_err` |

---

## 1. Mutu judul

### `inti_f1` — metrik utama untuk membandingkan judul

Rata-rata harmonik antara berapa bagian kata judul asli yang tersebut ulang
(recall) dan berapa bagian kata judul buatan yang benar-benar ada di judul asli
(presisi).

```
irisan  = kata(judul_buatan) ∩ kata(judul_asli)
inti_f1 = 2 × |irisan| / (|kata(judul_asli)| + |kata(judul_buatan)|)
```

Kata dinormalkan huruf kecil, minimal 4 karakter, dan kata henti dibuang
(`dan`, `untuk`, `yang`, `pcs`, `size`, …).

**Kenapa F1, bukan recall.** `inti` (recall murni) tidak menghukum kata
tambahan sama sekali, jadi bisa dinaikkan dengan menggelembungkan judul —
persis kebiasaan *keyword stuffing* yang justru ingin dihindari sistem ini.

Diuji dengan serangan langsung: menempelkan kata tersering di katalog ke
**setiap** judul, tanpa melihat produknya.

| kata sampah ditempel | `inti` | `inti_f1` |
|---:|---:|---:|
| 0 | 0,346 | 0,398 |
| 4 | 0,355 | 0,306 |
| 8 | 0,363 | 0,251 |
| 12 | 0,368 | 0,214 |

Recall naik +0,022 — cukup untuk membalik selisih pipeline lawan student. F1
turun 0,184 pada serangan yang sama. Karena itu `inti_f1` yang dipakai
membandingkan sistem.

### Skala acuan: berapa angka yang wajar

Ini bagian terpenting untuk laporan. **`inti_f1` tidak bisa mencapai 1,0**, dan
angka 0,4 bukan berarti "40% benar".

| pembanding | `inti_f1` |
|---|---:|
| judul acak dari katalog | **0,010** ← lantai |
| Baseline 12B | 0,292 |
| Student VLM 3B | 0,393 |
| RAG pipeline | 0,405 |
| **judul tetangga katalog, ditulis manusia** | **0,437** ← batas atas praktis |
| judul asli itu sendiri | 1,000 |

Batas atas 0,437 dihitung dari 216 produk: judul yang **ditulis penjual
sungguhan** untuk produk yang benar-benar mirip, dibandingkan dengan judul asli
produk uji. Dua manusia yang menjual barang serupa pun hanya sepakat 0,437,
karena tiap penjual memilih kata sendiri.

**Pipeline mencapai 93% dari batas atas manusia** (0,405 / 0,437).

Sebabnya 1,0 mustahil: judul marketplace asli penuh kata kunci berulang.

```
"Keripik Pisang Cokelat Lumer Snack Food Makanan Cokelat Manis Cemilan …"
```

Sistem yang menulis "Keripik Pisang Cokelat Lumer" — judul yang lebih baik —
tetap dihukum karena tidak menyalin "Snack Food Makanan Cemilan".

### `inti` dan `inti_presisi` — pelengkap, bukan pengganti

`inti` dipertahankan supaya angka lama bisa direproduksi. `inti_presisi`
memperlihatkan dari mana selisih F1 berasal — student VLM punya presisi
tertinggi (0,593) karena judulnya pendek tapi hampir semua katanya relevan.

---

## 2. Halusinasi

### `kata_asing` — satu-satunya yang tervalidasi

Porsi listing yang judulnya memuat **kata apa pun** yang tidak muncul di bacaan
foto.

```
kata_asing = ada kata di kata(judul) yang tidak ada di kata(bacaan_foto)
```

Katalog sengaja **tidak** memaafkan: pipeline punya katalog dan pembanding
tidak, jadi memaafkan lewat katalog membuat ukurannya timpang.

**Divalidasi pada 51 listing berlabel manusia** (buta, 23 Agustus 2026). Lima
aturan diuji:

| aturan | recall | presisi | F1 |
|---|---:|---:|---:|
| merek/istilah langka saja (lama) | 6,7% | 100% | 12,5 |
| **ada kata asing** | **93,3%** | **35%** | **50,9** |
| kata asing ≥ 3 | 60,0% | 39,1% | 47,4 |
| porsi kata asing > 40% judul | 66,7% | 34,5% | 45,5 |
| daftar atribut warna/rasa/bahan | 26,7% | 33,3% | 29,6 |

Yang paling sederhana menang. Daftar atribut buatan tangan justru lebih buruk —
batasnya bukan jenis kata melainkan apakah bisa disimpulkan dari bentuk
barangnya, dan aturan kata tidak bisa membedakan itu.

> ### Syarat pelaporan yang WAJIB disebut
>
> **Presisinya 35%** — dua dari tiga tuduhan sebenarnya sah. Kata jenis
> ("kaleng", "bibir") dan kata jualan ("praktis", "kekinian") ikut terhukum.
>
> Jadi `kata_asing% 84,3` **tidak berarti** "84% listing berhalusinasi". Yang
> bermakna **selisih antar sistem**, karena semuanya dihukum dengan cara sama.

### Metrik halusinasi yang GUGUR

`merek_ketat`, `merek_sempit`, `spek_karang`, `desk_asing`, `desk_spek`.

Penilaian manusia mengukur recall-nya:

| metrik | recall | artinya |
|---|---:|---|
| `merek_ketat%` | 6,7% | melewatkan 93% halusinasi |
| `spek_karang%` | 0,0% | tidak menangkap satu pun |
| `desk_asing%` | 9,1% | melewatkan 91% |

Sebabnya: ketiganya hanya mencari **nama merek dan istilah langka** — aturannya
`w in lex["merek"] or w not in lex["umum"]`. Yang dilewatkan adalah warna,
aroma, rasa, dan sifat produk, semuanya kata Indonesia lazim:

| judul yang dihasilkan | yang terlihat di foto |
|---|---|
| Sepatu Lari Pria **Hitam** | sepatu Puma Future |
| Sabun Mandi **Aroma Citrus Segar** | sabun cuci beras SEZA |
| Cheek & Lip Tint **Warna Merah Muda** | Implora liptint |

`merek_sempit` punya cacat kedua yang lebih dasar: ia **melingkar**. Penjaga
`saring_merek` membuang persis kata yang metrik ini ukur, jadi nolnya dijamin
konstruksi, bukan mutu.

Kelimanya tetap dihitung supaya angka lama bisa direproduksi, tapi disembunyikan
dari keluaran bawaan. `--semua` menampilkannya dengan peringatan.

---

## 3. Harga

### `harga_logerr` dan `harga_2x` — metrik utama

```
harga_logerr = median |log(tebakan / asli)|      0,69 = meleset tepat 2×
harga_2x     = porsi tebakan dalam 0,5× – 2,0× harga asli
```

**Kenapa bukan galat relatif.** `harga_err` (median absolute percentage error)
asimetris: menebak Rp 100rb untuk barang Rp 20rb tercatat 400%, sebaliknya cuma
80%. Itu bukan soal teori — baseline tidak menaksir harga melainkan memilih dari
menu angka bulat (397 tebakan hanya memakai 34 nilai unik, didominasi
Rp 100rb–200rb), sementara 54% produk berharga di bawah Rp 50rb. Akibatnya
galatnya melar sampai 104% dan keunggulan pipeline tampak lebih besar dari
sebenarnya.

Dengan ukuran simetris: pipeline unggul **2,6×**, bukan 3,6×.

### `harga_cakupan` dan `abstain` — harus dilaporkan berpasangan

Pipeline menyetel harga 0 untuk barang tak dikenal, dan baris itu keluar dari
`harga_err` sepenuhnya. Melaporkan galat tanpa cakupan berarti melaporkan
ketepatan pada kasus mudah saja.

Gunakan `--samakan-cakupan BERKAS` untuk menilai semua sistem hanya pada produk
yang BERKAS itu berani beri harga.

### `harga_model_err` — GUGUR

Seharusnya mengukur tebakan model sebelum katalog membetulkannya. Tapi
`ringkas_konteks` menaruh median harga tetangga **langsung di prompt**
("tengah Rp53.470"), jadi model menuliskan angka yang praktis sama dengan yang
nanti dihitung katalog — sama persis di 70% baris. Bukan ukuran yang berdiri
sendiri.

---

## 4. Kategori

### `kategori_sah` — objektif

Apakah keluarannya ada di taksonomi tujuh kelas: `bumbu_masak`,
`camilan_olahan`, `fashion_perawatan`, `kriya_rumah`, `minuman_herbal`,
`pokok_tani`, `lainnya`.

Pipeline 100% (dijamin `sahkan_kategori`), baseline 0% — ia mengarang taksonomi
Tokopedia sendiri: "Perawatan Wajah", "Komputer & Aksesoris",
"Pakaian Pria > Kemeja".

### `kategori_benar` — BATAS BAWAH, bukan ukuran murni

Apakah kategorinya sama dengan `kategori_umkm` di katalog. Masalahnya: sebagian
label katalog itu sendiri keliru.

Akurasi pipeline dipecah menurut **cara label dibuat**:

| cara label ditentukan | akurasi pipeline |
|---|---:|
| `tidak_terpetakan` | **90,6%** |
| `kata_kunci_judul` | 64,4% |
| `peta_l1` | 60,4% |
| `kata_kunci_kategori` | **42,4%** |

Pipeline paling akurat justru pada produk yang labelnya paling lemah — pola
terbalik dari yang diharapkan kalau modelnya yang bermasalah. Enam dari delapan
"kesalahan" pada produk `tidak_terpetakan` ternyata jawaban yang tepat:

| produk | label katalog | jawaban pipeline |
|---|---|---|
| Yuri Bathroom Cleaner | `lainnya` | `kriya_rumah` ✓ |
| Marina Bright Lotion | `lainnya` | `fashion_perawatan` ✓ |
| ABON SAPI DAPOERBABE | `lainnya` | `camilan_olahan` ✓ |

Rinciannya di [`CACAT_LABEL_KATEGORI.md`](CACAT_LABEL_KATEGORI.md). Laporkan
`kategori_benar 65,9%` sebagai batas bawah.

---

## 5. Deskripsi

Tiga metrik yang tetap sah karena mencocokkan **daftar frasa tertutup**, bukan
menebak apakah sesuatu berdasar:

| metrik | isi daftarnya |
|---|---|
| `desk_klaim` | garansi, BPOM, halal, MUI, SNI, FDA, menyembuhkan, khasiat, "100%" |
| `desk_sampah` | "selamat datang", "gratis ongkir", nomor WA, "wajib baca" |
| `desk_potong` | kalimat tidak berakhir tanda baca (anggaran token habis) |

`desk_asing` dan `desk_spek` gugur bersama metrik halusinasi judul.

---

## 6. Kecepatan

`detik_listing` — detik per listing, bukan per produk. Tiap produk menghasilkan
jumlah listing berbeda antar sistem (pipeline mengikuti `platform_profiles.json`,
baseline mengunci tiga), jadi detik per produk membandingkan dua satuan berbeda.

> **Hanya sebanding pada mesin dan tumpukan penyajian yang sama.** Pipeline dan
> baseline diukur lewat Ollama/llama.cpp Q4 di RTX 4090; kedua student lewat HF
> transformers bf16 tanpa batch. Angka student **tidak sah** — yang terukur
> tumpukan penyajian, bukan model.

---

## Protokol uji

### Index exclusion — bagian protokol, bukan bagian metode

Saat menguji satu produk, sebagian katalog dibuang dari indeks supaya sistem
tidak menemukan jawabannya sendiri.

| tingkat | yang dibuang | mensimulasikan |
|---|---|---|
| `self` | baris katalog produk itu sendiri | penjual mengunggah ulang barang yang sudah ada |
| `product line` | semua produk yang kata pertama judulnya sama | penjual dengan varian baru dari merek dikenal |
| `category` | seluruh produk sekategori UMKM | penjual dengan barang benar-benar asing |

`product line` dipakai sebagai acuan.

### Cacat pengukuran yang pernah ditemukan

Semuanya berpihak pada pipeline, dan tidak satu pun terlihat dari tabelnya.

1. **Baseline dinilai tanpa bukti penglihatan.** `baseline_besar.py` menulis
   `vlm: ""`, dan karangan dihitung `kata(judul) − kata(vlm) − kata(tetangga)`.
   Bukti kosong membuat seluruh kata judul terhitung karangan — baseline akan
   mencatat halusinasi 100% karena satu kolom kosong. Diperbaiki
   `patch_baseline_vlm.py`.
2. **Cakupan tidak sama.** Baris yang pipeline diamkan keluar dari `harga_err`.
   Ditambahkan `harga_cakupan` dan `--samakan-cakupan`.
3. **Satuan waktu berbeda.** Ditambahkan `detik_listing`.
4. **`merek_ketat` versi pertama** menandai judul karena satu kata lazim tak
   muncul di bacaan foto — mengukur irisan kosakata, bukan karangan.
5. **Metadata tersilang di berkas student.** Teks fakta dipetakan balik lewat
   dict padahal tidak unik; 8,7% keluaran mencatat judul asli produk lain.
6. **`harga_model_err` tidak berdiri sendiri** — model diberi tahu jawabannya
   di prompt.
7. **Tiga metrik halusinasi tidak mengukur halusinasi** — ditemukan penilaian
   manusia.
8. **`inti` bisa dinaikkan keyword stuffing** — ditemukan uji serangan.

---

## Cara menjalankan

```bash
# metrik yang sah saja
python scripts/eval_listing.py hasil_sesi2/S4_bersih.jsonl

# bandingkan beberapa sistem, platform disamakan
python scripts/eval_listing.py A.jsonl B.jsonl --hanya-platform blibli,tokopedia

# samakan cakupan harga sebelum membandingkan galat
python scripts/eval_listing.py A.jsonl B.jsonl --samakan-cakupan A.jsonl

# tampilkan juga metrik yang gugur (untuk mereproduksi angka lama)
python scripts/eval_listing.py A.jsonl --semua

# uji sendiri metriknya
python scripts/eval_listing.py --selfcheck
```

## Berkas terkait

```
docs/TABEL_SESI1.md            hasil lengkap semua konfigurasi
docs/PENILAIAN_MANUSIA.md      validasi metrik oleh manusia
docs/CACAT_LABEL_KATEGORI.md   kenapa kategori_benar batas bawah
docs/PERBAIKAN_SETELAH_S3.md   delta kode setelah tag sesi-3
scripts/eval_listing.py        implementasi semua metrik
```
