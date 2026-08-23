# Riset: Model Terbaik untuk Penentuan Harga Otomatis

**Tanggal:** 20 Agustus 2026
**Status:** kajian desain + rencana eksperimen + **hasil pengukuran (§7)**.
`merged.parquet` (28.443 baris) diunduh dari Drive pada 20 Agu 2026, jadi §7 berisi
angka yang benar-benar diukur. `data/products.db` tetap **tidak ada** di mesin ini dan
tidak bisa dipulihkan dari Drive, sehingga sinyal penjualan tokopedia belum terukur.
Angka di §1–§6 yang tidak bertanda §7 berasal dari `docs/OPTIMASI.md` dan
`docs/MODEL_HARGA.md`, bukan pengukuran ulang.

---

## 0. Ringkasan untuk yang buru-buru

Pertanyaan "model harga terbaik apa" tidak bisa dijawab sebagai satu pertanyaan,
karena sistem ini mengandung **dua estimand yang berbeda sifatnya**:

| | E1 — Estimasi harga pasar | E2 — Keputusan harga jual |
|---|---|---|
| Pertanyaan | Produk seperti ini dijual berapa di marketplace? | Dengan HPP sekian, saya pasang berapa? |
| Sifat | Prediksi statistik | Keputusan di bawah kendala keras |
| Ground truth | **Ada** — 28.443 harga nyata di katalog | **Tidak ada** — HPP tidak pernah dipublikasikan |
| Boleh ML? | **Ya, dan seharusnya** | **Tidak.** Deterministik sudah benar |
| Implementasi sekarang | TF-IDF judul, k=10, kuantil dari ±8 titik | `pricing_engine.py`, aritmetika + zona |

**Kesimpulan pokok: jangan ganti E2. Yang perlu diriset dan diperbaiki adalah E1.**
E1 adalah satu-satunya komponen yang benar-benar sebuah "model", dan saat ini ia
komponen paling lemah sekaligus paling sedikit dipertahankan di paper — padahal
seluruh logika zona (BAGUS/WAJAR/KETAT/BAHAYA) bergantung penuh pada tiga angka
yang ia keluarkan (p25, median, p75).

Urutan prioritas: **benchmark jujur → perbaikan retrieval → quantile regression
terkalibrasi**. Multimodal deep learning masuk BAB II sebagai related work,
bukan ke dalam kode.

**Hasil pengukuran nyata ada di §7** (20 Agu 2026, atas 28.443 baris). Tiga yang
paling mengubah rencana: cakupan sinyal penjualan **35,2%** — di bawah ambang, jadi
belum jadi dasar posisi harga (§7.1); asosiasi harga-terjual **negatif di 9 dari 9
kategori**, artinya opsi "premium" mengarah ke wilayah nyaris nol volume (§7.2); dan
**16,7% katalog** jatuh diam-diam ke kategori `lainnya` (§7.3, sudah diperbaiki).

Satu pengecualian penting di sisi E2, dibahas di §4.1: `MARGIN_DEFAULT` adalah
tabel 27 konstanta tanpa sumber, dan ia menentukan harga sepenuhnya di zona
TIDAK_ADA_DATA — jalur yang aktif justru untuk produk baru dan unik, use case
unggulan di BAB I. Itu perlu dibereskan sebelum BAB IV ditulis.

---

## 1. Tiga masalah pada E1 yang harus dibereskan lebih dulu

### 1.1 Angka "harga meleset 2,6%" dipakai untuk membela hal yang salah

`docs/MODEL_HARGA.md` §4.2 menutup argumen "kenapa tidak pakai ML" dengan baris
"Sudah terbukti — pipeline saat ini harga meleset 2,6%, cukup baik."

Argumen ini tidak sah, dan juri yang teliti akan menemukannya:

`harga_err` di `scripts/eval_listing.py:126` adalah `median(|tebakan − asli| / asli)`
— itu median absolute percentage error dari **E1** (harga pasar hasil retrieval).
Angka itu tidak mengukur apa pun tentang E2. Jadi §4.2 memakai akurasi lapisan
retrieval untuk membenarkan keputusan desain lapisan aritmetika. Dua hal yang
berbeda.

Argumen yang benar untuk E2 ada di baris-baris lain tabel yang sama dan sudah
kuat tanpa perlu angka itu: HPP adalah kendala keras, tidak ada ground truth
"harga yang benar" di data mana pun, dan UMKM butuh rincian yang bisa diaudit.
**Saran: buang baris "sudah terbukti" dari §4.2.** Ia melemahkan argumen yang
sebetulnya sudah menang.

### 1.2 Angka 2,6% itu sendiri kemungkinan besar terlalu optimistis

Yang sudah benar: `retrieve_pipeline.py:542` sudah membuang produk kueri dari
hasil pencarian (`if j != idx`). Kebocoran paling kasar sudah tertutup.

Yang belum tertutup:

- **1.221 judul duplikat (6,4%)** sudah terdokumentasi di `CLAUDE.md` tapi tidak
  dibuang dari indeks. Membuang diri sendiri tidak membuang kembarannya. Kalau
  produk yang sama muncul dua kali dengan harga sama, tetangga #1 adalah salinan
  persis dan MdAPE-nya nol secara artifisial.
- **Tidak ada group split.** Produk dari toko yang sama sering punya judul nyaris
  identik dengan harga identik. Split acak per baris membocorkan harga antar-baris
  satu toko. Yang benar: split per `shop`.
