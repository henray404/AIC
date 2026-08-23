# Cacat label kategori — terukur, belum diperbaiki

Status: **ditunda dengan sengaja.** Temuannya lengkap dan terukur; keputusan
memperbaikinya ditunda karena ongkosnya tidak sepadan dengan prioritas saat ini.

Halaman ini ada supaya angka `category_correct%` di
[`TABEL_SESI1.md`](TABEL_SESI1.md) dibaca dengan konteks yang benar, dan supaya
pekerjaannya bisa dilanjutkan tanpa mengulang analisis.

## Temuan inti

`category_correct%` **sebagian mengukur mutu label katalog, bukan mutu sistem.**

Bukti paling langsung: akurasi pipeline dipecah menurut cara label itu dibuat.

| cara label ditentukan | benar | salah | akurasi |
|---|---:|---:|---:|
| `tidak_terpetakan` | 77 | 8 | **90,6%** |
| `kata_kunci_judul` | 114 | 63 | 64,4% |
| `peta_l1` | 113 | 74 | 60,4% |
| `kata_kunci_kategori` | 14 | 19 | **42,4%** |

Pipeline paling akurat justru pada produk yang labelnya paling lemah, dan
paling "salah" pada label yang ditebak dari nama kategori. Pola itu terbalik
dari yang diharapkan kalau modelnya yang bermasalah.

Enam dari delapan "kesalahan" pada produk `tidak_terpetakan` ternyata jawaban
yang tepat:

| produk | label katalog | jawaban pipeline |
|---|---|---|
| Yuri Bathroom Cleaner | `lainnya` | `kriya_rumah` ✓ |
| Marina Bright Lotion | `lainnya` | `fashion_perawatan` ✓ |
| Mug Listrik / Teko Pemanas | `lainnya` | `kriya_rumah` ✓ |
| Gadoeh Rasa Kremes sachet | `lainnya` | `camilan_olahan` ✓ |
| ABON SAPI DAPOERBABE | `lainnya` | `camilan_olahan` ✓ |
| SPEEDS Matras Yoga PVC | `lainnya` | `kriya_rumah` ✓ |

## Kenapa labelnya rusak

`kategori_asal` bukan kategori marketplace — ia catatan **bagaimana** kategori
UMKM ditentukan:

| cara | jumlah | porsi |
|---|---:|---:|
| `peta_l1` | 10.854 | 38,2% |
| `kata_kunci_judul` | 9.907 | 34,8% |
| `tidak_terpetakan` | 5.799 | 20,4% |
| `kata_kunci_kategori` | 1.883 | 6,6% |

**`tidak_terpetakan` → `lainnya` 100%.** Semua 5.799 produk itu berlabel
`lainnya` semata karena tidak ada yang bisa memetakannya — bukan karena
barangnya memang tak berkategori.

Kode pelabelannya tidak ada di repo ini; `kategori_umkm` datang dari notebook
merge. [`DATASET.md`](DATASET.md) sudah menandainya sejak awal: *"Jangan pakai
sebagai label latih tanpa audit."*

## Masalah kedua: taksonominya tidak cocok dengan datanya

Tujuh kategori UMKM dirancang untuk pangan dan kriya. Data yang di-scrape
marketplace umum. Isi `lainnya` (10.738 produk) dipecah:

| kelompok | jumlah | porsi | perlu apa |
|---|---:|---:|---|
| elektronik | 5.269 | 49,1% | kategori baru |
| **label rusak** | 2.530 | 23,6% | sebenarnya `kriya_rumah` / `fashion_perawatan` |
| olahraga | 1.047 | 9,8% | kategori baru |
| tak jelas | 1.076 | 10,0% | perlu dilihat manusia |
| otomotif | 737 | 6,9% | kategori baru |
| kelompok kecil | 79 | 0,7% | biarkan (bayi 75, alat tulis 2, hewan 2) |

