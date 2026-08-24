# Hasil lengkap

Semua angka diukur pada **himpunan uji yang sama**: 492 produk yang ditahan dari
latihan model sulingan, dari katalog 28.443 produk marketplace Indonesia.
Dibatasi ke platform `blibli` dan `tokopedia` supaya tiap sistem menghasilkan
jumlah listing yang sama.

Definisi tiap metrik, validasinya, dan apa yang tidak boleh diklaim darinya ada
di [`METRIK.md`](METRIK.md). **Baca itu dulu sebelum mengutip angka apa pun.**

## Provenans

| label | kode | mesin | tanggal |
|---|---|---|---|
| **S3** | tag git `sesi-3` (commit `5c94ed3`) | RTX 4090 sewaan | 21–22 Agu 2026 |
| **S4** | `main`, setelah perbaikan kategori & judul | laptop RTX 5050 | 22 Agu 2026 |

`S3_baseline_12b` sah dibandingkan dengan S4: `baseline_besar.py` tidak ikut
berubah — yang disunting hanya cara memilih produk uji.

Angka waktu **tidak** sebanding antar S3 dan S4 (mesin berbeda).

Reproduksi angka S3: `git checkout sesi-3`.

---

## 1. Sistem yang diuji

| label | model | input | retrieval | penjaga | params |
|---|---|---|---|---|---|
| **RAG pipeline** | `gemma3:4b` baca foto + `qwen2.5:7b` tulis | foto | CLIP ViT-B/32 + TF-IDF atas 28.443 produk | filter merek, filter deskripsi, harga deterministik, penambat kategori, pemanjang judul | 4B + 7B |
| **Baseline 12B** | `gemma3:12b` | foto | — | — | 12B |
| **Student VLM** | `Qwen2.5-VL-3B` + LoRA | foto | — | — | 3B |
| **Student text** | `Qwen2.5-0.5B` + LoRA | keterangan ketikan | — | — | 0,5B |

Kedua *student* disuling dari RAG pipeline sebagai guru: pipeline menghasilkan
9.889 label untuk 6.000 produk, lalu model kecil dilatih LoRA di atasnya.

---

## 2. Perbandingan utama

492 produk, 984 listing tiap sisi, exclusion `product line`.

| system | `inti_f1` | `kata_asing%` | `kategori_sah%` | `kategori_benar%` | `harga_logerr` | `harga_2x%` | `panjang_patuh%` |
|---|---:|---:|---:|---:|---:|---:|---:|
| **RAG pipeline (S4)** | **0,398** | **84,3** | **100,0** | **65,9** | **0,300** | **72,4** | 25,6 |
| RAG pipeline (S3) | 0,405 | 85,4 | 41,6 | 36,4 | 0,300 | 72,4 | 39,7 |
| Student VLM 3B | 0,393 | **81,5** | 0,0 | 0,0 | — | — | 4,1 |
| Baseline 12B | 0,292 | 99,4 | 0,0 | 0,0 | 0,788 | 45,5 | **55,4** |

Deskripsi:

| system | `desk_char` | `desk_klaim%` | `desk_sampah%` | `desk_potong%` |
|---|---:|---:|---:|---:|
| **RAG pipeline (S4)** | 118 | **0,0** | **0,0** | 0,2 |
| Student VLM 3B | 110 | 0,2 | **0,0** | **0,0** |
| Baseline 12B | 188 | 0,5 | 0,2 | **0,0** |

### Yang berdiri

**Harga 2,6× lebih tepat.** `harga_logerr` 0,300 lawan 0,788, dengan ukuran
simetris bukan galat relatif yang asimetris.

**Judul 1,4× lebih cocok.** `inti_f1` 0,398 lawan 0,292 — dan itu **91% dari
batas atas manusia** (0,437; lihat [`METRIK.md`](METRIK.md) untuk skala acuan).

**Kategori selalu sah, dua pertiga tepat.** 100% dan 65,9% lawan 0% dan 0%.
Baseline tidak pernah sekali pun menghasilkan kategori yang ada di taksonomi.

