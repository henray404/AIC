# Catatan optimasi pipeline listing

Semua angka di bawah ini hasil eksperimen terkendali: 10 produk yang sama
(`--n 10 --seed 7`), tiga platform, 30 listing per konfigurasi, dijalankan
berurutan pada mesin dan model yang sama.

Diukur dengan `scripts/eval_listing.py`. Tiap perbaikan punya sakelar sendiri,
jadi efeknya bisa dipisah — bukan disimpulkan dari perasaan.

---

## Hasil pokok

| konfigurasi | harga meleset | merek karangan (sempit) | merek (lebar) | panjang patuh | inti | detik |
|---|---|---|---|---|---|---|
| **A** semua perbaikan mati | 34,4% | 6,9% | 20,7% | 13,8% | 0,292 | 20,3 |
| B penjaga galak | 2,6% | **0,0%** | 3,3% | 80,0% | 0,393 | 18,4 |
| C tanpa hitung harga | 2,6% | 0,0% | 10,3% | 82,8% | 0,399 | 18,4 |
| D tanpa saring merek | 2,6% | **17,2%** | 27,6% | 75,9% | 0,384 | 18,5 |
| E tanpa contoh + pemanjangan | 2,6% | 0,0% | 13,8% | **20,7%** | 0,278 | 18,4 |
| **F** penjaga presisi | **2,6%** | **0,0%** | 10,0% | 76,7% | **0,403** | 18,4 |
| **G** F + frasa "merek tidak" | **2,6%** | **0,0%** | 13,3% | **80,0%** | 0,387 | 18,7 |
| **I** penjaga angka + bukti foto | **2,6%** | **0,0%** | 17,2% | 79,3% | **0,399** | **17,8** |
| **M** I + penanganan deskripsi (**final**) | **2,6%** | **0,0%** | 13,3% | **82,8%** | 0,351 | 28,6 |

Kolom `spek_karang` — ukuran dan isi yang dikarang di judul — tuntas di I:
**10,0% → 0,0%**. M menambahkan penanganan deskripsi dan jadi keadaan akhir kode;
ia membayar 11 detik per produk untuk menghabiskan klaim berisiko dan merek
karangan yang selama ini bersembunyi di deskripsi.

Dua ukuran halusinasi merek dipakai bersamaan, dan bedanya penting:

- **lebar** — kata apa pun di judul yang tidak ada di keluaran tahap 1 maupun di
  judul produk kembar.
- **sempit** — dari kata-kata itu, hanya yang benar-benar bermasalah: nama merek
  nyata milik produk lain, atau istilah langka yang tidak ada di kosakata katalog.

Ukuran lebar menghukum kata Indonesia lazim seperti "pesta" dan "jogging" yang
sebenarnya sah. Karena itu B tampak menang atas F (3,3% lawan 10,0%) padahal pada
ukuran yang benar keduanya sama-sama **0,0%** — dan F mencapainya tanpa membuang
kata sah, sehingga `inti` justru naik ke 0,403.

Median panjang judul (kata):

| konfigurasi | blibli | tokopedia | shopee |
|---|---|---|---|
| target dari data | 6–11 | 10–20 | 8–15 |
| A | 5 | 6 | 4 |
| B | 6 | 10 | 8 |

---

## Yang dipakai, cara kerjanya, dan pengaruhnya

### 1. Penjaga merek pasca-generasi — berhasil, efeknya besar

**Cara kerja.** `scripts/build_lexicon.py` memanen kamus dari katalogmu sendiri:
1.934 kandidat merek (kolom `brand` blibli + kata pembuka judul yang muncul ≥3
kali) dan 758 kata jenis barang (sering muncul **dan** tersebar di ≥4 kategori,
jadi jelas bukan merek). Setelah model menulis judul, tiap kata diperiksa: kata
jenis selalu lolos; kata spesifik hanya lolos kalau muncul di penglihatan model
atau di judul produk kembar. Sisanya dibuang.

**Pengaruh.** Halusinasi merek pada ukuran sempit **17,2% → 0,0%** (D lawan F).
Contoh tertangkap: "Fantech" masuk judul keyboard karena merek itu ada di daftar
kosakata khas platform — bukan karena terbaca di foto; juga "Altraze" pada tas
yang tak bermerek, dan "Longchamp" pada tas biasa.

**Versi pertama terlalu galak, dan itu ketahuan dari contohnya, bukan dari
angkanya.** Penjaga v1 membuang 6 kata, tapi hanya 2 yang benar-benar merek
karangan — "Pesta", "Pelembut Pakaian", dan "Jogging" ikut terbuang padahal sah.
Ia juga memotong "Merek Tidak Tertera" jadi "Gaun Floral Merek Tidak".