- **Yang diukur bukan tugas sebenarnya.** Mengukur "bisakah kita menebak ulang
  harga produk yang sudah ada di katalog" berbeda dari "bisakah kita menebak
  harga produk UMKM baru yang belum ada di katalog mana pun". Yang kedua adalah
  use case yang diklaim di paper.

Sebagai kalibrasi: literatur Automated Valuation Model (AVM) properti — analog
terdekat yang metriknya sudah mapan — menganggap MdAPE di bawah ~5% sebagai kelas
institusional, untuk aset yang punya lokasi, luas, jumlah kamar, dan tahun bangun
sebagai fitur terstruktur. MdAPE 2,6% dari judul teks saja, untuk barang UMKM yang
heterogen, akan dicurigai sebagai kebocoran oleh reviewer mana pun. Angka jujurnya
hampir pasti lebih besar — dan itu tidak apa-apa, asal diukur dan dilaporkan benar.

### 1.3 Sisi HPP dinormalisasi per unit, sisi pasar tidak

Ini cacat asimetri yang paling merugikan akurasi, dan paling murah diperbaiki.

`PricingRequest.hpp_per_unit` (`pricing_engine.py:142`) menghitung modal per unit
jual dengan hati-hati: `KONVERSI_SATUAN` untuk lusin/kodi/gross, konversi kg→g dan
l→ml. Bagus.

Tapi di sisi pasar, `harga` diambil apa adanya dari kolom `price` tetangga. Artinya
"Keripik Pisang 250g" dan "Keripik Pisang 1kg" masuk ke median yang sama, padahal
harganya beda 4x karena isinya beda 4x. Median dari campuran ukuran bukan estimasi
harga apa pun.

Perbaikannya tidak butuh model: ekstrak angka+satuan dari judul dengan regex,
konversi harga tetangga ke **harga per gram / per ml / per pcs**, hitung kuantil di
ruang itu, lalu kalikan balik dengan ukuran kemasan jual user. Dampaknya paling
besar di `makanan_minuman`, `minuman_herbal`, dan `skincare_kecantikan` — tiga
kategori yang justru inti segmen UMKM.

### 1.4 Kuantil dari 8 titik

`k=10`, lalu trim 5–95% (`pricing_engine.py:438`), menyisakan ~8 harga. p25 dan p75
dari 8 titik punya standard error yang sangat besar; dua produk yang mirip bisa
jatuh ke zona berbeda hanya karena satu tetangga bergeser. Karena zona adalah
output yang paling dilihat user, kebisingan ini langsung terasa.

Perbaikan berurutan dari yang paling murah:
1. `k` adaptif — ambil semua tetangga di atas ambang skor, dengan lantai ~30.
2. Bootstrap kuantil untuk mendapat lebar interval, bukan titik.
3. Ganti kuantil empiris dengan quantile regression (§3).

---

## 2. Perbaikan retrieval — dampak besar, biaya kecil

Urutan ini disusun berdasarkan rasio dampak/biaya, bukan kecanggihan.

**(a) BM25 menggantikan TF-IDF buatan sendiri.**
`Indeks` di `pricing_engine.py:288` adalah TF-IDF dengan normalisasi panjang
sederhana. BM25 (saturasi frekuensi via `k1`, normalisasi panjang via `b`) adalah
baseline standar dan hampir selalu lebih baik pada judul pendek. Perubahannya
~15 baris di kelas yang sama, dan memberi paper satu baris ablasi yang gratis.

**(b) Bersihkan indeks.** Buang 1.221 duplikat judul dan 632 outlier harga (3,3%)
yang sudah terdokumentasi. Keduanya sudah diketahui tapi belum dipakai.

**(c) Filter kategori sebelum kuantil.** Sekarang kategori ditentukan dari modus
tetangga *setelah* tetangga dipilih. Akibatnya harga pasar bisa dihitung dari
campuran kategori. Yang lebih sehat: hitung kuantil hanya dari tetangga yang
kategorinya sama dengan modus.

**(d) Dense retrieval untuk judul bahasa Indonesia.** Multilingual E5 melaporkan
mE5-large mencapai **52,9 nDCG@10 pada subset Indonesia MIRACL**, dengan BM25
rata-rata **39,3 nDCG@10** across 16 bahasa benchmark yang sama (angka Indonesia
spesifik untuk BM25 tidak saya lihat — jangan kutip perbandingan langsung tanpa
mengeceknya). Alternatif lokal: koleksi `LazarusNLP/indonesian-sentence-embeddings`.
Cara paling aman: **hybrid** BM25 + dense digabung dengan Reciprocal Rank Fusion —
dense menangkap sinonim ("kaos" vs "t-shirt" vs "kaus"), BM25 menjaga presisi pada
kode ukuran dan nama merek yang jarang muncul.

**(e) CLIP baru setelah teks selesai.** Ini nomor 7 di roadmap `RESUME_PRICING.md`,
dan sebaiknya tetap di belakang. Alasannya justru argumen §4.2 sendiri, yang benar:
harga ditentukan merek dan ukuran, dan keduanya hidup di teks, bukan di piksel.
Pakai gambar sebagai **re-ranker** atas kandidat teks, bukan sebagai retriever utama.

---

## 3. Model prediksi harga — inilah "model terbaik" yang ditanyakan

### 3.1 Rujukan yang relevan, dan yang menyesatkan