**Deskripsi bebas klaim terlarang dan basa-basi lapak.** 0,0% di keduanya;
baseline 0,5% dan 0,2%.

**1,4× lebih cepat per listing.** 1,39 lawan 1,91 detik, diukur di mesin dan
tumpukan penyajian yang sama (S3).

### Yang gugur

**Judul lebih patuh panjang platform.** 25,6% lawan 55,4% — baseline menang
telak. Sebabnya `panjangkan_judul` diperketat supaya berhenti meminjam kata dari
tetangga; halusinasi turun, panjang ikut turun. Trade-off yang diambil sadar.

**"Pipeline jauh lebih bersih dari student".** `kata_asing` 84,3 lawan 81,5 —
student sedikit lebih baik. `inti_f1` 0,398 lawan 0,393 — praktis seri.

---

## 3. Tiga tingkat kesulitan

Semakin luas yang dibuang dari indeks, semakin mirip situasi penjual dengan
barang yang benar-benar baru.

| exclusion | `abstain%` | `harga_cakupan%` | `harga_logerr` | `inti_f1` | `kata_asing%` | `kategori_benar%` |
|---|---:|---:|---:|---:|---:|---:|
| `self` | 30,7 | 70,3 | **0,258** | **0,474** | 90,3 | **54,7** |
| **`product line`** | 56,1 | 44,5 | 0,300 | 0,405 | 85,4 | 36,4 |
| `category` | 81,3 | 18,9 | 0,409 | 0,370 | **83,7** | 0,0 |

**Degradasi tertib.** Saat kesulitan naik, sistem tidak menghasilkan jawaban
yang lebih buruk — ia makin sering **memilih diam**. Cakupan harga turun
70,3% → 44,5% → 18,9% sementara halusinasi justru ikut turun.

Klaim terlarang di deskripsi tetap **0,0% di ketiga tingkat**.

---

## 4. Ablasi ambang abstain

Ambang kemiripan visual CLIP. Di bawahnya produk dianggap asing: listing ditulis
murni dari foto, tanpa merek dan harga dari katalog.

| ambang | `abstain%` | `harga_cakupan%` | `harga_logerr` | `inti_f1` | `kata_asing%` | `panjang_patuh%` |
|---|---:|---:|---:|---:|---:|---:|
| 0,70 | 39,2 | **61,3** | 0,336 | **0,413** | 87,2 | **51,6** |
| **0,75** | 56,1 | 44,5 | 0,300 | 0,405 | 85,4 | 39,7 |
| 0,80 | 72,0 | 28,7 | **0,266** | 0,387 | **82,8** | 30,0 |

**Pertukaran murni, bukan parameter yang terbukti optimal.** Tidak ada nilai
yang mendominasi nilai lain di semua kolom: makin longgar ambangnya, makin
sering sistem menjawab dan makin sering pula ia meleset.

Bawaan 0,75 dipilih atas penilaian produk, bukan metrik: saran harga yang
meleset 30% masih berguna bagi penjual, sedangkan diam tidak berguna sama
sekali. **Tulis sebagai pilihan di laporan, bukan sebagai temuan.**

---

## 5. Ablasi pemanjang judul

Judul Tokopedia bermedian 15 kata, tapi model 4B menulis 6 kata betapapun
dimintanya. Kata tambahan diambil dari judul produk kembar di katalog — dan
sempat termasuk nama mereknya.

| title extender | `kata_asing%` | `inti_f1` | `panjang_patuh%` |
|---|---:|---:|---:|
| merek ikut ditambahkan | 85,9 | 0,408 | **41,9** |
| **merek disaring** | **85,4** | 0,405 | 39,7 |

| versi | judul yang dihasilkan |
|---|---|
| merek ikut ditambahkan | Headset Gaming Hitam Kabel Mikrofon **FANTECH** |
| merek disaring | Headset Gaming Hitam Kabel Mikrofon |

Fantech tidak pernah ada di foto — dipinjam dari judul produk tetangga.