Versi kedua memakai tiga golongan: kata yang ada dasarnya selalu lolos; nama merek
yang dikenal wajib punya dukungan; kata Indonesia lazim (muncul di ≥20 produk)
dibiarkan; hanya istilah langka tak dikenal yang dibuang. Frasa "merek tidak
tertera" dihapus utuh. Hasilnya sama bersih pada ukuran sempit, dengan kerusakan
sampingan jauh lebih sedikit.

**Kenapa ini jalan yang benar.** Menaikkan model dari 4B ke 7B tidak menyentuh
cacat ini sama sekali (skor inti 0,483 lawan 0,468 pada 100 gambar). Larangan
lewat prompt sudah dicoba tiga putaran dan tetap bocor. Merek tercetak di kemasan
dan terdaftar di katalogmu, jadi persoalannya mencocokkan, bukan mengingat.

### 1b. Penjaga angka dan aturan bukti — spesifikasi karangan 10,0% → 0,0%

**Masalah.** Penjaga merek hanya memeriksa kata; angka lolos bebas. Model menulis
"Shampoo … 500ml", "Softergent … 200g", "… 20 Sachet" untuk foto yang tidak memuat
satu pun angka itu. Ukuran salah di judul bukan sekadar cacat mutu — pembeli bisa
menuntut penjual.

**Cara kerja.** Angka dan satuan diperlakukan lebih ketat daripada kata: **hanya
foto yang jadi bukti**, katalog tidak berlaku. Tetangga boleh 500ml sementara botol
di foto 200ml. Kode varian yang benar-benar terbaca tetap lolos (`040-15`,
`26x26cm` selamat karena angkanya ada di keluaran tahap 1).

**Dua celah lain yang ikut tertutup**, keduanya ketahuan dari membaca keluaran:

- **"ZARA" lolos ke judul gaun tanpa merek** karena merek itu ada di judul tetangga
  katalog. Aturan diubah: dukungan katalog tidak lagi mengesahkan kata langka —
  merek milik produk lain bukan bukti untuk foto ini.
- **"Gaming" ikut terbuang** karena ada toko bernama begitu sehingga kata itu masuk
  daftar merek. Diperbaiki di sumbernya: sebuah kata baru dianggap merek kalau
  ≥50% kemunculannya sebagai **kata pertama** judul. Merek berperilaku begitu; kata
  deskriptif tidak. Daftar merek menyusut 1.934 → 1.642, dan "gaming" keluar
  sementara "fantech" tetap masuk.

### 2. Gaya per platform + contoh pola sepadan — berhasil, efeknya besar

**Cara kerja.** `scripts/build_platform_profiles.py` menurunkan dari data:
panjang judul lazim, pemakaian tanda `/`, panjang deskripsi, sebaran harga per
kategori, dan kosakata khas tiap platform. Saat menulis, model diberi aturan
platform tujuan **plus dua contoh judul nyata dari platform yang sama** untuk
produk semirip mungkin, dengan angka disamarkan agar tidak tersalin. Kalau judul
masih lebih pendek dari lazimnya, kata kunci pendukung ditambahkan dari judul
produk kembar — kata yang menurut definisi sudah punya dasar.

**Pengaruh.** Kepatuhan panjang **20,7% → 80,0%** (E lawan B). Judul Tokopedia
naik dari 6 ke 10 kata, Shopee 4 ke 8. Kecocokan dengan judul asli (`inti`) ikut
naik 0,278 → 0,393.

**Catatan.** Tiga putaran perbaikan prompt sebelumnya gagal menggeser panjang
judul sama sekali. Model 4B/7B mengabaikan instruksi panjang betapapun tegasnya.
Yang berhasil justru mengerjakannya di luar model.

### 3. Harga berbasis katalog — berhasil, tapi bukan lewat jalur yang kukira

**Masalah asal.** Demo menunjukkan tetangga katalog memberi Rp22.099 (tepat), tapi
listing keluar Rp50.000 dan Rp64.155 — model memakai tengah rentang kategori.
Penyebabnya kalimat promptku sendiri: *"Pakai ini sebagai dasar perkiraan_harga"*
pada rentang platform. Kategori `lainnya` membentang Rp21rb–Rp969rb, jadi
patokan itu tidak berarti apa-apa.

**Yang dikerjakan.** Kalimat itu diubah jadi arah saja, dengan penegasan
mengutamakan harga produk kembar. Ditambah penghitung deterministik
(`harga_deterministik`) yang mengalikan harga tengah tetangga dengan faktor
platform, dikunci 0,5–2x.

