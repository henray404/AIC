# Resume Proyek LAPAKIN — Pricing Model

**Tanggal:** 17 Agustus 2026  
**Dokumen ini:** Ringkasan eksekutif, cocok untuk presentasi atau laporan.

---

## Apa Itu LAPAKIN?

LAPAKIN adalah proyek riset untuk **membantu
pelaku UMKM lokal berjualan di e-commerce**. Saat ini LAPAKIN mampu:

1. ✅ **Menghasilkan judul produk** dari foto — otomatis, sesuai gaya tiap platform
2. ✅ **Menulis deskripsi** — hanya menyebut yang terlihat di foto, tidak mengarang
3. ✅ **Menentukan kategori** — dari 28.443 produk rujukan
4. ✅ **Memperkirakan harga pasar** — dari produk serupa di katalog
5. 🆕 **Menentukan harga jual yang tepat** — berdasarkan modal, pajak, biaya platform

---

## Masalah yang Diselesaikan

Penjual UMKM pemula sering **tidak tahu harus jual berapa**. Mereka tahu modal
Rp25.000, tapi tidak paham:

- Berapa potongan marketplace (5–15%)?
- Berapa pajaknya?
- Berapa margin yang wajar?
- Bagaimana harga pesaing?

Akibatnya: **jual terlalu murah → rugi**, atau **jual terlalu mahal → tidak laku**.

---

## Solusi: Model Penentuan Harga

### Input
| Data | Contoh |
|---|---|
| Foto barang | 📸 foto kaos polos |
| Modal (HPP) | Rp25.000 |
| Platform tujuan | Tokopedia / Shopee / Blibli |

### Proses
```
Foto → VLM (gemma3:4b) → "kaos polos pria hitam"
     → Cari produk serupa di 28.443 katalog
     → Hitung: HPP + pajak (0,5%) + komisi (5,5%) + ongkir (4%)
     → Sesuaikan dengan harga pasar
     → Bulatkan ke harga psikologis
```

### Output
| Informasi | Contoh |
|---|---|
| 💰 Harga rekomendasi | **Rp54.900** |
| 📉 Harga minimum (BEP) | Rp30.337 |
| 📊 Harga pasar (median) | Rp45.000 |
| 💵 Keuntungan bersih/unit | Rp22.409 (40,8%) |
| 📋 Breakdown lengkap | Modal, pajak, komisi, ongkir, margin |

---

## Kenapa Model Ini Berbeda?

### 1. Harga dihitung, bukan ditebak
Model **tidak memakai machine learning** untuk menentukan angka harga. Harga
dihitung secara deterministik dari formula:

```
Harga = (HPP + Biaya Packing) / (1 - Total Potongan%) × (1 + Margin%)
```

Ini dipilih karena:
- UMKM perlu **transparansi** — mereka harus paham kenapa harganya segitu
- HPP adalah **constraint keras** — tidak bisa dilanggar oleh prediksi model
- Formula bisa di-**audit** — tidak ada black box

### 2. Dikalibrasi ke harga pasar nyata
Formula tidak berdiri sendiri. Hasilnya di-**clamp** ke rentang harga produk
serupa yang sudah ada di marketplace:

- Kalau formula memberi Rp100.000 tapi pesaing jual Rp40.000–60.000, harga
  diturunkan ke rentang wajar
- Kalau formula memberi Rp30.000 tapi BEP = Rp35.000, harga DINAIKKAN — karena
  jual di bawah BEP = rugi

### 3. Tiga opsi harga
User diberi **tiga pilihan**, bukan satu angka mati:

| Strategi | Margin | Cocok untuk |
|---|---|---|
| 🔥 Agresif | Rendah (~30%) | Produk baru, perlu review dulu |
| ✅ Rekomendasi | Sedang (~50–80%) | Sehari-hari, stabil |
| 💎 Premium | Tinggi (~100–200%) | Produk unik, handmade, branded |

---

## Data yang Dipakai

| Sumber | Jumlah | Dipakai untuk |
|---|---|---|
| Tokopedia (scraping) | 18.443 produk | Benchmark harga + gaya judul |
| Blibli (ekspor mitra) | 8.800 produk | Benchmark harga lintas platform |
| Tokopedia 2025 | 1.200 produk | Tambahan cakupan |
| **Total** | **28.443 produk** | Katalog rujukan |

Dengan 126.583 gambar produk, 50 keyword, dari 8.695 toko berbeda.

---

## Penanganan Unit Modal dan Variasi

### Masalah: "Modal Rp50.000" — Itu untuk Apa?

UMKM sering beli bahan grosir tapi jual eceran. "Modal Rp50.000" bisa berarti:

| Yang dimaksud user | HPP sebenarnya per unit jual |
|---|---|
| Beli 1 kaos jadi | Rp50.000/pcs |
| Beli keripik 1 kg, jual per 100g | Rp5.000/bungkus |
| Beli sabun 1 lusin (12 pcs) | Rp4.167/pcs |

**Solusi:** Sistem akan **tanya balik** berdasarkan jenis barang yang dikenali
dari foto — bukan menebak. Pertanyaannya cerdas: kalau foto keripik, ditanya
"jual per berapa gram?"; kalau foto kaos, cukup "ini harga per pcs?".