**Catatan penting.** Dengan ukuran yang tervalidasi, ablasi ini nyaris tidak
menggeser apa pun (85,9 → 85,4). Metrik lama mencatat 10,5 → 3,6 dan terlihat
seperti perbaikan besar — itu karena menyaring merek menghilangkan **tepat apa
yang metrik lama ukur**. Perbaikan yang mengukur dirinya sendiri.

---

## 6. Cakupan disamakan — 216 produk

Pipeline menyetel harga 0 untuk barang tak dikenal, dan baris itu keluar dari
`harga_err` sepenuhnya. Di sini kedua sisi dinilai hanya pada produk yang
pipeline berani beri harga.

| system | `harga_err%` | `harga_logerr` | `harga_2x%` | `kata_asing%` |
|---|---:|---:|---:|---:|
| RAG pipeline `self` | 23,0 | **0,248** | **78,0** | 96,5 |
| **RAG pipeline `product line`** | 29,9 | 0,300 | 72,4 | 95,8 |
| RAG pipeline `category` | 35,9 | 0,350 | 67,6 | **88,7** |
| Baseline 12B | 104,1 | 0,964 | 40,5 | 99,3 |

`harga_err%` baseline melar dari 76,6 ke 104,1 di subset ini, tapi
`harga_logerr` cuma bergerak 0,788 → 0,964. Keunggulan pipeline memang sedikit
lebih besar di sini, tapi jauh lebih kecil dari yang galat relatif gambarkan —
**3,2× nyata, bukan 3,6×**.

Sebabnya: baseline tidak menaksir harga, ia memilih dari menu angka bulat
(397 tebakan hanya 34 nilai unik) sementara 54% produk berharga di bawah
Rp 50rb.

---

## 7. Model sulingan

Guru = RAG pipeline. Yang disuling **cara menulis**, bukan pengetahuan produk —
student tidak punya katalog dan tidak punya penjaga.

| system | params | input | `inti_f1` | `inti_presisi` | `kata_asing%` | `panjang_patuh%` |
|---|---:|---|---:|---:|---:|---:|
| RAG pipeline (guru) | 4B+7B | foto | **0,405** | 0,513 | 85,4 | **39,7** |
| **Student VLM** | **3B** | foto | **0,393** | **0,593** | **81,5** | 4,1 |
| Baseline 12B | 12B | foto | 0,292 | 0,376 | 99,4 | 55,4 |
| Student text | 0,5B | ketikan | 0,208 | — | 100,0 \* | 2,3 |

\* Student text tidak melihat foto sama sekali, jadi bacaan fotonya kosong dan
tiap kata otomatis terhitung asing. 100,0% berarti **"tidak bisa diukur"**,
bukan "selalu berhalusinasi".

### Student VLM 3B mengalahkan Baseline 12B

`inti_f1` 0,393 lawan 0,292, `kata_asing` 81,5 lawan 99,4 — dengan model
**empat kali lebih kecil**.

Dan ia nyaris menyamai gurunya (0,393 lawan 0,405) sambil menanggalkan katalog
28.443 produk, CLIP, dan seluruh lapisan penjaga.

### Tapi penjaga tidak ikut tersuling

Ini temuan yang lebih penting daripada angkanya. `saring_merek` dan
`pelanggaran_deskripsi` adalah **kode yang berjalan setelah model menulis** —
verifikasi, bukan gaya. Distilasi memindahkan cara menulis, tidak memindahkan
pemeriksaan.

Terlihat paling jelas di `panjang_patuh`: guru 39,7%, student 4,1%. Guru
mencapainya lewat `panjangkan_judul` yang menambahkan kata dari tetangga
katalog, dan student tidak punya tetangga.

Student juga tidak menghasilkan kategori maupun harga sama sekali — keduanya
dihasilkan kode, bukan model, jadi tidak ada yang bisa disuling.

### Sumbangan foto: pengenalan, bukan penulisan

Membelah berkas uji menurut apakah student menamai barangnya dengan benar:

