# LAPAKIN

**Nama Kelompok:** `[NAMA TIM]`
**Nama Inovasi:** LAPAKIN — Auto-Listing dan Rekomendasi Harga Jual untuk UMKM E-Commerce
**Kompetisi:** AI Innovation Challenge, COMPFEST 18 (2026)
**Tema:** AI for the Backbone of the Economy
**Area:** Smart Commerce (Toko & Pasar)

LAPAKIN menerima satu foto produk dan satu nilai Harga Pokok Penjualan, lalu mengembalikan judul, deskripsi, kategori, dan rentang harga jual yang sudah memperhitungkan komisi platform, biaya pemrosesan, dan pajak UMKM. Bagian yang menuntut persepsi dikerjakan model AI. Bagian yang menuntut kepastian aritmetika dikerjakan mesin hitung deterministik yang menyajikan rincian tiap komponen biaya, sehingga penjual dapat memeriksa asal setiap angka.

---

## DAFTAR ISI

1. Latar Belakang
2. Tujuan dan Manfaat Pengembangan
3. Metodologi
   3.1 Alur Memperoleh Dataset
   3.2 Alur Pengembangan Model per Fitur
   3.3 Alur Integrasi Model ke Environment Kode
4. Metode Lain yang Mendasari Pengambilan Keputusan
5. Batasan dan Keterbatasan
6. Kesimpulan

Daftar Pustaka · Lampiran

---

# 1. LATAR BELAKANG

Usaha Mikro, Kecil, dan Menengah menopang sebagian besar perekonomian Indonesia. Kementerian Koordinator Bidang Perekonomian mencatat 64,2 juta pelaku UMKM yang menyumbang 61,07% Produk Domestik Bruto dan menyerap sekitar 97% tenaga kerja nasional [1]. Badan Pusat Statistik mencatat 3,82 juta usaha e-commerce di 38 provinsi per akhir 2023, dengan mayoritas pelaku berasal dari kelompok usaha mikro [2].

Angka itu menyembunyikan satu masalah operasional pada titik terakhir rantai nilai, yaitu saat barang berpindah ke tangan konsumen. Seorang penjual yang baru membuka lapak menghadapi formulir kosong: kolom judul, kolom deskripsi, pilihan kategori, dan kolom harga. Keempatnya menentukan apakah produk muncul di hasil pencarian dan apakah pembeli menekan tombol beli. Penjual pemula mengisinya dengan menebak.

Kolom harga paling mahal kesalahannya. Penjual mengetahui modalnya, misalnya Rp25.000 per bungkus keripik, tetapi tidak mengetahui berapa yang dipotong marketplace. Tokopedia memungut komisi 3% sampai 8,5% bergantung kategori ditambah biaya pemrosesan Rp1.250 per pesanan. Shopee memungut biaya administrasi 4,25% sampai 12% ditambah program Gratis Ongkir XTRA 4% sampai 9%. Blibli memungut 4,25% sampai 10%. Di atas itu berlaku PPh Final UMKM 0,5% dari peredaran bruto, meskipun Peraturan Pemerintah Nomor 20 Tahun 2026 membebaskan omzet Rp500 juta pertama dalam satu tahun pajak bagi Wajib Pajak Orang Pribadi [3]. Penjual yang menetapkan harga dari modal ditambah persentase untung sering menemukan marginnya habis setelah seluruh potongan itu bekerja.

Kesalahan berjalan ke dua arah. Harga terlalu rendah membuat penjual menanggung rugi pada setiap transaksi tanpa menyadarinya. Harga terlalu tinggi membuat produk tidak pernah terjual. Literatur penetapan harga pada UKM menunjuk akar persoalannya: metode *cost-plus* menetapkan harga dari biaya produksi tanpa memperhitungkan nilai yang bersedia dibayar pembeli, sehingga berisiko menghasilkan harga di atas atau di bawah pasar [4].

## 1.1 Mengapa sekarang

Tiga perubahan membuat persoalan ini layak dikerjakan pada 2026.

**Aturan biaya berubah dalam satu tahun terakhir.** Peraturan Pemerintah Nomor 20 Tahun 2026 mempertahankan tarif PPh Final 0,5% dan membebaskan omzet Rp500 juta pertama [3]. Tokopedia menerapkan komisi dinamis per 18 Mei 2026 dan menurunkan batas atas biaya menjadi Rp80.000 per item pada Juli 2026, sementara Shopee memperbarui biaya administrasi per 2 Mei 2026. Penjual yang menghitung margin memakai angka tahun sebelumnya akan salah.

**Perangkatnya baru terjangkau.** Model *vision-language* 4 miliar parameter yang berjalan pada satu kartu grafis 8 GB baru tersedia sebagai *open-weights* dalam dua tahun terakhir [5]. Sebelum itu, pipeline seperti LAPAKIN menuntut API berbayar per gambar — biaya yang tidak masuk akal bagi penjual dengan omzet di bawah Rp500 juta.

**Perubahan tarif menuntut arsitektur yang bisa diperbarui tanpa melatih ulang.** Memperbarui komisi platform pada LAPAKIN berarti mengubah satu berkas konfigurasi, bukan menjalankan ulang pelatihan.

## 1.2 Celah terhadap pekerjaan yang sudah ada

| Sudut | Yang sudah ada | Yang belum dijawab |
|---|---|---|
| Digitalisasi UMKM | Kajian berhenti pada tingkat kebijakan dan literasi: berapa UMKM yang terhubung platform, program apa yang mempercepat | Tidak ada alat yang bekerja pada satu produk milik satu penjual, pada menit pertama ia mengisi formulir |
| VLM/LLM *open-weights* | Laporan teknis Gemma 3 [5] dan Qwen2.5 [6] melaporkan kinerja pada tolok ukur umum | Tidak menjawab apakah model 4B dan 7B cukup untuk menulis listing marketplace berbahasa Indonesia yang patuh gaya tiap platform |
| Halusinasi VLM | Survei Liu dkk. [7] meninjau mitigasi yang menyasar data pelatihan dan komponen model | Seluruhnya bekerja *di dalam* model, menuntut akses bobot dan komputasi besar |
| RAG untuk e-commerce | Zhang dkk. [10] mengambil contoh dwibahasa dari katalog untuk *few-shot* penerjemahan judul, chrF naik hingga 15,3% | Menerjemahkan judul yang **sudah ada**; tidak tersedia teks sumber bila judul harus disusun dari foto |
| Koridor harga UKM | Stromeyer dan Kurz [4] menetapkan batas bawah dari biaya produksi dan batas atas dari survei persepsi pelanggan | Menargetkan UKM barang modal: transaksi sedikit bernilai besar. UMKM marketplace sebaliknya, dan persepsi pelanggan tidak dapat disurvei per produk |