Tolok ukur paling dekat adalah **Mercari Price Suggestion Challenge**: prediksi
harga dari judul + deskripsi + kategori pada ~1,5 juta listing C2C. Pemenangnya
mencapai **RMSLE 0,3875**, memakai **ensemble MLP sparse di atas fitur teks**,
dalam kernel ~1900 detik dan ±75 baris kode. Repo solusi pemenang melaporkan
0,3733 untuk ensemble penuhnya.

Dua pelajaran yang langsung berlaku:

1. **Yang menang bukan deep multimodal.** Yang menang adalah fitur teks sparse
   yang baik + model dangkal yang cepat. Ini penting karena katalog LAPAKIN 28.443
   produk — **50x lebih kecil** dari Mercari. Pada skala itu, gradient boosting
   dan model linear teregularisasi akan mengalahkan neural network, bukan sebaliknya.
2. **RMSLE adalah metrik yang tepat.** Ia skala-invarian (Rp5.000 dan Rp5.000.000
   dinilai proporsional) dan menghukum *under-estimation* lebih berat daripada
   over-estimation. Untuk kasus UMKM, asimetri itu persis yang diinginkan: menyarankan
   harga terlalu rendah membuat penjual rugi, menyarankan terlalu tinggi hanya
   membuat lambat laku. Ini sejalan dengan kaidah default yang sudah ditulis di
   `MODEL_HARGA.md` §3.4.

Yang **tidak** perlu ditiru meski ada di literatur: fusi multimodal dalam (EfficientNet
+ BiLSTM + cross-attention untuk regresi harga ritel). Metode-metode itu nyata dan
layak dikutip di BAB II, tapi menuntut data jauh lebih besar; dengan `kategori_umkm`
yang 37,8% jatuh ke `lainnya`, model sebesar itu akan menghafal noise. Kutip, jangan
implementasikan.

### 3.2 Arsitektur yang saya rekomendasikan untuk E1

```
judul + kategori + platform + ukuran/berat terekstrak
        ↓
LightGBM, objective="quantile", α ∈ {0,25, 0,50, 0,75}   → 3 model
        ↓
Conformalized Quantile Regression (kalibrasi di split terpisah)
        ↓
(p25, median, p75) TERKALIBRASI → masuk ke tentukan_zona() apa adanya
```

Kenapa bentuk ini, dan bukan regresi titik biasa:

- **Output-nya persis bentuk yang sudah dipakai.** `tentukan_zona()`
  (`pricing_engine.py:352`) menerima `(bep, p25, median, p75)`. Quantile regression
  menghasilkan tepat tiga angka itu. Penggantiannya bersih — tidak ada bagian lain
  dari `pricing_engine.py` yang perlu diubah, dan seluruh lapisan E2 tetap utuh.
  Ini juga berarti ablasi "kuantil-tetangga vs quantile-regression" bisa dijalankan
  dengan satu flag, sesuai kebiasaan repo.
- **Conformal prediction memberi jaminan coverage.** Quantile regression saja sering
  mis-kalibrasi pada data baru — intervalnya terlalu sempit atau terlalu lebar.
  Conformalized Quantile Regression (CQR) mengoreksi ini dengan satu split kalibrasi
  dan menghasilkan interval dengan coverage yang terjamin secara distribution-free.
  Literatur AVM properti sudah memakainya persis untuk kasus ini: harga aset
  heterogen, ketidakpastian yang berbeda-beda per objek.
- **Ini kontribusi paper yang paling bisa dijual.** Saat ini rentang [p25, p75]
  adalah heuristik tanpa klaim statistik. Dengan CQR, ia menjadi interval dengan
  coverage terukur, dan zona berubah dari label arbitrer menjadi pernyataan
  probabilistik: alih-alih "zona KETAT", sistem bisa mengatakan **"peluang harga
  pasar berada di atas BEP Anda ≈ 62%"**. Itu jauh lebih berguna bagi penjual,
  tetap sepenuhnya auditable, dan tidak melanggar prinsip transparansi sedikit pun —
  angka akhirnya masih aritmetika, hanya anchor-nya yang sekarang terkalibrasi.

### 3.3 Retrieval tetap dipertahankan — untuk penjelasan, bukan untuk angka

Ini poin desain yang penting untuk menjaga argumen transparansi:

- **Model** menghasilkan angka (p25/median/p75).
- **Retrieval** menghasilkan bukti (5 produk serupa beserta harga dan tokonya).

User melihat "Rp54.900 — produk serupa di pasar: A Rp49.000, B Rp52.000, C Rp58.000".
Angkanya dari model terkalibrasi, pembenarannya dari data nyata. Tidak ada black box
yang dilihat user, dan `produk_serupa` di `PricingResult` sudah menyediakan slot ini.

---

## 4. E2 — apa yang tetap, apa yang layak diperbaiki

**Yang tetap:** aritmetika deterministik. Keputusan ini benar dan didukung literatur
pricing UMKM, bukan hanya intuisi — silakan pakai ini untuk memperkuat BAB II.
Temuan yang berulang di literatur MSME pricing: mayoritas UMKM masih memakai cost-plus
murni karena kepraktisannya, dan cost-plus murni gagal karena mengabaikan dinamika
pasar dan persepsi nilai; pendekatan **hybrid** yang menggabungkan pemulihan biaya
dengan adaptasi pasar dilaporkan mengungguli strategi tunggal. Desain market-first
LAPAKIN — pasar menentukan harga, HPP menentukan untung — persis pendekatan hybrid itu.
Itu positioning paper yang jauh lebih kuat daripada "kami tidak pakai ML supaya
transparan".

**Yang layak diperbaiki:**

