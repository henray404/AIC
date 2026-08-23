# Format proposal AIC — sumber: rulebook resmi

**Sumber tunggal yang sah:** `[AIC] AI Innovation Challenge.pdf` di akar repo
(28 halaman, PDF gambar tanpa layer teks). Dibaca 2026-08-22.

> **Koreksi.** Catatan sebelumnya menyatakan "format AIC = format Gemastik PPL,
> BAB I–V". **Itu salah.** Rulebook tidak meminta BAB sama sekali, tidak meminta
> Rumusan Masalah, tidak meminta Tinjauan Pustaka, dan tidak meminta Batasan
> Perangkat Lunak sebagai subbab wajib. Draf lama tersimpan di
> `docs/.PROPOSAL_v2_gemastik_backup.md`.

Membaca ulang PDF-nya (`pdftoppm`/poppler **tidak** terpasang; `pypdf` + `PIL` ada):

```bash
python3 -c "
import pypdf, pathlib
out=pathlib.Path('/tmp/gb'); out.mkdir(exist_ok=True)
r=pypdf.PdfReader('[AIC] AI Innovation Challenge.pdf')
for i,p in enumerate(r.pages):
    for im in p.images:
        (out/f'p{i+1:02d}{pathlib.Path(im.name).suffix}').write_bytes(im.data)"
# lalu konversi .jp2 -> .png dengan PIL sebelum dibaca
```

---

## Struktur proposal yang diminta (rulebook hal. 17)

Berkas PDF, **maksimal 20 halaman**, tidak termasuk cover, daftar pustaka, dan
lampiran. "Terdiri **setidaknya** atas bagian berikut" — bagian tambahan boleh,
bagian di bawah ini tidak boleh hilang:

| # | Bagian | Catatan |
|---|---|---|
| 1 | Nama Kelompok dan Judul/Nama Inovasi | nama tim maks 30 karakter |
| 2 | Latar Belakang | |
| 3 | Tujuan dan Manfaat Pengembangan | satu bagian, bukan dua |
| 4 | Metodologi | wajib memuat tiga alur di bawah |
| 4a | — Alur dalam memperoleh dataset | |
| 4b | — Alur pengembangan model (**tiap feature**) | per fitur, bukan satu blok |
| 4c | — Alur integrasi model ke environment kode | |
| 5 | Metode lain yang mendukung alasan pengambilan keputusan | tempat ablasi & perbandingan |
| 6 | Kesimpulan | |

Bagian tambahan yang layak dipertahankan: Batasan dan Keterbatasan (jujur soal
n kecil), Kepatuhan data & tata kelola, Kelayakan adopsi — dua terakhir menyasar
bonus *Business Value dan Governance*.

---

## Larangan yang mudah dilanggar

- **Institusi pendidikan dilarang muncul dalam bentuk apa pun** (hal. 7 butir 6,
  hal. 21). Tidak ada nama kampus, fakultas, NIM/NRP, dosen pembimbing, logo,
  atau alamat institusi — termasuk di sampul. Ini beda tajam dari format
  Gemastik, yang justru mewajibkannya.
- **"Model wajib di fine tune sesuai inovasi fitur per tim"** (hal. 7 butir 10,
  diulang hal. 16). Boleh pakai API dan *pre-trained*, tapi penyesuaian model
  dinyatakan wajib. Status LAPAKIN: pasangan latih 27.997 siap, *fine-tune*
  belum dijalankan. Jangan tulis seolah sudah.
- **Proyek hanya boleh dikerjakan 17 Juni – 25 Agustus 2026** (hal. 15).
  Melanjutkan proyek yang sudah ada sebelum periode itu dilarang.
- **Batas 20 halaman.** Cek perkiraannya sebelum menyerahkan.

---

## Deliverable penyisihan — proposal cuma satu dari empat (hal. 12, 17)

Deadline seluruhnya **25 Agustus 2026 pukul 23.55 WIB**, submisi lewat situs
COMPFEST. Boleh submit berulang; yang dinilai submisi terakhir.