**Pengaruh sebenarnya.** Setelah prompt dibetulkan, harga sudah mendarat di angka
katalog: 6 dari 9 produk keluar **persis sama** di semua konfigurasi (Rp55.100,
Rp85.000, Rp39.000, …). Penghitung deterministik **tidak memberi perbaikan yang
terukur** — konfigurasi C dengan penghitung mati tetap 2,6%. Selisih median A
lawan B pun digerakkan dua produk saja, terlalu kecil untuk diklaim.

Penghitung itu kupertahankan sebagai jaring pengaman, bukan penyumbang angka.
Klaim yang jujur: **perbaikannya datang dari membetulkan prompt**, dan buktinya
harga kini menempel ke katalog, bukan ke tengah rentang kategori.

#### Sebabnya, ditemukan belakangan: model diberi tahu jawabannya

Catatan di atas mengamati gejalanya tapi tidak menjelaskan mekanismenya.
Penyebabnya `ringkas_konteks`, yang menaruh median harga tetangga **langsung di
dalam prompt**:

    Kisaran harga pasar untuk barang serupa: Rp45.000 - Rp62.000 (tengah Rp53.470)

Model membaca "tengah Rp53.470" lalu menuliskan Rp53.500. `harga_deterministik`
kemudian menghitung median yang sama dan menimpanya dengan angka yang praktis
identik. Pada 214 baris S3 yang dinilai di platform asalnya, `perkiraan_harga`
dan `harga_model` **sama persis di 70%**.

Dua akibatnya:

1. `harga_model_err%` **bukan ukuran yang berdiri sendiri**. Ia seharusnya
   mengukur tebakan model sebelum katalog membetulkannya, tapi tebakan itu
   sudah bersumber dari katalog. Jangan dikutip sebagai bukti bahwa penghitung
   deterministik menambah nilai.
2. Menggantinya dengan tebakan model saat tetangga tidak sepadan tidak akan
   menolong — keduanya berasal dari sumber yang sama. Diuji: pada baris yang
   sebaran harga tetangganya di atas 6x, galat katalog dan galat model
   sama-sama 0,365.

Untuk benar-benar mengukur sumbangan penghitung itu, `ringkas_konteks` harus
berhenti menyebut angka harga, lalu keduanya dijalankan berdampingan. Belum
dikerjakan.

### 3b. Harga: tidak ada perbaikan murah yang tersedia

Dua cara diuji tanpa GPU pada data S3, keduanya ditolak datanya sendiri.

**Normalisasi per satuan isi.** Median tetangga menggambarkan ukuran kemasan
yang salah — keripik 250 g disandingkan tetangga 150 g dan 500 g. Diuji pada 53
produk yang punya ukuran di kedua sisi:

| aturan | \|log\| median | dalam 2x |
|---|---:|---:|
| median harga (sekarang) | 0,418 | 66,0% |
| per satuan isi | 0,442 | 62,3% |

19 membaik, 15 memburuk, 19 setara. Perbaikan besarnya nyata — tepung terigu
1 kg dari Rp150.000 jadi Rp18.000 lawan harga asli Rp17.400 — tapi kerusakannya
juga nyata, dan sumbernya bundel: "Minyak Kunci Mas 2 L Satu Dus isi 6" punya
ukuran per botol sementara harganya per dus. Tidak sepadan dengan pengurai
ukuran, konversi satuan, dan deteksi bundel yang harus dibangun.

**Menahan diri saat tetangga berselisih jauh.** Pada 216 produk bertetangga:

| aturan | cakupan | \|log\| median | dalam 2x |
|---|---:|---:|---:|
| semua (sekarang) | 100% | 0,300 | 71,8% |
| sebaran ≤ 10x | 75,9% | 0,295 | 72,6% |
| sebaran ≤ 6x | 62,0% | 0,256 | 76,9% |
| sebaran ≤ 4x | 53,2% | 0,223 | 80,0% |

Bekerja, tapi bentuknya sama dengan ambang CLIP: cakupan ditukar ketepatan,
bukan perbaikan gratis. Ambang 10x bahkan membuang 24% cakupan tanpa menambah
ketepatan sama sekali. Menambah dial kedua yang sejenis belum tentu perbaikan
desain, jadi ditinggalkan sebagai pilihan tercatat, bukan diterapkan.

### 4. Pipeline dua fase — berhasil, di sisi kecepatan

**Masalah.** VRAM 8 GB tidak muat `gemma3:4b` dan `qwen2.5:7b` sekaligus. Loop
lama memanggil keduanya bergantian tiap produk, jadi Ollama menukar bobot 20 kali
dan sebagian besar waktu habis memuat, bukan berpikir. Satu run 20 produk sempat
berjalan 25 menit dan baru selesai 5 produk.

