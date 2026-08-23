# Perbaikan setelah sesi 3

[`TABEL_SESI1.md`](TABEL_SESI1.md) memuat angka dari tag git `sesi-3`. Kode di
`main` sudah berubah sejak itu. Halaman ini mencatat apa yang berubah, berapa
pengaruhnya, dan kenapa angkanya tidak dicampurkan ke tabel utama.

## Kenapa dipisah

Tabel utama punya enam bagian yang saling sebanding: tiga tingkat exclusion,
cakupan disamakan, dua ablasi, dan perbandingan empat sistem. Semuanya satu
versi kode, satu mesin, satu himpunan uji.

Perbaikan di bawah baru dijalankan ulang pada **satu konfigurasi** (`product
line`), di **mesin berbeda** (laptop, bukan RTX 4090 sewaan). Mencampurkannya
akan merusak keterbandingan seluruh tabel demi memperbarui satu baris.

Jadi tabel utama tetap S3 dan utuh; halaman ini yang menunjukkan arah
perbaikannya.

## Tiga perubahan kode

### 1. Kategori ditambatkan ke taksonomi

Kategori adalah satu dari empat keluaran, tapi sampai sesi 3 ia **tidak pernah
dibatasi maupun diukur**. Prompt cuma menulis `"kategori": "..."` tanpa
menyebutkan nilai yang sah, dan `eval_listing.py` tidak menyentuhnya sama
sekali.

Begitu metriknya dibuat, keadaannya terlihat:

```
pipeline    299 nilai kategori unik, hanya 41,6% sah
baseline    344 nilai unik, 0,0% sah
```

Catatan penting untuk membaca `category_correct%`: sebagian "kesalahan" yang
dihitung ternyata label katalognya yang keliru, bukan sistemnya. Analisis
lengkapnya di [`CACAT_LABEL_KATEGORI.md`](CACAT_LABEL_KATEGORI.md) — angka 65,9%
adalah batas bawah.

`gemma3:12b` tidak pernah sekali pun menghasilkan kategori yang ada di
taksonomi — ia mengarang taksonomi Tokopedia sendiri: "Perawatan Wajah",
"Komputer & Aksesoris", "Pakaian Pria > Kemeja".

Perbaikannya: prompt menyebut ketujuh nilai sah, lalu keluarannya ditambatkan —
nilai model kalau sudah sah, kalau tidak kategori tetangga katalog, kalau tidak
kata penanda, kalau tidak `lainnya`. Pola yang sama dengan harga deterministik:
model menebak, katalog membetulkan.

Satu bug hampir lolos: pencocokan penanda memakai substring, sehingga `"ikan"`
cocok di dalam `"Kecantikan"` dan lipstik ditambatkan ke `pokok_tani`. Tabrakan
lain yang sama berbahayanya: `"tas"` di kertas/atas/kualitas, `"gula"` di
keunggulan, `"susu"` di susunan. Diganti pencocokan batas kata. Salah kategori
yang bentuknya sah lebih menyesatkan daripada karangan bebas yang jelas salah.

### 2. Pemanjang judul ikut suara mayoritas tetangga

Ambang lama "muncul di minimal dua tetangga" tidak bisa membedakan deskriptor
produk dari penanda varian produk lain. Pada keripik pisang cokelat, kata yang
dipunyai kelima tetangga cuma "coklat" dan "pisang"; "strawberry" muncul di
sebagian dan tetap lolos, lalu masuk ke judul padahal penjual sudah menyatakan
rasanya cokelat.

Sekarang kandidat harus disepakati lebih dari separuh tetangga. Kata yang
disepakati mayoritas menggambarkan jenis barangnya; kata yang cuma dipunyai
sebagian justru yang membedakan mereka satu sama lain.

### 3. Satuan dibuang bersama angkanya

`saring_merek` menilai token satu per satu. Untuk "Minyak Goreng Sunco 1 Liter"
yang bacaan fotonya tidak menyebut ukuran, "1" dibuang karena angkanya tidak
terlihat, tapi "Liter" lolos sebagai kata lazim — tidak ada yang tahu keduanya
sepasang. Hasilnya "Minyak Goreng Sunco Liter": penjaganya benar menangkap
ukuran karangan, tapi judulnya rusak.

Ditemukan saat menjalankan satu produk lewat antarmuka web, bukan dari tabel
metrik. `spec_halluc` mencatatnya sebagai keberhasilan — angka karangannya
memang hilang — dan tidak ada metrik yang mengeluh soal satuan yatim.

## Pengaruhnya, terukur

Konfigurasi identik: exclusion `product line`, 492 produk yang sama, platform
`blibli` dan `tokopedia`. Hanya kodenya yang berbeda.

