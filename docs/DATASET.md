# Peta dataset — mana yang siap pakai

Semua angka di bawah ini hasil hitung ulang, bukan salinan catatan lama.
Diverifikasi lewat `notebooks/04_eda_merged.ipynb` pada 15 Agustus 2026.

> **Data ini tidak untuk diredistribusi publik.** Isinya hasil scraping
> marketplace. Tautan Drive di bawah berlaku "siapa pun yang punya link" —
> jangan tempel di tempat umum, dan sebaiknya repo ini disetel **private**
> selama masih memuat tautan tersebut.

---

## Ringkas: pakai yang mana

| Kebutuhan | Berkas | Baris |
|---|---|---|
| Dataset gabungan siap olah | `data_drive/merged/merged_local.parquet` | 28.443 |
| Pasangan gambar → judul untuk latih/uji | `data_drive/merged/train_pairs.parquet` | 27.997 |
| Data Tokopedia paling lengkap (ada `specs`, `sold_count`, `rating`) | `data/exports/products.jsonl` | 18.997 |
| Sumber tunggal blibli | `data_drive/blibli/products.parquet` | 8.800 |

Kalau ragu: **`merged_local.parquet`**. Itu satu-satunya berkas yang path
gambarnya sudah menunjuk berkas nyata di mesin lokal dan sudah dicek satu per satu.

---

## Cara temanmu menyiapkannya (3 perintah)

```powershell
python scripts/fetch_drive_iac.py          # unduh semua dari Drive, kecuali tokopedia_dataset
python scripts/localize_merged.py          # path Colab -> path lokal, tiap berkas dicek ada
python scripts/build_train_pairs.py        # judul dibersihkan + specs -> train_pairs.parquet
```

Perintah pertama sekitar 0,9 GB. Aman diulang: berkas yang sudah ada dilewati.

Gambar blibli datang sebagai `images.zip` — ekstrak sekali:

```powershell
python -c "import zipfile; zipfile.ZipFile('data_drive/blibli/images.zip').extractall('data_drive/blibli')"
```

Kalau hanya butuh berkas datanya tanpa gambar:

```powershell
python scripts/fetch_drive_iac.py --skip-images     # ~640 MB
```

---

## Isi folder Drive `IAC`

<https://drive.google.com/drive/folders/1rUTMMD1rNW7Y_gE3cFIOEmT7IitcneJf>

### `merged/` — dataset gabungan tiga sumber

<https://drive.google.com/drive/folders/1JS0fVAyS_U_H6AVDSnGxaB9FvV1ZiyCd>