| system | jenis kena | `inti` saat kena | jenis meleset | `inti` saat meleset |
|---|---:|---:|---:|---:|
| Student VLM 3B · foto | 74,5% | 0,355 | 25,5% | 0,198 |
| Student text 0,5B · ketikan | 60,3% | 0,296 | 39,7% | 0,074 |

Saat keduanya menamai barangnya benar, selisih tinggal 0,059 — bukan 0,107.
Lebih dari separuh jaraknya berasal dari salah menebak barang apa.

| produk asli | Student text | Student VLM |
|---|---|---|
| kaos "180 Degrees …", diekstrak `jenis: BROWN` | Lipstik Matte Brown Lipstick | T-Shirt Pria Polos Putih |

Keterbatasan: proksi "jenis kena" adalah kata pertama judul student muncul di
judul asli, dan itu berbagi dasar dengan `inti`, jadi nilai mutlak kelompok
"kena" agak dipompa. Perbandingan antar kedua student tetap sah.

---

## 8. Penilaian manusia

51 listing, 1 penilai, buta. Hasil lengkapnya di
[`PENILAIAN_MANUSIA.md`](PENILAIAN_MANUSIA.md).

| system | n | judul dikarang | deskripsi dikarang | kategori tepat | layak dipakai |
|---|---:|---:|---:|---:|---:|
| Baseline 12B | 17 | **3 (17,6%)** | 4 (23,5%) | **16 (94,1%)** | **8 (47,1%)** |
| RAG pipeline | 17 | 6 (35,3%) | **2 (11,8%)** | 6 (35,3%) | 5 (29,4%) |
| Student VLM 3B | 17 | 6 (35,3%) | 5 (29,4%) | 0 (0,0%) | 3 (17,6%) |

**Baseline menang di tiga dari empat kolom**, berlawanan dengan tabel otomatis.
Tiga hal membatasi apa yang boleh disimpulkan:

1. **Satu penilai** — kesepakatan antar penilai belum pernah diukur.
2. **17 listing per sistem** — selisih 35,3% lawan 17,6% itu 6 kasus lawan 3.
3. **Kategori mengukur hal lain** — baseline bebas menulis "Makeup & Perawatan
   Tubuh" untuk lip tint, sementara pipeline dipaksa ke tujuh kategori UMKM yang
   memang tidak punya wadahnya. 16 dari 51 listing dinilai "tak ada kategori
   yang cocok".

Nilai utama ronde ini bukan perbandingan sistemnya, melainkan **validasi
metrik**: tiga metrik halusinasi terbukti tidak mengukur halusinasi.

---

## 9. Garis dasar tradisional — tanpa neural sama sekali

Pertanyaannya: berapa jauh pendekatan NLP klasik bisa sampai, dengan masukan
TEKS (keterangan penjual, tanpa foto)? Pembandingnya student teks 0,5B, karena
masukannya sama.

492 produk uji yang sama. Keterangan penjual disusun dari judul asli: `jenis`
(kata dari leksikon umum), `merek` (leksikon merek), `ukuran` (regex satuan),
`kategori`.

### Judul

| metode | `inti_f1` | halusinasi | kata | latihan |
|---|---:|---:|---:|---|
| **template slot** | **0,352** | **0,0%** | 1,9 | tidak ada |
| hibrida: template + suara tetangga | 0,365 | 50,0% | 3,7 | tidak ada |
| template + bigram katalog | 0,328 | 86,7% | 5,3 | tidak ada |
| retrieval + saring keterangan | 0,248 | 93,9% | 7,6 | tidak ada |
| retrieval tetangga terdekat | 0,243 | 98,6% | 10,6 | tidak ada |
| — pembanding neural — | | | | |
| Student teks 0,5B (LoRA, teks) | 0,208 | — | — | LoRA atas 9.889 contoh |
| Baseline 12B (pakai foto) | 0,292 | — | — | — |
| Student VLM 3B (pakai foto) | 0,393 | — | — | LoRA atas 9.889 contoh |
| RAG pipeline S3 (pakai foto) | 0,405 | — | — | — |
| batas atas manusia | 0,437 | — | — | — |