LAPAKIN mengisi celah tersebut dengan tiga keputusan: kueri temu kembali dibangkitkan lebih dulu oleh tahap penglihatan sehingga judul dapat disusun tanpa teks sumber; halusinasi ditekan melalui verifikasi *pasca-generasi* terhadap katalog dengan biaya komputasi mendekati nol; dan koridor harga memakai titik impas setelah komisi dan pajak sebagai batas bawah, serta persentil harga produk sejenis pada katalog sebagai batas atas.

---

# 2. TUJUAN DAN MANFAAT PENGEMBANGAN

## 2.1 Tujuan

1. Membangun pipeline *auto-listing* dua tahap yang memakai `gemma3:4b` untuk ekstraksi fakta visual dan `qwen2.5:7b` untuk penyusunan teks, dilengkapi penjaga pasca-generasi yang menolak merek dan angka tanpa dasar pada foto.
2. Membangun indeks TF-IDF atas 28.443 produk marketplace yang menghasilkan produk pembanding, kosakata khas platform, dan sebaran harga kategori pada saat inferensi.
3. Membangun mesin penetapan harga *Market-First* yang menghitung titik impas dari HPP, komisi platform, biaya pemrosesan, dan PPh Final, lalu menempatkannya terhadap persentil harga pasar untuk menghasilkan harga rekomendasi beserta rinciannya.
4. Mengukur setiap komponen melalui ablasi terkendali, dan melaporkan komponen yang tidak memberi perbaikan terukur beserta komponen yang memberi.

## 2.2 Manfaat

| Penerima | Manfaat |
|---|---|
| Penjual UMKM | Memangkas waktu pengisian formulir listing; menunjukkan batas harga terendah yang masih menghasilkan laba, lengkap dengan rincian potongan platform dan pajak yang dapat diperiksa baris demi baris |
| Ekosistem Smart Commerce | Menurunkan hambatan masuk pada titik terakhir rantai nilai, tempat produk UMKM bertemu konsumen digital |
| Peneliti | Studi kasus terukur tentang pemisahan tugas persepsi dan tugas aritmetika, termasuk ablasi yang menunjukkan komponen mana yang benar-benar menyumbang perbaikan |
| Pengembang sistem serupa | Kamus merek dan profil gaya platform diturunkan dari katalog secara otomatis, sehingga metode yang sama dapat dipindahkan ke katalog lain tanpa anotasi manual |

---

# 3. METODOLOGI

## 3.1 Alur Memperoleh Dataset

### 3.1.1 Sumber dan penggabungan

Katalog rujukan menggabungkan tiga sumber: 8.800 produk Blibli, 18.443 produk Tokopedia, dan 1.200 produk dari dataset Tokopedia 2025 — seluruhnya **28.443 baris dengan 25 kolom**. Hasil penggabungan diverifikasi baris demi baris terhadap ekspor sumbernya, dengan hasil nol baris hilang dan nol perubahan pada kolom judul, harga, deskripsi, kategori, maupun gambar.

Dari katalog itu diturunkan **27.997 pasangan latih** gambar → judul bersih melalui `scripts/build_train_pairs.py`. Targetnya judul yang sudah dibersihkan, bukan deskripsi: judul memuat jenis produk, merek, varian, dan ukuran — hampir semuanya terlihat pada foto, sedangkan deskripsi penuh spesifikasi yang tidak terlihat seperti berat kirim, garansi, dan isi karton.

### 3.1.2 Prosedur pengambilan

Pengumpulan Tokopedia berjalan dua tahap, dan urutannya wajib. Tahap pertama mengambil daftar produk dari hasil pencarian. Tahap kedua mengambil deskripsi lengkap dan galeri gambar dari halaman produk. Alasannya teknis: URL *thumbnail* dari hasil pencarian memakai tanda tangan yang kedaluwarsa dalam hitungan jam, sedangkan URL galeri dari halaman produk tidak bertanda tangan.

Setiap *response* mentah disimpan sebelum diparse. Konsekuensinya, perbaikan parser tidak pernah menuntut pengumpulan ulang — cukup `python main.py reparse`.

### 3.1.3 Batas dan etika pengambilan

Pengumpulan dijalankan dengan *concurrency* 1, jeda acak 2 sampai 5 detik antar-*request*, dan pemutus arus yang menghentikan proses setelah sepuluh kegagalan beruntun. Sistem tidak memuat pemecah CAPTCHA. Dataset tidak diredistribusikan dan setiap baris menyimpan URL sumbernya.

### 3.1.4 Karakter dan cacat dataset

Tahap pertama pengumpulan Tokopedia menghasilkan 18.997 produk unik dari 221 *request* dalam sekitar 21 menit tanpa satu pun galat, berasal dari 8.695 toko berbeda dengan toko terbesar menyumbang 0,61% dataset. Tahap kedua pada sampel 602 produk menghasilkan deskripsi teks untuk 96,7% produk dengan median 988 karakter, pada laju sekitar 3,5 detik per produk. Dari 28.443 baris gabungan, 28.093 (98,8%) memiliki minimal satu berkas gambar lokal yang sudah diverifikasi keberadaannya.

Enam temuan berikut muncul setelah data terkumpul, dan seluruhnya membatasi cara dataset boleh dipakai.

| Temuan | Angka | Konsekuensi |
|---|---|---|
| Gambar Tokopedia 2025 hilang | 9.614 berkas; 311 dari 1.200 produk tanpa gambar | Sumber tidak menyimpan URL CDN, tidak dapat diunduh ulang |
| Label kategori lemah | 37,8% `lainnya`; 55,2% hasil pencocokan kata kunci | Seluruh sebaran harga per kategori mewarisi kelemahan ini |
| Nomor telepon pada deskripsi | 4,3% baris | Data pribadi, wajib dibuang sebelum pemakaian apa pun |
| Deskripsi bukan teks jualan | 33,6% memuat ALL CAPS panjang; 20,9% membahas ongkir dan pengemasan | Perlu penyaringan sebelum dipakai sebagai contoh gaya |
| Duplikasi | 2.228 baris berjudul kembar; 4.280 baris berdeskripsi identik | Pemisahan *train* dan *test* wajib per grup, bukan acak |
| Ketimpangan sumber dan kategori | Tokopedia 65% baris; `fashion_perawatan` 7.566 lawan `minuman_herbal` 1.796 | Rujukan harga lebih kuat pada kategori besar |