### 4.1 `MARGIN_DEFAULT` adalah tabel karangan — dan ia menentukan harga di jalur paling penting

Ini cacat terbesar di sisi E2, dan letaknya justru di komponen yang paling
dibanggakan sebagai "transparan".

`MARGIN_DEFAULT` (`pricing_engine.py:103`) berisi 27 angka — fashion 50/80/150%,
kriya 50/100/200%, elektronik 10/20/30%, dan seterusnya. Di `MODEL_HARGA.md` §5.4,
tabel itu muncul sebagai blok kode di bawah judul, **tanpa satu kalimat pun yang
menyebut angkanya dari mana**. Tidak ada sumber, tidak ada pengukuran, tidak ada
rujukan ke katalog 28.443 produk. Ini melanggar aturan keras nomor 1 repo ini
("angka harus punya sumber") di dokumen yang sekaligus paling banyak dikutip
ke paper.

**Yang membuatnya serius bukan keberadaannya, tapi di mana ia dipakai.**

| Lokasi | Perannya |
|---|---|
| `pricing_engine.py:515` | zona **TIDAK_ADA_DATA** — `harga = bep × (1 + margin_mid)`. **Satu-satunya penentu harga.** |
| `pricing_engine.py:527–528` | jalur cadangan `harga_agresif` / `harga_premium` saat tidak ada data pasar |

Zona TIDAK_ADA_DATA aktif ketika retrieval gagal menemukan produk mirip
(`skor < min_skor`, default 2,0) — yaitu tepat ketika produknya **benar-benar baru
dan unik**. Itu use case unggulan yang dijual di BAB I. Jadi di jalur yang paling
ingin dipamerkan, sistem jatuh ke konstanta karangan, dan seluruh kalibrasi pasar
yang jadi inti desain market-first tidak ikut bekerja sama sekali.

**Konsekuensi untuk argumen paper.** Klaim "deterministik = bisa diaudit" perlu
dipersempit: yang transparan adalah *cara* menghitungnya, bukan *kebenaran* angkanya.
Formula dengan konstanta tak berdasar bukan lebih ilmiah daripada model — ia model
juga, dengan parameter yang di-set tangan dan tidak pernah divalidasi. Ini titik
serang yang jauh lebih mudah bagi juri daripada "kenapa tidak pakai neural network",
dan sejauh ini tidak dijawab di dokumen mana pun.

**Perbaikannya bukan mengganti dengan ML — hilangkan tabelnya.**

1. Sebaran agresif/rekomendasi/premium tidak perlu datang dari margin karangan.
   Ia bisa diturunkan dari **dispersi harga empiris per kategori** di katalog:
   rasio `p25/median` dan `p75/median` yang nyata terukur. Satu skrip, sekali jalan,
   dan 27 angka karangan berganti jadi 27 angka bersumber.
2. Untuk zona TIDAK_ADA_DATA, mundur ke **kategori induk yang lebih luas** dan pakai
   dispersinya, bukan mengarang margin. Kalau kategori induk pun kosong, katakan
   terus terang "data tidak cukup untuk menyarankan harga" dan tampilkan BEP saja.
   Menolak menjawab lebih baik daripada menjawab dengan konstanta.
3. Konstanta apa pun yang tetap tersisa setelah itu wajib punya baris di §5.4 yang
   menyebut asalnya — aturan yang sudah berlaku untuk `BIAYA_PLATFORM` dan `PAJAK`,
   dan tidak ada alasan margin dikecualikan.

**Sudah diukur — lihat §7.4.** Pada 299 produk contoh zona TIDAK_ADA_DATA aktif **0%**
dan tabel margin dibaca 299 kali tanpa nilainya dipakai sekali pun. Jadi butir ini
**tidak** naik jadi prioritas tertinggi. Tapi 0% itu diukur dengan kueri judul katalog
tanpa membuang self-match — batas paling optimistis. Ukur ulang setelah benchmark
Langkah 1 sebelum menyimpulkan apa pun untuk BAB IV.

### 4.2 Sisanya

1. **Ambang zona itu arbitrer.** p25/median/p75 sebagai batas BAGUS/WAJAR/KETAT/BAHAYA
   tidak diturunkan dari apa pun. Dengan distribusi prediktif terkalibrasi (§3.2),
   ganti dengan posisi BEP dalam distribusi itu — satu angka kontinu, tidak ada
   ambang yang perlu dibela.
2. **Batasi klaim — tapi tidak sejauh yang saya tulis semula.** Draf pertama
   dokumen ini menyatakan sistem tidak punya data penjualan sama sekali. **Itu
   keliru**, lihat §4.3: `sold_count` ada dan bisa dipulihkan. Yang tetap benar:
   sistem tidak bisa mengklaim "harga optimal" maupun elastisitas permintaan,
   karena `sold_count` kumulatif, sebagian dibucket, dan pasangan harga-kuantitas
   yang teramati adalah titik keseimbangan. Klaim yang bisa dipertahankan:
   *harga kompetitif di atas titik impas, pada posisi yang berasosiasi dengan
   volume terjual lebih tinggi di kelas produk sebanding*. Tulis batasan ini
   eksplisit di BAB I §1.6 dan di limitasi BAB IV.
3. **`fee_cap` Tokopedia tidak dipakai.** `BIAYA_PLATFORM["tokopedia"]["fee_cap"]`
   = 80.000 didefinisikan tapi `hitung_bep()` tidak pernah membacanya. Untuk produk
   di atas ~Rp1 juta, BEP jadi overestimate. Bug kecil, perbaikannya dua baris.