Elektronik sendirian **18,5% seluruh katalog**. Terlalu besar untuk keranjang
sampah.

## Tiga pilihan, dengan ongkosnya

| pilihan | `lainnya` jadi | ongkos |
|---|---:|---|
| sekarang | 37,8% | — |
| perbaiki label saja, taksonomi tetap 7 | 28,9% | ~1 jam, **tanpa GPU** |
| perbaiki label + 3 kategori baru | **4,1%** | ~2,6 jam GPU + label ulang |

Pilihan kedua murah karena `kategori_asli` **hanya dibaca `eval_listing.py`** —
ia tidak memengaruhi perilaku pipeline sama sekali. Yang dipakai pipeline saat
berjalan adalah kategori *tetangga*, bukan label produk ujinya sendiri.

Pilihan ketiga mahal karena mengubah keluaran sistem: prompt menyebut daftar
kategori, `sahkan_kategori` menambatkan ke daftar itu, dan
`harga_deterministik` memilih rentang harga per kategori. Semua angka kategori
harus diukur ulang.

## Berapa kategori yang masuk akal

Batasnya bukan jumlah, melainkan **produk per kategori** — sekitar 300–500.
Di bawah itu statistik harga jadi berisik dan model tidak bisa belajar.

```
elektronik  5.269  cukup
olahraga    1.047  cukup
otomotif      737  cukup
bayi           75  terlalu kecil
alat tulis      2  terlalu kecil
```

Jadi **10 kategori**, bukan 20. Elektronik bisa dipecah tiga (gawai, audio,
komputer) yang masing-masing masih di atas seribu — lebih berguna untuk
penjual, tapi tiga kategori berdekatan lebih sering tertukar dan
`category_correct%` kemungkinan turun.

Empat batasan kalau kategorinya ditambah terlalu banyak:

1. **Data per kelas habis** — di bawah ~300 produk tidak bisa dipelajari
2. **Statistik harga rontok** — `harga_deterministik` memakai median per
   kategori per platform; sel dengan <30 produk menghasilkan saran berisik
3. **Penambat tetangga goyah** — `sahkan_kategori` memakai modus lima tetangga;
   makin banyak kategori makin sering modusnya tidak bermakna
4. **Pelabel manusia melambat dan makin tidak sepakat** — tujuh pilihan muat di
   kepala, dua puluh tidak

## Kalau dilanjutkan nanti

**Siapa yang melabeli menentukan apakah angkanya bisa dipertahankan.** Kalau
pembuat sistem juga yang memperbaiki label kebenarannya, juri berhak curiga
labelnya digeser sampai sistemnya terlihat benar. Rancangannya harus buta:
pelabel melihat foto saja, tanpa pernah melihat jawaban sistem mana pun.

Model besar boleh dipakai melabeli, dengan dua syarat:

- **Bukan gemma dan bukan qwen.** `gemma3:12b` adalah pembanding di tabel; kalau
  ia juga menentukan kebenaran, baseline dinilai oleh dirinya sendiri. Pipeline
  pun memakai `gemma3:4b` di dalamnya, jadi kesalahannya berkorelasi.
- **Diverifikasi manusia pada sampel.** Label mesin + verifikasi manusia buta
  pada ~60 sampel menghasilkan klaim yang bisa dipertahankan: *"label diproduksi
  X, terverifikasi N% akurat terhadap penilaian manusia pada n=60."*

## Cara membaca angka kategori sementara ini

`category_correct% 65,9` di `TABEL_SESI1.md` adalah **batas bawah**. Sebagian
"kesalahan" yang dihitung adalah label katalog yang keliru, bukan sistem yang
salah menebak. Sebutkan itu di laporan; jangan sajikan sebagai ukuran murni
mutu sistem.

`category_valid% 100` tidak terpengaruh cacat ini — ia cuma mengukur apakah
keluarannya ada di taksonomi, dan itu dijamin kode.