Template slot — tiga slot, nol latihan, nol model — mengalahkan student 0,5B
yang dilatih atas 9.889 contoh (0,352 lawan 0,208), dan mendekati baseline 12B
yang punya akses foto.

Hibrida menaikkan `inti_f1` 0,013 dengan menukar halusinasi 0% jadi 50%.
Ditolak. Ini pengulangan temuan ablasi `panjangkan_judul` di bagian 5: kata yang
dipinjam dari tetangga menyatakan hal yang tidak ada buktinya pada produk ini.

### Deskripsi

Deskripsi asli penjual median 140 kata prosa pemasaran, jadi F1 kata terhadapnya
tidak berarti. Dua ukuran yang dipakai: `fakta_sampai` (porsi jenis/merek/ukuran
yang muncul di teks) dan `klaim_karang` (ada angka bersatuan atau merek yang
tidak ada di keterangan).

| metode | `fakta_sampai` | `klaim_karang` | kata |
|---|---:|---:|---:|
| **template berkerangka** | **1,000** | **0,0%** | 29 |
| tetangga + potong klaim asing | 0,307 | 0,2% | 44 |
| salin deskripsi tetangga | 0,445 | 81,9% | 145 |
| deskripsi ASLI penjual (acuan) | 0,713 | 66,9% | 162 |

Template menyampaikan seluruh fakta produk; penjual sendiri hanya 71%.

### Biaya

| tahap | waktu |
|---|---|
| bangun indeks TF-IDF 28k judul (sekali, CPU laptop) | 0,6 detik |
| template slot per listing | < 0,01 ms, CPU |
| RAG pipeline per listing | 2.600 ms, GPU sewa |
| Student teks 0,5B per listing | 1.570 ms, GPU sewa |
| Baseline 12B per listing | 3.800 ms, GPU sewa |

Latihan: nol detik. Tidak ada yang dilatih.

### Kebocoran yang sempat menyesatkan

Pengukuran pertama memberi retrieval `inti_f1` **0,459** — di atas pipeline
(0,405) dan bahkan di atas batas atas manusia (0,437). Sebabnya indeks memuat
produk uji itu sendiri, jadi "tetangga terdekat" adalah produknya sendiri dan
metodenya menyalin judul emas. Setelah eksklusi tingkat `product line`
diterapkan — sama seperti protokol pipeline di bagian *Index exclusion* —
angkanya jatuh ke 0,243.

**Angka 0,459 dan 0,449 tidak sah dan tidak boleh dikutip.**

### Yang harus ikut disebut

1. **Fakta diekstrak dari judul asli**, meniru apa yang diketik penjual. Adil
   terhadap student 0,5B (masukannya diturunkan dengan cara sama), tapi tidak
   adil sebagai angka mutlak — mengandaikan penjual mengetik jenis, merek, dan
   ukuran dengan tepat. Di lapangan ekstraksi ini akan meleset.
2. **Deskripsi template seragam.** Setiap listing berbunyi sama kecuali slotnya.
   `fakta_sampai` 1,000 didapat dengan mengorbankan seluruh variasi — biaya
   nyata yang tidak tertangkap metrik mana pun yang ada.
3. **Metrik deskripsi belum divalidasi manusia**, tidak seperti `kata_asing`.
   Versi pertamanya menandai 88% deskripsi asli penjual sebagai karangan (kata
   "toko" ada di leksikon merek; angka telanjang di prosa dihitung klaim).
   Sudah diperbaiki, tapi 0,0% itu belum berlabel manusia.

### Artinya untuk klaim proyek

Bukan pengganti pipeline — template tidak melihat foto, tidak menaksir harga,
dan judulnya 1,9 kata. Tapi ini bukti kedua untuk tesis yang sama dengan bagian
7: **verifikasi itu kode, bukan model.** Delapan baris aturan slot mengalahkan
LoRA 0,5B yang dilatih atas 9.889 contoh, dengan halusinasi 0% dan tanpa GPU.

---

## 10. Ringkasan klaim