4. **PPh final hanya aktif kalau omzet ≥ Rp500 juta**, dan `omzet_tahunan` default 0.
   Secara aturan ini benar (PP 20/2026), tapi artinya di jalur default pajak selalu
   nol — pastikan ini disebut apa adanya di paper, jangan sampai tabel komponen biaya
   menyiratkan pajak selalu dihitung.

### 4.3 `sold_count` ada, dan tidak dipakai sama sekali

Ini peluang terbesar yang sedang menganggur, dan ia tidak butuh scraping baru.

`Product` di `src/tokopedia_scraper/models.py` sudah punya `sold_count`, `rating`,
`review_count`, `original_price`, dan `discount_pct`. `parsers.py:428–430`
menariknya dari `stats.countReview` dan `txStats.countSold` di PDP. Datanya nyata
dan sudah tersimpan.

Yang bermasalah bukan keberadaannya, tapi jalurnya. `docs/DATASET.md:113–115` mencatat
sendiri: kolom-kolom itu kosong untuk seluruh **18.443 baris tokopedia** di dataset
gabungan karena ekspornya slim 8 kolom — "**bukan hilang saat merge**". Kolomnya
tetap ada di antara 25 kolom `merged.parquet`, isinya saja yang kosong, dan aslinya
utuh di `data/products.db`. Jadi ini **join pada `product_id_asli`, bukan scraping
ulang**. `scripts/build_train_pairs.py:84` sudah melakukan join yang persis sama —
tapi hasilnya masuk ke `train_pairs`, tidak pernah sampai ke jalur pricing.

**Kalau cakupannya memadai, tiga masalah selesai sekaligus:**

1. **`MARGIN_DEFAULT` mati sendiri.** Sebaran agresif/rekomendasi/premium berhenti
   jadi 27 konstanta karangan dan berganti jadi pertanyaan yang bisa diukur: *di
   posisi harga mana, dalam kumpulan produk sebanding, produk yang paling banyak
   terjual berada?*
2. **Klaim paper naik kelas** — dari "harga aman di atas BEP" (defensif) jadi "harga
   di posisi yang terbukti laku untuk kelas produk ini" (kontribusi).
3. **Zona dapat sumbu kedua.** Sekarang zona hanya bicara untung/rugi. Dengan sinyal
   penjualan ia bisa bicara untung *dan* peluang laku — dua hal berbeda yang
   dua-duanya dibutuhkan penjual.

**Tiga batas yang wajib ditulis, jangan dilewati.** Ini yang akan ditanyakan penguji
yang paham ekonometri:

- `sold_count` **kumulatif seumur listing, bukan laju**. Listing lama menumpuk angka
  besar terlepas dari harganya, dan umur listing tidak tersedia.
- Di stage 1 nilainya **dibucket** ("750+ terjual", `parsers.py:123`). Hanya baris
  `pdp_fetched = 1` yang eksak.
- Harga dan kuantitas yang teramati adalah **titik keseimbangan, bukan kurva
  permintaan**. Meregresikan terjual atas harga secara naif menghasilkan estimasi
  bias — masalah identifikasi klasik yang butuh instrumen.

Framing yang sah: **asosiasi antara posisi harga relatif dan volume terjual**,
bukan elastisitas, bukan kausal.

**Cara mengukurnya sudah ada:**

```bash
python scripts/cek_sinyal_jual.py            # join + ukur cakupan + tulis hasil
python scripts/cek_sinyal_jual.py --selfcheck  # uji logika tanpa data asli
```

Skrip itu menjawab satu pertanyaan keputusan: setelah join, berapa persen dari
28.443 baris punya angka terjual, dan berapa yang eksak vs bucket. **Ambangnya 40%**
(`AMBANG_LAYAK`): di bawah itu sinyal penjualan turun jadi fitur pelengkap; di atas
itu ia naik ke prioritas satu, di atas semua perbaikan retrieval di §2.

**Sudah dijawab di §7.1: keduanya membawa `sold_count` penuh, tokopedia nol, total
35,2% — di bawah ambang.** Catatan berikut disimpan karena alasannya masih berlaku.
Yang tadinya belum diketahui: apakah baris blibli (8.800) dan tokopedia2025 (1.200)
membawa `sold_count` sendiri. `DATASET.md:70` mendaftarkannya sebagai kolom
`merged.parquet`, tapi isinya belum pernah diperiksa. Skripnya melaporkan ini per
sumber, dan sengaja **tidak** menjoin baris non-tokopedia ke `products.db` — ID
blibli hidup di ruang yang berbeda dan bisa bertabrakan secara numerik dengan ID
tokopedia. Tabrakan itu diuji di `--selfcheck`.

---

## 5. Rencana eksperimen

Dikerjakan berurutan. Setiap langkah menghasilkan angka yang bisa dikutip di BAB IV.

**Langkah 0 — ukur cakupan sinyal penjualan.** `python scripts/cek_sinyal_jual.py`.
Murah, sekali jalan, dan hasilnya menentukan urutan semua langkah sesudahnya (§4.3).

**Langkah 1 — benchmark jujur (prasyarat semua yang lain).**
`scripts/eval_harga.py` baru:
- Split **per toko** (`GroupShuffleSplit` atas `shop`), bukan per baris.
- Buang duplikat judul dan outlier harga dari sisi indeks.
- Metrik: **MdAPE**, **PPE10** dan **PPE20** (proporsi estimasi dalam ±10%/±20%),
  **RMSLE**, dan **coverage** interval [p25, p75].