**Cara kerja.** Dipecah dua fase: semua panggilan penglihatan dulu, baru semua
penulisan. Tiap model dimuat sekali.

**Pengaruh.** Dari sekitar **300 detik/produk jadi 18 detik**. Ini juga yang
membuat lima konfigurasi di atas bisa diuji dalam satu malam.


### 5. Penanganan pelanggaran deskripsi — tiga lapis, dipakai bersama

Metrik deskripsi baru dibuat belakangan, dan begitu ada, tiga cacat langsung
terlihat pada keluaran yang judulnya sudah bersih: klaim berisiko ("khasiat",
"ampuh") 6,9%, kata tak berdasar 20,7%, dan merek yang **sudah disaring dari judul
tetap hidup di deskripsi** ("Tas Longchamp", "teknologi altraze"). Risikonya tidak
hilang, cuma pindah tempat.

Tiga cara diuji terpisah pada 10 produk yang sama, lalu digabung:

| cara | klaim | kata tak berdasar | angka karangan | panjang | ulang judul | detik |
|---|---|---|---|---|---|---|
| tanpa penanganan | 6,9% | 20,7% | 3,4% | 112 | 0,0% | 17,8 |
| (a) buang kalimat | 0,0% | 0,0% | 0,0% | **85** | 7,4% | 26,4 |
| (b) tulis ulang | 0,0% | 6,9% | 3,4% | 127 | 0,0% | 24,9 |
| (c) larangan prompt | 3,3% | 20,0% | 0,0% | 122 | 0,0% | 21,5 |
| **kombinasi (bawaan)** | **0,0%** | **0,0%** | **0,0%** | **123** | **0,0%** | 28,6 |

Masing-masing punya kelemahan sendiri. (a) menjamin bersih tapi memangkas isi —
satu kata "khasiat" membuang seluruh kalimatnya, dan 7,4% deskripsi berakhir cuma
mengulang judul. (b) mempertahankan isi tapi menyisakan 6,9% kata tak berdasar.
(c) paling murah, menghabiskan angka karangan, tapi **tidak menggeser kata tak
berdasar sama sekali** — melarang daftar kata tidak mencegah model mengarang merek.

Kombinasi memakai ketiganya bertingkat: larangan di prompt lebih dulu, lalu tulis
ulang untuk yang lolos, lalu buang kalimat kalau tulisan ulangnya masih melanggar.
Hasilnya jaminan mutlak seperti (a) dengan panjang isi seperti (b).

Dari 29 deskripsi: **24% perlu ditulis ulang, dan 10% masih melanggar setelah itu**
sehingga kalimatnya dibuang. Lapis ketiga bukan hiasan — model kecil mengulang
pelanggaran yang sama sepertiga waktunya.

---

## Dasar metodenya

- **RAG few-shot dari katalog sendiri.** Mengambil contoh sepadan dari katalog
  lalu memakainya sebagai few-shot terbukti menaikkan mutu keluaran e-commerce;
  penelitian Amazon melaporkan kenaikan chrF sampai 15,3% pada terjemahan judul
  produk untuk bahasa yang modelnya lemah.
- **Verifikasi eksternal untuk menekan halusinasi.** Literatur mitigasi halusinasi
  VLM memakai alat luar (OCR, pendeteksi objek) dan verifier saat atau sesudah
  decoding untuk mengoreksi bagian yang tidak ada dasarnya. Kamus merek di sini
  memainkan peran yang sama, hanya jauh lebih murah.

## Batas yang harus diketahui

1. **Sampel kecil.** 10 produk, 30 listing per konfigurasi. Cukup untuk efek besar
   (merek, panjang judul), tidak cukup untuk efek kecil (harga, `spek_karang`).
2. **Metrik hanya menguji konsistensi internal.** "Merek karangan" diukur terhadap
   keluaran tahap 1 dan katalog — bukan terhadap isi foto. Kalau tahap penglihatan
   salah baca, metrik ini tidak akan tahu. Untuk itu perlu penilaian manusia.
5. **Metrik bisa menyesatkan kalau definisinya sama dengan definisi penjaganya.**
   Ukuran lebar memberi nilai lebih baik kepada penjaga yang lebih galak, karena
   keduanya memakai definisi "tak berdasar" yang sama. Ketahuan hanya setelah
   keluarannya dibaca satu per satu. Selalu periksa contoh, jangan percaya tabel.
3. **Kategori masih lemah.** Semua sebaran harga bersandar pada `kategori_umkm`
   yang 37,8% jatuh ke `lainnya`.