Ditemukan pula 632 harga yang tidak masuk akal (3,3%), misalnya kaos seharga Rp1.999.960.000. *Response* mentahnya memang memuat angka tersebut, sehingga ini bukan kegagalan parser melainkan kesalahan ketik penjual. Notebook `03_eda_dataset.ipynb` mendeteksinya per kategori memakai *Median Absolute Deviation* pada logaritma harga.

## 3.2 Alur Pengembangan Model per Fitur

Sistem terdiri atas empat fitur. Ketiganya yang pertama memakai model AI; yang keempat sengaja tidak.

```
Foto produk
   │
   ├─► Fitur 1: Ekstraksi fakta visual (gemma3:4b)
   │      keluaran: fakta yang terlihat pada foto
   │
   ├─► Fitur 2: Temu kembali katalog (TF-IDF, 28.443 produk)
   │      keluaran: produk pembanding, kosakata platform,
   │               sebaran harga kategori (P25, median, P75)
   │
   ├─► Fitur 3: Penyusunan listing + penjaga bukti (qwen2.5:7b)
   │      keluaran: judul, deskripsi, kategori per platform
   │
   └─► Fitur 4: Penetapan harga Market-First (deterministik)
          masukan: HPP penjual, platform tujuan, sebaran harga
          keluaran: titik impas, zona, harga rekomendasi, rincian
```

### 3.2.1 Fitur 1 — Ekstraksi fakta visual

**Pertanyaan yang dijawab lebih dulu.** Sebelum memilih model, `scripts/probe_vlm_baseline.py` dijalankan untuk menguji apakah model dasar sudah mampu menyebut bendanya dengan benar. Dua model dibandingkan pada 100 gambar yang sama.

| Model | Skor inti | Keluaran bocor |
|---|---|---|
| `gemma3:4b` | **0,483** | **0** |
| `qwen3-vl:4b` | 0,371 | 11 |

`gemma3:4b` unggul pada kedua ukuran dan dipilih untuk tahap penglihatan. Uji lanjutan menaikkan ukuran model dari 4B ke 7B pada 100 gambar yang sama menghasilkan skor inti 0,483 lawan 0,468 — kenaikan ukuran model tidak memperbaiki cacat halusinasi merek sama sekali. Temuan ini yang mengarahkan pekerjaan berikutnya ke verifikasi pasca-generasi, bukan ke model yang lebih besar.

**Keluaran fitur.** Daftar fakta yang terbaca pada foto: jenis barang, warna, bentuk kemasan, dan teks yang benar-benar tercetak. Daftar ini berperan ganda — sebagai bahan penulisan dan sebagai *bukti* yang dipakai penjaga pada Fitur 3.

### 3.2.2 Fitur 2 — Temu kembali katalog

Indeks TF-IDF dibangun di atas judul bersih 28.443 produk. Pembobotan mengikuti prinsip *inverse document frequency* [8]: kecocokan pada istilah yang jarang bernilai lebih tinggi daripada kecocokan pada istilah yang sering muncul.

Kueri disusun dari keluaran Fitur 1. Keluarannya tiga hal: produk pembanding, kosakata khas platform tujuan, dan sebaran harga kategori berupa persentil 25, median, dan persentil 75.

Peran katalog di sini adalah memori non-parametrik yang dapat ditelusuri, seperti pada Retrieval-Augmented Generation [9]: katalog dipakai **saat inferensi**, sehingga penambahan atau pembaruan produk tidak menuntut pelatihan ulang.

`scripts/build_platform_profiles.py` menurunkan profil gaya per platform langsung dari data: panjang judul lazim, pemakaian tanda garis miring, panjang deskripsi, sebaran harga per kategori, dan kosakata khas tiap platform.

### 3.2.3 Fitur 3 — Penyusunan listing dan penjaga bukti

Tahap penulisan menerima fakta visual bersama dua contoh judul nyata dari platform tujuan untuk produk semirip mungkin, dengan angka pada contoh disamarkan agar tidak tersalin. Keluarannya kemudian diperiksa penjaga pasca-generasi, yang memperlakukan kata dan angka secara berbeda.

**Untuk kata.** `scripts/build_lexicon.py` memanen kamus dari katalog. Kandidat merek diambil dari kolom `brand` Blibli dan dari kata pembuka judul yang muncul minimal tiga kali. Kata jenis barang diambil dari kata yang sering muncul dan tersebar pada minimal empat kategori. Kata jenis selalu lolos. Kata spesifik hanya lolos bila muncul pada keluaran Fitur 1 atau pada judul produk pembanding.

Definisi merek disempurnakan setelah kata "gaming" ikut terbuang karena ada toko bernama demikian. Aturan diubah: sebuah kata dianggap merek bila minimal 50% kemunculannya berada pada posisi kata pertama judul — merek berperilaku demikian, kata deskriptif tidak. Daftar merek menyusut dari 1.934 menjadi 1.642 kandidat, "gaming" keluar, "fantech" tetap masuk.

**Untuk angka.** Angka dan satuan diperlakukan lebih ketat: hanya foto yang berlaku sebagai bukti, katalog tidak. Produk pembanding boleh berukuran 500 ml sementara botol pada foto berukuran 200 ml. Kode varian yang benar-benar terbaca tetap lolos.

Aturan ini menutup celah yang ditemukan saat membaca keluaran. Kata "ZARA" sempat lolos ke judul gaun tanpa merek karena merek tersebut muncul pada judul produk pembanding. Dukungan katalog kemudian dinyatakan tidak lagi mengesahkan kata langka, dengan alasan merek milik produk lain bukan bukti untuk foto yang sedang diproses.

**Hasil ablasi.** Tujuh konfigurasi dijalankan pada 10 produk yang sama, 30 listing per konfigurasi, pada mesin dan model yang sama.

| Konfigurasi | Harga meleset | Merek karangan (sempit) | Merek (lebar) | Panjang patuh | Inti | Detik |
|---|---|---|---|---|---|---|
| A semua perbaikan mati | 34,4% | 6,9% | 20,7% | 13,8% | 0,292 | 20,3 |
| B penjaga galak | 2,6% | 0,0% | 3,3% | 80,0% | 0,393 | 18,4 |
| C tanpa hitung harga | 2,6% | 0,0% | 10,3% | 82,8% | 0,399 | 18,4 |
| D tanpa saring merek | 2,6% | **17,2%** | 27,6% | 75,9% | 0,384 | 18,5 |
| E tanpa contoh pola, dengan pemanjangan | 2,6% | 0,0% | 13,8% | **20,7%** | 0,278 | 18,4 |
| F penjaga presisi | 2,6% | 0,0% | 10,0% | 76,7% | **0,403** | 18,4 |
| G F ditambah penanganan frasa merek | 2,6% | 0,0% | 13,3% | 80,0% | 0,387 | 18,7 |
| **I penjaga angka dan aturan bukti (final)** | **2,6%** | **0,0%** | 17,2% | 79,3% | **0,399** | **17,8** |

