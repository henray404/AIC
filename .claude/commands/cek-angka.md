---
description: Audit setiap angka dan klaim di sebuah dokumen terhadap sumbernya di repo
argument-hint: <path dokumen, mis. docs/PROPOSAL.md>
---

Audit berkas: $1

Tugasmu: cari setiap angka, persentase, nominal rupiah, jumlah baris data,
tanggal, nomor peraturan, dan klaim komparatif ("lebih cepat", "lebih akurat")
di dokumen itu, lalu telusuri sumbernya di repo.

Untuk tiap temuan, tentukan satu status:

- **TERLACAK** — ada perintah, berkas, atau dokumen di repo yang menghasilkan
  angka itu. Sebutkan sumbernya.
- **TIDAK COCOK** — sumbernya ada tapi angkanya beda. Tunjukkan kedua angka.
- **TANPA SUMBER** — tidak ada di repo. Ini yang paling berbahaya untuk paper lomba.
- **PERLU VERIFIKASI EKSTERNAL** — sitasi, tarif platform, atau dasar hukum yang
  sumbernya di luar repo. Cek status verifikasinya di `docs/MODEL_HARGA.md`.

Tempat mencari: `docs/DATASET.md`, `docs/OPTIMASI.md`, `docs/MODEL_HARGA.md`,
`README.md`, dan keluaran `python main.py stats`. Boleh jalankan perintah
pengukuran offline untuk membuktikan, jangan mengarang hasilnya.

Keluarkan satu tabel diurutkan: TANPA SUMBER dan TIDAK COCOK di atas. Jangan
perbaiki dokumennya kecuali diminta — laporkan dulu.