- Dilaporkan terpisah per kategori dan per desil harga.
- Tambahkan satu baris: **berapa persen kueri jatuh ke zona TIDAK_ADA_DATA** (§4.1).

Hasil yang diharapkan: MdAPE naik jauh di atas 2,6%. Itu bukan kemunduran — itu
angka pertama yang benar, dan menjadi baseline yang sah untuk semua ablasi berikutnya.

**Langkah 2 — ablasi retrieval.** TF-IDF sekarang → BM25 → BM25 + normalisasi unit
→ hybrid BM25+E5. Satu baris tabel per konfigurasi, sesuai gaya `docs/OPTIMASI.md`.

**Langkah 3 — quantile regression + CQR.** Bandingkan tiga cara mendapat (p25,
median, p75): kuantil-tetangga (sekarang), LightGBM quantile, LightGBM quantile+CQR.
Metrik pembanding: pinball loss, coverage empiris, dan **stabilitas zona** (berapa
persen produk berpindah zona kalau satu tetangga dibuang) — metrik terakhir ini
orisinal dan langsung menjawab §1.4.

**Langkah 4 — uji domain gap.** Ini ancaman validitas terbesar yang sudah dicatat
di riset sebelumnya: katalog berisi foto studio, input nyata adalah foto HP penjual.
Kumpulkan 30–50 foto produk UMKM asli, jalankan pipeline penuh, laporkan selisih
MdAPE antara katalog dan foto lapangan. Kalau angkanya jelek, itu tetap temuan yang
layak ditulis — dan jauh lebih baik ditemukan sendiri daripada oleh juri.

**Yang sengaja tidak dikerjakan** (tulis di BAB II sebagai related work, dengan alasan):
fusi multimodal dalam untuk regresi harga; dynamic pricing berbasis RL/bandit (butuh
umpan balik penjualan yang tidak dimiliki); pricing strategis game-theoretic di
sistem rekomendasi (mengasumsikan kompetisi penjual yang teramati).

---

## 6. Rujukan

Ditandai sesuai aturan repo: **[dibuka]** = halamannya benar-benar saya buka dan baca;
**[hasil pencarian]** = hanya muncul di hasil pencarian, isi spesifiknya belum
diverifikasi; **[BELUM DIVERIFIKASI]** = gagal diakses.

- **[dibuka]** Mercari Engineering, "Report of Mercari Price Suggestion Challenge" —
  RMSLE pemenang 0,3875, model MLP, kernel ±1900 detik, ±75 baris.
  https://engineering.mercari.com/en/blog/entry/2018-11-14-172509/
- **[dibuka]** pjankiewicz/mercari-solution (repo solusi juara 1) — ensemble MLP
  sparse, dilaporkan RMSLE 0,3733. https://github.com/pjankiewicz/mercari-solution
- **[dibuka]** Wang dkk., "Multilingual E5 Text Embeddings: A Technical Report",
  arXiv:2402.05672 — mE5-large 52,9 nDCG@10 pada MIRACL subset Indonesia; BM25
  rata-rata 39,3 nDCG@10 lintas 16 bahasa. https://arxiv.org/html/2402.05672v1
- **[hasil pencarian]** Romano, Patterson & Candès, Conformalized Quantile Regression —
  dasar teori interval terkalibrasi. Perlu dibuka sebelum dikutip di paper.
- **[hasil pencarian]** Penerapan conformal quantile regression pada prediksi harga
  properti, Journal of Property Research 42(1), 2025.
  https://www.tandfonline.com/doi/full/10.1080/09599916.2024.2403998
- **[BELUM DIVERIFIKASI]** "An Exposition of AVM Performance Metrics",
  doi 10.1080/15214842.2020.1757352 — sumber metrik MdAPE/PPE10/FSD. Situsnya
  menolak akses otomatis (HTTP 403); harus dibuka manual sebelum disitasi.
- **[hasil pencarian]** LazarusNLP, indonesian-sentence-embeddings.
  https://github.com/LazarusNLP/indonesian-sentence-embeddings
- **[hasil pencarian]** Literatur strategi harga UMKM (cost-plus vs market-based vs
  hybrid). Beberapa sumber ditemukan; belum ada yang dibuka. Untuk BAB II perlu
  dipilih 2–3 dan dibaca utuh.

---

## 7. Hasil pengukuran — 20 Agustus 2026

Semua angka di bawah diukur pada `data_drive/merged/merged.parquet` (28.443 baris,
diunduh dari Drive hari itu juga). `data/products.db` **tidak ada di mesin ini** dan
tidak bisa dipulihkan dari Drive — salinan di sana versi slim 8 kolom. Itu membatasi
sebagian pengukuran, dan dicatat di tiap tempat yang kena.

### 7.1 Cakupan sinyal penjualan — 35,2%, di bawah ambang

```
python scripts/cek_sinyal_jual.py --sumber data_drive/merged/merged.parquet --tanpa-tulis
```

| sumber | baris | punya `sold_count` | punya `rating` |
|---|---|---|---|
| blibli | 8.800 | 8.800 (100%) | 4.082 |
| tokopedia | 18.443 | **0 (0%)** | 0 |
| tokopedia2025 | 1.200 | 1.200 (100%) | 1.200 |
| **total** | **28.443** | **10.000 (35,2%)** | 5.282 |

Pertanyaan terbuka di §4.3 terjawab: **blibli dan tokopedia2025 keduanya membawa
`sold_count` penuh**; yang kosong hanya tokopedia. Angka 35,2% ini **lantai**, bukan
plafon — join `products.db` bisa menaikkannya sampai ~100%, tapi berkasnya tidak ada.