Perbandingan D lawan F menunjukkan efek terbesar pada pekerjaan ini: halusinasi merek pada ukuran sempit turun dari **17,2% menjadi 0,0%**. Contoh yang tertangkap penjaga mencakup "Fantech" yang masuk ke judul keyboard karena merek itu ada pada kosakata khas platform, "Altraze" pada tas tanpa merek, dan "Longchamp" pada tas biasa.

Penjaga merek memeriksa kata, sehingga angka lolos bebas. Model menuliskan "Shampoo 500ml", "Softergent 200g", dan "20 Sachet" untuk foto yang tidak memuat satu pun angka tersebut. Setelah aturan bukti foto diberlakukan pada konfigurasi I, spesifikasi karangan turun dari **10,0% menjadi 0,0%**.

Perbandingan E lawan B menunjukkan kepatuhan panjang judul naik dari **20,7% menjadi 80,0%**.

| Konfigurasi | Blibli | Tokopedia | Shopee |
|---|---|---|---|
| Target dari data | 6–11 | 10–20 | 8–15 |
| A | 5 | 6 | 4 |
| B | 6 | 10 | 8 |

Tiga putaran perbaikan *prompt* sebelumnya gagal menggeser panjang judul sama sekali. Model 4B dan 7B mengabaikan instruksi panjang seberapa pun tegasnya. Yang berhasil justru mengerjakan penyesuaian panjang **di luar model**, dengan menambahkan kata kunci pendukung dari judul produk pembanding.

### 3.2.4 Fitur 4 — Penetapan harga Market-First

Fitur ini tidak memanggil model apa pun. Seluruh keluarannya hasil aritmetika atas parameter yang tercatat pada berkas konfigurasi. Alasan pemilihannya dibahas pada Subbab 4.3.

**Langkah 1.** Menentukan harga pasar dari median harga produk pembanding hasil Fitur 2, beserta persentil 25 dan 75.

**Langkah 2.** Menghitung titik impas:

```
Harga_BEP = HPP_per_unit / (1 − Total_Potongan)
```

`Total_Potongan` menjumlahkan komisi platform, biaya Gratis Ongkir bila berlaku, biaya pemrosesan pesanan, dan PPh Final. Nilai per platform per kategori tercatat pada berkas konfigurasi beserta tanggal berlakunya (Lampiran 3).

**Langkah 3.** Menempatkan titik impas terhadap persentil harga pasar:

| Zona | Syarat | Arti |
|---|---|---|
| BAGUS | BEP ≤ P25 | Modal rendah, ruang margin lebar |
| WAJAR | P25 < BEP ≤ median | Posisi kompetitif normal |
| KETAT | median < BEP ≤ P75 | Dapat menjual dengan margin tipis |
| BAHAYA | BEP > P75 | Modal terlalu tinggi untuk bersaing |

**Langkah 4.** Menentukan harga rekomendasi menurut zona. Zona BAGUS memakai median pasar. Zona WAJAR menjepit median pasar antara BEP dikali 1,20 dan P75. Zona KETAT menjepit BEP dikali 1,15 antara median dan P75. Zona BAHAYA menampilkan peringatan bahwa modal terlalu tinggi, menyertakan saran taktis, dan tetap menyajikan angka P75 dengan penjelasan risikonya.

Perancangan zona BAHAYA menjawab kelemahan *cost-plus* yang dikritik pada literatur penetapan harga UKM [4]. Model versi pertama pada proyek ini mengalami cacat yang sama: ketika HPP ditambah margin menghasilkan Rp54.900 sementara P25 pasar berada di Rp35.000, model tetap merekomendasikan Rp54.900. Versi *Market-First* menolak menaikkan harga melampaui pasar dan memilih memperingatkan penjual.

**Hasil.** Proporsi harga meleset turun dari 34,4% pada konfigurasi A menjadi 2,6% pada seluruh konfigurasi lain; enam dari sembilan produk menghasilkan harga yang persis sama di semua konfigurasi. Penyebab perbaikan ini berbeda dari yang diperkirakan pada tahap perancangan. Masalah awalnya terletak pada satu kalimat *prompt* yang meminta model memakai rentang harga kategori sebagai dasar perkiraan; kategori `lainnya` membentang dari Rp21 ribu sampai Rp969 ribu, sehingga patokan tersebut tidak bermakna. Setelah kalimat itu diubah menjadi arahan yang mengutamakan harga produk pembanding, harga langsung mendarat pada angka katalog.

Penghitung harga deterministik versi awal yang ditambahkan sebagai komponen terpisah **tidak memberi perbaikan yang terukur**: konfigurasi C menjalankannya dalam keadaan mati dan tetap menghasilkan 2,6%. Klaim yang dapat dipertanggungjawabkan adalah bahwa perbaikan berasal dari pembetulan *prompt*, dan buktinya harga kini menempel pada katalog, bukan pada tengah rentang kategori.

`scripts/pricing_engine.py` versi *Market-First* menggantikan penghitung awal tersebut dan kini terintegrasi ke pipeline melalui `--hpp`. **Efek integrasi ini terhadap kelima metrik listing belum diukur** — perintah ablasinya tercantum pada Lampiran 2 dan hasilnya akan menggantikan paragraf ini begitu tersedia.

### 3.2.5 Status penyesuaian model

Ketentuan lomba mewajibkan model disesuaikan (*fine-tune*) menurut inovasi fitur tiap tim. Status faktual pekerjaan ini per penyusunan dokumen:

| Komponen | Status | Bukti di repo |
|---|---|---|
| Pasangan latih gambar → judul bersih | **Siap**, 27.997 pasangan | `scripts/build_train_pairs.py` → `train_pairs.parquet` |
| Uji kebutuhan *fine-tune* pada tahap penglihatan | **Selesai** | `scripts/probe_vlm_baseline.py`, n=100 |
| *Fine-tune* Fitur 1 dan Fitur 3 | **Belum dijalankan** | — |
| *Fine-tune* Fitur 4 | **Tidak dilakukan, disengaja** | Alasan pada Subbab 4.3 |