4. **Kesalahan yang tersisa nyata.** Gaun Eprise asli Rp479.800 disarankan
   Rp82rb–176rb karena tetangganya gaun murah; sepatu Zedruz Rp116.899 disarankan
   Rp75.000. Pencarian berbasis teks tidak bisa membedakan kelas harga dalam satu
   jenis barang.

## Langkah berikutnya yang paling menjanjikan

1. **Pencarian berbasis kemiripan gambar (CLIP).** Kesalahan harga tersisa berasal
   dari tetangga yang jenisnya benar tapi kelasnya beda. Kemiripan visual bisa
   memisahkan gaun premium dari gaun pasar; pencarian teks tidak bisa.
2. **Perbaiki `kategori_umkm`.** Semua saran harga bertumpu di atasnya.
3. **Uji dengan mata manusia**, 50–100 listing, untuk hal yang tidak bisa ditangkap
   metrik otomatis.

## Cara mengulang

```powershell
python scripts/build_platform_profiles.py
python scripts/build_lexicon.py
python scripts/retrieve_pipeline.py --n 10 --platform all --iris 0:5  --panjangkan --keluaran data_drive/eval/B.jsonl
python scripts/retrieve_pipeline.py --n 10 --platform all --iris 5:10 --panjangkan --keluaran data_drive/eval/B.jsonl
python scripts/eval_listing.py data_drive/eval/A.jsonl data_drive/eval/B.jsonl
```

`--iris` memecah satu sampel jadi beberapa jalan tanpa mengubah isinya: seed sama,
urutan sama, jadi potongan `0:5` selalu produk yang sama.

---

# Sesi 1 — pembanding model besar, 100 produk

Dijalankan 21 Agustus 2026 pada GPU sewaan (RTX 4090, 24 GB). Sampel sama untuk
kedua sisi: `--n 100 --seed 7`, sumber dan penyaringan identik, jadi `product_id`
cocok satu-satu. Baseline `gemma3:12b` sendirian tanpa retrieval, tanpa katalog,
tanpa penjaga — tepat 3× parameter `gemma3:4b` yang dipakai pipeline, satu
keluarga model supaya selisihnya berasal dari ukuran, bukan dari data latih.

Bagian ini menggantikan angka mana pun di atas yang bertentangan dengannya:
tabel A–M dijalankan pada 10 produk dan tanpa penyamaan cakupan.

## Tiga cacat pengukuran yang ditemukan lebih dulu

Ketiganya berpihak pada pipeline. Semuanya ditemukan dengan membaca kode
penilaian, bukan dari tabelnya — tabel yang salah tidak terlihat salah.

1. **Baseline dinilai tanpa bukti penglihatan.** `baseline_besar.py` menulis
   `vlm: ""`, dan `eval_listing.py` menghitung karangan sebagai
   `kata(judul) - kata(vlm) - kata(tetangga)`. Bukti kosong membuat seluruh kata
   judul terhitung karangan; baseline akan mencatat halusinasi 100% karena satu
   kolom kosong, bukan karena mutunya. Diperbaiki `patch_baseline_vlm.py`, yang
   menyalin bacaan penglihatan dari berkas pipeline lewat `product_id`.

2. **Cakupan tidak sama.** Pipeline menyetel `perkiraan_harga = 0` untuk barang
   tak dikenal, dan baris itu keluar dari `harga_err`. Pada tingkat `lini`,
   71 dari 100 produk berstatus `dikenal: false` — galat harga diukur di 29
   produk termudah sementara baseline menjawab semuanya. Ditambahkan
   `harga_cakupan%` dan `--samakan-cakupan`.

3. **Satuan waktu berbeda.** `detik` dicatat per produk, tapi pipeline menulis
   2 platform dan baseline 3. Ditambahkan `detik_listing`.

## Hasil, cakupan disamakan ke tingkat `lini` (29 produk)

| | merek_ketat% | harga_err% | inti | panjang_patuh% | detik_listing |
|---|---|---|---|---|---|
| pipeline (merek tetangga disaring) | **8,6** | **33,1** | **0,410** | 79,3 | **1,43** |
| pipeline (perilaku lama) | 17,2 | 33,1 | 0,407 | 82,8 | 1,35 |
| baseline gemma3:12b | 11,5 | 53,3 | 0,229 | 51,7 | 2,12 |

`merek_ketat%` adalah satu-satunya ukuran halusinasi yang setara: hanya bacaan
penglihatan yang memaafkan, katalog tidak — dan katalog cuma dipunyai pipeline.

**`merek_sempit%` 0% tidak boleh dikutip sebagai bukti.** Angka itu melingkar:
`saring_merek` membuang kata yang tidak didukung `fakta` atau `tetangga`, dan
`merek_sempit` mengukur kata yang tidak didukung `fakta` atau `tetangga`. Nolnya
dijamin konstruksi.

