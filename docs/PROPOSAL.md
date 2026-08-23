# PROPOSAL AI INNOVATION CHALLENGE 2026

## LAPAKIN: Sistem Rekomendasi Listing dan Harga Jual untuk UMKM E-Commerce Berbasis Vision-Language Model, Temu Kembali Hibrida TF-IDF–CLIP, dan Penetapan Harga Market-First

**Nama Kelompok:** `[NAMA TIM]`
**Nama Inovasi:** LAPAKIN
**Kompetisi:** AI Innovation Challenge, COMPFEST 18 (2026)
**Tema:** AI for the Backbone of the Economy
**Area:** Smart Commerce (Toko & Pasar)

LAPAKIN menerima satu foto produk dan satu nilai Harga Pokok Penjualan, lalu mengembalikan judul, deskripsi, kategori, dan rentang harga jual yang sudah memperhitungkan komisi platform, biaya pemrosesan, dan pajak UMKM. Bagian yang menuntut persepsi dikerjakan model AI. Bagian yang menuntut kepastian aritmetika dikerjakan mesin hitung deterministik yang menyajikan rincian tiap komponen biaya, sehingga penjual dapat memeriksa asal setiap angka.

---

## DAFTAR ISI

**BAB I PENDAHULUAN**
1.1 Latar Belakang
1.2 Rumusan Masalah
1.3 Tujuan Pengembangan
1.4 Manfaat Pengembangan
1.5 Batasan Sistem

**BAB II TINJAUAN PUSTAKA**
2.1 Digitalisasi UMKM dan Hambatan Onboarding di Marketplace
2.2 Vision-Language Model dan Large Language Model Open-Weights
2.3 Halusinasi pada Vision-Language Model dan Strategi Mitigasinya
2.4 Temu Kembali Informasi TF-IDF, Representasi Visual Bersama, dan Retrieval-Augmented Generation
2.5 Cost-Plus Pricing, Market-Based Pricing, dan Koridor Harga
2.6 Posisi LAPAKIN terhadap Penelitian Terdahulu

**BAB III METODOLOGI**
3.1 Arsitektur Sistem LAPAKIN
3.2 Alur Memperoleh Dataset
3.3 Alur Pengembangan Model per Fitur
3.4 Alur Integrasi Model ke Environment Kode
3.5 Metode Lain yang Mendasari Pengambilan Keputusan
3.6 Keterbatasan Hasil

**BAB IV KESIMPULAN DAN SARAN**
4.1 Kesimpulan
4.2 Saran

**DAFTAR PUSTAKA**

**LAMPIRAN**

---

# BAB I PENDAHULUAN

## 1.1 Latar Belakang

Usaha Mikro, Kecil, dan Menengah menopang sebagian besar perekonomian Indonesia. Kementerian Koordinator Bidang Perekonomian mencatat 64,2 juta pelaku UMKM yang menyumbang 61,07% Produk Domestik Bruto dan menyerap sekitar 97% tenaga kerja nasional [1]. Badan Pusat Statistik mencatat 3,82 juta usaha e-commerce di 38 provinsi per akhir 2023, dengan mayoritas pelaku berasal dari kelompok usaha mikro [2].

Angka itu menyembunyikan satu masalah operasional pada titik terakhir rantai nilai, yaitu saat barang berpindah ke tangan konsumen — area Smart Commerce pada tema kompetisi ini. Seorang penjual yang baru membuka lapak menghadapi formulir kosong: kolom judul, kolom deskripsi, pilihan kategori, dan kolom harga. Keempatnya menentukan apakah produk muncul di hasil pencarian dan apakah pembeli menekan tombol beli. Penjual pemula mengisinya dengan menebak.

Kolom harga paling mahal kesalahannya. Penjual mengetahui modalnya, misalnya Rp25.000 per bungkus keripik, tetapi tidak mengetahui berapa yang dipotong marketplace. Tokopedia memungut komisi 3% sampai 8,5% bergantung kategori ditambah biaya pemrosesan Rp1.250 per pesanan. Shopee memungut biaya administrasi 4,25% sampai 12% ditambah program Gratis Ongkir XTRA 4% sampai 9%. Blibli memungut 4,25% sampai 10%. Di atas itu berlaku PPh Final UMKM 0,5% dari peredaran bruto, meskipun Peraturan Pemerintah Nomor 20 Tahun 2026 membebaskan omzet Rp500 juta pertama dalam satu tahun pajak bagi Wajib Pajak Orang Pribadi [3]. Penjual yang menetapkan harga dari modal ditambah persentase untung sering menemukan marginnya habis setelah seluruh potongan itu bekerja.

Kesalahan berjalan ke dua arah. Harga terlalu rendah membuat penjual menanggung rugi pada setiap transaksi tanpa menyadarinya. Harga terlalu tinggi membuat produk tidak pernah terjual. Literatur penetapan harga pada UKM menunjuk akar persoalannya: metode *cost-plus* menetapkan harga dari biaya produksi tanpa memperhitungkan nilai yang bersedia dibayar pembeli, sehingga berisiko menghasilkan harga di atas atau di bawah pasar [4].

Kecerdasan buatan menawarkan jalan keluar untuk kolom judul dan deskripsi. Model *vision-language* *open-weights* berukuran kecil kini berjalan pada perangkat konsumen dan mampu membaca isi sebuah foto produk [5]. Model bahasa berukuran 7 miliar parameter mampu menyusun kalimat pemasaran berbahasa Indonesia [6]. Keduanya tersedia tanpa biaya API.

Kolom harga tidak dapat diselesaikan dengan cara yang sama. Harga jual yang benar bergantung pada Harga Pokok Penjualan milik penjual, tarif komisi platform tujuan, tarif pajak yang berlaku, dan sebaran harga pesaing. Tiga dari empat komponen itu berupa aritmetika bisnis yang eksak, bukan pola yang perlu dipelajari dari data. Model *deep learning* yang dilatih memprediksi harga dari foto hanya akan menghafal harga pasar, dan penjual tidak dapat memeriksa dari mana angka itu datang.

Sistem yang diusulkan dalam proposal ini, selanjutnya disebut LAPAKIN, memisahkan dua persoalan tersebut. Bagian yang menuntut persepsi diserahkan kepada model AI. Bagian yang menuntut kepastian aritmetika diserahkan kepada mesin hitung deterministik yang menyajikan rincian setiap komponen biaya. Katalog 28.443 produk marketplace berperan sebagai rujukan pasar pada saat sistem bekerja, bukan sebagai data latih yang dilebur menjadi bobot model.

**Mengapa sekarang.** Tiga perubahan membuat persoalan ini layak dikerjakan pada 2026. *Pertama,* aturan biaya berubah dalam satu tahun terakhir: PP Nomor 20 Tahun 2026 mempertahankan tarif PPh Final 0,5% dan membebaskan omzet Rp500 juta pertama [3]; Tokopedia menerapkan komisi dinamis per 18 Mei 2026 dan menurunkan batas atas biaya menjadi Rp80.000 per item pada Juli 2026; Shopee memperbarui biaya administrasi per 2 Mei 2026. Penjual yang menghitung margin memakai angka tahun sebelumnya akan salah. *Kedua,* perangkatnya baru terjangkau: model *vision-language* 4 miliar parameter yang berjalan pada satu kartu grafis 8 GB baru tersedia sebagai *open-weights* dalam dua tahun terakhir [5], sedangkan sebelumnya pipeline seperti LAPAKIN menuntut API berbayar per gambar. *Ketiga,* perubahan tarif menuntut arsitektur yang parameternya dapat diperbarui tanpa melatih ulang model apa pun.

## 1.2 Rumusan Masalah

1. Bagaimana menghasilkan judul, deskripsi, dan kategori produk yang sesuai gaya masing-masing marketplace hanya dari satu foto produk, tanpa model menyebut merek, ukuran, atau spesifikasi yang tidak terbaca pada foto tersebut?
2. Bagaimana memanfaatkan katalog produk marketplace sebagai rujukan saat inferensi melalui temu kembali informasi, sehingga sistem memperoleh kosakata, kategori, dan sebaran harga produk sejenis tanpa melatih ulang model?
3. Bagaimana merancang mesin penetapan harga yang menggabungkan Harga Pokok Penjualan penjual, komisi platform, biaya pemrosesan, dan pajak UMKM dengan sebaran harga pasar, serta menghasilkan rincian yang dapat diperiksa penjual?
4. Bagaimana sistem memperlakukan kasus modal penjual terlalu tinggi untuk bersaing, yaitu ketika titik impas berada di atas kuartil atas harga pasar?

## 1.3 Tujuan Pengembangan

1. Membangun pipeline *auto-listing* dua tahap yang memakai `gemma3:4b` untuk ekstraksi fakta visual dan `qwen2.5:7b` untuk penyusunan teks, dilengkapi penjaga pasca-generasi yang menolak merek dan angka tanpa dasar pada foto.
2. Membangun temu kembali hibrida atas 28.443 produk marketplace — TF-IDF pada judul dan CLIP pada 28.093 gambar — yang menghasilkan produk pembanding, kosakata khas platform, sebaran harga kategori, dan penanda barang asing pada saat inferensi.
3. Membangun mesin penetapan harga *Market-First* yang menghitung titik impas dari HPP, komisi platform, biaya pemrosesan, dan PPh Final, lalu menempatkannya terhadap persentil harga pasar untuk menghasilkan harga rekomendasi beserta rinciannya.
4. Mengukur setiap komponen melalui ablasi terkendali, dan melaporkan komponen yang tidak memberi perbaikan terukur beserta komponen yang memberi.