Fitur 4 tidak akan disesuaikan dalam bentuk apa pun, dan itu keputusan desain yang dipertahankan: harga jual ditentukan HPP penjual, tarif komisi, dan tarif pajak — tiga besaran eksak yang berubah lewat peraturan, bukan pola yang dapat dipelajari dari data. Fitur 1 dan Fitur 3 adalah tempat penyesuaian model relevan, dan pasangan latihnya sudah tersedia; yang belum ada adalah bobot hasil latih beserta angka pembandingnya terhadap keluaran *prompt-only*. Sesuai aturan penulisan proyek ini, klaim tidak dituliskan mendahului artefaknya.

## 3.3 Alur Integrasi Model ke Environment Kode

### 3.3.1 Pemisahan dua fase dan alasannya

Pemisahan Fitur 1 dan Fitur 3 bukan pilihan gaya. Kartu grafis 8 GB tidak memuat `gemma3:4b` dan `qwen2.5:7b` sekaligus. Pipeline versi awal memanggil keduanya bergantian untuk setiap produk, sehingga Ollama menukar bobot model dua puluh kali dalam satu *run*: satu *run* 20 produk berjalan 25 menit dan baru menyelesaikan lima produk, setara sekitar **300 detik per produk**. Sebagian besar waktu terpakai untuk memuat bobot, bukan untuk inferensi.

Pipeline diubah menjadi dua fase: seluruh panggilan penglihatan dijalankan lebih dulu, kemudian seluruh panggilan penulisan. Setiap model dimuat satu kali. Waktu turun menjadi **17,8 detik per produk** pada konfigurasi final. Perubahan inilah yang memungkinkan tujuh konfigurasi pada Subbab 3.2.3 diuji dalam satu malam.

### 3.3.2 Batas modul

| Lapisan | Isi | Berkas |
|---|---|---|
| Inferensi AI | Panggilan VLM dan LLM, penyusunan *prompt*, penjaga pasca-generasi | `scripts/retrieve_pipeline.py` |
| Aritmetika harga | BEP, zona, harga rekomendasi, rincian biaya | `scripts/pricing_engine.py` |
| Turunan katalog | Kamus merek, profil gaya platform, indeks TF-IDF | `scripts/build_lexicon.py`, `build_platform_profiles.py` |
| Data | Pengambilan, parsing, penyimpanan *response* mentah | `src/tokopedia_scraper/` |
| Konfigurasi | Tarif komisi, biaya pemrosesan, tarif pajak, tanggal berlaku | `config.yaml`, konstanta pada `pricing_engine.py` |

Lapisan aritmetika harga tidak mengimpor apa pun dari lapisan inferensi AI. Konsekuensinya, `pricing_engine.py` dapat diuji tanpa Ollama hidup — `scripts/pricing_demo_offline.py` dan `tests/test_pricing.py` berjalan sepenuhnya luring.

### 3.3.3 Antarmuka dan cara menjalankan

Ruang lingkup MVP mengikuti batasan lomba: antarmuka hanya memuat alur interaksi inti — pengguna mengunggah satu foto dan mengisi HPP, sistem menampilkan judul, deskripsi, kategori, dan rincian harga per platform. Tidak ada dasbor analitik, tidak ada otentikasi, tidak ada halaman riwayat. *Backend* hanya memproses interaksi sinkron; tidak ada *background job* maupun basis data terdistribusi.

Parameter model bersifat statis saat demonstrasi berjalan. Panduan menjalankan sistem secara lokal berada pada `README.md`, dan seluruh layanan dibungkus `docker compose` sehingga penilai dapat menjalankannya tanpa menyiapkan lingkungan Python secara manual.

### 3.3.4 Uji dan reproduksi

Seluruh berkas uji dijalankan luring; `tests/conftest.py` memasang penjaga yang menggagalkan uji apa pun yang menyentuh jaringan. Setiap perbaikan pipeline memiliki sakelar mematikan sendiri — `--tanpa-harga-hitung`, `--tanpa-saring-merek`, `--tanpa-contoh-pola` — sehingga efek tiap komponen dapat dipisahkan dan diukur ulang. Perintah lengkapnya pada Lampiran 2.

---

# 4. METODE LAIN YANG MENDASARI PENGAMBILAN KEPUTUSAN

## 4.1 Ablasi terkendali sebagai syarat klaim

Aturan kerja proyek ini: klaim perbaikan hanya sah bila ada angka sebelum dan sesudah. Sepuluh produk yang sama (`--n 10 --seed 7`), tiga platform, 30 listing per konfigurasi, dijalankan berurutan pada mesin dan model yang sama. Benih tetap membuat potongan `--iris a:b` selalu memuat produk yang sama, sehingga satu konfigurasi dapat dikerjakan beberapa kali tanpa mengubah sampelnya.

Lima metrik dicatat per konfigurasi:

| Metrik | Definisi |
|---|---|
| Harga meleset | Proporsi listing dengan harga di luar rentang wajar produk pembanding |
| Merek karangan (sempit) | Nama merek nyata milik produk lain, atau istilah langka di luar kosakata katalog |
| Merek karangan (lebar) | Kata apa pun pada judul yang tidak ada pada keluaran Fitur 1 maupun judul produk pembanding |
| Panjang patuh | Proporsi judul yang panjangnya masuk rentang lazim platform tujuan |
| Inti | Kecocokan judul yang dihasilkan terhadap judul asli produk |

**Dua ukuran halusinasi dipakai bersamaan, dan itu disengaja.** Perbandingan B lawan F memperlihatkan jebakan metodologis yang ditemukan di tengah jalan: pada ukuran lebar, B tampak menang (3,3% lawan 10,0%); pada ukuran sempit keduanya sama-sama 0,0%. Ukuran lebar memberi nilai lebih baik kepada penjaga yang lebih galak, karena keduanya memakai definisi "tak berdasar" yang sama. Hal ini hanya ketahuan setelah keluaran dibaca satu per satu — bukan dari tabel angka.

Kejadian yang sama terjadi pada penjaga v1, yang membuang enam kata padahal hanya dua di antaranya benar-benar merek karangan; kata "Pesta", "Pelembut Pakaian", dan "Jogging" ikut terbuang, dan frasa "Merek Tidak Tertera" terpotong menjadi "Gaun Floral Merek Tidak". Versi kedua memakai tiga golongan kata: kata yang memiliki dasar selalu lolos, nama merek yang dikenal wajib memiliki dukungan, dan kata Indonesia lazim (muncul pada minimal 20 produk) dibiarkan. Hasil pada ukuran sempit sama bersihnya dengan kerusakan sampingan jauh lebih sedikit, dan skor inti justru naik menjadi 0,403.

