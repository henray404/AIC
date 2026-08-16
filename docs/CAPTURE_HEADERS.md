# Capture header & query GraphQL Tokopedia

Nama query, struktur payload, dan nama field GraphQL Tokopedia **berubah sewaktu-waktu**.
Karena itu tidak ada satu pun nama query atau nama field yang di-hardcode di project ini.
Semuanya datang dari hasil capture kamu sendiri di DevTools.

Kalau scraper mulai kena 403 terus, atau parser tiba-tiba mengembalikan nol produk:
**ulangi prosedur di halaman ini.** Tidak perlu menyentuh kode.

---

## Ringkas

```powershell
# 1. capture di Chrome (langkah A-E di bawah), simpan ke dua file
# 2. jalankan:
python scripts/curl_to_config.py capture_page1.txt capture_page2.txt --keyword "air fryer"
# 3. verifikasi:
jupyter notebook notebooks/01_explore_endpoints.ipynb
```

---

## A. Buka Tokopedia dan siapkan DevTools

1. Buka Chrome, masuk ke <https://www.tokopedia.com>.
2. Login kalau kamu memang mau scraping sebagai user login. Tidak wajib — hasil
   pencarian bisa diakses tanpa login, dan cookie tanpa login lebih aman
   dipakai. **Rekomendasi: jangan login.** Kalau kamu login, cookie sesi akun
   kamu ikut tersimpan di `.env`.
3. Tekan `F12` untuk membuka DevTools.
4. Pindah ke tab **Network**.
5. Klik filter **Fetch/XHR**. Ini membuang request gambar, CSS, dan font.
6. Centang **Preserve log** supaya request tidak hilang saat halaman navigasi.
7. Klik ikon Clear untuk mengosongkan daftar.

## B. Picu request pencarian

1. Ketik `air fryer` di kotak pencarian Tokopedia, tekan Enter.
2. Tunggu hasil muncul.
3. Di panel Network, cari request ke host **`gql.tokopedia.com`**.
   Ketik `gql` di kotak Filter untuk mempersempit.
4. Akan ada beberapa. Yang kamu cari adalah yang **response-nya berisi daftar produk**.
   Klik satu per satu, lihat tab **Response** atau **Preview**, cari yang isinya
   array produk dengan judul dan harga.

   > Nama query-nya apa? **Tidak perlu kamu hafal.** Script yang akan membacanya
   > dari URL request. Yang penting kamu memilih request yang response-nya benar.

5. Setelah ketemu, **klik kanan request itu -> Copy -> Copy as cURL (bash)**.

   PENTING: di Windows, Chrome menawarkan **Copy as cURL (cmd)** dan
   **Copy as cURL (bash)**. Pilih **bash**. Varian `cmd` memakai escape `^`
   yang tidak bisa diparse dengan andal.

6. Paste ke file teks, simpan sebagai `capture_page1.txt` di root project.

## C. Capture halaman kedua (untuk menemukan parameter paging)

Parameter paging tidak bisa ditebak — namanya bisa `page`, `start`, `rows`, atau
apa pun. Cara paling andal: bandingkan dua request yang hanya berbeda halamannya.

1. Di halaman hasil pencarian yang sama, scroll ke bawah, klik **halaman 2**
   (atau scroll sampai batch berikutnya termuat).
2. Di Network, cari request `gql.tokopedia.com` **yang baru muncul** dengan nama
   query yang sama seperti tadi.
3. **Copy as cURL (bash)** lagi, simpan sebagai `capture_page2.txt`.

Script akan men-diff kedua payload dan melaporkan field mana yang berubah — itulah
parameter paging-nya. Tanpa langkah ini scraper hanya bisa mengambil halaman 1
dan akan menandai paging sebagai `TODO` di file config.

## D. Capture halaman produk (PDP) — untuk stage 2

Deskripsi produk tidak ada di hasil pencarian. Ulangi prosedur yang sama:

1. Clear Network log, klik salah satu produk sampai masuk ke halaman detailnya.
2. Cari request `gql.tokopedia.com` yang response-nya berisi **deskripsi panjang**
   produk (bukan cuma judul dan harga). Biasanya ada beberapa request; yang kamu
   cari adalah yang punya field teks panjang.
3. **Copy as cURL (bash)** -> simpan sebagai `capture_pdp.txt`.

## E. Jalankan script

```powershell
# stage 1 (search) - dengan deteksi paging
python scripts/curl_to_config.py capture_page1.txt capture_page2.txt --keyword "air fryer"

# stage 2 (PDP)
python scripts/curl_to_config.py capture_pdp.txt --stage pdp --product-url "https://www.tokopedia.com/namatoko/nama-produk"
```