| metrik | S3 (`sesi-3`) | S4 (`main`) | |
|---|---:|---:|---|
| `category_valid%` | 41,6 | **100,0** | semua sah |
| `category_correct%` | 36,4 | **65,9** | +81% relatif |
| `ungrounded_words%` | 85,4 | **84,3** | −1,1 poin |
| `price_err%` | 29,9 | **28,8** | |
| `price_logerr` | 0,300 | 0,300 | harga tidak disentuh |
| `abstain%` | 56,1 | 56,1 | tidak berubah |
| `title_recall` | 0,364 | 0,346 | −5% |
| `length_ok%` | 39,7 | 25,6 | **−35%** |

Baris halusinasi dulu berbunyi `brand_strict%` 3,6 → 1,2 dan dibaca sebagai
"3× lebih bersih". Metrik itu **gugur** — recall-nya 6,7% terhadap penilaian
manusia. Penggantinya mencatat perbaikannya cuma 1,1 poin.

Artinya perubahan kode ini **hampir tidak menyentuh halusinasi sama sekali**.
Yang benar-benar diperbaikinya kategori: dari 36,4% ke 65,9% tepat. Itu klaim
yang berdiri, dan lebih jujur daripada yang dulu ditulis.

Lawan baseline 12B — angka baseline dari S3, sah dibandingkan karena
`baseline_besar.py` tidak ikut berubah:

| metrik | pipeline S4 | baseline 12B |
|---|---:|---:|
| `title_recall` | **0,346** | 0,267 |
| `category_valid%` | **100,0** | 0,0 |
| `category_correct%` | **65,9** | 0,0 |
| `ungrounded_words%` | **84,3** | 99,4 |
| `price_logerr` | **0,300** | 0,788 |
| `length_ok%` | 25,6 | **55,4** |

Lima dari enam kolom.

Tiga baris halusinasi lama (`brand_strict%`, `spec_halluc%`,
`desc_ungrounded%`) dibuang dari kedua tabel — ketiganya gugur setelah
penilaian manusia mengukur recall-nya 6,7%, 0,0%, dan 9,1%. Penggantinya
`ungrounded_words%` (recall 93,3%, presisi 35%) mencatat selisih yang jauh
lebih kecil: 84,3 lawan 99,4, bukan 1,2 lawan 14,4.

Presisi 35% berarti angka mutlaknya tidak berarti "84% listing berhalusinasi";
yang bermakna selisihnya. Lihat [`PENILAIAN_MANUSIA.md`](PENILAIAN_MANUSIA.md).

## Ongkosnya, dan kenapa tetap diambil

`length_ok%` turun 39,7 → 25,6, memperlebar kekalahan dari baseline.

Kata yang berhenti ditambahkan diperiksa satu per satu pada 389 judul, tanpa
GPU, memakai tetangga yang sudah tersimpan di berkas S3:

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

Kesimpulan yang jujur: `length_ok%` versi S3 **sebagian palsu** — dipompa kata
yang tidak menggambarkan produknya. Angka 25,6 lebih rendah dan lebih benar.

## Yang belum diukur ulang

| konfigurasi | status |
|---|---|
| exclusion `product line` | sudah, S4 |
| exclusion `self`, `category` | belum, masih S3 |
| ablasi ambang 0,70 / 0,80 | belum, masih S3 |
| ablasi pemanjang judul | belum, masih S3 |
| Student VLM, Student text | belum, dan tidak dilatih ulang |
| Baseline 12B | tidak perlu — kodenya tidak berubah |

Sekitar 8 jam GPU di laptop, atau ~1 jam di 4090 sewaan. Sewa itu sekaligus
mengembalikan angka kecepatan yang sebanding — S4 dijalankan di laptop, jadi
`sec/listing`-nya tidak bisa disandingkan dengan apa pun di tabel utama.

## Cara mereproduksi

```bash
# angka tabel utama
git checkout sesi-3

# angka halaman ini
git checkout main
for i in 0 100 200 300 400; do
  python scripts/retrieve_pipeline.py --platform all --panjangkan --eksklusi lini \
      --ids-dari hasil_sesi2/murid_vlm.jsonl --iris "$i:$((i+100))" \
      --keluaran data_drive/eval/S4_pipeline_lini.jsonl
done

python scripts/eval_listing.py \
    hasil_sesi2/S3_pipeline_lini.jsonl hasil_sesi2/S4_bersih.jsonl \
    --hanya-platform blibli,tokopedia
```

Berkas hasilnya sudah tersimpan: `hasil_sesi2/S4_bersih.jsonl`, 492 baris.