Ablasi yang memburuk tetap dilaporkan pada dokumen ini. Konfigurasi E memperlihatkan kepatuhan panjang jatuh ke 20,7% dan skor inti ke 0,278 — angka terburuk pada tabel — dan tetap dicantumkan karena justru itu yang membuktikan contoh pola bekerja.

## 4.2 Verifikasi eksternal dipilih setelah model yang lebih besar gagal

Tiga temuan menunjuk arah yang sama. Menaikkan model dari 4B ke 7B menggeser skor inti dari 0,468 ke 0,483 dan tidak menyentuh halusinasi merek. Tiga putaran perbaikan *prompt* gagal menghilangkan merek karangan. Penjaga pasca-generasi menurunkannya ke 0,0%.

Penjelasannya terletak pada sifat persoalannya. Merek tercetak pada kemasan dan terdaftar pada katalog, sehingga tugasnya adalah **mencocokkan**, bukan mengingat. Pencocokan dikerjakan lebih baik oleh pencarian pada kamus daripada oleh parameter model. Temuan ini sejalan dengan arah literatur mitigasi halusinasi yang memakai verifikasi terhadap sumber di luar model [7], dan menambahkan satu hal: verifikasi tersebut tidak harus mahal.

## 4.3 Mengapa harga tidak diserahkan ke model pembelajaran

Harga jual yang benar bergantung pada empat komponen: Harga Pokok Penjualan milik penjual, tarif komisi platform tujuan, tarif pajak yang berlaku, dan sebaran harga pesaing. Tiga dari empat komponen itu berupa aritmetika bisnis yang eksak.

Model yang dilatih memprediksi harga dari foto hanya akan menghafal harga pasar. Tiga akibatnya konkret. Pertama, penjual tidak dapat memeriksa dari mana angka itu datang, padahal yang ia butuhkan justru rinciannya. Kedua, perubahan tarif komisi menuntut pelatihan ulang, sementara Tokopedia dan Shopee mengubah struktur biaya dua kali dalam rentang Mei sampai Juli 2026. Ketiga, model tidak dapat menyatakan "modal Anda terlalu tinggi untuk bersaing" — ia hanya akan mengeluarkan angka harga pasar tanpa memberi tahu bahwa pada angka itu penjual merugi.

Mesin deterministik menjawab ketiganya: rinciannya dapat dibaca baris demi baris, tarif diperbarui lewat satu berkas konfigurasi, dan zona BAHAYA merupakan keluaran yang sah.

## 4.4 Kepatuhan data dan tata kelola

| Aspek | Keputusan |
|---|---|
| Sifat pengumpulan | Riset non-komersial; *concurrency* 1, jeda 2–5 detik, pemutus arus setelah sepuluh kegagalan beruntun; tanpa pemecah CAPTCHA |
| Redistribusi | Tidak dilakukan; `data/` dan `data_drive/` tidak masuk kendali versi |
| Ketertelusuran | Setiap baris menyimpan URL sumbernya |
| Data pribadi | 4,3% deskripsi memuat nomor telepon penjual; kolom ini wajib disaring sebelum dipakai sebagai contoh gaya |
| Rahasia sesi | Berkas `.env` dan `config/gql_capture.yaml` memuat *cookie* sesi dan tidak masuk kendali versi |
| Hak merek | Penjaga merek menolak nama merek milik produk lain; ini alasan mengapa targetnya 0,0%, bukan sekadar "berkurang" |

Halusinasi merek diperlakukan sebagai persoalan hukum, bukan persoalan mutu tulisan. Judul yang menyebut merek milik produk lain berpotensi melanggar hak merek. Judul yang menyebut "500ml" untuk botol 200 ml membuat penjual berhadapan dengan tuntutan pembeli.

## 4.5 Kelayakan adopsi

Biaya operasional sistem mendekati nol pada sisi model: `gemma3:4b` dan `qwen2.5:7b` berjalan lokal pada kartu grafis 8 GB tanpa biaya API per gambar, dengan 17,8 detik per produk. Ini yang membuat pemakaian oleh penjual beromzet di bawah Rp500 juta masuk akal secara ekonomi — segmen yang justru terbesar menurut data BPS [2] dan tidak terjangkau oleh alat berbasis API berbayar.

Biaya pemeliharaan terpusat pada satu titik: tarif komisi dan pajak berubah beberapa kali setahun, dan pembaruannya berupa suntingan satu berkas konfigurasi tanpa pelatihan ulang model apa pun.

---

# 5. BATASAN DAN KETERBATASAN

**Batasan cakupan.**

1. LAPAKIN menghasilkan usulan judul, deskripsi, kategori, dan rentang harga. Sistem tidak menerbitkan listing ke marketplace dan tidak terhubung ke API penjual mana pun. Keputusan akhir berada pada penjual.
2. Masukan berupa satu foto produk dan satu nilai HPP per produk. Sistem tidak menerima video, tidak membaca dokumen faktur, dan tidak menghitung HPP dari komponen bahan baku.
3. Platform tujuan: Tokopedia, Shopee, dan Blibli. Tarif ketiganya tercatat pada berkas konfigurasi beserta tanggal berlakunya.
4. Sebaran harga berasal dari 28.443 produk yang dikumpulkan pada Agustus 2026. Sistem tidak memantau harga secara waktu nyata dan tidak mendeteksi perubahan harga pesaing setelah tanggal pengumpulan.

**Keterbatasan hasil.**