## Apa yang berdiri dan apa yang gugur

| klaim | status |
|---|---|
| harga ~1,6× lebih akurat | berdiri — 33,1% lawan 53,3% pada 29 produk yang sama |
| ~1,5× lebih cepat per listing | berdiri — 1,43 lawan 2,12 detik |
| judul lebih cocok produk aslinya | berdiri — inti 0,410 lawan 0,229 |
| ~~deskripsi bebas kata asing~~ | **gugur** — metriknya (`desc_ungrounded%`) melewatkan 91% halusinasi |
| ~~"hampir tanpa halusinasi merek"~~ | **gugur** — metriknya melewatkan 93% |
| unggul 2,4× kecepatan | **gugur** — itu detik per produk atas jumlah platform berbeda |

> **Catatan belakangan.** Kedua klaim halusinasi di atas gugur setelah
> penilaian manusia pada 51 listing (23 Agustus 2026). `desc_ungrounded%` dan
> `brand_strict%` hanya mencari nama merek dan istilah langka, sehingga
> melewatkan warna, aroma, rasa, dan sifat produk — kata Indonesia lazim yang
> justru paling sering dikarang. Penggantinya `ungrounded_words%` mencatat
> selisih yang jauh lebih kecil. Lihat
> [`PENILAIAN_MANUSIA.md`](PENILAIAN_MANUSIA.md).

## Ablasi: memanjangkan judul menyelundupkan merek

`panjangkan_judul` menambah kata dari judul produk kembar sampai judul mencapai
panjang lazim platform. Docstring-nya dulu mengklaim itu tidak menambah risiko
halusinasi "karena sudah didukung bukti". Didukung katalog, bukan didukung foto.

Kandidatnya termasuk nama merek, dan merek tetangga selalu milik produk lain:

    sebelum : Headset Gaming Hitam Kabel Mikrofon FANTECH
    sesudah : Headset Gaming Hitam Kabel Mikrofon

Menyaring merek dari kandidat menurunkan `merek_ketat%` dari 17,2% ke 8,6%,
dengan ongkos 3,5 poin `panjang_patuh%`. `harga_err%` dan `inti` tidak bergerak,
sesuai dugaan — penyaringan hanya menyentuh pemilihan kata di judul.

Efek ini tak terlihat sama sekali tanpa penyamaan cakupan (5,0% lawan 9,0%),
karena 71 dari 100 produk tidak punya tetangga, jadi tidak ada yang bisa dipinjam.

## Penarikan diri, dan harganya

`dikenal: false` per tingkat eksklusi:

| tingkat | mengaku asing | cakupan harga |
|---|---|---|
| diri | 48/100 | 52,6% |
| lini | 71/100 | 28,9% |
| kategori | 89/100 | 11,3% |

Pada tingkat `lini` sistem tidak memberi angka harga untuk 71% produk. Itu
perilaku yang disengaja — tanpa padanan katalog tidak ada dasar menyebut harga —
tapi harus dilaporkan sebagai angka utama, bukan catatan kaki. Sistem yang benar
28,9% dari waktu dan diam sisanya bukan sistem yang benar 71,1% dari waktu.

Ambang visualnya 0,80 dan belum pernah diuji tandingannya. Ablasi 0,70 / 0,75 /
0,80 akan memperlihatkan berapa cakupan yang bisa ditebus dengan berapa ketepatan.

## Yang belum dikerjakan

1. **Uji mata manusia.** Semua di atas otomatis. `merek_ketat%` memihak pipeline
   secara struktural: bacaan penglihatan dipakai sebagai bukti untuk kedua sisi,
   padahal pipeline menulis dari teks itu sementara baseline menulis dari fotonya.
   Kata baseline bisa benar-benar terlihat di foto namun absen dari bacaan, dan
   tetap dihukum. Hanya manusia yang bisa menutup celah ini.
2. **Ablasi ambang visual.**
3. **Distilasi.** Guru = pipeline, murid = satu model kecil. Belum dimulai.

## Cara mengulang sesi 1

```bash
bash sesi1.sh                                   # 3 tingkat eksklusi + baseline
python scripts/patch_baseline_vlm.py \
    --baseline data_drive/eval/S1_baseline_12b.jsonl \
    --sumber   data_drive/eval/S1_pipeline_diri.jsonl
python scripts/eval_listing.py data_drive/eval/S1_*.jsonl \
    --samakan-cakupan data_drive/eval/S1_pipeline_lini.jsonl
```

---

# Sesi 1 lanjutan — ambang, N=500, dan dua murid sulingan