Kalau user tidak jawab → asumsi paling aman: per 1 pcs. Lebih baik harga
terlalu tinggi (tapi untung) daripada terlalu rendah (dan rugi).

### Masalah: Variasi Produk — Harga Beda-beda

Ada **tiga jenis variasi**, dan masing-masing ditangani berbeda:

| Variasi | Contoh | Efek ke harga |
|---|---|---|
| **Warna/motif** | Hitam, Putih, Navy | Harga **SAMA** — 1 harga untuk semua |
| **Ukuran/isi** | 100g / 250g / 500g, S / M / L | Harga **BERBEDA** — proporsional |
| **Material/grade** | Reguler vs Premium | Harga **BERBEDA** — HPP beda |

Contoh output untuk kaos dengan variasi:

```
📋 Daftar Harga per Varian:

  Warna (harga sama untuk semua):
    Rp54.900 — Hitam, Putih, Navy, Abu

  Ukuran:
    S–XL : Rp54.900 (harga sama)
    XXL  : Rp59.900 (+5% bahan)
    3XL  : Rp64.900 (+10% bahan)
```

Detail lengkap: lihat [MODEL_HARGA.md](file:///Users/syahribanun/Documents/KULIAHH/Programming/AIC/AIC/docs/MODEL_HARGA.md) §3.4–3.5.

---

## Komponen Biaya yang Diperhitungkan

```
┌────────────────────────────────────────────────┐
│                HARGA JUAL                       │
│                                                │
│  ┌──────────────┐                              │
│  │   Modal/HPP  │ ← Input user                 │
│  ├──────────────┤                              │
│  │   Packing    │ ← Input user (opsional)      │
│  ├──────────────┤                              │
│  │ Komisi Platf │ ← 1%–15% (otomatis)          │
│  ├──────────────┤                              │
│  │ Gratis Ongkir│ ← 3%–6% (otomatis)           │
│  ├──────────────┤                              │
│  │ PPh Final    │ ← 0,5% (otomatis)            │
│  ├──────────────┤                              │
│  │ PPN (jk PKP) │ ← 12% (otomatis, opsional)  │
│  ├──────────────┤                              │
│  │   MARGIN     │ ← 10%–200% (per kategori)    │
│  └──────────────┘                              │
└────────────────────────────────────────────────┘
```

---

## Hasil Evaluasi Pipeline Sebelumnya

Dari eksperimen terdokumentasi di `docs/OPTIMASI.md`:

| Metrik | Sebelum Optimasi | Sesudah Optimasi |
|---|---|---|
| Harga meleset | 34,4% | **2,6%** |
| Merek karangan | 6,9% | **0,0%** |
| Kepatuhan panjang judul | 13,8% | **80,0%** |
| Skor inti listing | 0,292 | **0,403** |
| Kecepatan | 300 detik/produk | **18 detik/produk** |

---

## Status dan Langkah Selanjutnya

| No | Langkah | Status | Prioritas |
|---|---|---|---|
| 1 | Scraping + dataset | ✅ Selesai | — |
| 2 | Pipeline foto → listing | ✅ Selesai | — |
| 3 | Optimasi (merek, gaya, harga) | ✅ Selesai | — |
| 4 | **Model harga berbasis HPP** | 📐 **Draft selesai** | Tinggi |
| 5 | Implementasi `pricing_engine.py` | ⬜ Belum | Tinggi |
| 6 | Perbaikan `kategori_umkm` | ⬜ Belum | Tinggi |
| 7 | CLIP image similarity | ⬜ Belum | Sedang |
| 8 | Frontend/UI | ⬜ Belum | Rendah |

---

## Struktur File Proyek

```
AIC/
├── docs/
│   ├── MODEL_HARGA.md          ← 🆕 Draft model penentuan harga (baru dibuat)
│   ├── RESUME_PRICING.md       ← 🆕 Ringkasan ini (baru dibuat)
│   ├── DATASET.md              ← Peta dataset lengkap
│   ├── OPTIMASI.md             ← Hasil eksperimen pipeline
│   └── CAPTURE_HEADERS.md      ← Panduan capture headers
├── scripts/
│   ├── retrieve_pipeline.py    ← Pipeline foto → listing
│   ├── build_platform_profiles.py ← Profil harga per platform
│   ├── build_lexicon.py        ← Kamus merek dan kata jenis
│   └── ...
├── src/tokopedia_scraper/      ← Core scraper
├── notebooks/                  ← EDA dan eksplorasi
├── README.md                   ← Dokumentasi utama
└── config.yaml                 ← Konfigurasi
```

---

## Kesimpulan

Model penentuan harga LAPAKIN dirancang dengan prinsip:

1. **Transparan** — setiap komponen bisa dilihat dan dipahami UMKM
2. **Aman** — selalu di atas harga minimum, penjual tidak akan rugi
3. **Realistis** — dikalibrasi ke harga pasar dari 28.443 produk nyata
4. **Fleksibel** — tiga opsi harga (agresif, rekomendasi, premium) untuk strategi berbeda
5. **Terintegrasi** — memperluas pipeline yang sudah ada, bukan membangun ulang

Langkah berikutnya: **implementasi kode `pricing_engine.py`** dan pengujian pada
50–100 produk nyata untuk validasi.
