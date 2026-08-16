# Tokopedia product scraper

Mengumpulkan judul, harga, deskripsi lengkap, dan gambar produk Tokopedia untuk
riset non-komersial: melatih model auto-description dan rekomendasi harga bagi
penjual UMKM.

Dua tahap, tiga backend yang bisa ditukar lewat config, resume otomatis dari
database.

---

## Baca ini dulu

Ketentuan layanan Tokopedia secara umum **melarang pengumpulan data otomatis**.
Project ini ditulis dengan asumsi pemakaian riset non-komersial bervolume wajar:

- Concurrency default **1**, jeda acak 2–5 detik antar-request.
- Circuit breaker berhenti setelah 10 kegagalan beruntun, bukan terus menghantam.
- Dataset dan gambar **tidak untuk diredistribusikan publik**.
- URL sumber selalu disimpan, jadi setiap baris bisa dilacak asalnya.
- Tidak ada pemecah CAPTCHA, dan tidak akan ada.

Menaikkan `rate_limit.concurrency` di atas 1 memperbesar risiko blokir dan
membebani server orang lain. Batas kerasnya 3; config menolak nilai di atas itu.

---

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m playwright install chromium   # hanya jika pakai backend playwright
```

Opsional, agar notebook memakai interpreter yang benar:

```powershell
.\.venv\Scripts\python.exe -m ipykernel install --user --name tokopedia-scraper --display-name "Python (tokopedia-scraper)"
```

Lalu salin template environment:

```powershell
Copy-Item .env.example .env
```

`.env` dan `config/gql_capture.yaml` sudah masuk `.gitignore`. Jangan pernah
di-commit — isinya cookie sesi.

---

## Capture dulu, baru scraping

Tidak ada satu pun nama query GraphQL, struktur payload, atau nama field
Tokopedia yang di-hardcode. Semuanya berasal dari capture DevTools milikmu.
Ketika Tokopedia mengubah schema, kamu capture ulang — kode tidak disentuh.

Langkah lengkapnya di **[docs/CAPTURE_HEADERS.md](docs/CAPTURE_HEADERS.md)**.
Ringkasnya:

```powershell
# 1. Chrome Incognito, jendela dimaksimalkan, DevTools > Network > Fetch/XHR
# 2. Cari produk, lalu Copy as cURL (bash): dua halaman search + satu halaman produk
python scripts/curl_to_config.py capture_page1.txt capture_page2.txt --keyword "air fryer"
python scripts/curl_to_config.py capture_pdp.txt --stage pdp --product-url "https://www.tokopedia.com/toko/slug"

# 3. verifikasi: satu request, satu parse, satu laporan
python scripts/verify_capture.py --product-url "https://www.tokopedia.com/toko/slug"