## Ambang visual: 0,80 kalah oleh 0,75

Ambang 0,80 dipilih di awal tanpa tandingan. Diuji, ia kalah:

| ambang | cakupan harga | harga_err% | merek_ketat% | inti | panjang_patuh% |
|---|---|---|---|---|---|
| 0,70 | 63,9% | 37,8 | 7,5 | **0,405** | **50,0** |
| **0,75** | **44,3%** | **30,5** | 3,5 | 0,377 | 41,5 |
| 0,80 | 28,9% | 33,1 | **2,5** | 0,343 | 30,5 |

0,75 menambah cakupan 53% relatif sambil **menurunkan** galat harga. Ongkosnya
`merek_ketat` 2,5 → 3,5. Turun lagi ke 0,70 baru mahal: galat harga naik ke 37,8
dan karangan merek melipat dua.

Bawaannya diubah ke 0,75. Kelemahan terbesar laporan sesi 1 — "sistem diam di
71% kasus" — separuhnya hilang hanya dengan menggeser satu angka.

## N=500: keunggulan tumbuh, bukan menyusut

Cakupan disamakan ke pipeline (126 produk, 252 listing tiap sisi):

| | N=100 pipeline : baseline | N=500 pipeline : baseline |
|---|---|---|
| harga_err% | 33,1 : 53,3 | **29,4 : 75,3** |
| spek_karang% | 4,5 : 24,5 | **0,0 : 18,3** |
| merek_ketat% | 5,0 : 9,5 | 12,3 : 16,3 |
| inti | 0,343 : 0,229 | **0,423 : 0,213** |
| panjang_patuh% | 30,5 : 51,5 | **72,2 : 53,6** |
| desk_asing% | 0,0 : 24,7 | 0,0 : 33,7 |
| detik_listing | 1,48 : 2,15 | 1,38 : 1,90 |

Pipeline bertahan; baseline **memburuk tajam** (53,3 → 75,3). Sampel lebih besar
berarti produk lebih beragam, dan model besar tanpa katalog makin sering meleset.
`panjang_patuh` bahkan berbalik arah.

N=500 menggantikan N=100 sebagai angka utama: galat harga di sana diukur pada
125 produk, bukan 28.

## Empat tingkat

| tingkat | model | masuk | inti | merek_ketat% | desk_asing% | detik_listing |
|---|---|---|---|---|---|---|
| baseline | gemma3:12b | foto | 0,25 | 9,0 | 24,7 | 2,15 |
| pipeline | 4B+7B+CLIP+indeks | foto | **0,343** | **2,5** | **0,0** | **1,48** |
| murid VLM | 3B | foto | 0,315 | 11,4 | 8,7 | 2,77 |
| murid teks | 0,5B | ketikan | 0,208 | 19,2 *(tak berarti)* | 16,1 | 1,58 |

**Penjaga itu kode, bukan gaya.** Murid VLM mendekati `inti` pipeline (0,315
lawan 0,343) tapi `merek_ketat`-nya 11,4% — lebih buruk dari baseline 9,0%, dan
`desk_asing` kembali dari 0,0% ke 8,7%. `saring_merek` dan `pelanggaran_deskripsi`
berjalan **setelah** model menulis; distilasi memindahkan cara menulis, tidak
memindahkan pemeriksaan.

Itu bukti positif, bukan kegagalan: jaminan nol milik pipeline berasal dari
verifikasi eksternal, bukan dari bobot model. Menanggalkan perkakasnya
mengembalikan halusinasi, persis seperti yang diramalkan kalau penyebabnya
memang penjaga. Dan penjaga itu bisa dipasang ke murid — `saring_merek` cuma
butuh leksikon, bukan katalog.

## Kecepatan murid: klaimnya gugur, dan sebabnya bukan modelnya

`detik_listing` murid VLM 2,77 — paling lambat dari keempatnya. Tapi yang
dibandingkan bukan model:

    pipeline & baseline : Ollama / llama.cpp, Q4_K_M, KV-cache matang
    kedua murid         : HF transformers, bf16, generate() satu-satu

3B bf16 lewat `generate()` lawan 12B Q4 lewat llama.cpp mengukur tumpukan
penyajian, bukan ukuran model. Klaim kecepatan untuk tingkat murid **tidak
berdiri** sampai keduanya disajikan sama.

Percobaan menyamakannya gagal: penggabungan LoRA terverifikasi benar lewat HF
(keluaran koheren), tapi setelah `ollama create` ke GGUF Q4_K_M keluarannya
rusak — "?????" berulang di semua variasi prompt. Laju mentahnya terukur 0,526
detik/listing, tapi angka itu **tidak dipakai**: tidak terverifikasi berasal dari
model yang menghasilkan listing benar.