## 1.4 Manfaat Pengembangan

| Penerima | Manfaat |
|---|---|
| Penjual UMKM | Memangkas waktu pengisian formulir listing; menunjukkan batas harga terendah yang masih menghasilkan laba, lengkap dengan rincian potongan platform dan pajak yang dapat diperiksa baris demi baris |
| Ekosistem Smart Commerce | Menurunkan hambatan masuk pada titik terakhir rantai nilai, tempat produk UMKM bertemu konsumen digital |
| Peneliti | Studi kasus terukur tentang pemisahan tugas persepsi dan tugas aritmetika, termasuk ablasi yang menunjukkan komponen mana yang benar-benar menyumbang perbaikan |
| Pengembang sistem serupa | Kamus merek dan profil gaya platform diturunkan dari katalog secara otomatis, sehingga metode yang sama dapat dipindahkan ke katalog lain tanpa anotasi manual |

## 1.5 Batasan Sistem

1. **Cakupan keluaran.** LAPAKIN menghasilkan usulan judul, deskripsi, kategori, dan rentang harga. Sistem tidak menerbitkan listing ke marketplace dan tidak terhubung ke API penjual mana pun. Keputusan akhir berada pada penjual.
2. **Masukan.** Satu foto produk dan satu nilai HPP per produk. Sistem tidak menerima video, tidak membaca dokumen faktur, dan tidak menghitung HPP dari komponen bahan baku.
3. **Platform tujuan.** Tokopedia, Shopee, dan Blibli. Tarif ketiganya tercatat pada berkas konfigurasi beserta tanggal berlakunya.
4. **Sifat rujukan harga.** Sebaran harga berasal dari 28.443 produk yang dikumpulkan pada Agustus 2026. Sistem tidak memantau harga secara waktu nyata dan tidak mendeteksi perubahan harga pesaing setelah tanggal pengumpulan.
5. **Label kategori.** Kolom `kategori_umkm` pada dataset merupakan label lemah: 37,8% baris jatuh ke kelas `lainnya` dan 55,2% dipetakan melalui pencocokan kata kunci judul. Seluruh sebaran harga per kategori mewarisi keterbatasan ini.
6. **Skala evaluasi.** Ablasi komponen dijalankan pada 10 produk dengan 30 listing per konfigurasi, dan perbandingan model visual pada 100 gambar. Angka yang dilaporkan berlaku pada skala tersebut.
7. **Cakupan katalog menentukan mutu keluaran.** Untuk produk yang tidak memiliki padanan di katalog, sistem tidak menyusun harga dan menandainya perlu ditentukan penjual. Batas ini disengaja dan terukur pada Tabel 3.6.
8. **Metrik otomatis.** Metrik halusinasi mengukur konsistensi antara keluaran tahap penulisan dan keluaran tahap penglihatan. Metrik ini tidak memeriksa apakah tahap penglihatan membaca foto dengan benar.
9. **Status data.** Dataset berasal dari pengumpulan otomatis untuk riset non-komersial dan tidak diredistribusikan. Setiap baris menyimpan URL sumbernya.

---

# BAB II TINJAUAN PUSTAKA

## 2.1 Digitalisasi UMKM dan Hambatan Onboarding di Marketplace

UMKM Indonesia berjumlah 64,2 juta dengan kontribusi 61,07% terhadap PDB dan penyerapan 97% tenaga kerja [1]. Survei e-commerce Badan Pusat Statistik mencatat 3,82 juta usaha e-commerce per 31 Desember 2023, dengan dominasi kelompok usaha mikro pada sektor perdagangan dan industri pengolahan [2].

Kajian mengenai transformasi digital UMKM umumnya berhenti pada tingkat kebijakan dan literasi: berapa banyak UMKM yang sudah terhubung platform digital, dan program apa yang mempercepatnya. Pertanyaan operasional yang dihadapi penjual pada menit pertama, yaitu bagaimana mengisi kolom judul dan menentukan angka pada kolom harga, jarang diperlakukan sebagai persoalan teknis yang dapat diotomatisasi.

**Celah yang tersisa.** Literatur digitalisasi UMKM memetakan hambatan pada tingkat agregat, tetapi tidak menyediakan alat yang bekerja pada satu produk milik satu penjual. LAPAKIN mengisi ruang itu.

## 2.2 Vision-Language Model dan Large Language Model Open-Weights

Gemma 3 merupakan keluarga model *open-weights* berukuran 1 sampai 27 miliar parameter yang menambahkan kemampuan pemahaman visual, cakupan bahasa yang lebih luas, dan konteks minimal 128 ribu token. Arsitekturnya menaikkan rasio lapisan atensi lokal terhadap global untuk menekan konsumsi memori KV-*cache* pada konteks panjang [5]. Sifat itu penting bagi LAPAKIN karena pipeline dijalankan pada satu kartu grafis 8 GB.

Qwen2.5 merupakan seri model bahasa yang dilatih pada 18 triliun token dengan penyempurnaan pasca-pelatihan berupa *supervised finetuning* lebih dari satu juta sampel dan pembelajaran penguatan bertahap, yang menaikkan kemampuan pembangkitan teks panjang dan kepatuhan pada instruksi [6]. LAPAKIN memakai varian 7 miliar parameter untuk menyusun judul dan deskripsi.

**Celah yang tersisa.** Kedua laporan teknis melaporkan kinerja pada tolok ukur umum. Keduanya tidak menjawab apakah model berukuran 4B dan 7B cukup untuk menulis listing marketplace berbahasa Indonesia yang patuh pada gaya tiap platform. Subbab 3.3 menjawabnya secara empiris.

## 2.3 Halusinasi pada Vision-Language Model dan Strategi Mitigasinya

Survei Liu dkk. mendefinisikan halusinasi pada *Large Vision-Language Model* sebagai ketidakselarasan antara isi visual faktual dan teks yang dihasilkan, lalu meninjau metode mitigasi yang menyasar data pelatihan, komponen model, dan metodologi evaluasi [7].

Bagi LAPAKIN, halusinasi bukan persoalan akademik. Judul yang menyebut merek milik produk lain berpotensi melanggar hak merek. Judul yang menyebut "500ml" untuk botol 200 ml membuat penjual berhadapan dengan tuntutan pembeli. Kesalahan jenis ini harus mencapai nol, bukan sekadar berkurang.

**Celah yang tersisa.** Metode mitigasi pada survei tersebut bekerja di dalam model, melalui pengubahan strategi *decoding* atau penyetelan komponen, sehingga menuntut akses dan sumber daya komputasi. LAPAKIN menempuh jalur lain: memverifikasi keluaran terhadap katalog dan terhadap keluaran tahap penglihatan setelah teks selesai ditulis, dengan biaya komputasi yang mendekati nol.

## 2.4 Temu Kembali Informasi TF-IDF, Representasi Visual Bersama, dan Retrieval-Augmented Generation

Spärck Jones mengusulkan pembobotan istilah menurut frekuensi kemunculannya pada koleksi, sehingga kecocokan pada istilah yang jarang bernilai lebih tinggi daripada kecocokan pada istilah yang sering muncul. Ukuran tersebut kemudian dikenal sebagai *inverse document frequency* [8].

Lewis dkk. memperkenalkan *Retrieval-Augmented Generation*, yaitu penggabungan memori parametrik model terlatih dengan memori non-parametrik berupa indeks yang dapat ditelusuri. Model yang memakai pendekatan ini menghasilkan keluaran yang lebih spesifik dan lebih faktual dibanding model yang hanya mengandalkan parameter [9].

Penerapannya pada domain e-commerce dilaporkan Zhang, Nakatani, dan Walter. Mereka mengambil contoh dwibahasa yang mirip dari katalog produk lalu memakainya sebagai *few-shot prompt* untuk penerjemahan judul produk, dan mencatat kenaikan skor chrF hingga 15,3% pada pasangan bahasa yang penguasaan modelnya terbatas [10].

Radford dkk. melatih CLIP pada 400 juta pasangan gambar dan teks, menghasilkan ruang representasi bersama tempat gambar dan teks dapat dibandingkan secara langsung. Model tersebut mencapai kinerja *zero-shot* yang bersaing dengan model terlatih khusus pada sejumlah tugas klasifikasi tanpa memerlukan contoh berlabel [11].

**Celah yang tersisa.** Pekerjaan Zhang dkk. menerjemahkan judul yang sudah ada. LAPAKIN menyusun judul dari foto, sehingga tidak tersedia teks sumber untuk dicocokkan. Kueri temu kembali pada LAPAKIN harus dibangkitkan terlebih dahulu oleh tahap penglihatan, dan mutu temu kembali bergantung pada mutu kueri tersebut. Ketergantungan berantai inilah yang membuat temu kembali murni teks rapuh: satu kata keliru pada keluaran tahap penglihatan cukup untuk menarik produk pembanding dari kategori yang sama sekali berbeda. LAPAKIN karena itu memakai representasi visual bersama sebagai jalur kedua yang tidak melewati kueri teks sama sekali.