| Berkas | Ketentuan |
|---|---|
| Repo GitHub | visibility **public**, README berisi setup guide yang jelas, **docker compose**, pesan commit ikut Conventional Commits (`feat:`/`fix:`/`refactor:`) |
| Video proof of work | ≤ 7 menit, YouTube **unlisted**, judul `COMPFEST 18 AIC: PROOF OF WORK - [Nama Tim] - [Nama Proyek]`. Double screen terminal + aplikasi + timestamp. Boleh *fast-forward* dan *voice over*; **dilarang keras memotong (cut)** |
| Video promosi | ≤ 5 menit, MP4 min 720p, YouTube **public**, judul `COMPFEST 18 AIC: [Nama Tim] - [Nama Proyek]` |
| Proposal | PDF, struktur di atas |

Panitia berhak mendiskualifikasi bila ada poin belum lengkap, **terutama link
video proof of work dan source code**.

---

## Batasan ruang lingkup MVP (hal. 15) — jangan *overbuilt*

Dinilai eksplisit: "tidak overbuilt atau underbuilt".

- **Frontend:** hanya alur interaksi inti — satu input dari pengguna, tampilkan
  output AI. Tanpa dasbor analitik, tanpa otentikasi kompleks, tanpa halaman riwayat.
- **Backend:** hanya pemrosesan interaksi sinkron. Tanpa *background job*, tanpa
  *automated data logging*, tanpa basis data terdistribusi. Harus bisa dijalankan
  lewat `docker compose` mengikuti README.
- **Model AI:** hanya *core inference* dengan parameter statis saat demo. Tidak
  diminta *auto-tuning*, *bulk testing scripts*, atau *feedback loop* otomatis.

---

## Bobot penilaian penyisihan (hal. 23–25)

| Kriteria | Bobot |
|---|---|
| Implementasi Teknologi & Kematangan Arsitektur | 25% |
| Orisinalitas dan Dampak Sosial | 20% |
| Kesiapan MVP untuk Babak Final | 15% |
| Video Promosi | 15% |
| **Kualitas Proposal & Proses Pengembangan** | **15%** |
| Relevansi dengan Tema | 10% |
| Business Value dan Governance (bonus) | 3,5% |
| AIC Talks (bonus) | 1,5% |

Yang ditanya juri pada butir Kualitas Proposal: apakah strukturnya sesuai
ketentuan (metodologi, alur dataset, alur integrasi model); seberapa rinci dan
logis argumentasi teknisnya; apakah *decision making* pemilihan teknologi
dijelaskan **berbasis data atau analisis**; dan apakah cerita pengembangan
mencerminkan **proses iteratif yang reflektif, bukan sekadar deskripsi fitur**.
Ablasi LAPAKIN — termasuk yang memburuk — persis menjawab butir terakhir.

Butir Kematangan Arsitektur menanyakan modularitas: apakah komponen AI, backend,
dan frontend terpisah bersih, dan apakah README cukup untuk memahami alur sistem.

---

## Tema (hal. 3)

**"AI for the Backbone of the Economy"** — tiga area rantai pasok pasca-produksi
primer: Smart Manufacturing (pabrik), Smart Logistics (gudang & distribusi),
**Smart Commerce (toko & pasar)**. LAPAKIN masuk Smart Commerce. Relevansi tema
bernilai 10%; sebut temanya secara eksplisit, jangan biarkan juri menebak.

---

## Jadwal (hal. 10–11)

| Kegiatan | Tanggal 2026 |
|---|---|
| Periode pengerjaan | 17 Juni – 25 Agustus |
| Periode penjurian | 27 Agustus – 8 September |
| Standby Discord (kemungkinan live demo) | 9 & 10 September, 20.00 |
| Pengumuman finalis (8 tim) | 11 September |
| Mentoring / TM final | 20 & 22 September |
| Hackathon luring 10 jam | 26 September |
| Live pitching & Awarding Night | 27 September |

---

## Daftar pustaka

Tidak dihitung ke batas 20 halaman. Gaya IEEE bernomor urut kemunculan tetap
dipakai (warisan yang layak dari format Gemastik):

```
[6] X. Xie, J. Liu, H. Fan, Z. Han, Y. Tang, dan L. Qu, "DVG-Diffusion: Dual-View
    Guided Diffusion Model for CT Reconstruction from X-Rays," arXiv:2503.17804,
    2025. [Daring]. Tersedia: https://arxiv.org/abs/2503.17804
```

Perhatikan penghubung **"dan"** bukan "and", dan penanda **"[Daring]. Tersedia:"**.