### Akar bug "?????": tokenizer transformers 5.x lawan konverter tua

Percobaan kedua tidak sempat menuntaskan uji korektnes — `convert_hf_to_gguf.py`
berhasil menghasilkan GGUF F16 994 MB dalam semenit, tapi membangun `llama-cli`
dari sumber baru sampai 76% saat batas waktu habis, jadi F16-nya tidak pernah
diuji. Yang justru berharga muncul di tengah jalan:
`pip install -r requirements-convert_hf_to_gguf.txt` menurunkan transformers dari
5.15.1 ke 4.57.6, dan versi lama itu **crash** membaca `extra_special_tokens`
karena bentuknya list, bukan dict.

Isi `murid_lora/tokenizer_config.json` memastikan pergeserannya nyata:

    extra_special_tokens : ['<|im_start|>', '<|im_end|>', ...]   list, bukan dict
    added_tokens_decoder : TIDAK ADA
    kunci lain           : backend, is_local, local_files_only  (bawaan 5.x)

`added_tokens_decoder` itu tempat transformers 4.x menyimpan pemetaan id → token
khusus, dan di berkas ini tidak ada sama sekali. Ollama membundel konverter dari
galur llama.cpp yang lebih tua; diberi tata letak 5.x ia tidak crash seperti
skrip di atas — ia gagal diam-diam, kehilangan token khusus, lalu tiap token
keluar sebagai `?`.

Dugaan awal bahwa `vocab.json` dan `merges.txt` hilang **salah**. Keduanya memang
tidak ada, tapi itu normal: `tokenizer.json` sudah membawa seluruh kosakata.
Masalahnya versi format, bukan berkas yang kurang.

Menuntaskannya tidak butuh GPU sama sekali:

1. gabung LoRA ke bobot dasar
2. **salin tokenizer dari repo `Qwen2.5-0.5B-Instruct` asli**, jangan pakai yang
   tersimpan di `murid_lora/` — langkah ini melewati seluruh masalah format
3. `convert_hf_to_gguf.py` (~1 menit, sudah terbukti jalan)
4. bangun `llama.cpp` (~30 menit CPU, sekali seumur hidup)
5. ukur detik/listing, lalu bandingkan pada kuantisasi yang sama dengan pipeline

## Apa yang disumbang foto: mengenali benda, bukan menulis

Membelah berkas uji menurut apakah muridnya menamai barangnya dengan benar:

| | jenis kena | inti | jenis meleset | inti |
|---|---|---|---|---|
| murid teks | 60,3% | 0,296 | 39,7% | 0,074 |
| murid VLM | 74,5% | 0,355 | 25,5% | 0,198 |

Saat keduanya menamai barangnya dengan benar, selisihnya tinggal 0,059 — bukan
0,107. Lebih dari separuh jaraknya berasal dari murid teks lebih sering salah
menebak barang apa.

Jadi sumbangan foto adalah **pengenalan**, bukan penulisan. Contohnya konkret:
kaos "180 Degrees ..." diekstrak sebagai `jenis: BROWN` karena "brown" kebetulan
ada di kosakata umum dan muncul lebih dulu; murid teks menulis "Lipstik Matte
Brown Lipstick", murid VLM melihat fotonya dan menulis "T-Shirt Pria Polos Putih".

Implikasinya: memperbaiki ekstraktor `jenis` menutup sebagian besar jarak tanpa
perlu foto. Ekstraktor itu heuristik posisi yang sudah ditandai `ponytail:` di
`build_text_pairs.py`.

Keterbatasan ukuran ini: proksi "jenis kena" adalah kata pertama judul murid
muncul di judul asli, dan itu berbagi dasar dengan `inti`, jadi nilai mutlak
kelompok "kena" agak dipompa. Perbandingan antar kedua murid tetap sah karena
keduanya diukur dengan proksi yang sama.

## Sisa pekerjaan

1. **Uji mata manusia.** Belum dikerjakan sama sekali, dan `merek_ketat%` masih
   memihak pipeline secara struktural.
2. **Pasang penjaga di murid VLM.** `saring_merek` butuh leksikon saja.
   Kemungkinan menurunkan `merek_ketat` 11,4% mendekati nol tanpa melatih ulang.
3. **Perbaiki ekstraktor `jenis`.**
4. **Samakan tumpukan penyajian** sebelum klaim kecepatan murid dipakai.
   Akar bugnya sudah diketahui (tokenizer transformers 5.x lawan konverter tua)
   dan langkahnya tidak butuh GPU — lihat bagian di atas.