## 2.5 Cost-Plus Pricing, Market-Based Pricing, dan Koridor Harga

Stromeyer dan Kurz meneliti penetapan harga pada UKM sektor barang modal dan mengusulkan kerangka *Weighted Dynamic Corridor Price Optimisation*. Kerangka itu menetapkan harga minimum dari biaya produksi dan tujuan strategis, sedangkan harga maksimum mencerminkan nilai yang dipersepsikan pelanggan, ambang harga psikologis, dan dinamika pasar. Penulisnya menyatakan pendekatan koridor menekan risiko harga terlalu tinggi maupun terlalu rendah dibanding penerapan *cost-plus* murni [4].

Kritik terhadap *cost-plus pricing* berpusat pada satu titik: metode itu menetapkan harga dari biaya produksi tanpa memperhitungkan nilai yang bersedia dibayar pelanggan, sehingga harga dapat menyimpang jauh dari pasar [4].

**Celah yang tersisa.** Kerangka koridor Stromeyer dan Kurz menargetkan UKM barang modal, yang jumlah transaksinya sedikit dengan nilai per transaksi besar, dan batas atas koridornya diperoleh dari survei persepsi pelanggan. UMKM marketplace berada pada kondisi sebaliknya: transaksi banyak bernilai kecil, dan persepsi pelanggan tidak dapat disurvei per produk. LAPAKIN mengambil struktur koridornya, lalu mengganti sumber batas atas dengan persentil harga produk sejenis pada katalog, dan mengganti batas bawah dengan titik impas yang sudah memperhitungkan komisi platform dan pajak.

## 2.6 Posisi LAPAKIN terhadap Penelitian Terdahulu

| Aspek | Penelitian terdahulu | Posisi LAPAKIN |
|---|---|---|
| Sumber contoh *few-shot* | Katalog dwibahasa untuk penerjemahan judul [10] | Katalog satu bahasa untuk penyusunan judul dari foto |
| Jalur temu kembali | Kemiripan teks terhadap teks sumber [10] | Hibrida: TF-IDF pada judul dan CLIP [11] pada gambar, karena teks sumber tidak ada |
| Penanganan barang di luar katalog | Tidak dibahas | Ditandai asing di bawah ambang 0,80; katalog tidak dipakai dan harga tidak ditebak |
| Mitigasi halusinasi | Intervensi di dalam model [7] | Verifikasi pasca-generasi terhadap katalog dan keluaran tahap penglihatan |
| Batas bawah harga | Biaya produksi dan tujuan strategis [4] | Titik impas setelah komisi platform, biaya pemrosesan, dan PPh Final |
| Batas atas harga | Survei persepsi pelanggan [4] | Persentil harga produk sejenis pada katalog 28.443 produk |
| Peran dataset | Data latih | Rujukan saat inferensi, tanpa pelatihan ulang |

---

# BAB III METODOLOGI

## 3.1 Arsitektur Sistem LAPAKIN

Sistem terdiri atas empat fitur. Tiga yang pertama memakai model AI; yang keempat sengaja tidak.

```
Foto produk
   │
   ├─► Fitur 1: Ekstraksi fakta visual (gemma3:4b)
   │      keluaran: fakta yang terlihat pada foto
   │
   ├─► Fitur 2: Temu kembali katalog (hibrida, 28.443 produk)
   │      TF-IDF atas judul + CLIP ViT-B-32 atas 28.093 gambar
   │      keluaran: produk pembanding, kosakata platform,
   │               sebaran harga kategori (P25, median, P75),
   │               penanda barang asing bila skor visual < 0,80
   │
   ├─► Fitur 3: Penyusunan listing + penjaga bukti (qwen2.5:7b)
   │      keluaran: judul, deskripsi, kategori per platform
   │
   └─► Fitur 4: Penetapan harga Market-First (deterministik)
          masukan: HPP penjual, platform tujuan, sebaran harga
          keluaran: titik impas, zona, harga rekomendasi, rincian
```

**Gambar 3.1** Alur empat fitur LAPAKIN

Sebagaimana ditunjukkan pada Gambar 3.1, Fitur 4 tidak memanggil model apa pun. Seluruh keluarannya berupa hasil aritmetika atas parameter yang tercatat pada berkas konfigurasi. Alasan pemilihan pendekatan ini dibahas pada Subbab 3.5.3.

## 3.2 Alur Memperoleh Dataset

### 3.2.1 Sumber dan penggabungan

Katalog rujukan menggabungkan tiga sumber: 8.800 produk Blibli, 18.443 produk Tokopedia, dan 1.200 produk dari dataset Tokopedia 2025 — seluruhnya **28.443 baris dengan 25 kolom**. Hasil penggabungan diverifikasi baris demi baris terhadap ekspor sumbernya, dengan hasil nol baris hilang dan nol perubahan pada kolom judul, harga, deskripsi, kategori, maupun gambar.

Dari katalog itu diturunkan **27.997 pasangan latih** gambar → judul bersih melalui `scripts/build_train_pairs.py`. Targetnya judul yang sudah dibersihkan, bukan deskripsi: judul memuat jenis produk, merek, varian, dan ukuran — hampir semuanya terlihat pada foto, sedangkan deskripsi penuh spesifikasi yang tidak terlihat seperti berat kirim, garansi, dan isi karton.

### 3.2.2 Prosedur pengambilan

Pengumpulan Tokopedia berjalan dua tahap, dan urutannya wajib. Tahap pertama mengambil daftar produk dari hasil pencarian. Tahap kedua mengambil deskripsi lengkap dan galeri gambar dari halaman produk. Alasannya teknis: URL *thumbnail* dari hasil pencarian memakai tanda tangan yang kedaluwarsa dalam hitungan jam, sedangkan URL galeri dari halaman produk tidak bertanda tangan.

Setiap *response* mentah disimpan sebelum diparse. Konsekuensinya, perbaikan parser tidak pernah menuntut pengumpulan ulang — cukup `python main.py reparse`.

### 3.2.3 Batas dan etika pengambilan

Pengumpulan dijalankan dengan *concurrency* 1, jeda acak 2 sampai 5 detik antar-*request*, dan pemutus arus yang menghentikan proses setelah sepuluh kegagalan beruntun. Sistem tidak memuat pemecah CAPTCHA. Dataset tidak diredistribusikan dan setiap baris menyimpan URL sumbernya.

### 3.2.4 Karakter dan cacat dataset

Tahap pertama pengumpulan Tokopedia menghasilkan 18.997 produk unik dari 221 *request* dalam sekitar 21 menit tanpa satu pun galat, berasal dari 8.695 toko berbeda dengan toko terbesar menyumbang 0,61% dataset. Tahap kedua pada sampel 602 produk menghasilkan deskripsi teks untuk 96,7% produk dengan median 988 karakter, pada laju sekitar 3,5 detik per produk. Dari 28.443 baris gabungan, 28.093 (98,8%) memiliki minimal satu berkas gambar lokal yang sudah diverifikasi keberadaannya.

Enam temuan berikut muncul setelah data terkumpul, dan seluruhnya membatasi cara dataset boleh dipakai.

**Tabel 3.1** Temuan yang membatasi pemakaian dataset

| Temuan | Angka | Konsekuensi |
|---|---|---|
| Gambar Tokopedia 2025 hilang | 9.614 berkas; 311 dari 1.200 produk tanpa gambar | Sumber tidak menyimpan URL CDN, tidak dapat diunduh ulang |
| Label kategori lemah | 37,8% `lainnya`; 55,2% hasil pencocokan kata kunci | Seluruh sebaran harga per kategori mewarisi kelemahan ini |
| Nomor telepon pada deskripsi | 4,3% baris | Data pribadi, wajib dibuang sebelum pemakaian apa pun |
| Deskripsi bukan teks jualan | 33,6% memuat ALL CAPS panjang; 20,9% membahas ongkir dan pengemasan | Perlu penyaringan sebelum dipakai sebagai contoh gaya |
| Duplikasi | 2.228 baris berjudul kembar; 4.280 baris berdeskripsi identik | Pemisahan *train* dan *test* wajib per grup, bukan acak |
| Ketimpangan sumber dan kategori | Tokopedia 65% baris; `fashion_perawatan` 7.566 lawan `minuman_herbal` 1.796 | Rujukan harga lebih kuat pada kategori besar |

Ditemukan pula 632 harga yang tidak masuk akal (3,3%), misalnya kaos seharga Rp1.999.960.000. *Response* mentahnya memang memuat angka tersebut, sehingga ini bukan kegagalan parser melainkan kesalahan ketik penjual. Notebook `03_eda_dataset.ipynb` mendeteksinya per kategori memakai *Median Absolute Deviation* pada logaritma harga.

## 3.3 Alur Pengembangan Model per Fitur

### 3.3.1 Fitur 1 — Ekstraksi fakta visual

**Pertanyaan yang dijawab lebih dulu.** Sebelum memilih model, `scripts/probe_vlm_baseline.py` dijalankan untuk menguji apakah model dasar sudah mampu menyebut bendanya dengan benar. Dua model dibandingkan pada 100 gambar yang sama.

**Tabel 3.2** Perbandingan model visual, n=100 gambar

| Model | Skor inti | Keluaran bocor |
|---|---|---|
| `gemma3:4b` | **0,483** | **0** |
| `qwen3-vl:4b` | 0,371 | 11 |

