---
name: paper-aic
description: Menulis, merevisi, atau memeriksa proposal lomba AIC (AI Innovation Challenge, COMPFEST 18). Pakai saat diminta menulis latar belakang, tujuan, metodologi, alur dataset, alur model per fitur, kesimpulan, atau saat mengecek klaim di draf proposal.
---

# Menulis paper AIC

Paper ini dinilai juri yang boleh curiga. Nilai jatuh bukan karena tulisan
kurang indah, tapi karena **angka tanpa sumber, sitasi karangan, dan limitasi
yang disembunyikan**. Skill ini menjaga tiga hal itu.

## Format

**Sumber tunggal: rulebook resmi** `[AIC] AI Innovation Challenge.pdf` di akar
repo. Baca `references/format-proposal.md` sebelum menulis bagian mana pun.

Catatan lama "format AIC = Gemastik PPL, BAB I-V" **sudah dikoreksi 2026-08-22**
setelah rulebook dibaca: tidak ada BAB, tidak ada Rumusan Masalah, tidak ada
Tinjauan Pustaka. Strukturnya enam bagian datar, maksimal 20 halaman:

1. Nama Kelompok dan Judul/Nama Inovasi
2. Latar Belakang
3. Tujuan dan Manfaat Pengembangan
4. Metodologi -> alur dataset / alur pengembangan model **tiap fitur** / alur
   integrasi model ke environment kode
5. Metode lain yang mendukung alasan pengambilan keputusan
6. Kesimpulan

Tiga larangan yang paling mudah dilanggar: **institusi pendidikan dilarang
muncul dalam bentuk apa pun**, **model wajib di-fine-tune**, dan proyek hanya
boleh dikerjakan 17 Juni - 25 Agustus 2026. Proposal cuma satu dari empat
deliverable; bobotnya 15% dari total.

## Dari mana isi tiap bagian datang

Draf hidup: `docs/PROPOSAL.md` — sudah direstrukturisasi ke format rulebook
2026-08-22. Revisi berkas itu, jangan bikin berkas paper baru. Versi lama
bergaya Gemastik disimpan di `docs/.PROPOSAL_v2_gemastik_backup.md`.

| Bagian rulebook | Sumber di repo |
|---|---|
| 1 Nama Kelompok & Judul Inovasi | **nama tim masih placeholder `[NAMA TIM]`** |
| 2 Latar Belakang | `docs/MODEL_HARGA.md` §1–2; kaitkan ke tema Smart Commerce |
| 3 Tujuan dan Manfaat | — |
| 4a Alur dataset | `docs/DATASET.md`, `scripts/build_train_pairs.py` |
| 4b Alur model per fitur | `scripts/probe_vlm_baseline.py`, `retrieve_pipeline.py`, `build_lexicon.py`, `pricing_engine.py`, rekap `docs/OPTIMASI.md` |
| 4c Alur integrasi ke environment kode | `README.md`, batas modul, docker compose |
| 5 Metode lain pendukung keputusan | `docs/OPTIMASI.md` (ablasi + yang memburuk), `docs/RISET_MODEL_HARGA.md` |
| 6 Kesimpulan | — |

Angka yang boleh dipakai: 28.443 produk gabungan, 27.997 pasangan latih, skor
inti gemma3:4b 0,483 lawan qwen3-vl:4b 0,371 (n=100), 17,8 detik per produk,
tabel ablasi tujuh konfigurasi (n=10 produk, 30 listing per konfigurasi).
Sumbernya `docs/DATASET.md` dan `docs/OPTIMASI.md`. **Kalau sebuah angka tidak
ada di dua berkas itu atau di keluaran perintah nyata, angka itu belum diukur** —
jalankan pengukurannya (skill `eksperimen-aic`) atau tulis "belum diukur".
Jangan interpolasi, jangan bulatkan ke angka yang enak dibaca.

Dua hal yang saat ini berstatus **belum diukur** dan harus tetap ditulis begitu:
efek integrasi `pricing_engine.py` ke pipeline lewat `--hpp`, dan *fine-tune*
Fitur 1 / Fitur 3.

## Sitasi

- Hanya kutip yang sumbernya benar-benar dilihat di sesi ini atau tersimpan di repo.
- Tidak ada judul, penulis, tahun, DOI, atau URL yang ditulis dari ingatan.
- Peraturan (PP 20/2026, UU HPP No. 7/2021) dan tarif komisi marketplace sudah
  dicatat di `docs/MODEL_HARGA.md` lengkap dengan status verifikasinya —
  ikuti status itu, jangan naikkan sendiri jadi "terverifikasi".
- Butuh referensi akademik baru → pakai skill `litreview` atau
  `research-summarizer`, lalu catat sumbernya. Yang belum ketemu ditulis
  `[BELUM DIVERIFIKASI]`, bukan dikarang lalu diperbaiki nanti.

## Limitasi wajib muncul — bagian "Batasan dan Keterbatasan"

Rulebook tidak mewajibkan bagian ini, tapi butir penilaian Kesiapan MVP justru
menanyakan "apakah terdapat komponen yang **diakui tim** sebagai area yang masih
dapat ditingkatkan". Proposal tanpa batasan yang jujur dibongkar juri lebih cepat
daripada proposal dengan hasil sedang. Empat yang sudah terdokumentasi
(`CLAUDE.md` aturan 3): gambar tokopedia2025 hilang, `kategori_umkm` label lemah,
nomor telepon di deskripsi, outlier harga dan judul duplikat. Tambahkan: ablasi
baru di n=10 produk dan perbandingan model visual di n=100 — sebut n-nya, jangan
generalisasi.

## Serangan yang harus sudah dijawab di dalam paper

Tulis jawabannya di badan paper, bukan disiapkan untuk sesi tanya jawab saja:

1. **Kenapa bukan end-to-end deep learning untuk harga?** — harga ditentukan
   HPP, komisi, dan pajak; ML akan menghafal harga pasar tanpa bisa dijelaskan
   per komponen. Argumen ini sudah ada di `docs/PROPOSAL.md` §1.1.
2. **Datanya legal?** — riset non-komersial, tidak diredistribusi, rate limit 1
   concurrency, tidak ada pemecah CAPTCHA. Sumber tiap baris tersimpan.
3. **Angka biaya platform 2026 dari mana?** — status verifikasi per komponen ada
   di `docs/MODEL_HARGA.md`. Yang belum terverifikasi jangan dipakai sebagai
   klaim kuat.
4. **Generalisasi ke kategori lain?** — jawab dengan sebaran kategori dataset,
   bukan dengan optimisme.

## Gaya

Panggil skill `stop-slop` sebelum menyerahkan draf. Selain itu:

- Bahasa Indonesia baku, istilah teknis boleh Inggris dengan huruf miring pada
  kemunculan pertama.
- Tabel mengalahkan kata sifat. "17 detik per produk, n=20" bukan "sangat cepat".
- Tanpa pembuka basa-basi per bagian dan tanpa kalimat penutup yang mengulang
  isi bab.
- Klaim komparatif butuh pembanding yang nyata dan disebut n-nya.

## Sebelum selesai

Jalankan `/cek-angka docs/PROPOSAL.md` (atau berkas yang baru diedit) dan
laporkan angka yang tidak punya sumber. Jangan bilang selesai selagi masih ada
`[BELUM DIVERIFIKASI]` yang belum ditunjukkan ke user.