Script akan:

- mengekstrak **endpoint** dan **nama query** dari URL,
- memisahkan **header biasa** (masuk `config/gql_capture.yaml`) dari
  **header rahasia** — cookie, authorization, token (masuk `.env`),
- mengganti keyword kamu di body dengan placeholder `{{KEYWORD}}`,
- men-diff dua capture untuk menemukan parameter paging -> `{{PAGE}}` / `{{START}}`,
- menulis `config/gql_capture.yaml` dan meng-update `.env`.

Keduanya sudah masuk `.gitignore`. **Jangan pernah commit salah satunya.**

## F. Verifikasi

Buka `notebooks/01_explore_endpoints.ipynb` dan jalankan semua sel. Notebook itu
mengirim **satu** request dan menampilkan struktur response mentahnya. Kalau
sukses, lanjut ke pipeline. Kalau tidak, lihat tabel di bawah.

---

## Format `config/gql_capture.yaml`

Ditulis otomatis oleh script. Boleh kamu edit tangan kalau deteksi otomatisnya
meleset — file inilah satu-satunya tempat pengetahuan tentang schema Tokopedia.

```yaml
captured_at: '2026-08-04T14:03:11+00:00'

search:
  endpoint: https://gql.tokopedia.com/graphql/CONTOH_NAMA_QUERY
  operation_name: CONTOH_NAMA_QUERY
  method: POST
  headers:                       # header non-rahasia, aman disimpan
    content-type: application/json
    referer: https://www.tokopedia.com/search?q=air+fryer
    x-source: tokopedia-lite
  secret_env:                    # nama header -> nama env var; NILAI ada di .env
    cookie: TOKOPEDIA_COOKIE
    user-agent: TOKOPEDIA_UA
  body_template: |
    [{"operationName":"CONTOH_NAMA_QUERY","variables":{"params":"q={{KEYWORD}}&start={{START}}&rows={{ROWS}}"},"query":"..."}]
  paging:
    mode: start                  # start | page | none
    rows_per_page: 60            # dipakai untuk menghitung START = (page-1)*rows
  notes:
    - 'paging terdeteksi dari diff capture_page1 vs capture_page2'

pdp:
  endpoint: https://gql.tokopedia.com/graphql/CONTOH_QUERY_PDP
  operation_name: CONTOH_QUERY_PDP
  method: POST
  headers: {}
  secret_env: {}
  body_template: |
    [{"operationName":"CONTOH_QUERY_PDP","variables":{"shopDomain":"{{SHOP}}","productKey":"{{SLUG}}"},"query":"..."}]
```

Placeholder yang dikenali `GraphQLFetcher`:

| Placeholder | Diisi dengan |
|---|---|
| `{{KEYWORD}}` | keyword pencarian, sudah URL-encoded |
| `{{PAGE}}` | nomor halaman, 1-based |
| `{{START}}` | offset baris = `(page - 1) * rows_per_page` |
| `{{ROWS}}` | `search.rows_per_page` dari `config.yaml` |
| `{{SHOP}}` | segmen toko dari URL produk |
| `{{SLUG}}` | segmen slug produk dari URL produk |
| `{{URL}}` | URL produk lengkap |

---

## Kapan harus capture ulang

| Gejala | Kemungkinan besar | Tindakan |
|---|---|---|
| 403 berulang, circuit breaker terbuka | cookie kadaluwarsa | ulangi langkah A-E |
| 200 tapi nol produk terparse | schema berubah | ulangi capture, lalu re-parse dari `raw_responses` — tidak perlu scraping ulang |
| 404 di endpoint | nama query diganti Tokopedia | ulangi langkah A-B |
| Log penuh `schema drift: ... unhandled field` | Tokopedia menambah field | tidak mendesak; data lama tetap valid |

Cookie Tokopedia biasanya bertahan beberapa hari sampai beberapa minggu.
Anggap capture ulang sebagai perawatan rutin, bukan tanda ada yang rusak.

---

## Keamanan

- `.env` dan `config/gql_capture.yaml` ada di `.gitignore`. Cek dengan
  `git status` sebelum commit pertama.
- File `capture_*.txt` berisi cookie mentah. **Hapus setelah script dijalankan:**
  ```powershell
  Remove-Item capture_page1.txt, capture_page2.txt, capture_pdp.txt
  ```
- Jangan tempel isi cURL ke chat, issue, atau screenshot. Cookie di dalamnya
  setara dengan password sesi.
- Kalau kamu login saat capture, cookie itu mewakili akun kamu. Perlakukan
  seperti kredensial.