5. **Sampel kecil.** Sepuluh produk dan 30 listing per konfigurasi cukup untuk mendeteksi efek besar seperti halusinasi merek dan kepatuhan panjang judul. Sampel ini tidak cukup untuk efek kecil, dan itulah alasan klaim mengenai penghitung harga deterministik tidak diajukan. Perbandingan model visual berjalan pada 100 gambar.
6. **Metrik hanya menguji konsistensi internal.** Halusinasi merek diukur terhadap keluaran Fitur 1 dan katalog, bukan terhadap isi foto. Bila tahap penglihatan salah membaca, metrik ini tidak akan mendeteksinya. Penilaian manusia atas 50 sampai 100 listing diperlukan untuk menutup celah ini.
7. **Metrik dapat menyesatkan bila definisinya sama dengan definisi penjaganya**, sebagaimana kasus B lawan F pada Subbab 4.1.
8. **Kategori masih lemah.** Seluruh sebaran harga bersandar pada `kategori_umkm` yang 37,8% jatuh ke kelas `lainnya` dan 55,2% dipetakan lewat pencocokan kata kunci judul.
9. **Kesalahan harga yang tersisa bersifat sistematis.** Gaun Eprise berharga asli Rp479.800 memperoleh saran Rp82 ribu sampai Rp176 ribu karena produk pembandingnya gaun murah. Sepatu Zedruz berharga Rp116.899 memperoleh saran Rp75.000. Pencarian berbasis teks tidak dapat membedakan kelas harga di dalam satu jenis barang.
10. **Tarif platform berlaku pada tanggal tertentu.** Angka komisi yang dipakai berasal dari data Mei sampai Agustus 2026; sistem tidak memantau perubahannya secara otomatis.
11. **Efek integrasi mesin harga *Market-First* ke pipeline belum diukur**, sebagaimana dinyatakan pada Subbab 3.2.4.
12. **Penyesuaian model pada Fitur 1 dan Fitur 3 belum dijalankan**, sebagaimana dinyatakan pada Subbab 3.2.5.

---

# 6. KESIMPULAN

1. Pipeline dua tahap yang memakai `gemma3:4b` untuk ekstraksi visual dan `qwen2.5:7b` untuk penyusunan teks menghasilkan judul, deskripsi, dan kategori produk dari satu foto dengan waktu **17,8 detik per produk** pada perangkat berkartu grafis 8 GB, tanpa biaya API. Pemecahan pipeline menjadi dua fase memangkas waktu dari sekitar 300 detik per produk.

2. Penjaga pasca-generasi yang memverifikasi keluaran terhadap kamus katalog dan keluaran tahap penglihatan menurunkan halusinasi merek dari **17,2% menjadi 0,0%** dan spesifikasi karangan dari **10,0% menjadi 0,0%** pada ukuran sempit. Menaikkan ukuran model dari 4B ke 7B tidak menyentuh cacat yang sama (skor inti 0,468 lawan 0,483 pada 100 gambar). Untuk persoalan ini, verifikasi eksternal terbukti lebih efektif daripada kapasitas model.

3. Profil gaya per platform yang diturunkan dari data menaikkan kepatuhan panjang judul dari **20,7% menjadi 80,0%**, setelah tiga putaran perbaikan *prompt* gagal menggeser panjang judul sama sekali. Yang berhasil adalah mengerjakan penyesuaian di luar model.

4. Mesin penetapan harga *Market-First* menghitung titik impas dari HPP, komisi platform, biaya pemrosesan, dan PPh Final, lalu menempatkannya terhadap persentil harga pasar untuk menghasilkan empat zona keputusan. Zona BAHAYA menangani kasus modal terlalu tinggi dengan peringatan, bukan dengan menaikkan harga melampaui pasar — menjawab kelemahan *cost-plus* yang dikritik pada literatur penetapan harga UKM [4].

5. Perbaikan akurasi harga berasal dari pembetulan kalimat *prompt*, bukan dari penghitung deterministik versi awal; ablasi konfigurasi C menunjukkan pipeline tanpa penghitung tersebut tetap mencatat 2,6% harga meleset. Komponen itu dipertahankan sebagai jaring pengaman tanpa diklaim sebagai penyumbang angka.

6. Katalog 28.443 produk berperan sebagai rujukan saat inferensi. Memperbarui tarif komisi atau tarif pajak menuntut perubahan satu berkas konfigurasi, tanpa pelatihan ulang model — sifat yang penting mengingat tarif berubah dua kali dalam rentang Mei sampai Juli 2026.

**Yang belum selesai dan akan dikerjakan pada tahap berikutnya:** penyesuaian model pada Fitur 1 dan Fitur 3 memakai 27.997 pasangan latih yang sudah tersedia beserta pembandingnya terhadap keluaran *prompt-only*; pengukuran efek integrasi mesin harga *Market-First* ke pipeline; temu kembali berbasis kemiripan gambar seperti CLIP [11] untuk memisahkan kelas harga di dalam satu jenis barang; perbaikan label `kategori_umkm`; penilaian manusia atas 50 sampai 100 listing; dan pembesaran sampel ablasi.

---

# DAFTAR PUSTAKA

[1] Kementerian Koordinator Bidang Perekonomian Republik Indonesia, "UMKM Menjadi Pilar Penting dalam Perekonomian Indonesia." [Daring]. Tersedia: https://www.ekon.go.id/publikasi/detail/2969/umkm-menjadi-pilar-penting-dalam-perekonomian-indonesia

[2] Badan Pusat Statistik, *Statistik E-Commerce 2023*. Jakarta: Badan Pusat Statistik, 2025. [Daring]. Tersedia: https://www.bps.go.id/id/publication/2025/01/30/d52af11843aee401403ecfa6/statistik-e-commerce-2023.html

[3] Direktorat Jenderal Pajak, "PP 20/2026: Tarif PPh 0,5% bagi UMKM Orang Pribadi Berlaku Selamanya," 2026. [Daring]. Tersedia: https://www.pajak.go.id/en/node/119950

[4] K. Stromeyer dan W. Kurz, "Optimizing Pricing Strategies in Capital Goods SMEs: A Weighted Dynamic Corridor Approach to Cost-Plus and Value-Based Pricing," *Business and Management Studies*, vol. 11, no. 1, 2025. doi: 10.11114/bms.v11i1.7453. [Daring]. Tersedia: https://doi.org/10.11114/bms.v11i1.7453

[5] Gemma Team, Google DeepMind, "Gemma 3 Technical Report," arXiv:2503.19786, 2025. [Daring]. Tersedia: https://arxiv.org/abs/2503.19786

[6] A. Yang, B. Yang, B. Zhang, B. Hui, dkk., "Qwen2.5 Technical Report," arXiv:2412.15115, 2025. [Daring]. Tersedia: https://arxiv.org/abs/2412.15115

[7] H. Liu, W. Xue, Y. Chen, D. Chen, X. Zhao, K. Wang, L. Hou, R. Li, dan W. Peng, "A Survey on Hallucination in Large Vision-Language Models," arXiv:2402.00253, 2024. [Daring]. Tersedia: https://arxiv.org/abs/2402.00253

[8] K. Spärck Jones, "A Statistical Interpretation of Term Specificity and Its Application in Retrieval," *Journal of Documentation*, vol. 28, no. 1, hlm. 11–21, 1972. doi: 10.1108/eb026526. [Daring]. Tersedia: https://www.emerald.com/insight/content/doi/10.1108/eb026526/full/html

