# LAPAKIN — Auto-listing dan rekomendasi harga untuk UMKM

Proyek lomba **AI Innovation Challenge (COMPFEST 18)**. Empat deliverable, tenggat
semuanya **25 Agustus 2026 pukul 23.55 WIB**: repo GitHub public (README + docker
compose), video proof of work ≤7 menit, video promosi ≤5 menit, dan proposal PDF
≤20 halaman. Bobot proposal hanya 15%; implementasi + kesiapan MVP 40%.

Repo ini bukan proyek baru. Sudah ada dataset 28.443 produk, pipeline yang
terukur, dan enam dokumen di `docs/`. Baca dulu, jangan bangun ulang.

---

## Peta cepat

| Butuh | Buka |
|---|---|
| Gambaran utuh + cara jalanin | `README.md` |
| Aturan lomba yang mengikat (tenggat, format, larangan) | `[AIC] AI Innovation Challenge.pdf` + `.claude/skills/paper-aic/references/format-proposal.md` |
| Draf proposal yang sudah ada | `docs/PROPOSAL.md` |
| Model harga lengkap + dasar hukum | `docs/MODEL_HARGA.md` |
| Ringkasan eksekutif untuk presentasi | `docs/RESUME_PRICING.md` |
| Dataset: mana yang siap pakai, mana yang cacat | `docs/DATASET.md` |
| Hasil ablasi & optimasi listing | `docs/OPTIMASI.md` |
| Cara capture ulang saat scraper mati | `docs/CAPTURE_HEADERS.md` |

Pipeline: `foto → gemma3:4b (VLM) → TF-IDF atas 28.443 produk → qwen2.5:7b (LLM)
→ judul/deskripsi/kategori` + `pricing_engine.py` (aritmetika bisnis, bukan ML).

---

## Aturan keras

**1. Angka harus punya sumber.** Setiap angka yang masuk paper, README, atau
docs wajib bisa dilahirkan ulang oleh satu perintah nyata di repo ini. Kalau
belum diukur, tulis "belum diukur" — jangan taksir. Ini aturan yang sudah
dipakai di seluruh `docs/`; jangan turunkan standarnya.

**2. Jangan mengarang sitasi.** Tidak ada judul paper, DOI, URL, nama penulis,
atau nomor peraturan yang ditulis dari ingatan. Yang belum diverifikasi ditandai
`[BELUM DIVERIFIKASI]` di draf, bukan dibiarkan lolos.

**3. Kekurangan dataset ikut ditulis, bukan disembunyikan.** Empat hal ini sudah
terdokumentasi dan harus muncul di bagian limitasi paper:
- 9.614 gambar tokopedia2025 hilang dan tidak bisa diunduh ulang
- `kategori_umkm` label lemah: 37,8% `lainnya`, 55,2% tebakan kata kunci
- 4,3% deskripsi memuat nomor telepon penjual
- 632 harga outlier (3,3%) dan 1.221 judul duplikat (6,4%)

**4. Data tidak diredistribusi.** Hasil scraping marketplace. `data/` dan
`data_drive/` ter-gitignore dan tetap begitu.

**5. Jangan sentuh rahasia.** `.env` dan `config/gql_capture.yaml` berisi cookie
sesi. Tidak dibaca, tidak di-echo, tidak di-commit.

**6. Bahasa dokumen: Indonesia.** Istilah teknis boleh Inggris. Kode dan nama
variabel ikut gaya yang sudah ada di file terkait.

---

## Kebiasaan kerja di repo ini

- Parser rusak → perbaiki `parsers.py` lalu `python main.py reparse`. **Jangan
  pernah scraping ulang** — setiap response mentah tersimpan di `raw_responses`.
- Klaim perbaikan pipeline hanya sah kalau ada angka sebelum/sesudah. Tiap
  perbaikan punya flag mematikan sendiri (`--tanpa-harga-hitung`,
  `--tanpa-saring-merek`, `--tanpa-contoh-pola`) supaya efeknya bisa diukur.
- Test tidak boleh menyentuh jaringan; `tests/conftest.py` memasang guard.
- Notebook memanggil fungsi dari `src/`, tidak menyalin logika pipeline.

## Perintah yang sering dipakai

```bash
python -m pytest -q                                    # test, offline total
python main.py stats                                   # kesehatan dataset
python scripts/retrieve_pipeline.py --n 20 --platform all
python scripts/eval_listing.py data_drive/eval/A.jsonl data_drive/eval/B.jsonl
python scripts/pricing_demo_offline.py                 # pricing tanpa Ollama
```

## Skill proyek

- `paper-aic` — menulis / merevisi paper lomba
- `eksperimen-aic` — menjalankan dan mengukur perubahan pipeline
- `/cek-angka <file>` — audit setiap angka di sebuah dokumen ke sumbernya