Sebagaimana ditunjukkan pada Tabel 3.2, `gemma3:4b` unggul pada kedua ukuran dan dipilih untuk tahap penglihatan. Uji lanjutan menaikkan ukuran model dari 4B ke 7B pada 100 gambar yang sama menghasilkan skor inti 0,483 lawan 0,468 — kenaikan ukuran model tidak memperbaiki cacat halusinasi merek sama sekali. Temuan ini yang mengarahkan pekerjaan berikutnya ke verifikasi pasca-generasi, bukan ke model yang lebih besar.

**Keluaran fitur.** Daftar fakta yang terbaca pada foto: jenis barang, warna, bentuk kemasan, dan teks yang benar-benar tercetak. Daftar ini berperan ganda — sebagai bahan penulisan dan sebagai *bukti* yang dipakai penjaga pada Fitur 3.

### 3.3.2 Fitur 2 — Temu kembali katalog

Temu kembali berjalan pada dua jalur yang saling menutup kelemahan: TF-IDF pada judul dan kemiripan visual pada gambar. Indeks TF-IDF dibangun di atas judul bersih 28.443 produk. Pembobotan mengikuti prinsip *inverse document frequency* [8]: kecocokan pada istilah yang jarang bernilai lebih tinggi daripada kecocokan pada istilah yang sering muncul.

Kueri disusun dari keluaran Fitur 1. Keluarannya tiga hal: produk pembanding, kosakata khas platform tujuan, dan sebaran harga kategori berupa persentil 25, median, dan persentil 75.

Peran katalog di sini adalah memori non-parametrik yang dapat ditelusuri, seperti pada *Retrieval-Augmented Generation* [9]: katalog dipakai **saat inferensi**, sehingga penambahan atau pembaruan produk tidak menuntut pelatihan ulang.

`scripts/build_platform_profiles.py` menurunkan profil gaya per platform langsung dari data: panjang judul lazim, pemakaian tanda garis miring, panjang deskripsi, sebaran harga per kategori, dan kosakata khas tiap platform.

**Pencarian berbasis kemiripan gambar.** Pencarian teks dapat tersesat pada satu kata. Gaun Eprise seharga Rp479.800 memperoleh produk pembanding berupa parfum, karena kata "Rose" pada keluaran Fitur 1 cukup untuk menariknya, lalu disarankan Rp176.000. `scripts/build_image_index.py` menutup celah ini dengan mengubah 28.093 gambar utama menjadi vektor CLIP ViT-B-32 [11] dalam 7,5 menit pada kartu grafis RTX 5050, menghasilkan indeks berukuran 26 MB. Satu gambar diambil per produk, bukan seluruh galeri: produk Tokopedia memuat rata-rata tujuh foto, dan memakai seluruhnya membuat produk tersebut tujuh kali lebih mungkin terpilih sebagai pembanding hanya karena difoto lebih banyak. Pada kasus Eprise, pembandingnya berubah menjadi produk lini Eprise warna lain dengan saran Rp579.800, dan skor inti pada mode gambar naik dari 0,351 menjadi 0,550.

**Ambang barang asing.** Skor kemiripan visual di bawah 0,80 menandai produk sebagai asing bagi katalog. Ambang ini diturunkan dari sebaran nyata, bukan dipilih bulat: produk yang memiliki padanan di katalog seluruhnya memperoleh skor minimal 0,91, sedangkan yang tidak memiliki padanan jatuh pada 0,67 sampai 0,77. Di bawah ambang, konteks katalog tidak dipakai sama sekali dan harga tidak ditebak, melainkan ditandai perlu ditentukan penjual. Mekanisme ini menutup sumber halusinasi yang khas: nama "Longchamp" dan "altraze" dahulu masuk ke listing sebagai merek pinjaman dari produk yang kebetulan mirip rupanya.

**Eksklusi indeks pada pengujian.** Saat sebuah produk diuji, produk itu sendiri beserta kerabatnya dibuang dari indeks melalui `--eksklusi`. Tanpa ini, gaun "Eprise Midi Hitam" menemukan "Eprise Midi Blue" lalu nyaris menyalinnya, dan angka yang dihasilkan mengukur penyalinan, bukan penyusunan. Tiga tingkat tersedia: `diri` membuang produk itu saja, `lini` menambahkan seluruh produk dengan kata pertama judul yang sama (74 produk Eprise), dan `kategori` menambahkan seluruh kategorinya (7.537 produk `fashion_perawatan`). Blokir diterapkan sebelum pengurutan skor, bukan menyaring hasil teratas sesudahnya, karena penyaringan belakangan dapat menyisakan nol pembanding tanpa peringatan. Pengaruh ketiga tingkat terhadap hasil dilaporkan pada Tabel 3.5.

### 3.3.3 Fitur 3 — Penyusunan listing dan penjaga bukti

Tahap penulisan menerima fakta visual bersama dua contoh judul nyata dari platform tujuan untuk produk semirip mungkin, dengan angka pada contoh disamarkan agar tidak tersalin. Keluarannya kemudian diperiksa penjaga pasca-generasi, yang memperlakukan kata dan angka secara berbeda.

**Untuk kata.** `scripts/build_lexicon.py` memanen kamus dari katalog. Kandidat merek diambil dari kolom `brand` Blibli dan dari kata pembuka judul yang muncul minimal tiga kali. Kata jenis barang diambil dari kata yang sering muncul dan tersebar pada minimal empat kategori. Kata jenis selalu lolos. Kata spesifik hanya lolos bila muncul pada keluaran Fitur 1 atau pada judul produk pembanding.

Definisi merek disempurnakan setelah kata "gaming" ikut terbuang karena ada toko bernama demikian. Aturan diubah: sebuah kata dianggap merek bila minimal 50% kemunculannya berada pada posisi kata pertama judul — merek berperilaku demikian, kata deskriptif tidak. Daftar merek menyusut dari 1.934 menjadi 1.642 kandidat, "gaming" keluar, "fantech" tetap masuk.

**Untuk angka.** Angka dan satuan diperlakukan lebih ketat: hanya foto yang berlaku sebagai bukti, katalog tidak. Produk pembanding boleh berukuran 500 ml sementara botol pada foto berukuran 200 ml. Kode varian yang benar-benar terbaca tetap lolos.

Aturan ini menutup celah yang ditemukan saat membaca keluaran. Kata "ZARA" sempat lolos ke judul gaun tanpa merek karena merek tersebut muncul pada judul produk pembanding. Dukungan katalog kemudian dinyatakan tidak lagi mengesahkan kata langka, dengan alasan merek milik produk lain bukan bukti untuk foto yang sedang diproses.

**Hasil ablasi.** Sembilan konfigurasi dijalankan pada 10 produk yang sama, 30 listing per konfigurasi, pada mesin dan model yang sama.

**Tabel 3.3** Ablasi komponen pipeline listing, n=10 produk, 30 listing per konfigurasi, `--eksklusi diri`

| Konfigurasi | Harga meleset | Merek karangan (sempit) | Merek (lebar) | Panjang patuh | Inti | Detik |
|---|---|---|---|---|---|---|
| A semua perbaikan mati | 34,4% | 6,9% | 20,7% | 13,8% | 0,292 | 20,3 |
| B penjaga galak | 2,6% | 0,0% | 3,3% | 80,0% | 0,393 | 18,4 |
| C tanpa hitung harga | 2,6% | 0,0% | 10,3% | 82,8% | 0,399 | 18,4 |
| D tanpa saring merek | 2,6% | **17,2%** | 27,6% | 75,9% | 0,384 | 18,5 |
| E tanpa contoh pola, dengan pemanjangan | 2,6% | 0,0% | 13,8% | **20,7%** | 0,278 | 18,4 |
| F penjaga presisi | 2,6% | 0,0% | 10,0% | 76,7% | **0,403** | 18,4 |
| G F ditambah penanganan frasa merek | 2,6% | 0,0% | 13,3% | 80,0% | 0,387 | 18,7 |
| I penjaga angka dan aturan bukti | 2,6% | **0,0%** | 17,2% | 79,3% | **0,399** | **17,8** |
| **M I ditambah penanganan deskripsi (final)** | **2,6%** | **0,0%** | 13,3% | **82,8%** | 0,351 | 28,6 |

Seluruh baris pada Tabel 3.3 dijalankan dengan produk uji masih berada di dalam indeks. Kolom Inti dan Harga meleset karenanya merupakan batas atas, bukan angka yang mewakili pemakaian nyata; koreksinya dilaporkan pada Tabel 3.5. Kolom Merek karangan dan spesifikasi karangan tidak terpengaruh, dan alasannya dijelaskan setelah tabel tersebut.

Perbandingan D lawan F pada Tabel 3.3 menunjukkan efek terbesar pada pekerjaan ini: halusinasi merek pada ukuran sempit turun dari **17,2% menjadi 0,0%**. Contoh yang tertangkap penjaga mencakup "Fantech" yang masuk ke judul keyboard karena merek itu ada pada kosakata khas platform, "Altraze" pada tas tanpa merek, dan "Longchamp" pada tas biasa.

Penjaga merek memeriksa kata, sehingga angka lolos bebas. Model menuliskan "Shampoo 500ml", "Softergent 200g", dan "20 Sachet" untuk foto yang tidak memuat satu pun angka tersebut. Setelah aturan bukti foto diberlakukan pada konfigurasi I, spesifikasi karangan turun dari **10,0% menjadi 0,0%**.