# 4. hapus file capture, isinya cookie mentah
Remove-Item capture_page1.txt, capture_page2.txt, capture_pdp.txt
```

Kenapa **dua** halaman untuk search: parameter paging diturunkan dari selisih
kedua capture, bukan ditebak. Halaman tidak harus berurutan — script membagi
selisih offset dengan selisih nomor halaman.

Kenapa **Incognito**: kalau login, `user_id` dan koordinat lokasimu ikut terbawa
ke setiap request scraper.

---

## Menjalankan

```powershell
python main.py search                              # stage 1: daftar produk
python main.py enrich                              # stage 2: deskripsi + galeri
python main.py images                              # unduh berkas gambar
python main.py export --format jsonl csv parquet
python main.py stats
```

Opsi yang sering dipakai:

```powershell
python main.py search --keyword "air fryer" --max-pages 3
python main.py enrich --limit 50
python main.py search --fetcher playwright
python main.py reparse                             # parse ulang dari raw, tanpa jaringan
python main.py --log-level DEBUG enrich
```

**Semuanya resume otomatis.** Ctrl-C aman: database di-commit setiap halaman dan
setiap produk. Jalankan ulang perintah yang sama untuk melanjutkan — keyword yang
sudah selesai dilewati tanpa request, produk yang sudah punya PDP tidak diambil ulang.

### Urutan yang benar

`search` → `enrich` → `images`.

Alasannya: thumbnail dari hasil search memakai URL bertanda tangan yang mati
dalam beberapa jam. `enrich` menggantinya dengan URL galeri dari PDP yang
**tidak bertanda tangan dan tidak kedaluwarsa**, sehingga `images` bisa
dijalankan kapan saja setelahnya.

Urutan ini dipaksakan, bukan sekadar disarankan: `images` hanya mengambil baris
yang sudah `pdp_fetched = 1`. Kalau kamu memang ingin thumbnail search yang
beresolusi rendah itu, panggil
`storage.products_needing_images(include_unenriched=True)`.

---

## Hasil terukur

Angka dari run nyata pada 50 keyword, bukan perkiraan:

| | |
|---|---|
| Stage 1 | 221 request, **18.997 produk unik**, ~21 menit, nol error |
| Kelengkapan | judul/harga/toko/gambar 100%, sold 98,9%, rating 94,9%, kategori 94,4% |
| Keberagaman | 8.695 toko berbeda; toko terbesar hanya 0,61% dataset |
| Stage 2 (sampel 602) | 96,7% menghasilkan deskripsi teks, median **988 karakter** |
| Laju stage 2 | ~3,5 detik per produk, jadi ~18 jam untuk 19 ribu produk |

Tokopedia memotong hasil di sekitar 320 produk per keyword. Menambah halaman
tidak menambah produk — yang menambah adalah **menambah keyword**.

Dua hal yang baru terlihat setelah datanya banyak, dan keduanya bukan bug:

- **632 harga tidak masuk akal (3,3%)**, misalnya kaos seharga Rp1.999.960.000.
  Response mentahnya memang berisi angka itu; penjualnya iseng atau salah ketik
  nol. Notebook 03 mendeteksinya per kategori dengan MAD pada log-harga.
- **1.221 judul duplikat (6,4%)** — produk yang di-listing ulang dengan id
  berbeda. `product_id` tetap unik, jadi ini bukan kegagalan dedupe, tapi perlu
  ditangani sebelum membagi train/test agar tidak bocor.

---

## Dataset siap pakai

Peta lengkapnya — termasuk tautan tiap berkas di Drive, jumlah baris, skema, dan
mana yang **jangan** dipakai — ada di **[docs/DATASET.md](docs/DATASET.md)**.

Datanya sendiri tidak ikut di repo (`data/` dan `data_drive/` ter-gitignore).
Tiga perintah untuk menyiapkannya dari nol:

```powershell
python scripts/fetch_drive_iac.py      # unduh dataset dari Drive (~0,9 GB)
python scripts/localize_merged.py      # path Colab -> path lokal, tiap berkas dicek ada
python scripts/build_train_pairs.py    # judul dibersihkan + specs -> train_pairs.parquet
```

Kalau hanya butuh berkas datanya tanpa gambar: tambahkan `--skip-images` (~640 MB).

### Pakai yang mana

| Kebutuhan | Berkas | Baris |
|---|---|---|
| Dataset gabungan siap olah | `data_drive/merged/merged_local.parquet` | 28.443 |
| Pasangan gambar → judul untuk latih/uji | `data_drive/merged/train_pairs.parquet` | 27.997 |
| Tokopedia paling lengkap (`specs`, `sold_count`, `rating`) | `data/exports/products.jsonl` | 18.997 |
| Sumber tunggal blibli | `data_drive/blibli/products.parquet` | 8.800 |

Dataset gabungan berisi **blibli 8.800 + tokopedia 18.443 + tokopedia2025 1.200**,
dan sudah dicocokkan baris demi baris ke ekspor sumbernya: nol baris hilang, nol
judul/harga/deskripsi/kategori/gambar yang berubah.

Tiga hal yang harus diketahui sebelum memakainya:

- **9.614 gambar tokopedia2025 tidak ada di mana pun** dan tidak bisa diunduh ulang
  (sumber itu tidak menyimpan URL). 311 dari 1.200 produknya berakhir tanpa gambar.
- **`kategori_umkm` label lemah** — 37,8% `lainnya`, 55,2% hasil tebakan kata kunci.
- **4,3% deskripsi memuat nomor telepon penjual.** Buang sebelum melatih apa pun.

---

## Pipeline gambar → listing

Prototipe dua tahap yang jalan sepenuhnya lokal lewat Ollama, tanpa API berbayar:

```
foto -> gemma3:4b -> fakta yang terlihat
      -> indeks TF-IDF 28 ribu produk -> kategori, kosakata, kisaran harga
      -> qwen2.5:7b -> judul + deskripsi + kategori + perkiraan harga
```

```powershell
# sekali saja: turunkan profil gaya per platform + kamus merek dari katalog
python scripts/build_platform_profiles.py
python scripts/build_lexicon.py

