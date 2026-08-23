---
name: eksperimen-aic
description: Mengubah dan mengukur pipeline AIC (VLM, retrieval TF-IDF, generator listing, pricing engine). Pakai saat diminta memperbaiki kualitas judul/deskripsi/harga, membandingkan model, menjalankan ablasi, atau mencatat hasil eksperimen.
---

# Mengubah pipeline AIC dengan bukti

Repo ini sudah punya kebiasaan: setiap perbaikan diukur, dan setiap perbaikan
bisa dimatikan sendiri supaya efeknya kelihatan. Ikuti itu.

## Urutan yang tidak boleh dilompati

1. **Baseline dulu.** Jalankan pengukuran pada kondisi sekarang, simpan
   keluarannya sebagai berkas. Tanpa baseline, perubahan apa pun tidak punya arti.
2. **Satu perubahan, satu flag.** Perbaikan baru harus punya flag untuk
   mematikannya, mengikuti pola yang ada: `--tanpa-harga-hitung`,
   `--tanpa-saring-merek`, `--tanpa-contoh-pola`, `--panjangkan`.
3. **Rerun dengan n dan seed yang sama.** Beda n = bukan perbandingan.
4. **Laporkan delta apa adanya**, termasuk yang memburuk.

## Perintah pengukuran

```bash
python scripts/probe_vlm_baseline.py --model gemma3:4b --n 100   # kualitas model visi
python scripts/retrieve_pipeline.py --n 20 --platform all        # pipeline penuh
python scripts/retrieve_pipeline.py --hanya-cari "sunscreen tube biru"
python scripts/eval_listing.py data_drive/eval/A.jsonl data_drive/eval/B.jsonl
python scripts/pricing_demo_offline.py                           # pricing tanpa Ollama
python scripts/pricing_demo.py --hpp 25000 --platform tokopedia
```

Rinciannya di `docs/OPTIMASI.md`. Angka pembanding yang sudah ada:
`gemma3:4b` skor inti 0,483 lawan `qwen3-vl:4b` 0,371 (n=100); pipeline penuh 17
detik per produk, deviasi harga 19% (n=20).

## Metrik yang dipakai

Pakai metrik yang sudah ada di `eval_listing.py` — jangan bikin skor baru di
tengah eksperimen lalu membandingkannya dengan angka lama. Kalau memang butuh
metrik baru, hitung ulang baseline dengan metrik itu juga.

Yang selalu dilaporkan bersama angka: **n, model, perintah persisnya, tanggal.**

## Batasan repo yang mengikat

- Parser berubah → `python main.py reparse`. **Tidak pernah scraping ulang**;
  semua response mentah ada di tabel `raw_responses`.
- Test tidak boleh menyentuh jaringan. `tests/conftest.py` memasang guard yang
  membuat request apa pun gagal keras — jangan dilonggarkan.
- Kolom milik stage 2 (`description`, `specs`, `image_urls`, `category_path`,
  `review_count`, `sold_count`) terkunci setelah `pdp_fetched = 1`. Jangan tulis
  ulang dari stage 1.
- Notebook memanggil fungsi dari `src/`; logika pipeline tidak disalin ke dalam sel.
- `.env` dan `config/gql_capture.yaml` berisi cookie sesi. Tidak dibaca, tidak dicetak.
- Pricing engine adalah aritmetika bisnis deterministik. Jangan diganti model
  ML — transparansi breakdown biaya adalah inti argumen paper.

## Mencatat hasil

Hasil yang bertahan masuk ke `docs/OPTIMASI.md` dengan format yang sudah dipakai
di sana: perintah, n, angka sebelum, angka sesudah. Angka yang masuk paper harus
sudah lewat sini dulu — lihat skill `paper-aic`.

Kalau eksperimen gagal atau memburuk, tetap catat. Ablasi yang gagal adalah isi
bagian hasil yang sah, dan lebih dipercaya juri daripada deretan angka yang
semuanya naik.