Perbandingan E lawan B menunjukkan kepatuhan panjang judul naik dari **20,7% menjadi 80,0%**.

**Tabel 3.4** Panjang judul rata-rata (kata) terhadap rentang lazim tiap platform

| Konfigurasi | Blibli | Tokopedia | Shopee |
|---|---|---|---|
| Target dari data | 6–11 | 10–20 | 8–15 |
| A | 5 | 6 | 4 |
| B | 6 | 10 | 8 |

Tiga putaran perbaikan *prompt* sebelumnya gagal menggeser panjang judul sama sekali. Model 4B dan 7B mengabaikan instruksi panjang seberapa pun tegasnya. Yang berhasil justru mengerjakan penyesuaian panjang **di luar model**, dengan menambahkan kata kunci pendukung dari judul produk pembanding.

**Penanganan pelanggaran pada deskripsi.** Metrik deskripsi disusun setelah penjaga judul selesai, dan begitu tersedia, tampak bahwa risikonya tidak hilang melainkan berpindah tempat: merek yang sudah disaring dari judul tetap hidup di deskripsi, dalam bentuk "Tas Longchamp" dan "teknologi altraze". Tiga cara diuji terpisah pada 10 produk yang sama sebelum digabungkan.

**Tabel 3.5** Penanganan pelanggaran deskripsi, n=10 produk, 29 deskripsi

| Cara | Klaim berisiko | Kata tak berdasar | Angka karangan | Panjang (karakter) | Mengulang judul |
|---|---|---|---|---|---|
| Tanpa penanganan | 6,9% | 20,7% | 3,4% | 112 | 0,0% |
| (a) Membuang kalimat | 0,0% | 0,0% | 0,0% | **85** | **7,4%** |
| (b) Menulis ulang | 0,0% | 6,9% | 3,4% | 127 | 0,0% |
| (c) Larangan pada *prompt* | 3,3% | 20,0% | 0,0% | 122 | 0,0% |
| **Kombinasi bertingkat (final)** | **0,0%** | **0,0%** | **0,0%** | **123** | **0,0%** |

Ketiganya memiliki kelemahan sendiri. Cara (a) menjamin bersih tetapi memangkas isi: satu kata bermasalah membuang seluruh kalimatnya, dan 7,4% deskripsi berakhir hanya mengulang judul. Cara (b) mempertahankan isi tetapi menyisakan 6,9% kata tak berdasar. Cara (c) paling murah dan menghabiskan angka karangan, tetapi tidak menggeser kata tak berdasar sama sekali, dari 20,7% menjadi 20,0% — melarang daftar kata pada *prompt* tidak mencegah model mengarang merek. Konfigurasi final memakai ketiganya bertingkat dan mencapai 0,0% pada seluruh jenis pelanggaran dengan panjang isi 123 karakter, dengan biaya 11 detik per produk. Dari 29 deskripsi, 24% memerlukan penulisan ulang dan 10% masih melanggar sesudahnya sehingga kalimatnya dibuang; lapis ketiga bukan hiasan.

**Pengaruh kebocoran indeks terhadap seluruh angka di atas.** Seluruh tabel sebelumnya dijalankan pada tingkat eksklusi `diri`. Pengujian ulang pada ketiga tingkat yang dijelaskan pada Subbab 3.3.2 memberi hasil berikut.

**Tabel 3.6** Pengaruh tingkat eksklusi indeks, n=10 produk, 30 listing per tingkat

| Tingkat eksklusi | Produk dikenal | Skor pembanding | Inti | Harga ditebak | Merek karangan (sempit) | Spesifikasi karangan |
|---|---|---|---|---|---|---|
| `diri` | 7/10 | 0,93 | 0,474 | 21/30 | **0,0%** | **0,0%** |
| **`lini`** | **5/10** | **0,81** | **0,269** | **15/30** | **0,0%** | **0,0%** |
| `kategori` | 2/10 | 0,62 | 0,239 | 6/30 | **0,0%** | **0,0%** |

Tingkat `lini` adalah yang mewakili keadaan pemakaian sebenarnya: penjual mengunggah produk yang belum ada di katalog, sementara produk sejenis milik penjual lain tersedia. Pada tingkat itu skor inti adalah **0,269**, bukan 0,474 sebagaimana terbaca pada tingkat `diri`.

Dua hal yang perlu dibaca bersamaan dari Tabel 3.6. *Pertama,* mutu penyusunan judul memang bersandar pada ketersediaan pembanding, dan angka yang dilaporkan sebelum eksklusi diberlakukan melebih-lebihkan kemampuan sistem. *Kedua,* halusinasi merek dan spesifikasi karangan tetap **0,0% pada ketiga tingkat**. Ketika pembanding menipis, sistem menurun dengan cara mengaku tidak tahu — produk dikenal jatuh dari 7/10 ke 2/10 dan harga yang ditebak dari 21/30 ke 6/30 — bukan dengan mengarang. Klaim utama pekerjaan ini, bahwa verifikasi pasca-generasi menghapus halusinasi merek, karena itu tidak bersandar pada kebocoran indeks. Klaim mengenai skor inti bersandar padanya, dan angkanya dikoreksi di sini.

### 3.3.4 Fitur 4 — Penetapan harga Market-First

**Langkah 1.** Menentukan harga pasar dari median harga produk pembanding hasil Fitur 2, beserta persentil 25 dan 75.

**Langkah 2.** Menghitung titik impas:

```
Harga_BEP = HPP_per_unit / (1 − Total_Potongan)
```

`Total_Potongan` menjumlahkan komisi platform, biaya Gratis Ongkir bila berlaku, biaya pemrosesan pesanan, dan PPh Final. Nilai per platform per kategori tercatat pada berkas konfigurasi beserta tanggal berlakunya (Lampiran 3).

**Langkah 3.** Menempatkan titik impas terhadap persentil harga pasar.

**Tabel 3.7** Zona keputusan harga

| Zona | Syarat | Arti |
|---|---|---|
| BAGUS | BEP ≤ P25 | Modal rendah, ruang margin lebar |
| WAJAR | P25 < BEP ≤ median | Posisi kompetitif normal |
| KETAT | median < BEP ≤ P75 | Dapat menjual dengan margin tipis |
| BAHAYA | BEP > P75 | Modal terlalu tinggi untuk bersaing |

**Langkah 4.** Menentukan harga rekomendasi menurut zona. Zona BAGUS memakai median pasar. Zona WAJAR menjepit median pasar antara BEP dikali 1,20 dan P75. Zona KETAT menjepit BEP dikali 1,15 antara median dan P75. Zona BAHAYA menampilkan peringatan bahwa modal terlalu tinggi, menyertakan saran taktis, dan tetap menyajikan angka P75 dengan penjelasan risikonya.

Perancangan zona BAHAYA menjawab kelemahan *cost-plus* yang dikritik pada Subbab 2.5. Model versi pertama pada proyek ini mengalami cacat yang sama: ketika HPP ditambah margin menghasilkan Rp54.900 sementara P25 pasar berada di Rp35.000, model tetap merekomendasikan Rp54.900. Versi *Market-First* menolak menaikkan harga melampaui pasar dan memilih memperingatkan penjual.

**Hasil.** Proporsi harga meleset turun dari 34,4% pada konfigurasi A menjadi 2,6% pada seluruh konfigurasi lain; enam dari sembilan produk menghasilkan harga yang persis sama di semua konfigurasi. Penyebab perbaikan ini berbeda dari yang diperkirakan pada tahap perancangan. Masalah awalnya terletak pada satu kalimat *prompt* yang meminta model memakai rentang harga kategori sebagai dasar perkiraan; kategori `lainnya` membentang dari Rp21 ribu sampai Rp969 ribu, sehingga patokan tersebut tidak bermakna. Setelah kalimat itu diubah menjadi arahan yang mengutamakan harga produk pembanding, harga langsung mendarat pada angka katalog.

Penghitung harga deterministik versi awal yang ditambahkan sebagai komponen terpisah **tidak memberi perbaikan yang terukur**: konfigurasi C menjalankannya dalam keadaan mati dan tetap menghasilkan 2,6%. Klaim yang dapat dipertanggungjawabkan adalah bahwa perbaikan berasal dari pembetulan *prompt*, dan buktinya harga kini menempel pada katalog, bukan pada tengah rentang kategori.

Angka 2,6% tersebut berlaku pada tingkat eksklusi `diri`, yaitu ketika produk uji sendiri dibuang dari indeks tetapi kerabatnya tidak. Pada tingkat `lini`, harga yang ditebak model naik menjadi 15 dari 30 listing (Tabel 3.6). Kalimat "harga mendarat pada angka katalog" karena itu perlu dibaca dengan syaratnya: harga mendarat pada angka katalog **ketika produk kembarnya memang ada di katalog**. Untuk produk yang benar-benar baru, sistem tidak menebak melainkan menandai harga perlu ditentukan penjual, dan di situlah Fitur 4 mengambil alih.