**Verdikt terhadap ambang 40%: belum lewat.** Sesuai aturan yang dipasang di depan,
sinyal penjualan berstatus fitur pelengkap, bukan dasar posisi harga. Yang mengubah
status ini cuma satu hal: menemukan kembali `products.db`.

### 7.2 Tapi sinyalnya nyata, konsisten, dan arahnya melawan desain sekarang

Spearman antara persentil harga (dalam kategori × sumber) dan `log1p(sold_count)`:

| sumber | kategori | n | rho | p |
|---|---|---|---|---|
| tokopedia2025 | lainnya | 812 | **−0,647** | 2e−97 |
| tokopedia2025 | kriya_rumah | 161 | −0,594 | 9e−17 |
| tokopedia2025 | fashion_perawatan | 163 | −0,403 | 9e−08 |
| blibli | fashion_perawatan | 2.120 | −0,362 | 1e−66 |
| blibli | lainnya | 3.070 | −0,305 | 5e−67 |
| blibli | camilan_olahan | 513 | −0,274 | 3e−10 |
| blibli | bumbu_masak | 1.122 | −0,175 | 4e−09 |
| blibli | pokok_tani | 1.235 | −0,159 | 2e−08 |
| blibli | kriya_rumah | 673 | −0,072 | 0,061 |

**Sembilan dari sembilan negatif, delapan signifikan.** Median unit terjual per desil
harga (desil 1 = termurah dalam kategorinya):

```
blibli           14     8     4     4     3     2     1     1     0     0
tokopedia2025 11230 14481 11882  7840  5902   735   996   150   274    26
```

Ini **berlawanan dengan asumsi desain sekarang**. Opsi `harga_premium` mengarah ke
`p75 × 1,1`; di data, desil 8–10 adalah tempat penjualan runtuh ke median 0–1 unit.
"Premium" bukan pilihan strategi dengan trade-off sedang — di katalog ini ia wilayah
nyaris nol volume. Tiga opsi harga perlu ditimbang ulang dengan angka ini, bukan
dengan tabel margin.

**Tiga batas yang tidak boleh dilanggar saat mengutip angka di atas:**

1. **Jangan gabungkan dua sumber.** Median terjual blibli 2, tokopedia2025 3.050 —
   beda tiga orde. Definisi kolomnya hampir pasti tidak sama. Analisis per sumber.
2. **Sinyal per produk sangat lemah.** Di blibli 38,3% baris bernilai 0, mediannya 2.
   Asosiasi di atas hanya muncul di agregat ribuan baris; ia tidak bisa menentukan
   harga satu produk.
3. **Komposisi ukuran belum dikendalikan.** Dalam satu kategori, produk murah
   cenderung kemasan kecil dan yang mahal kemasan besar. Sebagian rho negatif bisa
   jadi efek komposisi, bukan respons permintaan terhadap harga — akar yang sama
   dengan §1.3. **Belum diuji.**

### 7.3 Kosakata kategori tidak pernah dicocokkan ke data

`kategori_umkm` di katalog hanya berisi tujuh nilai:

| kategori | n | ada di tabel engine (sebelum perbaikan)? |
|---|---|---|
| lainnya | 10.738 | ya |
| fashion_perawatan | 7.566 | ya |
| kriya_rumah | 3.594 | ya |
| pokok_tani | 1.847 | **tidak** |
| minuman_herbal | 1.796 | ya |
| bumbu_masak | 1.543 | **tidak** |
| camilan_olahan | 1.359 | **tidak** |

**4.749 produk — 16,7% katalog, seluruhnya segmen pangan — jatuh diam-diam ke
`lainnya`** lewat `.get(kategori, ...)`, tanpa satu pun peringatan. Sebaliknya lima
kunci di engine (`makanan_minuman`, `skincare_kecantikan`, `elektronik_gadget`,
`dapur_rumah`, `kesehatan_olahraga`) muncul **nol kali**: **15 dari 27 konstanta
margin tidak pernah terjangkau.**

**Kenapa lolos selama ini.** Ketiga label pangan itu tidak muncul di satu berkas pun
di repo — grep seluruh repo, nol hasil. Pelabelan dilakukan di luar repo (Colab) dan
kosakatanya tidak pernah dibawa balik. Sementara satu-satunya pemeriksa pricing yang
bisa jalan tanpa data, `scripts/pricing_demo_offline.py`, **mengarang datanya sendiri
memakai kosakata karangan yang sama dengan engine**. Pemeriksa yang dibangun dari
asumsi yang sama dengan kode tidak bisa mendeteksi asumsi itu salah.

**Dampak angkanya kecil — jangan dibesar-besarkan.** HPP Rp15.000, `lainnya` vs tarif
pangan: tokopedia ±Rp0, shopee −Rp228, blibli +Rp301 (~2%). Margin `lainnya` bahkan
**identik** dengan `makanan_minuman`. Yang rusak catatannya, bukan harganya:
`docs/PROPOSAL.md:488` memuat tabel komisi berkunci `makanan_minuman` — paper
mendeskripsikan cabang kode yang tidak pernah dieksekusi, dan hasil per-kategori di
BAB IV akan berlabel salah.

### 7.4 Sebaran zona, dan tabel margin yang dibaca tapi tidak dipakai

299 produk contoh, kueri = judul katalog, HPP diasumsikan 60% harga jual **hanya
untuk menjalankan logika zona** (bukan klaim tentang HPP UMKM):