| klaim | status | angka |
|---|---|---|
| harga 2,6× lebih tepat | **berdiri** | `harga_logerr` 0,300 lawan 0,788 |
| judul 1,4× lebih cocok, 91% batas atas manusia | **berdiri** | `inti_f1` 0,398 lawan 0,292; batas atas 0,437 |
| kategori selalu sah, 2/3 tepat | **berdiri** | 100% dan 65,9% lawan 0% dan 0% |
| deskripsi bebas klaim terlarang | **berdiri** | 0,0% lawan 0,5% |
| 1,4× lebih cepat per listing | **berdiri** | 1,39 lawan 1,91 detik (S3, mesin sama) |
| student 3B mengalahkan baseline 12B | **berdiri** | `inti_f1` 0,393 lawan 0,292 |
| degradasi tertib saat kesulitan naik | **berdiri** | abstain 30,7→81,3% sementara halusinasi turun |
| lebih jarang mengarang | **berdiri, tipis** | `kata_asing` 84,3 lawan 99,4 |
| judul lebih patuh panjang platform | **gugur** | 25,6% lawan 55,4% |
| "ambang 0,75 optimal" | **gugur** | pertukaran murni |
| "pipeline jauh lebih bersih dari student" | **gugur** | 84,3 lawan 81,5 — student sedikit unggul |
| ~~halusinasi merek 4× lebih jarang~~ | **gugur** | metriknya melewatkan 93% |
| ~~spesifikasi hampir tak pernah dikarang~~ | **gugur** | metriknya menangkap 0% |
| ~~deskripsi bebas kata asing~~ | **gugur** | metriknya melewatkan 91% |
| kecepatan student | **tak sah** | tumpukan penyajian berbeda |

Dua syarat yang wajib ikut disebut kalau klaim halusinasi dipakai:

1. **Presisi `kata_asing` 35%** — angka mutlaknya bukan kadar halusinasi.
2. **Student VLM sedikit lebih baik dari pipeline** di ukuran itu.

---

## 11. Yang belum dikerjakan

| pekerjaan | butuh apa |
|---|---|
| Penilaian manusia ronde 2 (50 listing, bocornya sudah ditutup) | ~20 menit penilai |
| Perbaiki label kategori — lihat [`CACAT_LABEL_KATEGORI.md`](CACAT_LABEL_KATEGORI.md) | ~1 jam tanpa GPU, atau 2,6 jam GPU kalau taksonomi ditambah |
| Jalankan ulang S3 dengan kode terkini | ~8 jam GPU laptop, ~1 jam di 4090 sewaan |
| Ukur kecepatan student di tumpukan yang sama | perbaiki konversi GGUF dulu, lihat [`OPTIMASI.md`](OPTIMASI.md) |
| Perbaiki presisi `kata_asing` dari 35% | butuh VLM sebagai hakim, dari keluarga model lain |

## Berkas sumber

```
hasil_sesi2/S3_pipeline_diri.jsonl        S3, exclusion self
hasil_sesi2/S3_pipeline_lini.jsonl        S3, exclusion product line (acuan)
hasil_sesi2/S3_pipeline_kategori.jsonl    S3, exclusion category
hasil_sesi2/S3_ambang_0.70.jsonl          ablasi ambang
hasil_sesi2/S3_ambang_0.80.jsonl          ablasi ambang
hasil_sesi2/S3_panjangkan_merek.jsonl     ablasi pemanjang judul
hasil_sesi2/S3_baseline_12b.jsonl         pembanding
hasil_sesi2/S4_bersih.jsonl               kode terkini, exclusion product line
hasil_sesi2/murid_vlm.jsonl               student VLM 3B
hasil_sesi2/murid.jsonl                   student teks 0,5B
hasil_sesi2/guru.jsonl                    9.889 label untuk distilasi
penilaian/hasil.json                      51 penilaian manusia
```

Skrip yang menghasilkan bagian 9 (jalankan dari akar proyek, tanpa GPU):

```
scripts/uji_tradisional.py                judul: template, bigram, retrieval
scripts/uji_deskripsi.py                  deskripsi: template, tetangga
scripts/uji_hibrida.py                    judul: template + suara tetangga
```