Mode pencarian gambar mengubah gambaran ini dan tidak seluruhnya ke arah yang baik. Proporsi harga meleset naik dari 2,6% menjadi 20,8%. Penelusuran keluaran menunjukkan sebabnya bukan mutu pencarian gambar: mode tersebut menghabiskan kesalahan besar, dari 63% menjadi 0%, dan menambah kesalahan kecil, karena produk yang rupanya mirip belum tentu sekelas harga. Kedua jenis kesalahan menuntut penanganan terpisah dan itu belum dikerjakan; angka gabungannya dilaporkan apa adanya.

`scripts/pricing_engine.py` versi *Market-First* menggantikan penghitung awal tersebut dan kini terintegrasi ke pipeline melalui `--hpp`. **Efek integrasi ini terhadap kelima metrik listing belum diukur** — perintah ablasinya tercantum pada Lampiran 2 dan hasilnya akan menggantikan paragraf ini begitu tersedia.

### 3.3.5 Status penyesuaian model

Ketentuan lomba mewajibkan model disesuaikan (*fine-tune*) menurut inovasi fitur tiap tim. Status faktual pekerjaan ini per penyusunan dokumen:

**Tabel 3.8** Status penyesuaian model per komponen

| Komponen | Status | Bukti di repo |
|---|---|---|
| Pasangan latih gambar → judul bersih | **Siap**, 27.997 pasangan | `scripts/build_train_pairs.py` → `train_pairs.parquet` |
| Uji kebutuhan *fine-tune* pada tahap penglihatan | **Selesai** | `scripts/probe_vlm_baseline.py`, n=100 |
| *Fine-tune* Fitur 1 dan Fitur 3 | **Belum dijalankan** | — |
| Pembanding satu model besar tanpa retrieval | **Skrip siap, belum dijalankan** | `scripts/baseline_besar.py`, `paket_sesi1/sesi1.sh` |
| *Fine-tune* Fitur 4 | **Tidak dilakukan, disengaja** | Alasan pada Subbab 3.5.3 |

Pembanding satu model besar disiapkan untuk menjawab pertanyaan yang mendahului keputusan *fine-tune*: apakah pipeline 4B ditambah retrieval dan penjaga benar-benar mengungguli satu model yang tiga kali lebih besar bekerja sendirian. Pembandingnya sengaja `gemma3:12b`, satu keluarga dengan `gemma3:4b` dan tepat tiga kali parameternya, sehingga selisih yang terukur berasal dari ukuran model dan bukan dari perbedaan data latih. Skrip dan paket penjalannya sudah ada; angkanya belum, dan tidak dituliskan mendahului artefaknya.

Fitur 4 tidak akan disesuaikan dalam bentuk apa pun, dan itu keputusan desain yang dipertahankan: harga jual ditentukan HPP penjual, tarif komisi, dan tarif pajak — tiga besaran eksak yang berubah lewat peraturan, bukan pola yang dapat dipelajari dari data. Fitur 1 dan Fitur 3 adalah tempat penyesuaian model relevan, dan pasangan latihnya sudah tersedia; yang belum ada adalah bobot hasil latih beserta angka pembandingnya terhadap keluaran *prompt-only*. Sesuai aturan penulisan proyek ini, klaim tidak dituliskan mendahului artefaknya.

## 3.4 Alur Integrasi Model ke Environment Kode

### 3.4.1 Pemisahan dua fase dan alasannya

Pemisahan Fitur 1 dan Fitur 3 bukan pilihan gaya. Kartu grafis 8 GB tidak memuat `gemma3:4b` dan `qwen2.5:7b` sekaligus. Pipeline versi awal memanggil keduanya bergantian untuk setiap produk, sehingga Ollama menukar bobot model dua puluh kali dalam satu *run*: satu *run* 20 produk berjalan 25 menit dan baru menyelesaikan lima produk, setara sekitar **300 detik per produk**. Sebagian besar waktu terpakai untuk memuat bobot, bukan untuk inferensi.

Pipeline diubah menjadi dua fase: seluruh panggilan penglihatan dijalankan lebih dulu, kemudian seluruh panggilan penulisan. Setiap model dimuat satu kali. Waktu turun menjadi **17,8 detik per produk**, dan menjadi 28,6 detik setelah penanganan pelanggaran deskripsi ditambahkan pada konfigurasi final. Perubahan inilah yang memungkinkan sembilan konfigurasi pada Subbab 3.3.3 diuji dalam satu malam.

### 3.4.2 Batas modul

**Tabel 3.9** Pemisahan lapisan sistem

| Lapisan | Isi | Berkas |
|---|---|---|
| Inferensi AI | Panggilan VLM dan LLM, penyusunan *prompt*, penjaga pasca-generasi | `scripts/retrieve_pipeline.py` |
| Aritmetika harga | BEP, zona, harga rekomendasi, rincian biaya | `scripts/pricing_engine.py` |
| Turunan katalog | Kamus merek, profil gaya platform, indeks TF-IDF, indeks gambar CLIP | `scripts/build_lexicon.py`, `build_platform_profiles.py`, `build_image_index.py` |
| Data | Pengambilan, parsing, penyimpanan *response* mentah | `src/tokopedia_scraper/` |
| Konfigurasi | Tarif komisi, biaya pemrosesan, tarif pajak, tanggal berlaku | `config.yaml`, konstanta pada `pricing_engine.py` |

Lapisan aritmetika harga tidak mengimpor apa pun dari lapisan inferensi AI. Konsekuensinya, `pricing_engine.py` dapat diuji tanpa Ollama hidup — `scripts/pricing_demo_offline.py` dan `tests/test_pricing.py` berjalan sepenuhnya luring.

### 3.4.3 Antarmuka dan cara menjalankan

Ruang lingkup MVP mengikuti batasan lomba: antarmuka hanya memuat alur interaksi inti — pengguna mengunggah satu foto dan mengisi HPP, sistem menampilkan judul, deskripsi, kategori, dan rincian harga per platform. Tidak ada dasbor analitik, tidak ada otentikasi, tidak ada halaman riwayat. *Backend* hanya memproses interaksi sinkron; tidak ada *background job* maupun basis data terdistribusi.

Parameter model bersifat statis saat demonstrasi berjalan. Panduan menjalankan sistem secara lokal berada pada `README.md`, dan seluruh layanan dibungkus `docker compose` sehingga penilai dapat menjalankannya tanpa menyiapkan lingkungan Python secara manual.

### 3.4.4 Uji dan reproduksi

Seluruh berkas uji dijalankan luring; `tests/conftest.py` memasang penjaga yang menggagalkan uji apa pun yang menyentuh jaringan. Setiap perbaikan pipeline memiliki sakelar mematikan sendiri — `--tanpa-harga-hitung`, `--tanpa-saring-merek`, `--tanpa-contoh-pola` — sehingga efek tiap komponen dapat dipisahkan dan diukur ulang. Perintah lengkapnya pada Lampiran 2.

## 3.5 Metode Lain yang Mendasari Pengambilan Keputusan

### 3.5.1 Ablasi terkendali sebagai syarat klaim

Aturan kerja proyek ini: klaim perbaikan hanya sah bila ada angka sebelum dan sesudah. Sepuluh produk yang sama (`--n 10 --seed 7`), tiga platform, 30 listing per konfigurasi, dijalankan berurutan pada mesin dan model yang sama. Benih tetap membuat potongan `--iris a:b` selalu memuat produk yang sama, sehingga satu konfigurasi dapat dikerjakan beberapa kali tanpa mengubah sampelnya.

**Tabel 3.10** Definisi metrik evaluasi

| Metrik | Definisi |
|---|---|
| Harga meleset | Proporsi listing dengan harga di luar rentang wajar produk pembanding |
| Merek karangan (sempit) | Nama merek nyata milik produk lain, atau istilah langka di luar kosakata katalog |
| Merek karangan (lebar) | Kata apa pun pada judul yang tidak ada pada keluaran Fitur 1 maupun judul produk pembanding |
| Panjang patuh | Proporsi judul yang panjangnya masuk rentang lazim platform tujuan |
| Inti | Kecocokan judul yang dihasilkan terhadap judul asli produk |
| Spesifikasi karangan | Angka dan satuan pada judul yang tidak terbaca pada foto |
| Kata tak berdasar (deskripsi) | Kata pada deskripsi tanpa dasar pada keluaran Fitur 1 maupun katalog |
| Klaim berisiko | Kata khasiat atau efek yang tidak dapat diverifikasi dari foto |
| Produk dikenal | Proporsi produk uji yang memperoleh pembanding di atas ambang |

**Dua ukuran halusinasi dipakai bersamaan, dan itu disengaja.** Perbandingan B lawan F memperlihatkan jebakan metodologis yang ditemukan di tengah jalan: pada ukuran lebar, B tampak menang (3,3% lawan 10,0%); pada ukuran sempit keduanya sama-sama 0,0%. Ukuran lebar memberi nilai lebih baik kepada penjaga yang lebih galak, karena keduanya memakai definisi "tak berdasar" yang sama. Hal ini hanya ketahuan setelah keluaran dibaca satu per satu — bukan dari tabel angka.

Kejadian yang sama terjadi pada penjaga v1, yang membuang enam kata padahal hanya dua di antaranya benar-benar merek karangan; kata "Pesta", "Pelembut Pakaian", dan "Jogging" ikut terbuang, dan frasa "Merek Tidak Tertera" terpotong menjadi "Gaun Floral Merek Tidak". Versi kedua memakai tiga golongan kata: kata yang memiliki dasar selalu lolos, nama merek yang dikenal wajib memiliki dukungan, dan kata Indonesia lazim (muncul pada minimal 20 produk) dibiarkan. Hasil pada ukuran sempit sama bersihnya dengan kerusakan sampingan jauh lebih sedikit, dan skor inti justru naik menjadi 0,403.