| Berkas | Ukuran | Isi | Pakai? |
|---|---|---|---|
| [`merged.parquet`](https://drive.google.com/file/d/1DRwY4evMVMK8i3PJgMHPcWINDdrn9ttG/view) | 28,7 MB | 28.443 baris × 25 kolom | **ya** — paling ringkas dan bertipe benar |
| [`merged.jsonl`](https://drive.google.com/file/d/1arJ8Mch273IIu9jo6LQQ1OQenAGhlz9C/view) | 94,5 MB | isi sama | ya, kalau butuh baris demi baris |
| [`merged.csv`](https://drive.google.com/file/d/1I1yuIUtHXWAnlMlvIqFHnkHOE-SkgYxg/view) | 81,6 MB | isi sama | hindari — kolom list jadi string |
| [`MERGED_DATASET.md`](https://drive.google.com/file/d/1zpD8QaUnSTInrDfMWDnFBwbHWNrtHGXC/view) | 6 KB | dokumentasi versi lama | versi terbaru ada di repo ini |

Isinya: **blibli 8.800 + tokopedia 18.443 + tokopedia2025 1.200**.

Kolom: `product_id, title, price, category_path, description, image_urls,
local_image_paths, url, source, product_id_asli, id_sintetis, original_price,
rating, rating_count, sold_count, location, brand, merchant_name, official,
search_keyword, scraped_at, kategori_umkm, kategori_asal, dup_url, dup_judul`.

Sudah diverifikasi terhadap ekspor sumbernya: **nol baris hilang, nol judul /
harga / deskripsi / kategori / gambar yang berubah** di ketiga sumber.
`product_id` unik, tidak ada harga atau deskripsi bernilai null.

### `blibli/` — 8.800 produk

<https://drive.google.com/drive/folders/1r4wcvve_qKuqiCzIJuWCprD9sOZkRcD_>

| Berkas | Ukuran | Catatan |
|---|---|---|
| [`products.parquet`](https://drive.google.com/file/d/1RJIUGq56JIaipc7Cc7fjXKWZZmpbxxn9/view) | 4,8 MB | 21 kolom — **paling lengkap**, ada `rating`, `sold_count`, `merchant_name`, `brand`, `scraped_at` |
| [`products.jsonl`](https://drive.google.com/file/d/1qFm9JFQxsnI8XsBYtxg-HliWTBqkoQYa/view) | 20,2 MB | isi sama |
| [`products.csv`](https://drive.google.com/file/d/1dqovbxW8STcZXeZxz5ZqunDEaDaXJ6fj/view) | 17,4 MB | isi sama |
| [`images.zip`](https://drive.google.com/file/d/1rEQxOqWLkp9xgeuQW2w-WgtS2y8YsMyy/view) | 131 MB | 8.761 gambar — pakai ini, jangan unduh folder `images/` satu per satu |

Catatan: blibli hanya menyimpan **satu gambar per produk**, padahal `image_urls`
memuat 30.856 URL. Sisa galerinya belum diunduh, tapi URL-nya masih ada.

### `data/external/tokopedia2025/` — 1.200 produk

<https://drive.google.com/drive/folders/1zAp_FuAwA8iCFVHKk8GaaHry-ULFsm9H>

| Berkas | Ukuran | Catatan |
|---|---|---|
| [`products.csv`](https://drive.google.com/file/d/1hdjA5auFCvA5m66vBtGAeyeU5hZtZyQi/view) | 2,9 MB | 36 kolom: `id, name, description, price, images, thumbnail, shop_name, sold_count, rating, category_name, …` |
| [`products.json`](https://drive.google.com/file/d/1lNMbvL9aS8PUXsxuNbJrIGyAtci0mVBD/view) | 3,8 MB | isi sama |

**Gambarnya cacat.** Dataset merujuk 11.831 path, tapi folder Drive hanya berisi
2.109 gambar + 1.191 thumbnail. **9.614 gambar tidak ada di mana pun**, dan sumber
ini tidak menyimpan URL CDN sama sekali — jadi tidak bisa diunduh ulang. Hasilnya
311 dari 1.200 produk berakhir tanpa gambar.

### `tokopedia_dataset/` — punya Henry, jangan diunduh ulang

<https://drive.google.com/drive/folders/16FFY-_Z5-NcB2RXQHnz8wCMcrK-Ri5xE>

Isinya `products.jsonl` (59 MB) yang identik dengan
`data/exports/products_slim_ready.jsonl` di repo ini — **ekspor slim, 8 kolom**.
`scripts/fetch_drive_iac.py` sengaja melewatinya.

Ini juga penjelasan kenapa `rating`, `sold_count`, `merchant_name`,
`original_price`, `search_keyword`, dan `scraped_at` kosong untuk seluruh 18.443
baris tokopedia di dataset gabungan: kolom itu **tidak pernah ikut diekspor**,
bukan hilang saat merge. Semuanya masih utuh di `data/products.db`.

### Sumber yang ada di Drive tapi tidak ikut digabung

| Folder | Kolomnya | Kenapa tidak ikut |
|---|---|---|
| [`data/external/shopee/`](https://drive.google.com/drive/folders/1J0JYgFtiAOzEwcL4sD4Pg73mfcGVzOMm) | `product_id, image, name, shop_name, main_category, sub_category` | tanpa harga, tanpa deskripsi |
| [`data/external/tokopedia_listings/`](https://drive.google.com/drive/folders/12GSY_jyqpNvjtrgtv4_nZ7kAH5gL6C2H) | `Nama Produk, Nama Toko, Lokasi Toko, Terjual, Jumlah Ulasan, Rating, Harga (IDR), Diskon (%), Produk URL` | tanpa deskripsi, tanpa gambar |

Keduanya tidak bisa dipakai untuk auto-description maupun model berbasis gambar.

### `data/` — pipeline webstore, terpisah dari yang di atas

<https://drive.google.com/drive/folders/15HtEZc4snoOgBkRw851JV6RXufPNJyR6>

Ini hasil scraping toko-toko Shopify/webstore, **bukan** bagian dari dataset
gabungan. Belum diverifikasi sedalam yang lain.

| Berkas | Baris | Isi |
|---|---|---|
| [`produk.jsonl`](https://drive.google.com/file/d/1ew-mlWK5ig5TM1gwZkOMVOmeP8aygNj7/view) | 111.436 | `toko, nama_toko, platform, nama_produk, kategori_situs, harga_min, harga_max, mata_uang, deskripsi, detail, gambar, jumlah_gambar, url` |
| [`produk.csv`](https://drive.google.com/file/d/1nDwk7m7-hJb_rR87UkdZhNQdRS8Q5eer/view) | 27.653 | 18 kolom, sudah dikategorikan |
| [`produk.parquet`](https://drive.google.com/file/d/1oTd9lBsNljOb9oD-GluXs1iOQGN5sbpm/view) | 3.260 | 18 kolom |
| [`dataset_kategori.jsonl`](https://drive.google.com/file/d/1m7vwMKrGJRBGRrZa8ijyDuPQ13tEDhO8/view) | 11.487 | seluruhnya `sumber_data: shopee` |
| [`dataset_gabungan.jsonl`](https://drive.google.com/file/d/1c_ndcOuy7SutOdmiaaxTHSNVPmBkXWOt/view) | 2.048 | 1.885 scraping + 163 tokopedia2025 |
| [`dataset.jsonl`](https://drive.google.com/file/d/1tF0DWhbIxsdPMEd2E4xH7VXsfakVAoI7/view) | 1.885 | versi tanpa kolom `sumber_data` |
| [`harga_pasar.json`](https://drive.google.com/file/d/1h4MSR2cJQjiIC6V7jy-4oE_mtpzFy_il/view) | — | statistik harga per kategori: `p25`, `median`, `p75`, `total_terjual` |
| [`stores.json`](https://drive.google.com/file/d/1fR8Fh426ZlbEIW-jiGLaoXwqOWUhXuwE/view) | — | daftar toko: `host`, `platform`, `nama_toko`, `kota` |

**Hati-hati:** `produk.jsonl` (111.436), `produk.csv` (27.653), dan
`produk.parquet` (3.260) punya jumlah baris yang jauh berbeda. Ketiganya versi
pemrosesan yang berlainan, bukan format berbeda dari isi yang sama. Periksa dulu
sebelum memakai salah satunya.

---

## Berkas lokal di repo ini (semua ter-gitignore)

### `data/products.db` — 1,3 GB, sumber kebenaran Tokopedia

18.997 produk, plus tabel `raw_responses` (response mentah tiap request) dan
`keyword_progress`. Kalau butuh kolom yang tidak ada di dataset gabungan
(`specs`, `sold_count`, `rating`, `shop_name`), ambil dari sini.

### `data/exports/`

| Berkas | Baris | Kolom | Pakai? |
|---|---|---|---|
| `products.jsonl` / `.csv` / `.parquet` | 18.997 | 21 | **ya** — paling lengkap |
| `products_slim.jsonl` | 18.997 | 9 | untuk model teks saja |
| `products_slim_ready.jsonl` / `.csv` / `.parquet` | 18.443 | 8 | inilah yang masuk ke dataset gabungan |

Selisih 18.997 → 18.443 adalah produk yang belum ter-*enrich* (tanpa deskripsi PDP).

### `data/images/` — 126.583 berkas

Rata-rata 6,9 gambar per produk, maksimum 8. **Diverifikasi 100% ada**; 300
berkas sampel dibuka dengan PIL, tidak ada yang rusak atau di bawah 200 px.

### `data_drive/merged/` — hasil olahan yang siap pakai

| Berkas | Isi |
|---|---|
| `merged_local.parquet` | 28.443 baris; path gambar sudah lokal dan terverifikasi; tambahan kolom `n_gambar_lokal`, `gambar_hilang` |
| `train_pairs.parquet` | 27.997 baris; satu gambar utama per produk, `title_bersih` bebas promo/ALL CAPS, `specs` untuk 18.477 baris |
| `path_report.json` | ringkasan cakupan gambar per sumber |

---

## Cakupan gambar setelah dilokalkan

| Sumber | Baris | Gambar ketemu | Hilang | Baris tanpa gambar |
|---|---|---|---|---|
| tokopedia | 18.443 | 126.583 | 0 | 0 |
| blibli | 8.800 | 8.761 | 0 | 39 |
| tokopedia2025 | 1.200 | 2.217 | **9.614** | 311 |

Total: 28.093 dari 28.443 produk (98,8%) punya minimal satu gambar lokal.

---

## Yang perlu diwaspadai sebelum melatih

1. **`kategori_umkm` label lemah.** 37,8% jatuh ke `lainnya`, dan 55,2% dipetakan
   lewat tebakan kata kunci judul atau tidak terpetakan sama sekali. Sepatu lari
   pun bisa berlabel `kriya_rumah`. Jangan pakai sebagai label latih tanpa audit.
2. **Gambar tokopedia2025 tidak lengkap** dan tidak bisa dipulihkan.
3. **Deskripsi bukan teks jualan.** 33,6% memuat ALL CAPS panjang, 20,9% membahas
   ongkir/packing, 4,3% memuat nomor telepon penjual — **buang nomor telepon
   sebelum melatih apa pun**, itu data pribadi.
4. **Pisahkan train/test per grup, jangan acak.** 2.228 baris berjudul kembar dan
   4.280 baris memakai deskripsi yang sama persis dengan produk lain.
5. **Timpang.** Tokopedia 65% baris; `fashion_perawatan` 7.566 lawan
   `minuman_herbal` 1.796.

---

## Perlu sampling?

Untuk kerja tabel: **tidak**. 28.443 baris hanya 56 MB di memori — muat penuh.

Untuk gambar: satu gambar utama per produk = 28.093 berkas, masih wajar. Kalau
seluruh galeri dipakai (137.454 berkas), model akan melihat produk Tokopedia
tujuh kali lebih sering daripada blibli — batasi 1–2 gambar per produk, bukan
sampling baris.