[9] P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis, W. Yih, T. Rocktäschel, S. Riedel, dan D. Kiela, "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," arXiv:2005.11401, 2020. [Daring]. Tersedia: https://arxiv.org/abs/2005.11401

[10] B. Zhang, T. Nakatani, dan S. Walter, "Enhancing E-commerce Product Title Translation with Retrieval-Augmented Generation and Large Language Models," arXiv:2409.12880, 2024. [Daring]. Tersedia: https://arxiv.org/abs/2409.12880

[11] A. Radford, J. W. Kim, C. Hallacy, dkk., "Learning Transferable Visual Models From Natural Language Supervision," dalam *Proceedings of the 38th International Conference on Machine Learning*, PMLR vol. 139, 2021. [Daring]. Tersedia: https://arxiv.org/abs/2103.00020

[12] Republik Indonesia, *Undang-Undang Nomor 7 Tahun 2021 tentang Harmonisasi Peraturan Perpajakan*. [Daring]. Tersedia: https://peraturan.bpk.go.id/Details/185162

---

# LAMPIRAN

## Lampiran 1. Status verifikasi sumber

Rujukan [4] sampai [11] diperiksa langsung pada halaman sumbernya, mencakup judul, daftar penulis, tahun, dan pengenal arXiv atau DOI.

Rujukan [1], [2], [3], dan [12] berasal dari laman resmi lembaga pemerintah dan diperoleh melalui hasil pencarian. Laman BPS dan Kementerian Koordinator Bidang Perekonomian menolak akses otomatis pada saat penyusunan, sehingga **URL dan angka pada keempat rujukan tersebut perlu dibuka kembali dan dicocokkan sebelum dokumen ini dikumpulkan**.

## Lampiran 2. Perintah reproduksi hasil

```bash
# Menyiapkan dataset
python scripts/fetch_drive_iac.py
python scripts/localize_merged.py
python scripts/build_train_pairs.py

# Menurunkan profil gaya platform dan kamus merek dari katalog
python scripts/build_platform_profiles.py
python scripts/build_lexicon.py

# Subbab 3.2.1: perbandingan model visual
python scripts/probe_vlm_baseline.py --model gemma3:4b --n 100

# Subbab 3.2.3: ablasi komponen listing
python scripts/retrieve_pipeline.py --n 10 --platform all --iris 0:5  --panjangkan --keluaran data_drive/eval/B.jsonl
python scripts/retrieve_pipeline.py --n 10 --platform all --iris 5:10 --panjangkan --keluaran data_drive/eval/B.jsonl
python scripts/eval_listing.py data_drive/eval/A.jsonl data_drive/eval/B.jsonl

# Subbab 3.2.4: mesin penetapan harga, luring
python scripts/pricing_demo_offline.py

# Subbab 3.2.4: efek integrasi Market-First ke pipeline (BELUM DIJALANKAN)
python scripts/retrieve_pipeline.py --n 10 --platform all --hpp 25000 --keluaran data_drive/eval/J.jsonl
python scripts/eval_listing.py data_drive/eval/I.jsonl data_drive/eval/J.jsonl

# Subbab 3.1.4: statistik dataset
python main.py stats

# Uji, luring total
python -m pytest -q
```

Sakelar ablasi: `--tanpa-harga-hitung`, `--tanpa-saring-merek`, `--tanpa-contoh-pola`, `--panjangkan`.

## Lampiran 3. Ringkasan biaya platform yang dipakai pada perhitungan

Nilai efektif (komisi ditambah Gratis Ongkir dan biaya pemrosesan) per kategori, berlaku menurut data Mei sampai Agustus 2026.

Tabel disusun menurut **kosakata kategori yang benar-benar ada pada dataset** — tujuh nilai `kategori_umkm` hasil `value_counts()` atas 28.443 baris, bukan taksonomi yang disusun secara apriori. Tarif marketplace memakai taksonomi platform sendiri, sehingga kolom pertama sekaligus menampilkan pemetaannya: tanda panah menunjukkan kelompok tarif tempat kategori tersebut jatuh.

| Kategori (kosakata data → kelompok tarif) | Tokopedia | Shopee (Star) | Blibli |
|---|---|---|---|
| `bumbu_masak` → *makanan_minuman* | 6,5% + Rp1.250 | 10% + 6% ongkir + Rp1.250 | 5,75% |
| `camilan_olahan` → *makanan_minuman* | 6,5% + Rp1.250 | 10% + 6% ongkir + Rp1.250 | 5,75% |
| `fashion_perawatan` | 8% + Rp1.250 | 10% + 6% ongkir + Rp1.250 | 10% |
| `kriya_rumah` | 8% + Rp1.250 | 10% + 6% ongkir + Rp1.250 | 8% |
| `lainnya` | 6,5% + Rp1.250 | 9% + 6% ongkir + Rp1.250 | 7,5% |
| `minuman_herbal` | 6,5% + Rp1.250 | 6,5% + 6% ongkir + Rp1.250 | 5,75% |
| `pokok_tani` → *makanan_minuman* | 6,5% + Rp1.250 | 10% + 6% ongkir + Rp1.250 | 5,75% |

Rincian per platform beserta tanggal berlakunya tercantum pada `docs/MODEL_HARGA.md` Subbab 2.2. Seluruh isi tabel ini dibangkitkan langsung dari `KATEGORI_DATA`, `KE_TARIF`, dan `BIAYA_PLATFORM` pada `scripts/pricing_engine.py`, sehingga tidak dapat menyimpang dari nilai yang dipakai program.

Versi tabel sebelum 20 Agustus 2026 memuat lima kategori — `elektronik_gadget`, `makanan_minuman`, `skincare_kecantikan`, `dapur_rumah`, dan `kesehatan_olahraga` — yang tidak muncul satu kali pun pada dataset, dan tidak memuat `pokok_tani`, `bumbu_masak`, `camilan_olahan`, `minuman_herbal`, maupun `lainnya` yang mencakup seluruh 28.443 baris. Ketiga kategori pangan tersebut sebelumnya diperlakukan program sebagai `lainnya` tanpa peringatan apa pun, mencakup 4.749 produk atau 16,7% katalog. Selisih harga yang ditimbulkannya terukur kecil — pada HPP Rp15.000 sebesar Rp0 di Tokopedia, −Rp228 di Shopee, dan +Rp301 di Blibli — sehingga koreksi ini menyangkut ketepatan pelaporan, bukan perubahan hasil. Pembahasan lengkap terdapat pada `docs/RISET_MODEL_HARGA.md` Subbab 7.3.