Ablasi yang memburuk tetap dilaporkan pada dokumen ini. Konfigurasi E memperlihatkan kepatuhan panjang jatuh ke 20,7% dan skor inti ke 0,278 — angka terburuk pada Tabel 3.3 — dan tetap dicantumkan karena justru itu yang membuktikan contoh pola bekerja. Hal yang sama berlaku pada mode pencarian gambar, yang menaikkan skor inti tetapi memperburuk akurasi harga (Subbab 3.3.4), dan tetap dilaporkan apa adanya.

**Kebocoran indeks sebagai syarat sahnya seluruh angka di atas.** Kesalahan metodologis terbesar pada pekerjaan ini bukan pada pemilihan metrik, melainkan pada penyusunan pengujian: produk uji dibiarkan berada di dalam indeks yang dicarinya. Sistem karena itu sebagian sedang menyalin, bukan menyusun, dan setiap angka mutu yang dihasilkannya melebih-lebihkan kemampuan sebenarnya. Persoalan ini baru ketahuan setelah keluaran dibaca satu per satu dan tampak gaun "Eprise Midi Hitam" menemukan "Eprise Midi Blue". Koreksinya dilaporkan pada Tabel 3.6, angka lama dipertahankan sebagai batas atas, dan seluruh klaim pada BAB IV memakai tingkat `lini`. Pelajaran metodologisnya sejajar dengan kasus B lawan F: tabel angka tidak dapat mendeteksi kesalahan jenis ini, hanya pembacaan keluaran yang bisa.

### 3.5.2 Verifikasi eksternal dipilih setelah model yang lebih besar gagal

Tiga temuan menunjuk arah yang sama. Menaikkan model dari 4B ke 7B menggeser skor inti dari 0,468 ke 0,483 dan tidak menyentuh halusinasi merek. Tiga putaran perbaikan *prompt* gagal menghilangkan merek karangan. Penjaga pasca-generasi menurunkannya ke 0,0%.

Kedua pembanding tersebut berjarak kecil, 4B lawan 7B, sehingga bantahan yang wajar adalah bahwa lompatan ukuran yang lebih besar mungkin menyelesaikannya. Pembanding `gemma3:12b` yang bekerja sendirian tanpa katalog dan tanpa penjaga disiapkan untuk menutup bantahan itu, dan belum dijalankan (Subbab 3.3.5). Argumen di bawah ini karena itu berdiri pada dua pembanding, bukan tiga.

Penjelasannya terletak pada sifat persoalannya. Merek tercetak pada kemasan dan terdaftar pada katalog, sehingga tugasnya adalah **mencocokkan**, bukan mengingat. Pencocokan dikerjakan lebih baik oleh pencarian pada kamus daripada oleh parameter model. Temuan ini sejalan dengan arah literatur mitigasi halusinasi yang memakai verifikasi terhadap sumber di luar model [7], dan menambahkan satu hal: verifikasi tersebut tidak harus mahal.

### 3.5.3 Mengapa harga tidak diserahkan ke model pembelajaran

Harga jual yang benar bergantung pada empat komponen: Harga Pokok Penjualan milik penjual, tarif komisi platform tujuan, tarif pajak yang berlaku, dan sebaran harga pesaing. Tiga dari empat komponen itu berupa aritmetika bisnis yang eksak.

Model yang dilatih memprediksi harga dari foto hanya akan menghafal harga pasar. Tiga akibatnya konkret. Pertama, penjual tidak dapat memeriksa dari mana angka itu datang, padahal yang ia butuhkan justru rinciannya. Kedua, perubahan tarif komisi menuntut pelatihan ulang, sementara Tokopedia dan Shopee mengubah struktur biaya dua kali dalam rentang Mei sampai Juli 2026. Ketiga, model tidak dapat menyatakan "modal Anda terlalu tinggi untuk bersaing" — ia hanya akan mengeluarkan angka harga pasar tanpa memberi tahu bahwa pada angka itu penjual merugi.

Mesin deterministik menjawab ketiganya: rinciannya dapat dibaca baris demi baris, tarif diperbarui lewat satu berkas konfigurasi, dan zona BAHAYA merupakan keluaran yang sah.

### 3.5.4 Kepatuhan data dan tata kelola

**Tabel 3.11** Keputusan tata kelola data

| Aspek | Keputusan |
|---|---|
| Sifat pengumpulan | Riset non-komersial; *concurrency* 1, jeda 2–5 detik, pemutus arus setelah sepuluh kegagalan beruntun; tanpa pemecah CAPTCHA |
| Redistribusi | Tidak dilakukan; `data/` dan `data_drive/` tidak masuk kendali versi |
| Ketertelusuran | Setiap baris menyimpan URL sumbernya |
| Data pribadi | 4,3% deskripsi memuat nomor telepon penjual; kolom ini wajib disaring sebelum dipakai sebagai contoh gaya |
| Rahasia sesi | Berkas `.env` dan `config/gql_capture.yaml` memuat *cookie* sesi dan tidak masuk kendali versi |
| Hak merek | Penjaga merek menolak nama merek milik produk lain; ini alasan mengapa targetnya 0,0%, bukan sekadar "berkurang" |

Halusinasi merek diperlakukan sebagai persoalan hukum, bukan persoalan mutu tulisan. Judul yang menyebut merek milik produk lain berpotensi melanggar hak merek. Judul yang menyebut "500ml" untuk botol 200 ml membuat penjual berhadapan dengan tuntutan pembeli.

### 3.5.5 Kelayakan adopsi

Biaya operasional sistem mendekati nol pada sisi model: `gemma3:4b` dan `qwen2.5:7b` berjalan lokal pada kartu grafis 8 GB tanpa biaya API per gambar, dengan 28,6 detik per produk. Ini yang membuat pemakaian oleh penjual beromzet di bawah Rp500 juta masuk akal secara ekonomi — segmen yang justru terbesar menurut data BPS [2] dan tidak terjangkau oleh alat berbasis API berbayar.

Biaya pemeliharaan terpusat pada satu titik: tarif komisi dan pajak berubah beberapa kali setahun, dan pembaruannya berupa suntingan satu berkas konfigurasi tanpa pelatihan ulang model apa pun.

## 3.6 Keterbatasan Hasil

1. **Sampel kecil.** Sepuluh produk dan 30 listing per konfigurasi cukup untuk mendeteksi efek besar seperti halusinasi merek dan kepatuhan panjang judul. Sampel ini tidak cukup untuk efek kecil, dan itulah alasan klaim mengenai penghitung harga deterministik tidak diajukan. Perbandingan model visual berjalan pada 100 gambar.
2. **Metrik hanya menguji konsistensi internal.** Halusinasi merek diukur terhadap keluaran Fitur 1 dan katalog, bukan terhadap isi foto. Bila tahap penglihatan salah membaca, metrik ini tidak akan mendeteksinya. Penilaian manusia atas 50 sampai 100 listing diperlukan untuk menutup celah ini.
3. **Metrik dapat menyesatkan bila definisinya sama dengan definisi penjaganya**, sebagaimana kasus B lawan F pada Subbab 3.5.1.
4. **Kategori masih lemah.** Seluruh sebaran harga bersandar pada `kategori_umkm` yang 37,8% jatuh ke kelas `lainnya` dan 55,2% dipetakan lewat pencocokan kata kunci judul.
5. **Kesalahan harga yang tersisa bersifat sistematis.** Gaun Eprise berharga asli Rp479.800 memperoleh saran Rp82 ribu sampai Rp176 ribu karena produk pembandingnya gaun murah. Sepatu Zedruz berharga Rp116.899 memperoleh saran Rp75.000. Pencarian berbasis teks tidak dapat membedakan kelas harga di dalam satu jenis barang. Pencarian gambar menyembuhkan kasus Eprise tetapi memperburuk angka harga secara keseluruhan, sebagaimana dilaporkan pada Subbab 3.3.4; persoalan ini belum tuntas.
6. **Angka mutu penyusunan bersandar pada ketersediaan produk pembanding.** Pada tingkat eksklusi `lini` skor inti adalah 0,269, sedangkan pengujian yang membiarkan kerabat produk tetap di indeks memberi 0,474 (Tabel 3.6). Angka pertama yang dipakai sebagai dasar klaim dokumen ini.
7. **Ketiga rangkaian pengujian yang dilaporkan tidak sebanding satu sama lain.** Skor inti 0,351 pada konfigurasi final, 0,474 pada tingkat eksklusi `diri`, dan 0,550 pada mode pencarian gambar berasal dari tiga rangkaian dengan sakelar berbeda dan tidak boleh disandingkan dalam satu perbandingan. Satu rangkaian tunggal pada n=100 yang mengukur seluruhnya sekaligus sudah disiapkan pada `paket_sesi1/sesi1.sh` dan belum dijalankan.
8. **Tarif platform berlaku pada tanggal tertentu.** Angka komisi yang dipakai berasal dari data Mei sampai Agustus 2026; sistem tidak memantau perubahannya secara otomatis.
9. **Efek integrasi mesin harga *Market-First* ke pipeline belum diukur**, sebagaimana dinyatakan pada Subbab 3.3.4.
10. **Penyesuaian model pada Fitur 1 dan Fitur 3 belum dijalankan**, sebagaimana dinyatakan pada Subbab 3.3.5.