| zona | n | % |
|---|---|---|
| BAGUS | 186 | 62,2% |
| WAJAR | 57 | 19,1% |
| BAHAYA | 30 | 10,0% |
| KETAT | 26 | 8,7% |
| TIDAK_ADA_DATA | 0 | **0,0%** |

`MARGIN_DEFAULT` **dibaca 299 kali dan nilainya dipakai nol kali**, karena ia hanya
menentukan harga di zona TIDAK_ADA_DATA yang tidak pernah aktif. Ini menguatkan §4.1
dari arah lain: tabel itu bukan cuma tak bersumber, ia praktis tak terpakai — sampai
retrieval gagal, yaitu justru pada produk yang benar-benar baru.

**Dua peringatan keras soal angka 0% itu.** Kueri memakai judul katalog dan
**self-match tidak dibuang**, jadi retrieval hampir dijamin dapat tetangga. Pada alur
nyata kuerinya teks keluaran VLM dari foto HP — jauh lebih berisik. **0% adalah batas
paling optimistis, bukan estimasi.** Angka jujurnya baru muncul setelah benchmark
Langkah 1 (§5) dengan group split per toko.

### 7.5 Perubahan kode yang sudah diterapkan

| Perubahan | Berkas |
|---|---|
| `KATEGORI_DATA` + `KE_TARIF` — kosakata diturunkan dari `value_counts()`, pemetaan tarif eksplisit | `scripts/pricing_engine.py` |
| `kategori_tarif()` — kategori asing tetap mundur ke `lainnya` tapi **selalu memperingatkan** | `scripts/pricing_engine.py` |
| Tiga kategori pangan dapat baris margin sendiri | `scripts/pricing_engine.py` |
| `fee_cap` Tokopedia Rp80.000 akhirnya dibaca — di BEP dan di breakdown | `scripts/pricing_engine.py` |
| Demo offline memakai kosakata nyata; lingkaran tertutupnya putus | `scripts/pricing_demo_offline.py` |
| 16 test baru, termasuk penjaga kosakata dan `fee_cap` | `tests/test_pricing.py` |
| Pengukur cakupan sinyal penjualan, jalan juga tanpa `products.db` | `scripts/cek_sinyal_jual.py` |

`python -m pytest -q` → **102 passed**, tetap offline total.

**Yang belum dikerjakan dan kenapa:**

- **`MARGIN_DEFAULT` masih berisi konstanta karangan.** Menggantinya dengan dispersi
  empiris (§4.1) butuh keputusan desain, bukan patch — dan §7.4 menunjukkan ia tidak
  mendesak selama zona TIDAK_ADA_DATA tidak pernah aktif. Sudah ditandai "BELUM
  DIUKUR" di kode dan di `MODEL_HARGA.md` §5.4.
- **`docs/PROPOSAL.md:488` belum disentuh.** Tabelnya memakai kategori karangan dan
  perlu ditulis ulang dengan kosakata nyata, tapi itu isi paper — keputusanmu.
- **Label skenario di demo tidak cocok dengan zona yang keluar** (dinamai "ZONA
  WAJAR"/"ZONA KETAT", hasilnya BAGUS). Ini mendahului perubahan saya —
  `pricing_engine.py` dan demonya belum pernah di-commit, jadi tidak ada versi
  pembanding di git. Periksa terpisah sebelum skenario itu dikutip ke BAB IV.

## Lampiran — berkas dan baris yang dirujuk

| Klaim | Lokasi |
|---|---|
| `harga_err` = median APE | `scripts/eval_listing.py:126` |
| Produk kueri dibuang dari retrieval | `scripts/retrieve_pipeline.py:542` |
| Konversi satuan sisi HPP | `scripts/pricing_engine.py:142` |
| Kuantil pasar tanpa normalisasi unit | `scripts/pricing_engine.py:438` |
| Indeks TF-IDF | `scripts/pricing_engine.py:288` |
| `tentukan_zona()` | `scripts/pricing_engine.py:352` |
| `fee_cap` didefinisikan tapi tak dipakai | `scripts/pricing_engine.py:53` vs `hitung_bep()` :334 |
| `MARGIN_DEFAULT`, 27 konstanta tanpa sumber | `scripts/pricing_engine.py:103`, `docs/MODEL_HARGA.md` §5.4 |
| Margin karangan jadi satu-satunya penentu harga | `scripts/pricing_engine.py:515` (zona TIDAK_ADA_DATA) |
| Jalur cadangan agresif/premium | `scripts/pricing_engine.py:527–528` |
| `sold_count`/`rating` ada di skema produk | `src/tokopedia_scraper/models.py` |
| Ditarik dari PDP tokopedia | `src/tokopedia_scraper/parsers.py:428–430` |
| Sold count stage 1 dibucket | `src/tokopedia_scraper/parsers.py:123` |
| Kolom kosong karena ekspor slim, bukan hilang saat merge | `docs/DATASET.md:113–115` |
| Join yang sama sudah ada, tapi tidak ke jalur pricing | `scripts/build_train_pairs.py:84` |
| Pengukur cakupan sinyal penjualan | `scripts/cek_sinyal_jual.py` |
| Argumen "sudah terbukti 2,6%" (sudah diperbaiki 20 Agu 2026) | `docs/MODEL_HARGA.md` §4.2 |
| Tabel ablasi sumber angka 34,4% → 2,6% | `docs/OPTIMASI.md` baris 14–24 |