python scripts/probe_vlm_baseline.py --model gemma3:4b --n 100   # ukur model dasar
python scripts/retrieve_pipeline.py --n 20 --platform all        # satu foto, tiga lapak
python scripts/retrieve_pipeline.py --hanya-cari "sunscreen tube biru"
python scripts/eval_listing.py data_drive/eval/A.jsonl data_drive/eval/B.jsonl
```

Tiap perbaikan bisa dimatikan sendiri untuk diukur efeknya: `--tanpa-harga-hitung`,
`--tanpa-saring-merek`, `--tanpa-contoh-pola`, dan `--panjangkan` untuk menyalakan
pemanjangan judul. Rinciannya di **[docs/OPTIMASI.md](docs/OPTIMASI.md)**.

Datasetnya dipakai **saat model bekerja** — sebagai katalog rujukan untuk merek,
istilah, dan harga — bukan dilebur jadi bobot lewat fine-tune.

Yang terukur di 100 gambar yang sama: `gemma3:4b` unggul atas `qwen3-vl:4b`
(skor inti 0,483 lawan 0,371; nol keluaran bocor lawan 11). Pipeline penuh di 20
produk: 17 detik per produk, nol spesifikasi karangan, perkiraan harga meleset 19%.

---

## Backend

Ditukar lewat `config.yaml` (`fetcher:`) atau `--fetcher`, tanpa mengubah
sebaris pun kode pipeline.

| Backend | Biaya | Cara kerja | Kapan dipakai |
|---|---|---|---|
| `graphql` | gratis | `curl_cffi` dengan `impersonate="chrome"` langsung ke API internal | default; paling cepat |
| `playwright` | gratis | Chrome sungguhan, **mencegat** response GraphQL halaman | kalau `graphql` mulai kena 403 terus |
| `managed` | bayar | penyedia scraping pihak ketiga | mepet deadline; **baca peringatan di bawah** |
| `auto` | gratis | `graphql`, pindah ke `playwright` setelah N gagal beruntun | run panjang tanpa ditunggui |

Kenapa `curl_cffi` dan bukan `requests`: Tokopedia memeriksa sidik jari TLS.
Request dengan header selengkap apa pun dari `requests` tetap kena 403, karena
tanda tangan JA3-nya sudah ketahuan bukan browser sebelum satu header pun dibaca.

`PlaywrightFetcher` sengaja **tidak** membaca HTML. Ia menjalankan halaman lalu
mencegat request GraphQL yang dibuat halaman itu sendiri, sehingga parser JSON
yang sama dipakai ulang dan tidak ada selektor CSS yang perlu ditebak.

> **`playwright.headless` harus `false`.** Diuji langsung: Chromium headless
> ditolak Tokopedia di level HTTP/2 (`net::ERR_HTTP2_PROTOCOL_ERROR`) pada
> setiap halaman termasuk homepage — tanpa route-blocking, tanpa profil
> persisten, tanpa konfigurasi tambahan apa pun. Mode berjendela mendapat
> HTTP 200 dan 60 produk terparse. Jendela Chrome yang muncul adalah harga
> agar backend ini jalan; pakai di mesin yang sedang kamu gunakan, bukan di
> server tanpa layar.

> **`managed` belum diverifikasi.** Penanganan kredensial, pemilihan provider,
> dan pesan errornya sudah selesai dan teruji. Tapi bentuk request
> provider-spesifiknya ditulis dari ingatan, bukan dari dokumentasi resmi, dan
> setiap parameter bertanda `TODO verify` di
> `src/tokopedia_scraper/fetchers/managed.py`. `zenrows` dan `apify` adalah stub
> yang menolak jalan, bukan menebak. Sebelum menghabiskan uang: cek dokumentasi
> provider, lalu uji satu request dengan
> `python main.py enrich --fetcher managed --limit 1`.

---

## Skema data

Satu tabel `products` di `data/products.db`:

| kolom | catatan |
|---|---|
| `product_id` | primary key; dedupe otomatis |
| `shop_id`, `shop_name`, `url` | `url` sudah dibuang query trackingnya |
| `title`, `price`, `original_price`, `discount_pct`, `currency` | |
| `rating`, `review_count`, `sold_count` | `review_count` **hanya** ada dari PDP |
| `category_path` | list JSON |
| `description` | **prosa saja**; `NULL` kalau penjual mengunggahnya sebagai gambar |
| `specs` | dict JSON, mis. `{"Kondisi":"Baru"}`; tetap terisi walau `description` kosong |
| `image_urls`, `local_image_paths` | list JSON |
| `source_keyword`, `fetcher_used`, `scraped_at` | `scraped_at` ISO-8601 UTC |
| `pdp_fetched` | penanda resume stage 2 |

Dua tabel pendukung: `raw_responses` (setiap response disimpan **sebelum**
diparse) dan `keyword_progress` (checkpoint stage 1).

### Kenapa `description` boleh kosong

Banyak penjual Tokopedia menaruh seluruh deskripsi sebagai gambar. Untuk dataset
auto-description, produk seperti itu **harus terlihat kosong**, bukan ditambal
dengan teks yang bukan prosa. `specs` menampung fakta terstrukturnya, dan
`python main.py stats` melaporkan jumlahnya lewat metrik `specs_no_description`.

### Kepemilikan kolom

Stage 1 memiliki `price` dan menyegarkannya setiap run. Stage 2 memiliki
`description`, `specs`, `image_urls`, `category_path`, `review_count`, dan
`sold_count` — kolom itu terkunci begitu `pdp_fetched = 1`, sehingga re-run
search untuk memperbarui harga tidak merusak hasil enrich.

---

## Kalau ada yang rusak

| Gejala | Penyebab | Tindakan |
|---|---|---|
| 403 beruntun, circuit breaker terbuka | cookie kadaluwarsa | capture ulang (`docs/CAPTURE_HEADERS.md`) |
| 404 di endpoint | Tokopedia mengganti nama query | capture ulang |
| HTTP 200 tapi nol produk terparse | schema berubah | perbaiki `parsers.py`, lalu `python main.py reparse` — **tanpa scraping ulang** |
| `CaptureIncomplete` | `config/gql_capture.yaml` hilang/tidak lengkap | jalankan `scripts/curl_to_config.py` |
| `MissingCredential` | `.env` kosong untuk header yang diminta capture | isi `.env` |
| log penuh `schema drift` | Tokopedia menambah field | tidak mendesak; data lama tetap valid |

Diagnosis tercepat:

```powershell
python scripts/verify_capture.py            # satu request + laporan kelengkapan
python scripts/verify_capture.py --offline  # parse ulang response tersimpan, tanpa jaringan
```

Karena setiap response mentah tersimpan di `raw_responses`, bug parser **tidak
pernah** memaksa scraping ulang.

---

## Notebook

| Notebook | Untuk apa |
|---|---|
| `01_explore_endpoints.ipynb` | satu request, lihat struktur mentahnya. Buka ini pertama kali setiap ada yang rusak |
| `02_run_scrape.ipynb` | jalankan pipeline dengan progress bar; cocok untuk run kecil |
| `03_eda_dataset.ipynb` | menilai apakah dataset layak dipakai training |
| `04_eda_merged.ipynb` | memeriksa `data/merged/merged.parquet` — dataset gabungan tiga sumber dari Drive: kelengkapan, duplikat, harga, deskripsi, kategori, dan keberadaan berkas gambar |

Notebook memanggil fungsi dari `src/` — tidak ada logika pipeline yang
diduplikasi di dalam sel.

---

## Test

```powershell
python -m pytest -q
```

Fixture-nya response asli yang sudah direkam dan dipangkas. **Tidak ada satu pun
test yang menyentuh jaringan** — `conftest.py` memasang guard yang membuat
request apa pun gagal keras.

Setiap modul juga punya self-check yang bisa dijalankan sendiri:

```powershell
python -m tokopedia_scraper.parsers
python -m tokopedia_scraper.storage
```

---

## Struktur

```
main.py                     CLI: search | enrich | images | reparse | export | stats
config.yaml                 keyword dan semua knob
.env                        cookie dan API key (gitignored)
config/gql_capture.yaml     hasil capture DevTools (gitignored)
docs/CAPTURE_HEADERS.md     panduan capture langkah demi langkah
docs/DATASET.md             peta dataset: lokal + Drive, mana yang siap pakai
scripts/
  curl_to_config.py         cURL -> config + .env
  verify_capture.py         satu request, satu parse, satu laporan
  rename_images.py          menata ulang nama berkas gambar
  make_share_bundle.py      mengemas dataset untuk dibagikan
  fetch_drive_iac.py        unduh folder Drive IAC -> data_drive/
  localize_merged.py        path gambar Colab -> path lokal terverifikasi
  build_train_pairs.py      judul dibersihkan + specs -> train_pairs.parquet
  probe_vlm_baseline.py     ukur ketepatan model vision di gambar produkmu
  retrieve_pipeline.py      pipeline foto -> katalog -> judul + deskripsi
src/tokopedia_scraper/
  config.py                 config.yaml + .env, tervalidasi Pydantic
  models.py                 skema Product + coercion defensif
  storage.py                SQLite; database itu sendiri checkpoint-nya
  ratelimit.py              pacing, backoff, circuit breaker
  parsers.py                response mentah -> baris Product
  pipeline.py               stage 1, stage 2, reparse, export
  image_downloader.py       unduhan gambar terbatas
  fetchers/                 base, graphql, playwright, managed
tests/                      pytest + fixture response terekam
data/                       products.db, images/, exports/ (gitignored)
```