---

# BAB IV KESIMPULAN DAN SARAN

## 4.1 Kesimpulan

1. Pipeline dua tahap yang memakai `gemma3:4b` untuk ekstraksi visual dan `qwen2.5:7b` untuk penyusunan teks menghasilkan judul, deskripsi, dan kategori produk dari satu foto dengan waktu **28,6 detik per produk** pada konfigurasi final berkartu grafis 8 GB, tanpa biaya API. Tanpa penanganan pelanggaran deskripsi waktunya 17,8 detik; selisih 11 detik itu harga yang dibayar untuk menghabiskan klaim berisiko dan merek karangan di dalam deskripsi. Pemecahan pipeline menjadi dua fase memangkas waktu dari sekitar 300 detik per produk.

2. Penjaga pasca-generasi yang memverifikasi keluaran terhadap kamus katalog dan keluaran tahap penglihatan menurunkan halusinasi merek dari **17,2% menjadi 0,0%** dan spesifikasi karangan dari **10,0% menjadi 0,0%** pada ukuran sempit. Menaikkan ukuran model dari 4B ke 7B tidak menyentuh cacat yang sama (skor inti 0,468 lawan 0,483 pada 100 gambar). Untuk persoalan ini, verifikasi eksternal terbukti lebih efektif daripada kapasitas model. Klaim ini bertahan ketika kebocoran indeks ditutup: pada ketiga tingkat eksklusi, termasuk tingkat `kategori` yang membuang 7.537 produk sekategori dari indeks, kedua ukuran tetap 0,0% (Tabel 3.6). Sistem menurun dengan cara mengaku tidak tahu, bukan dengan mengarang.

3. Profil gaya per platform yang diturunkan dari data menaikkan kepatuhan panjang judul dari **20,7% menjadi 80,0%**, setelah tiga putaran perbaikan *prompt* gagal menggeser panjang judul sama sekali. Yang berhasil adalah mengerjakan penyesuaian di luar model.

4. Mesin penetapan harga *Market-First* menghitung titik impas dari HPP, komisi platform, biaya pemrosesan, dan PPh Final, lalu menempatkannya terhadap persentil harga pasar untuk menghasilkan empat zona keputusan. Zona BAHAYA menangani kasus modal terlalu tinggi dengan peringatan, bukan dengan menaikkan harga melampaui pasar — menjawab kelemahan *cost-plus* yang dikritik pada literatur penetapan harga UKM [4].

5. Perbaikan akurasi harga berasal dari pembetulan kalimat *prompt*, bukan dari penghitung deterministik versi awal; ablasi konfigurasi C menunjukkan pipeline tanpa penghitung tersebut tetap mencatat 2,6% harga meleset. Angka itu berlaku pada tingkat eksklusi `diri`; pada tingkat `lini` proporsi harga yang ditebak model naik menjadi 15 dari 30 listing, dan pada mode pencarian gambar proporsi harga meleset naik menjadi 20,8%. Akurasi harga karena itu belum dapat diklaim sebagai hasil yang matang. Penghitung deterministik dipertahankan sebagai jaring pengaman tanpa diklaim sebagai penyumbang angka.

6. Mutu keluaran ditentukan oleh cakupan katalog, dan batas itu terukur. Pada tingkat eksklusi `lini`, produk yang dikenali katalog tinggal 5 dari 10 dan skor inti 0,269. Ini menetapkan arah pengembangan yang paling berpengaruh: memperluas dan memperbaiki katalog memberi pengaruh lebih besar daripada memperbesar model, sebagaimana ditunjukkan pula oleh perbandingan 4B lawan 7B pada butir 2.

7. Katalog 28.443 produk berperan sebagai rujukan saat inferensi. Memperbarui tarif komisi atau tarif pajak menuntut perubahan satu berkas konfigurasi, tanpa pelatihan ulang model — sifat yang penting mengingat tarif berubah dua kali dalam rentang Mei sampai Juli 2026.

## 4.2 Saran

1. **Menyelesaikan penyesuaian model pada Fitur 1 dan Fitur 3.** Pasangan latih 27.997 baris sudah tersedia; yang belum ada adalah bobot hasil latih beserta pembandingnya terhadap keluaran *prompt-only*. Ini pekerjaan terdekat yang harus diselesaikan, sebagaimana dinyatakan pada Subbab 3.3.5.

2. **Mengukur efek integrasi mesin harga ke pipeline.** Perintah ablasinya sudah tercatat pada Lampiran 2 dan tinggal dijalankan.

3. **Memisahkan dua jenis kesalahan harga pada mode pencarian gambar.** Pencarian CLIP sudah terpasang (Subbab 3.3.2) dan menghabiskan kesalahan harga besar, tetapi menambah kesalahan kecil sehingga angka gabungannya memburuk. Arah yang masuk akal: pembanding dipilih lewat kemiripan rupa, kelas harganya disaring lewat isyarat teks.

4. **Memperbaiki label `kategori_umkm`.** Seluruh saran harga bertumpu pada label yang 37,8% jatuh ke kelas `lainnya`. Perbaikan label akan menaikkan mutu setiap keluaran harga sekaligus.

5. **Menjalankan penilaian manusia atas 50 sampai 100 listing.** Metrik otomatis tidak dapat mendeteksi kesalahan baca pada tahap penglihatan.

6. **Menjalankan satu rangkaian pengujian tunggal pada n=100.** Angka-angka pada dokumen ini berasal dari beberapa rangkaian n=10 dengan sakelar berbeda dan tidak sebanding satu sama lain. `paket_sesi1/sesi1.sh` mengukur ketiga tingkat eksklusi beserta pembanding `gemma3:12b` dalam satu jalan; hasilnya menggantikan Tabel 3.3, Tabel 3.5, dan Tabel 3.6. Sepuluh produk cukup untuk efek besar, tidak untuk efek kecil seperti kontribusi penghitung harga deterministik.

7. **Membangun mekanisme pembaruan tarif.** Tarif komisi marketplace berubah beberapa kali dalam setahun. Pemantauan terjadwal atas halaman tarif resmi akan menjaga hasil hitung tetap benar.

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

# Subbab 3.3.1: perbandingan model visual
python scripts/probe_vlm_baseline.py --model gemma3:4b --n 100

# Subbab 3.3.3: ablasi komponen listing
python scripts/retrieve_pipeline.py --n 10 --platform all --iris 0:5  --panjangkan --keluaran data_drive/eval/B.jsonl
python scripts/retrieve_pipeline.py --n 10 --platform all --iris 5:10 --panjangkan --keluaran data_drive/eval/B.jsonl
python scripts/eval_listing.py data_drive/eval/A.jsonl data_drive/eval/B.jsonl

# Subbab 3.3.2: indeks gambar CLIP dan mode pencarian gambar
python scripts/build_image_index.py
python scripts/retrieve_pipeline.py --n 10 --platform all --panjangkan --mode-cari gambar --keluaran data_drive/eval/gambar.jsonl

# Tabel 3.6: pengaruh tingkat eksklusi indeks
python scripts/retrieve_pipeline.py --n 10 --platform all --panjangkan --eksklusi lini      --keluaran data_drive/eval/lini.jsonl
python scripts/retrieve_pipeline.py --n 10 --platform all --panjangkan --eksklusi kategori  --keluaran data_drive/eval/kategori.jsonl
python scripts/eval_listing.py data_drive/eval/lini.jsonl data_drive/eval/kategori.jsonl

# Tabel 3.5: penanganan pelanggaran deskripsi
python scripts/retrieve_pipeline.py --n 10 --platform all --panjangkan --desk-mode kalimat     --keluaran data_drive/eval/desk_a.jsonl
python scripts/retrieve_pipeline.py --n 10 --platform all --panjangkan --desk-mode tulis-ulang --keluaran data_drive/eval/desk_b.jsonl
python scripts/retrieve_pipeline.py --n 10 --platform all --panjangkan --desk-mode prompt      --keluaran data_drive/eval/desk_c.jsonl

# Subbab 3.3.5: pembanding satu model besar, n=100 (BELUM DIJALANKAN)
bash paket_sesi1/sesi1.sh

# Subbab 3.3.4: mesin penetapan harga, luring
python scripts/pricing_demo_offline.py

# Subbab 3.3.4: efek integrasi Market-First ke pipeline (BELUM DIJALANKAN)
python scripts/retrieve_pipeline.py --n 10 --platform all --hpp 25000 --keluaran data_drive/eval/J.jsonl
python scripts/eval_listing.py data_drive/eval/I.jsonl data_drive/eval/J.jsonl

# Subbab 3.2.4: statistik dataset
python main.py stats

# Uji, luring total
python -m pytest -q
```

Sakelar ablasi: `--tanpa-harga-hitung`, `--tanpa-saring-merek`, `--tanpa-contoh-pola`, `--panjangkan`, `--desk-mode`, `--eksklusi`, `--mode-cari`, `--ambang-visual`.

Seluruh pengujian pada dokumen ini memakai `--seed 7`, sehingga sampel 10 produknya selalu sama. Tanpa `--eksklusi`, bawaannya `diri`.

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
