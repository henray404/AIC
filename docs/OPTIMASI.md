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
| **F** penjaga presisi (dipakai) | **2,6%** | **0,0%** | 10,0% | 76,7% | **0,403** | 18,4 |

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

### 4. Pipeline dua fase — berhasil, di sisi kecepatan

**Masalah.** VRAM 8 GB tidak muat `gemma3:4b` dan `qwen2.5:7b` sekaligus. Loop
lama memanggil keduanya bergantian tiap produk, jadi Ollama menukar bobot 20 kali
dan sebagian besar waktu habis memuat, bukan berpikir. Satu run 20 produk sempat
berjalan 25 menit dan baru selesai 5 produk.

**Cara kerja.** Dipecah dua fase: semua panggilan penglihatan dulu, baru semua
penulisan. Tiap model dimuat sekali.

**Pengaruh.** Dari sekitar **300 detik/produk jadi 18 detik**. Ini juga yang
membuat lima konfigurasi di atas bisa diuji dalam satu malam.

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
