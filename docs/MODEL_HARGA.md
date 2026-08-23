# Model Penentuan Harga Jual E-Commerce untuk UMKM

**Tanggal:** 17 Agustus 2026  
**Proyek:** LAPAKIN — Auto-listing untuk UMKM lokal  
**Tujuan:** Memberikan rekomendasi harga jual produk UMKM di marketplace Indonesia
berdasarkan foto barang, modal awal, dan data pasar dari 28.443 produk yang sudah
dikumpulkan.

---

## 1. Ringkasan Masalah

Penjual UMKM sering kebingungan menentukan harga jual yang **wajar** dan
**kompetitif** saat memulai jualan di e-commerce. Mereka tahu berapa modal
pembuatan barangnya, tapi tidak tahu:

- Berapa margin keuntungan yang wajar untuk kategori barangnya?
- Berapa pajak dan biaya platform yang harus ditanggung?
- Bagaimana harga pesaing untuk barang serupa?
- Berapa harga psikologis yang pas agar terlihat menarik?

**Input dari user:**
1. **Foto barang** — untuk mengenali jenis, kategori, dan kelas produk
2. **Modal awal** — biaya produksi / HPP (Harga Pokok Penjualan)

**Output:**
- Harga jual yang direkomendasikan (per platform: Tokopedia, Shopee, Blibli)
- Breakdown komponen harga (modal, pajak, biaya platform, margin)
- Rentang harga kompetitor untuk barang serupa
- Penjelasan mengapa harga segitu

---

## 2. Komponen Pembentuk Harga

### 2.1 Pajak UMKM (Diverifikasi — PP 20/2026 & UU HPP)

| Komponen | Tarif | Ketentuan | Dasar hukum |
|---|---|---|---|
| **PPh Final UMKM** | **0,5%** dari omzet bruto | Omzet ≤ Rp4,8M/tahun. Berlaku untuk WP Orang Pribadi, PT Perorangan, dan Koperasi. **Tanpa batas waktu** untuk OP & PT Perorangan. | PP 20/2026 (merevisi PP 55/2022) |
| **Pembebasan PPh** | **0%** (bebas) | Omzet s.d. **Rp500 juta** pertama dalam setahun **tidak dikenai pajak** | PP 20/2026 Pasal 7 |
| **PPN** | **12%** | Wajib hanya kalau sudah PKP (omzet > Rp4,8M/tahun). Sebagian besar UMKM pemula **belum PKP** → **tidak kena PPN**. | UU HPP No. 7/2021 |

> **Untuk UMKM pemula dengan omzet < Rp500 juta/tahun: pajak = 0%.**
> Baru mulai bayar 0,5% setelah omzet melewati Rp500 juta. Ini artinya untuk
> kebanyakan user target kita, pajak bukan faktor signifikan di awal.

### 2.2 Biaya Platform (Diverifikasi — Data Mei–Agustus 2026)

#### Tokopedia (per 18 Mei 2026, terintegrasi TikTok Shop)

| Kategori | Komisi Dinamis | Catatan |
|---|---|---|
| Elektronik & Gadget | 3%–4% | Telepon 3%, Komputer 4% |
| Fashion & Aksesori | 7%–8,5% | Pakaian 8%, Aksesori 7,5% |
| Kecantikan & Perawatan | 7% | |
| Kebutuhan Harian (FMCG) | 6,5% | |
| Rumah Tangga & Dapur | 8% | |
| Mainan & Hobi | 8% | |
| Otomotif | 6,5%–7,5% | |
| **Biaya tambahan** | | |
| Biaya Pemrosesan Order | Rp1.250/pesanan | Flat per pesanan berhasil |
| Biaya Pre-Order | +3% | Kalau pakai fitur pre-order |
| Fee Cap | Maks Rp80.000/item | Per Juli 2026 (sebelumnya Rp650.000) |

> Tarif sudah termasuk pajak. Diskon komisi tersedia via program GMV Max / Growth Xtra.

#### Shopee (per 2 Mei 2026)

| Kategori Shopee | Biaya Admin (Star/Star+) | Biaya Admin (Reguler, ~20% lebih tinggi) |
|---|---|---|
| **Kat. A** — Fashion, F&B, Perlengkapan Rumah | 10% | ~12% |
| **Kat. B** — Aksesori, Tas, Skincare, Perlengkapan Bayi | 9%–9,5% | ~11% |
| **Kat. C** — Susu Formula, Suplemen, Perlengkapan Mandi Bayi | 6,5%–6,75% | ~8% |
| **Kat. D** — Elektronik (Laptop, HP, Kamera, Audio) | 5,25%–7,5% | ~7%–9% |
| **Kat. E** — Barang Mewah, Logam Mulia | 4,25% | ~5% |
| **Kat. Khusus** — E-money, Voucher, Tiket | 2,5% | ~3% |
| **Biaya tambahan** | | |
| Biaya Proses Pesanan | Rp1.250/pesanan | |
| Gratis Ongkir XTRA | 4%–9% (tergantung kategori & ukuran) | Opsional tapi sangat mempengaruhi visibilitas |
| Biaya Pre-Order | +3% | |

> Biaya admin sudah termasuk PPN. Penjual baru bisa dapat insentif bebas biaya untuk 500–1.000 pesanan pertama.

#### Blibli (2025–2026, Seller Regular)

| Kategori | Komisi |
|---|---|
| Elektronik (HP, Tablet, Komputer) | ~4,25% |
| Kuliner, Buku, Produk Digital | ~5,75% |
| Home & Living, Mainan, Bayi | 7,5%–8% |
| Fashion & Lifestyle | Hingga 10% |

> Flagship Store punya skema berbeda. Cek menu "Kontrak & Komisi" di Blibli Seller Center.

#### Ringkasan Total Biaya Platform (Estimasi untuk Model)

Untuk perhitungan, kita pakai **total efektif** (komisi + gratis ongkir + biaya proses):

| Kategori (kami) | Tokopedia | Shopee (Star) | Blibli |
|---|---|---|---|
| `fashion_perawatan` | **8% + Rp1.250** | **10% + 6% ongkir + Rp1.250** | **10%** |
| `elektronik_gadget` | **3,5% + Rp1.250** | **6,5% + 5% ongkir + Rp1.250** | **4,25%** |
| `makanan_minuman` | **6,5% + Rp1.250** | **10% + 6% ongkir + Rp1.250** | **5,75%** |
| `skincare_kecantikan` | **7% + Rp1.250** | **9,5% + 6% ongkir + Rp1.250** | **8%** |
| `dapur_rumah` | **8% + Rp1.250** | **10% + 6% ongkir + Rp1.250** | **7,5%** |
| `kesehatan_olahraga` | **6,5% + Rp1.250** | **9% + 5% ongkir + Rp1.250** | **7,5%** |
| `kriya_rumah` | **8% + Rp1.250** | **10% + 6% ongkir + Rp1.250** | **8%** |

> **Shopee paling mahal** karena gratis ongkir XTRA menambah 4–9% di atas biaya admin.
> **Tokopedia** fee cap Rp80.000/item menguntungkan produk mahal.
> **Blibli** paling sederhana, tapi traffic lebih rendah.

### 2.3 Faktor Sekunder (Pengaruh Signifikan)

| Faktor | Pengaruh | Cara menentukan |
|---|---|---|
| **Harga kompetitor** | Benchmark utama: kalau terlalu mahal tidak laku, kalau terlalu murah rugi | Dari dataset 28.443 produk (TF-IDF similarity search) |
| **Kategori barang** | Margin wajar berbeda per kategori (fashion 50–200%, F&B 30–100%) | Dari foto → VLM → pencarian katalog |
| **Kondisi barang** | Baru vs bekas mempengaruhi valuasi | Dari specs/VLM |
| **Brand/merek** | Barang bermerek bisa premium, tanpa merek harus kompetitif | Dari foto + lexicon |
| **Tren permintaan** | Produk trending bisa lebih mahal | Dari sold_count data |

### 2.4 Faktor Tersier (Pengaruh Kecil tapi Ada)

| Faktor | Contoh |
|---|---|
| Ongkos kirim | Barang berat/besar perlu harga lebih tinggi untuk menutup subsidi ongkir |
| Biaya packing | Bubble wrap, kardus, stiker, dll |
| Return rate | Kategori fashion return-nya lebih tinggi |
| Psikologi harga | Rp49.900 vs Rp50.000 — yang pertama "terasa" lebih murah |
| Musim/seasonal | Harga payung naik saat hujan; harga AC naik saat kemarau |

---

## 3. Formula Penentuan Harga

### 3.1 Formula Dasar (Floor Price / Harga Minimum)

```
Harga_Minimum = HPP / (1 - Total_Potongan%)

dimana:
  Total_Potongan% = Komisi_Platform% + Pajak% + Biaya_Ongkir% + Biaya_Packing%
```

**Contoh:**
- HPP = Rp50.000
- Komisi Tokopedia = 5%
- Pajak PPh Final = 0,5%
- Subsidi ongkir = 5%
- Biaya packing = 2%

```
Total_Potongan% = 5% + 0.5% + 5% + 2% = 12.5%
Harga_Minimum   = 50.000 / (1 - 0.125) = 50.000 / 0.875 = Rp57.143
```

> Ini adalah **harga BEP** (break-even point). Di bawah ini, penjual RUGI.

### 3.2 Formula Harga Jual dengan Margin

```
Harga_Jual = Harga_Minimum × (1 + Target_Margin%)
```

**Target margin per kategori** (diturunkan dari data dan benchmark industri):

| Kategori | Margin Wajar | Alasan |
|---|---|---|
| `fashion_perawatan` | 50%–150% | Nilai persepsi tinggi, biaya produksi rendah |
| `elektronik_gadget` | 10%–30% | Persaingan ketat, harga transparan |
| `makanan_minuman` | 30%–80% | Perlu cepat laku, ada expired date |
| `minuman_herbal` | 40%–100% | Niche market, persepsi premium |
| `skincare_kecantikan` | 40%–120% | Brand value tinggi, repeat purchase |
| `dapur_rumah` | 25%–60% | Fungsional, banyak pembanding |
| `kesehatan_olahraga` | 30%–70% | Campuran fungsional dan lifestyle |
| `kriya_rumah` | 50%–200% | Handmade/artisan premium |
| `lainnya` | 30%–80% | Default konservatif |

### 3.3 Formula Lengkap: Harga Rekomendasi Final (REVISI — Market-First)

**Prinsip utama: harga ditentukan oleh PASAR, bukan oleh HPP + margin.**

Model versi pertama punya cacat: kalau HPP + margin = Rp54.900 tapi pasar P25 =
Rp35.000, model tetap merekomendasikan Rp54.900. Hasilnya produk UMKM
kemahalan dan tidak laku.

Logika yang benar: **pasar yang menentukan berapa orang mau bayar.** HPP hanya
menentukan apakah kamu bisa untung di harga itu.

```
# LANGKAH 1: Tentukan harga PASAR dulu (dari data 28.443 produk)
Harga_Pasar = Median harga produk serupa dari katalog

# LANGKAH 2: Hitung BEP (break-even point)
Harga_BEP = HPP_per_unit / (1 - Total_Potongan%)

# LANGKAH 3: Bandingkan BEP vs Pasar → tentukan ZONA
if Harga_BEP > Harga_Pasar_P75:
    ZONA = "BAHAYA"     → HPP terlalu tinggi, tidak bisa bersaing
elif Harga_BEP > Harga_Pasar_Median:
    ZONA = "KETAT"      → Bisa jual tapi margin tipis
elif Harga_BEP > Harga_Pasar_P25:
    ZONA = "WAJAR"      → Posisi kompetitif normal
else:
    ZONA = "BAGUS"      → HPP rendah, banyak ruang margin

# LANGKAH 4: Tentukan harga berdasarkan ZONA
if ZONA == "BAHAYA":
    # JANGAN rekomendasikan harga di atas pasar!
    # Tampilkan PERINGATAN ke user:
    peringatan = "Modal kamu terlalu tinggi untuk bersaing di kategori ini."
    saran = ["Turunkan HPP (cari supplier lebih murah)",
             "Tambah value (bundling, kemasan premium)",
             "Jual di platform yang lebih mahal (Blibli)",
             "Target niche market, jangan mass market"]
    harga_rekom = Harga_Pasar_P75   # tetap kasih angka, tapi dengan disclaimer

elif ZONA == "KETAT":
    # Margin tipis tapi masih bisa jual
    harga_rekom = clamp(
        Harga_BEP × 1.15,              # margin tipis 15%
        Harga_Pasar_Median,             # minimal di median pasar
        Harga_Pasar_P75                 # jangan di atas P75
    )
    peringatan = "Margin kamu tipis. Pertimbangkan cara menurunkan HPP."

elif ZONA == "WAJAR":
    # Posisi ideal — anchor ke pasar, pastikan di atas BEP
    harga_rekom = clamp(
        Harga_Pasar_Median,             # anchor utama: median pasar
        Harga_BEP × 1.20,              # minimal BEP + 20% margin
        Harga_Pasar_P75                 # jangan di atas P75
    )

elif ZONA == "BAGUS":
    # HPP rendah, banyak ruang. Jual di median pasar, untung besar
    harga_rekom = Harga_Pasar_Median
    # Margin otomatis tinggi karena HPP jauh di bawah harga jual
```

**Kenapa market-first lebih baik dari cost-plus?**

| | Cost-Plus (lama) | Market-First (baru) |
|---|---|---|
| Logika | HPP × margin = harga | Pasar = harga; cek apakah HPP bisa untung |
| Kalau HPP tinggi | Harga melambung, tidak laku | **Peringatan:** "HPP terlalu tinggi" |
| Kalau HPP rendah | Harga terlalu murah, meninggalkan uang di meja | Jual di median pasar, margin besar |
| Anchor | Modal penjual | **Kemauan bayar pembeli** |

### 3.3.1 Penanganan Zona BAHAYA: "HPP Terlalu Tinggi"

Ini skenario yang sering terjadi dan **harus ditangani eksplisit**, bukan
disembunyikan:

```
┌────────────────────────────────────────────────────────┐
│  ⚠️  PERINGATAN: Modal Kamu Terlalu Tinggi             │
│                                                        │
│  Modal per unit:  Rp27.000                              │
│  Harga BEP:       Rp33.300 (setelah biaya platform)     │
│  Harga pasar:     Rp15.000 – Rp28.000 (median Rp22.000) │
│                                                        │
│  Kalau jual di Rp33.300 → TERLALU MAHAL                 │
│  Produk serupa di marketplace rata-rata Rp22.000        │
│  Pembeli akan pilih yang lebih murah.                    │
│                                                        │
│  💡 Saran:                                              │
│  1. Turunkan modal → cari supplier lebih murah          │
│  2. Tambah kemasan premium → bisa jual lebih tinggi     │
│  3. Bundling → jual set 3 pcs dapat diskon per unit     │
│  4. Coba platform lain → Blibli biayanya lebih rendah   │
│  5. Target segmen premium → bukan mass market           │
│                                                        │
│  Kalau tetap mau jual: harga minimum Rp33.300           │
│  (di bawah ini RUGI)                                    │
└────────────────────────────────────────────────────────┘
```

Kemudian diterapkan **pembulatan psikologis**:

```python
def bulatkan_psikologis(harga: int) -> int:
    """Bulatkan ke angka psikologis terdekat."""
    if harga < 10_000:
        return round(harga / 500) * 500 - 100      # Rp4.900, Rp7.400
    elif harga < 100_000:
        return round(harga / 1_000) * 1_000 - 100   # Rp49.900, Rp79.900
    elif harga < 1_000_000:
        return round(harga / 5_000) * 5_000 - 100   # Rp149.900, Rp249.900
    else:
        return round(harga / 10_000) * 10_000 - 100  # Rp999.900, Rp1.499.900
```

---

## 3.4 Masalah Unit Modal: Per Pcs, Per Kg, atau Per Bal?

### Masalahnya

UMKM sering membeli bahan/barang dalam satuan **grosir** tapi menjual dalam
satuan **eceran**. Kalau user bilang "modal Rp50.000", bisa berarti:

| Yang user maksud | HPP per unit jual |
|---|---|
| Beli kaos 1 pcs = Rp50.000 | Rp50.000/pcs |
| Beli kain 1 meter = Rp50.000 (jadi 2 kaos) | Rp25.000/pcs |
| Beli keripik 1 kg = Rp50.000 (jual per 100g) | Rp5.000/bungkus |
| Beli sabun 1 bal (12 pcs) = Rp50.000 | Rp4.167/pcs |
| Beli benang 1 gulung = Rp50.000 (jadi 5 gelang) | Rp10.000/pcs |

Kalau kita **salah asumsi unit**, harga jual bisa meleset sangat jauh.

### Strategi Penanganan

**Pendekatan: Tanya eksplisit, bantu dengan konteks dari foto.**

Sistem tidak boleh menebak unit — harus **selalu tanya user**. Tapi pertanyaannya
bisa dipintar-pintarkan berdasarkan jenis barang yang terdeteksi dari foto:

```python
# Unit yang lazim per kategori — untuk menyodorkan pilihan yang relevan
UNIT_LAZIM = {
    "makanan_minuman": {
        "satuan_beli": ["kg", "liter", "karung", "bal", "dus"],
        "satuan_jual": ["pcs", "bungkus", "sachet", "botol", "cup"],
        "pertanyaan": "Modal Rp{hpp:,} ini untuk beli berapa {satuan_beli}? "
                      "Dan per kemasan jual isinya berapa {satuan_jual}?",
    },
    "fashion_perawatan": {
        "satuan_beli": ["pcs", "lusin (12)", "kodi (20)", "meter (kain)"],
        "satuan_jual": ["pcs"],
        "pertanyaan": "Modal Rp{hpp:,} ini untuk {satuan_beli} barang?",
    },
    "skincare_kecantikan": {
        "satuan_beli": ["pcs", "lusin (12)", "liter (isi ulang)"],
        "satuan_jual": ["pcs", "botol", "tube", "sachet"],
        "pertanyaan": "Modal Rp{hpp:,} ini untuk berapa {satuan_beli}?",
    },
    "elektronik_gadget": {
        "satuan_beli": ["pcs", "unit"],
        "satuan_jual": ["pcs", "unit"],
        "pertanyaan": None,  # elektronik hampir selalu per pcs
    },
    "kriya_rumah": {
        "satuan_beli": ["pcs", "meter (kain)", "gulung (benang)", "lembar"],
        "satuan_jual": ["pcs"],
        "pertanyaan": "Modal Rp{hpp:,} ini bahan untuk berapa produk jadi?",
    },
}
```

### Alur Klarifikasi Unit

```
User upload foto + isi modal Rp50.000
    │
    ▼
VLM kenali: "keripik pisang" → kategori: makanan_minuman
    │
    ▼
Sistem tanya:
    ┌────────────────────────────────────────────────┐
    │  Foto kamu dikenali sebagai: Keripik Pisang    │
    │                                                │
    │  Modal Rp50.000 ini untuk:                     │
    │  ○ 1 bungkus jadi (siap jual)                  │
    │  ○ 1 kg bahan mentah (pisang)                  │
    │  ○ ... kg keripik jadi (isi sendiri)            │
    │  ○ Lainnya: ___ [satuan] = ___ [jumlah]        │
    │                                                │
    │  Kalau isi sendiri, per bungkus berapa gram?    │
    │  ○ 100g  ○ 150g  ○ 250g  ○ 500g  ○ ___g       │
    └────────────────────────────────────────────────┘
```

### Konversi ke HPP Per Unit Jual

```python
def hitung_hpp_per_unit(modal_total: int, jumlah_unit: float,
                        biaya_produksi_per_unit: int = 0) -> int:
    """Konversi modal grosir → HPP per unit jual.

    Args:
        modal_total: total uang yang dikeluarkan untuk beli bahan
        jumlah_unit: berapa unit jual yang dihasilkan
        biaya_produksi_per_unit: biaya tambahan per unit (kemasan, label, dll)
    """
    hpp_bahan = modal_total / jumlah_unit
    return int(hpp_bahan + biaya_produksi_per_unit)

# Contoh:
# Beli pisang 5 kg @ Rp50.000, jadi 20 bungkus keripik @ 250g
# Biaya kemasan per bungkus Rp1.500
hpp = hitung_hpp_per_unit(
    modal_total=50_000,     # beli 5 kg
    jumlah_unit=20,         # jadi 20 bungkus
    biaya_produksi_per_unit=1_500  # kemasan
)
# → hpp = 50.000/20 + 1.500 = Rp4.000/bungkus
```

### Default Kalau User Tidak Jawab

Kalau user skip pertanyaan unit, pakai **asumsi paling aman** (per 1 unit jual)
supaya harga tidak pernah terlalu rendah. Lebih baik salah ke atas (terlalu
mahal tapi untung) daripada salah ke bawah (terlalu murah dan rugi).

---

## 3.5 Masalah Variasi Produk: Ukuran, Warna, Berat

### Tiga Jenis Variasi dan Dampaknya ke Harga

Tidak semua variasi mempengaruhi harga. Penanganannya **sangat berbeda**:

| Jenis Variasi | Contoh | Efek ke Harga | Penanganan |
|---|---|---|---|
| **Ukuran/isi (kuantitatif)** | 100g / 250g / 500g, S / M / L / XL | **Harga BERBEDA** — proporsional | Hitung per satuan terkecil, kalikan |
| **Warna/motif (kosmetik)** | Hitam / Putih / Merah, Polos / Stripe | **Harga SAMA** | Satu harga untuk semua |
| **Material/grade (kualitatif)** | Katun / Polyester, Premium / Reguler | **Harga BERBEDA** — tidak proporsional | Hitung terpisah per varian |

### Variasi Ukuran/Isi — Harga Proporsional

Paling umum di makanan, minuman, skincare. Harga biasanya **tidak 100% linear**
— ada diskon volume:

```python
# Faktor harga per ukuran — diturunkan dari pola marketplace
FAKTOR_UKURAN = {
    "makanan_minuman": {
        # ukuran_kecil : ukuran_besar
        # harga per gram TURUN seiring ukuran naik (diskon volume)
        "rasio": {
            "50g":   1.00,    # harga dasar
            "100g":  1.85,    # bukan 2x, tapi 1.85x (diskon 7.5%)
            "150g":  2.60,    # bukan 3x, tapi 2.60x (diskon 13%)
            "250g":  4.00,    # bukan 5x, tapi 4.00x (diskon 20%)
            "500g":  7.00,    # bukan 10x, tapi 7.00x (diskon 30%)
            "1kg":  12.00,    # bukan 20x, tapi 12.00x (diskon 40%)
        },
        "catatan": "Semakin besar kemasan, harga per gram semakin murah"
    },
    "skincare_kecantikan": {
        "rasio": {
            "15ml":  1.00,
            "30ml":  1.80,    # diskon 10%
            "60ml":  3.20,    # diskon 20%
            "100ml": 4.80,    # diskon 25%
        },
    },
}
```

**Contoh:** User jual keripik, HPP per 100g = Rp5.000

| Ukuran | Faktor | HPP | Harga Jual (margin 50%) |
|---|---|---|---|
| 100g | 1.00× | Rp5.000 | Rp12.900 |
| 150g | 1.40× | Rp7.000 | Rp17.900 |
| 250g | 2.15× | Rp10.750 | Rp27.900 |
| 500g | 3.70× | Rp18.500 | Rp44.900 |

### Variasi Warna/Motif — Harga Sama

Paling umum di fashion, aksesoris, perlengkapan rumah. Harga biasanya **sama**
untuk semua warna, kecuali kalau ada warna/motif yang butuh proses ekstra
(misalnya batik tulis vs batik cap).

```python
def variasi_kosmetik(harga_dasar: int, jumlah_varian: int) -> dict:
    """Warna/motif → harga sama, tapi perlu daftar semua varian."""
    return {
        "harga": harga_dasar,
        "catatan": f"Harga sama untuk semua {jumlah_varian} varian warna/motif",
        "saran": "Di marketplace, buat 1 listing dengan pilihan varian, "
                 "bukan listing terpisah per warna"
    }
```

### Variasi Material/Grade — Harga Berbeda Tidak Proporsional

Paling umum di fashion (katun vs polyester), kerajinan (kayu jati vs pinus),
dan makanan (premium vs reguler).

Tidak bisa dihitung proporsional karena **HPP-nya beda**. Solusi: minta user
input HPP per grade, atau kalau cuma satu HPP, berikan estimasi berdasarkan
rasio pasar:

```python
RASIO_GRADE = {
    "fashion_perawatan": {
        "reguler": 1.0,
        "premium":  1.5,    # bahan lebih bagus → harga 1,5x
    },
    "makanan_minuman": {
        "reguler": 1.0,
        "premium":  1.8,    # organik/special → harga 1,8x
    },
    "kriya_rumah": {
        "reguler": 1.0,
        "premium":  2.5,    # handmade/custom → harga 2,5x
    },
}
```

### Alur Penanganan Variasi dalam Pipeline

```
Foto dikenali → "kaos polos pria"
    │
    ├─ Cek di katalog: produk serupa punya variasi apa?
    │   Misal: 60% punya variasi warna, 30% punya variasi ukuran
    │
    ├─ Tanya user (kalau diperlukan):
    │   ┌─────────────────────────────────────────────┐
    │   │  Produk kamu punya variasi?                  │
    │   │                                              │
    │   │  ☑ Warna/motif (harga sama)                  │
    │   │    → Berapa varian? [___]                     │
    │   │                                              │
    │   │  ☐ Ukuran (S/M/L/XL)                         │
    │   │    → HPP tiap ukuran sama?                    │
    │   │      ○ Sama semua                             │
    │   │      ○ Beda: S=___ M=___ L=___ XL=___        │
    │   │                                              │
    │   │  ☐ Tidak ada variasi                          │
    │   └─────────────────────────────────────────────┘
    │
    ▼
Hasilkan harga per varian:
    ┌─────────────────────────────────────────────────┐
    │  📋 Daftar Harga per Varian:                    │
    │                                                 │
    │  Warna (harga sama untuk semua):                │
    │    Rp54.900 — Hitam, Putih, Navy, Abu           │
    │                                                 │
    │  Ukuran (kalau ada):                            │
    │    S  : Rp49.900                                │
    │    M  : Rp54.900                                │
    │    L  : Rp54.900                                │
    │    XL : Rp59.900                                │
    │    XXL: Rp64.900                                │
    └─────────────────────────────────────────────────┘
```

### Variasi Ukuran Fashion: Aturan Khusus

Fashion punya konvensi unik — ukuran S sampai XL biasanya **harga sama**, tapi
ukuran jumbo (XXL ke atas) lebih mahal karena bahan lebih banyak:

```python
ATURAN_UKURAN_FASHION = {
    # Ukuran standar → harga sama
    "standar": ["XS", "S", "M", "L", "XL"],
    # Ukuran jumbo → markup per step
    "jumbo": {
        "XXL":  1.05,    # +5%
        "3XL":  1.10,    # +10%
        "4XL":  1.15,    # +15%
        "5XL":  1.20,    # +20%
    },
    "catatan": "Konvensi marketplace Indonesia: S-XL harga sama, "
               "XXL ke atas ada tambahan Rp5.000-Rp20.000"
}
```

### Bagaimana Kalau User Tidak Tahu Variasinya?

Kadang user baru mulai dan belum tentukan varian apa yang mau dijual.
Strategi: **berikan harga untuk produk dasar (tanpa variasi)**, lalu tampilkan
simulasi "kalau kamu buat varian":

```
┌────────────────────────────────────────────────┐
│  💡 Saran Varian:                              │
│                                                │
│  Produk serupa di marketplace biasa punya:     │
│  • 3–5 pilihan warna (harga sama)              │
│  • Ukuran S sampai XL (harga sama)             │
│                                                │
│  Dengan variasi, potensi penjualan naik        │
│  karena pembeli bisa pilih sesuai selera.       │
│  Harga rekomendasi tetap: Rp54.900/pcs         │
└────────────────────────────────────────────────┘
```

### Pola Variasi dari Data Katalog (28.443 produk)

Data dari `specs` dan judul bisa diekstrak untuk mengetahui variasi lazim per
kategori:

| Kategori | Variasi paling umum | Sumber di data |
|---|---|---|
| `fashion_perawatan` | Warna (78%), Ukuran (65%) | specs: `Warna`, `Ukuran` |
| `makanan_minuman` | Berat/isi (52%), Rasa (38%) | judul: pola `\d+\s*(g|gr|ml|kg)` |
| `skincare_kecantikan` | Ukuran/ml (60%), Shade (25%) | judul: pola `\d+\s*ml` |
| `elektronik_gadget` | Warna (45%), Kapasitas (30%) | specs: `Warna`, judul: `\d+\s*(GB|TB)` |
| `dapur_rumah` | Warna (55%), Ukuran (35%) | specs: `Warna`, `Ukuran` |

Informasi ini bisa dipakai untuk **proaktif menyarankan** varian yang lazim
kepada user, bahkan sebelum mereka bertanya.

---

## 4. Arsitektur Model

### 4.1 Pipeline Penentuan Harga

```
┌──────────────────────────────────────────────────────────────────┐
│                     INPUT USER                                   │
│        Foto Barang  +  Modal (HPP)  +  Platform Tujuan          │
└───────────────┬──────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────┐
│  TAHAP 1: PENGENALAN PRODUK (VLM — gemma3:4b)                   │
│  - Identifikasi jenis barang, merek, kondisi                     │
│  - Ekstraksi fitur visual (warna, ukuran, material)              │
│  - Output: teks deskripsi fakta visual                           │
└───────────────┬──────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────┐
│  TAHAP 2: PENCARIAN PRODUK SERUPA (TF-IDF Index)                 │
│  - Cari 5–10 tetangga terdekat dari katalog 28.443 produk        │
│  - Ambil: harga, kategori, sold_count, rating                    │
│  - Filter: minimal skor kemiripan ≥ 2.0                          │
└───────────────┬──────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────┐
│  TAHAP 3: KALKULASI HARGA (Deterministik)                        │
│                                                                  │
│  3a. Hitung Harga Minimum (BEP)                                  │
│      HPP / (1 - biaya_platform% - pajak% - ongkir%)             │
│                                                                  │
│  3b. Hitung Harga Pasar                                          │
│      Median harga tetangga × faktor_platform                     │
│                                                                  │
│  3c. Tentukan Margin Kategori                                    │
│      Dari tabel margin per kategori_umkm                         │
│                                                                  │
│  3d. Harga Rekomendasi                                           │
│      max(Harga_BEP × (1+margin), Harga_Pasar)                   │
│      Clamp ke rentang P25–P75 pasar                              │
│      Bulatkan psikologis                                         │
└───────────────┬──────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────┐
│  OUTPUT                                                          │
│  - harga_minimum: harga BEP (jual di bawah ini = rugi)           │
│  - harga_rekomendasi: harga jual yang disarankan                 │
│  - harga_kompetitor: {p25, median, p75} dari produk serupa       │
│  - margin_persen: berapa % untung dari HPP                       │
│  - breakdown: {hpp, pajak, komisi, ongkir, margin, total}        │
│  - penjelasan: teks narasi kenapa harga segitu                   │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 Kenapa Keputusan Harga Tidak Diserahkan ke Model?

Pertanyaannya perlu dipecah dulu, karena sistem ini mengandung dua hal yang
sifatnya berbeda dan sering tertukar:

| | E1 — estimasi harga pasar | E2 — keputusan harga jual |
|---|---|---|
| Pertanyaan | Produk seperti ini dijual berapa? | Dengan HPP sekian, saya pasang berapa? |
| Ground truth | **Ada** — 28.443 harga nyata di katalog | **Tidak ada** |
| Pakai ML? | **Ya** — retrieval, dan seharusnya lebih jauh | **Tidak** |

**E1 memang tugas model, dan diperlakukan begitu.** Ia punya label, punya metrik,
dan bisa dievaluasi. Arah perbaikannya dibahas di `RISET_MODEL_HARGA.md`.

**E2 tidak punya jalur supervised sama sekali** — dan itulah alasan utamanya,
bukan preferensi desain:

| Alasan | Penjelasan |
|---|---|
| **Label-nya tidak eksis** | Melatih `fitur → harga` menghasilkan model yang tidak melihat HPP, jadi jawabannya sama untuk penjual ber-HPP Rp15.000 dan Rp40.000 — dan yang kedua disuruh rugi. Menjadikan HPP sebagai fitur butuh data pasangan (HPP, harga terpilih); tidak ada marketplace yang mempublikasikan HPP. Menurunkannya dari harga (`modal = harga × 0,6`) membuat target sirkular: model hanya belajar mengalikan konstanta. |
| **HPP adalah constraint keras** | Harga jual HARUS di atas HPP + biaya. Ini kendala bisnis yang tidak boleh dilanggar prediksi, bukan pola yang dipelajari dari data. |
| **Harga bukan pola visual** | Dua gaun yang identik secara visual bisa beda harga 10x karena merek. Model tidak akan belajar ini dari foto. |
| **Data label lemah** | `kategori_umkm` yang jadi dasar pemilihan biaya dan margin punya 37,8% jatuh ke `lainnya`. |
| **Transparansi** | UMKM perlu tahu _kenapa_ harganya segitu. Rincian aritmetika bisa dibaca baris per baris. |

ML dipakai untuk:
1. Mengenali jenis barang dari foto (VLM) → menentukan kategori
2. Mencari produk serupa di katalog (TF-IDF) → menentukan benchmark harga (E1)

Perhitungan harga final = **aritmatika** dari HPP + biaya + margin + benchmark.

**Batas kejujuran klaim ini.** "Deterministik" menjamin *cara* hitungnya bisa
diaudit, bukan bahwa *konstanta* di dalamnya benar. Tabel margin di §5.4 belum
punya dasar terukur, dan di zona TIDAK_ADA_DATA ia satu-satunya penentu harga.
Selama itu belum dibereskan, formula ini adalah model juga — hanya dengan
parameter yang di-set tangan. Lihat `RISET_MODEL_HARGA.md` §4.

---

## 5. Detail Implementasi

### 5.1 Struktur Data Input

```python
@dataclass
class PricingRequest:
    image_path: str          # path ke foto barang
    platform: str            # "tokopedia" | "shopee" | "blibli"

    # ── Modal / HPP ──
    # User bisa input dalam berbagai bentuk:
    #   - "50000" → asumsi per 1 unit jual
    #   - "50000 per kg" → perlu konversi ke per unit jual
    #   - "600000 per lusin" → 600.000 / 12 = Rp50.000/pcs
    hpp_total: int           # total modal yang dikeluarkan (Rupiah)
    hpp_satuan: str = "pcs"  # satuan modal: "pcs", "kg", "lusin", "kodi", "bal", "meter", dll
    hpp_jumlah: float = 1.0  # berapa satuan yang didapat dari modal itu

    # ── Konversi ke unit jual (kalau beli grosir) ──
    # Contoh: beli 1 kg keripik (hpp_satuan="kg"), jual per 100g
    #   → jual_per_unit = 100, jual_satuan = "g"
    #   → 1 kg = 1000g / 100g = 10 unit jual
    jual_per_unit: float | None = None   # isi per kemasan jual (gram, ml, dll)
    jual_satuan: str | None = None       # satuan kemasan jual

    # ── Variasi ──
    variasi_warna: list[str] | None = None   # ["Hitam", "Putih", "Navy"]
    variasi_ukuran: list[str] | None = None  # ["S", "M", "L", "XL"] atau ["100g", "250g"]
    hpp_per_ukuran: dict[str, int] | None = None  # {"S": 25000, "XL": 30000} (kalau beda)
    variasi_grade: list[str] | None = None   # ["Reguler", "Premium"]
    hpp_per_grade: dict[str, int] | None = None   # {"Reguler": 25000, "Premium": 40000}

    # ── Biaya tambahan ──
    biaya_packing: int = 0   # biaya packing per unit (Rupiah)
    biaya_produksi: int = 0  # biaya produksi per unit selain bahan (tenaga, listrik)
    berat_gram: int = 0      # berat barang (untuk estimasi ongkir)
    is_ppn: bool = False     # apakah sudah PKP (wajib PPN)?

    @property
    def hpp_per_unit(self) -> int:
        """Konversi modal grosir → HPP per 1 unit jual."""
        # Konversi satuan beli ke satuan jual
        KONVERSI = {
            "lusin": 12, "kodi": 20, "gross": 144,
            "bal": 12,  # bal bervariasi, default 12
            "dus": 24,  # dus bervariasi, default 24
        }
        jumlah_dari_beli = self.hpp_jumlah * KONVERSI.get(self.hpp_satuan, 1)

        # Kalau jual per unit berat/volume, hitung berapa unit per satuan beli
        if self.jual_per_unit and self.jual_satuan:
            GRAM = {"g": 1, "gr": 1, "kg": 1000}
            ML = {"ml": 1, "l": 1000, "liter": 1000}
            if self.hpp_satuan == "kg" and self.jual_satuan in GRAM:
                total_gram = self.hpp_jumlah * 1000
                jumlah_dari_beli = total_gram / (self.jual_per_unit * GRAM[self.jual_satuan])
            elif self.hpp_satuan in ("l", "liter") and self.jual_satuan in ML:
                total_ml = self.hpp_jumlah * 1000
                jumlah_dari_beli = total_ml / (self.jual_per_unit * ML[self.jual_satuan])

        hpp_bahan = self.hpp_total / max(jumlah_dari_beli, 1)
        return int(hpp_bahan + self.biaya_packing + self.biaya_produksi)
```

### 5.2 Struktur Data Output

```python
@dataclass
class VariantPrice:
    """Harga untuk satu varian spesifik."""
    label: str               # "M - Hitam", "250g", "Premium"
    harga_minimum: int       # BEP
    harga_rekomendasi: int   # harga jual yang disarankan
    harga_agresif: int       # margin rendah
    harga_premium: int       # margin tinggi
    hpp_unit: int            # HPP per unit untuk varian ini
    margin_persen: float     # margin keuntungan
    komponen: dict           # breakdown {hpp, pajak, komisi, ongkir, packing, margin}

@dataclass
class PricingResult:
    # ── Harga utama (varian default / tanpa variasi) ──
    harga_minimum: int          # BEP — di bawah ini rugi
    harga_rekomendasi: int      # harga jual yang disarankan
    harga_agresif: int          # harga kompetitif (margin rendah)
    harga_premium: int          # harga premium (margin tinggi)

    # ── Harga per varian (kalau ada variasi) ──
    varian: list[VariantPrice]  # kosong kalau tidak ada variasi

    # ── Pasar ──
    harga_pasar_p25: int        # persentil 25 kompetitor
    harga_pasar_median: int     # median kompetitor
    harga_pasar_p75: int        # persentil 75 kompetitor
    jumlah_kompetitor: int      # berapa produk serupa ditemukan

    # ── Info ──
    komponen: dict              # breakdown {hpp, pajak, komisi, ongkir, packing, margin}
    margin_persen: float        # margin keuntungan dalam persen
    kategori: str               # kategori produk yang terdeteksi
    hpp_per_unit: int           # HPP per unit jual (sudah dikonversi)
    satuan_jual: str            # "pcs", "bungkus", "botol", dll

    # ── Konteks ──
    produk_serupa: list[dict]   # 5 produk terdekat {judul, harga, sold}
    variasi_disarankan: dict    # saran varian dari data katalog
    penjelasan: str             # narasi dalam bahasa Indonesia
```

### 5.3 Konfigurasi Biaya Platform (Diverifikasi Agustus 2026)

```python
BIAYA_PLATFORM = {
    "tokopedia": {
        # Komisi Dinamis per 18 Mei 2026 (sudah termasuk pajak)
        "komisi_pct": {
            "fashion_perawatan":   8.0,   # Pakaian 8%, Aksesori 7,5%
            "elektronik_gadget":   3.5,   # Telepon 3%, Komputer 4%
            "makanan_minuman":     6.5,   # FMCG 6,5%
            "skincare_kecantikan": 7.0,   # Kecantikan & Perawatan 7%
            "dapur_rumah":         8.0,   # Perlengkapan Rumah 8%
            "kesehatan_olahraga":  6.5,   # 
            "kriya_rumah":         8.0,   # Hobi 8%
            "minuman_herbal":      6.5,   # FMCG 6,5%
            "lainnya":             6.5,
        },
        "gratis_ongkir_pct": 0.0,   # Sudah termasuk di komisi dinamis
        "biaya_proses": 1250,        # Rp1.250/pesanan (flat)
        "fee_cap": 80_000,           # Maks komisi per item (Juli 2026)
    },
    "shopee": {
        # Biaya Admin Star/Star+ per 2 Mei 2026
        "komisi_pct": {
            "fashion_perawatan":  10.0,   # Kat. A
            "elektronik_gadget":   6.5,   # Kat. D (5,25%-7,5%)
            "makanan_minuman":    10.0,   # Kat. A
            "skincare_kecantikan": 9.5,   # Kat. B
            "dapur_rumah":        10.0,   # Kat. A
            "kesehatan_olahraga":  9.0,   # Kat. B
            "kriya_rumah":        10.0,   # Kat. A
            "minuman_herbal":      6.5,   # Kat. C (suplemen)
            "lainnya":             9.0,
        },
        "gratis_ongkir_pct": 6.0,   # Gratis Ongkir XTRA (4-9%, rata-rata 6%)
        "biaya_proses": 1250,        # Rp1.250/pesanan
        "fee_cap": None,             # Tidak ada cap
    },
    "blibli": {
        # Seller Regular 2025-2026
        "komisi_pct": {
            "fashion_perawatan":  10.0,
            "elektronik_gadget":   4.25,
            "makanan_minuman":     5.75,
            "skincare_kecantikan": 8.0,
            "dapur_rumah":         7.5,
            "kesehatan_olahraga":  7.5,
            "kriya_rumah":         8.0,
            "minuman_herbal":      5.75,
            "lainnya":             7.5,
        },
        "gratis_ongkir_pct": 0.0,   # Tidak ada program gratis ongkir wajib
        "biaya_proses": 0,           # Termasuk di komisi
        "fee_cap": None,
    },
}

# Pajak — PP 20/2026
PAJAK = {
    "pph_final_pct": 0.5,    # 0,5% dari omzet (omzet ≤ Rp4,8M)
    "bebas_omzet": 500_000_000,  # Rp500 juta pertama BEBAS pajak
    "ppn_pct": 12.0,         # Hanya kalau PKP (omzet > Rp4,8M)
}
```

### 5.4 Tabel Margin Default per Kategori

> **Belum diukur.** Angka-angka di bawah ini disusun dari perkiraan, bukan
> diturunkan dari 28.443 produk katalog maupun dari sumber luar mana pun.
> Tabel ini menentukan harga sepenuhnya di zona TIDAK_ADA_DATA dan menentukan
> sebaran agresif/premium di jalur cadangan. Rencana penggantiannya — dispersi
> harga empiris per kategori — ada di `RISET_MODEL_HARGA.md` §4.1.
>
> **Terukur 20 Agu 2026** (`RISET_MODEL_HARGA.md` §7.4): pada 299 produk contoh
> tabel ini dibaca 299 kali dan nilainya dipakai **nol kali**, karena zona
> TIDAK_ADA_DATA tidak pernah aktif ketika retrieval selalu menemukan tetangga.
> Ia baru menentukan harga saat retrieval gagal — yaitu untuk produk yang
> benar-benar baru, use case unggulan BAB I.
>
> **Kosakata kategorinya juga sudah diperbaiki.** Sampai 20 Agu 2026 tabel ini
> dan `komisi_pct` memakai lima kunci yang muncul **nol kali** di data
> (`makanan_minuman`, `skincare_kecantikan`, `elektronik_gadget`, `dapur_rumah`,
> `kesehatan_olahraga`), sementara tiga kategori pangan nyata — `pokok_tani`,
> `bumbu_masak`, `camilan_olahan`, **16,7% katalog** — jatuh diam-diam ke
> `lainnya`. Sekarang kosakatanya diturunkan dari data (`KATEGORI_DATA`) dan
> kategori asing selalu memicu peringatan. Rinciannya di §7.3.

```python
MARGIN_DEFAULT = {
    "fashion_perawatan":   {"lo": 0.50, "mid": 0.80, "hi": 1.50},
    "elektronik_gadget":   {"lo": 0.10, "mid": 0.20, "hi": 0.30},
    "makanan_minuman":     {"lo": 0.30, "mid": 0.50, "hi": 0.80},
    "minuman_herbal":      {"lo": 0.40, "mid": 0.60, "hi": 1.00},
    "skincare_kecantikan": {"lo": 0.40, "mid": 0.70, "hi": 1.20},
    "dapur_rumah":         {"lo": 0.25, "mid": 0.40, "hi": 0.60},
    "kesehatan_olahraga":  {"lo": 0.30, "mid": 0.45, "hi": 0.70},
    "kriya_rumah":         {"lo": 0.50, "mid": 1.00, "hi": 2.00},
    "lainnya":             {"lo": 0.30, "mid": 0.50, "hi": 0.80},
}
```

---

## 6. Pseudocode Lengkap (Market-First)

```python
def tentukan_harga(foto_path, hpp_per_unit, platform, **opsi):
    """Pipeline lengkap: foto + modal → harga jual.
    
    Logika MARKET-FIRST: pasar menentukan harga, HPP menentukan
    apakah kamu bisa untung.
    """

    # ── Tahap 1: Kenali produk dari foto ──
    fakta = panggil_vlm(foto_path)          # gemma3:4b → "kaos polos pria"

    # ── Tahap 2: Cari produk serupa ──
    tetangga = indeks.cari(fakta, k=10)     # TF-IDF di 28.443 produk
    if skor_teratas < 2.0:
        tetangga = []                       # terlalu jauh, jangan pakai

    kategori = tetangga["kategori_umkm"].mode()
    harga = pd.to_numeric(tetangga["price"], errors="coerce").dropna()
    harga = harga[(harga > harga.quantile(0.05)) & (harga < harga.quantile(0.95))]
    p25, median, p75 = harga.quantile(0.25), harga.median(), harga.quantile(0.75)

    # ── Tahap 3: Hitung biaya platform ──
    biaya = BIAYA_PLATFORM[platform]
    komisi = biaya["komisi_pct"][kategori]
    total_potongan_pct = komisi + biaya["gratis_ongkir_pct"]
    biaya_flat = biaya["biaya_proses"]
    # Pajak: UMKM pemula omzet < Rp500jt → 0%; di atas itu → 0,5%
    pajak_pct = 0.0 if opsi.get("omzet_tahunan", 0) < 500_000_000 else 0.5

    # ── Tahap 4: Hitung BEP ──
    harga_bep = (hpp_per_unit + biaya_flat) / (1 - (total_potongan_pct + pajak_pct) / 100)

    # ── Tahap 5: Tentukan ZONA ──
    if not len(harga):
        zona = "TIDAK_ADA_DATA"
    elif harga_bep > p75:
        zona = "BAHAYA"
    elif harga_bep > median:
        zona = "KETAT"
    elif harga_bep > p25:
        zona = "WAJAR"
    else:
        zona = "BAGUS"

    # ── Tahap 6: Tentukan harga berdasarkan zona ──
    peringatan = None
    saran = []

    if zona == "BAHAYA":
        harga_rekom = bulatkan_psikologis(int(p75))
        peringatan = (
            f"⚠️ Modal kamu (Rp{hpp_per_unit:,}) terlalu tinggi! "
            f"Setelah biaya platform, BEP kamu Rp{int(harga_bep):,}, "
            f"tapi produk serupa di pasar rata-rata Rp{int(median):,}."
        )
        saran = [
            "Cari supplier lebih murah untuk turunkan HPP",
            "Tambah value (kemasan premium, bundling, bonus)",
            f"Coba platform lain (Blibli biayanya lebih rendah)",
            "Target niche market, jangan mass market",
        ]
        margin_persen = round((harga_rekom - hpp_per_unit) / hpp_per_unit * 100, 1)
        if margin_persen < 0:
            peringatan += " KAMU AKAN RUGI di harga pasar."
    
    elif zona == "KETAT":
        # Margin tipis: jual di antara BEP+15% dan P75
        rekom = max(harga_bep * 1.15, median)
        rekom = min(rekom, p75)
        harga_rekom = bulatkan_psikologis(int(rekom))
        peringatan = (
            f"💡 Margin tipis. HPP + biaya = Rp{int(harga_bep):,}, "
            f"pasar median Rp{int(median):,}. Pertimbangkan turunkan HPP."
        )
    
    elif zona == "WAJAR":
        # Anchor ke median pasar, pastikan minimal BEP + 20%
        rekom = max(median, harga_bep * 1.20)
        rekom = min(rekom, p75)
        harga_rekom = bulatkan_psikologis(int(rekom))
    
    elif zona == "BAGUS":
        # HPP rendah → jual di median pasar, margin besar otomatis
        harga_rekom = bulatkan_psikologis(int(median))
    
    else:  # TIDAK_ADA_DATA
        # Fallback ke cost-plus
        margin = MARGIN_DEFAULT.get(kategori, MARGIN_DEFAULT["lainnya"])
        harga_rekom = bulatkan_psikologis(int(harga_bep * (1 + margin["mid"])))
        peringatan = "Tidak ada data produk serupa. Harga berdasarkan estimasi margin."

    # ── Tahap 7: Tiga opsi (selalu di atas BEP) ──
    harga_agresif = bulatkan_psikologis(int(max(p25, harga_bep * 1.10)))
    harga_premium = bulatkan_psikologis(int(min(p75 * 1.1, harga_bep * 2.0)))

    return PricingResult(
        harga_minimum=int(harga_bep),
        harga_rekomendasi=max(harga_rekom, int(harga_bep) + 1),
        harga_agresif=max(harga_agresif, int(harga_bep) + 1),
        harga_premium=harga_premium,
        zona=zona,
        peringatan=peringatan,
        saran=saran,
        ...
    )
```

---

## 7. Contoh Skenario (Market-First)

### Skenario 1: ZONA BAGUS — Keripik Pisang, jual di Blibli

HPP rendah, banyak ruang margin. **Harga ikut pasar, untung besar.**

| Parameter | Nilai |
|---|---|
| HPP per bungkus (250g) | Rp4.000 (beli 5 kg @ Rp50.000, jadi 20 bungkus, + kemasan Rp1.500) |
| Komisi Blibli (kuliner) | 5,75% |
| Biaya proses | Rp0 (termasuk komisi) |
| PPh Final | 0% (omzet < Rp500 juta) |
| **Total potongan** | **5,75%** |

```
Harga BEP    = 4.000 / (1 - 0.0575) = 4.000 / 0.9425 = Rp4.244
Harga pasar  = P25 Rp12.000 | Median Rp18.000 | P75 Rp25.000
ZONA         = BAGUS (BEP Rp4.244 < P25 Rp12.000)
Rekomendasi  = Median pasar = Rp17.900 (psikologis)
Margin       = (17.900 - 4.000) / 4.000 = 347%! 🎉
```

### Skenario 2: ZONA WAJAR — Kaos Polos Pria, jual di Tokopedia

Posisi normal, anchor ke median pasar.

| Parameter | Nilai |
|---|---|
| HPP | Rp25.000/pcs |
| Biaya packing | Rp2.000 |
| Komisi Tokopedia (fashion) | 8% |
| Biaya proses | Rp1.250/pesanan |
| PPh Final | 0% (omzet < Rp500 juta) |
| **Total potongan** | **8%** + Rp1.250 flat |

```
HPP total    = 25.000 + 2.000 = Rp27.000
Harga BEP    = (27.000 + 1.250) / (1 - 0.08) = 28.250 / 0.92 = Rp30.707
Harga pasar  = P25 Rp35.000 | Median Rp45.000 | P75 Rp65.000
ZONA         = WAJAR (BEP Rp30.707 antara P25 dan Median)
Rekom        = max(Median Rp45.000, BEP×1.20 = Rp36.848) = Rp45.000
Psikologis   = Rp44.900
Margin       = (44.900 - 27.000) / 27.000 = 66%
```

**Breakdown per unit terjual Rp44.900:**

| Komponen | Nominal | % |
|---|---|---|
| HPP + packing | Rp27.000 | 60,1% |
| Komisi Tokopedia (8%) | Rp3.592 | 8,0% |
| Biaya proses | Rp1.250 | 2,8% |
| **Laba bersih** | **Rp13.058** | **29,1%** |

### Skenario 3: ZONA KETAT — Serum Skincare UMKM, jual di Shopee

HPP mendekati median pasar. Margin tipis.

| Parameter | Nilai |
|---|---|
| HPP | Rp30.000/botol (30ml) |
| Biaya packing | Rp3.000 (bubble wrap) |
| Komisi Shopee (skincare, Star) | 9,5% |
| Gratis Ongkir XTRA | 6% |
| Biaya proses | Rp1.250 |
| **Total potongan** | **15,5%** + Rp1.250 |

```
HPP total    = 30.000 + 3.000 = Rp33.000
Harga BEP    = (33.000 + 1.250) / (1 - 0.155) = 34.250 / 0.845 = Rp40.533
Harga pasar  = P25 Rp32.000 | Median Rp55.000 | P75 Rp89.000
ZONA         = WAJAR (BEP < Median)
  → Tapi karena ini UMKM tanpa brand, pesaingnya di P25-Median
Rekom        = max(Rp55.000, BEP×1.20 = Rp48.639) = Rp54.900
Margin       = (54.900 - 33.000) / 33.000 = 66%
```

> **Catatan:** Shopee paling mahal totalnya (15,5%!). Kalau biaya terlalu
> tinggi, pertimbangkan Tokopedia (komisi 7%) atau Blibli (komisi 8%).

### Skenario 4: ZONA BAHAYA — Tas Handmade, jual di Shopee ⚠️

HPP terlalu tinggi untuk bersaing. **Model memberi PERINGATAN.**

| Parameter | Nilai |
|---|---|
| HPP | Rp150.000/pcs (bahan kulit, tenaga jahit) |
| Biaya packing | Rp5.000 |
| Komisi Shopee (fashion, Star) | 10% |
| Gratis Ongkir XTRA | 6% |
| Biaya proses | Rp1.250 |
| **Total potongan** | **16%** + Rp1.250 |

```
HPP total    = 150.000 + 5.000 = Rp155.000
Harga BEP    = (155.000 + 1.250) / (1 - 0.16) = 156.250 / 0.84 = Rp186.012
Harga pasar  = P25 Rp65.000 | Median Rp120.000 | P75 Rp180.000
ZONA         = BAHAYA (BEP Rp186.012 > P75 Rp180.000!!)
```

Output:
```
┌──────────────────────────────────────────────────────────┐
│  ⚠️  PERINGATAN: Modal Terlalu Tinggi!                   │
│                                                          │
│  Modal per unit:   Rp155.000                              │
│  Harga BEP:        Rp186.012 (setelah biaya Shopee 16%)  │
│  Harga pasar:      Rp65.000 – Rp180.000                   │
│                                                          │
│  BEP kamu (Rp186.012) LEBIH TINGGI dari harga            │
│  tertinggi di pasar (Rp180.000)!                          │
│  Artinya: TIDAK ADA harga yang bisa untung di Shopee.    │
│                                                          │
│  💡 Saran:                                                │
│  1. Pindah ke Tokopedia (biaya 8% vs 16%)                │
│     → BEP turun jadi Rp170.924, masih bisa untung tipis  │
│  2. Pindah ke Blibli (biaya 10%)                          │
│     → BEP = Rp173.611                                     │
│  3. Jual langsung (Instagram/WhatsApp, biaya 0%)          │
│     → BEP = Rp155.000, jual Rp250.000 margin 61%         │
│  4. Turunkan HPP: target < Rp120.000                      │
│  5. Rebranding premium: foto profesional + storytelling   │
│     → bisa masuk segmen Rp200.000-300.000                 │
└──────────────────────────────────────────────────────────┘
```

---

## 8. Integrasi dengan Pipeline yang Ada

### 8.1 Posisi dalam Pipeline `retrieve_pipeline.py`

Saat ini pipeline sudah punya `harga_deterministik()` yang menghitung harga dari
median tetangga × faktor platform. Model harga baru **menggantikan** fungsi ini
dengan menambahkan dimensi HPP.

```diff
 # retrieve_pipeline.py

-def harga_deterministik(tetangga, profil, plat, kategori, faktor_global):
-    """Saran harga dihitung dari median tetangga × faktor platform."""
-    ...
-    return int(round(acuan / 100) * 100)

+def harga_rekomendasi(tetangga, profil, plat, kategori, faktor_global,
+                      hpp=None, biaya_packing=0, is_ppn=False):
+    """Saran harga: HPP + biaya + margin, dikalibrasi ke pasar."""
+    ...
+    if hpp is None:
+        # fallback ke logika lama kalau user tidak kasih HPP
+        return harga_deterministik_lama(tetangga, profil, plat, kategori)
+    return pricing_result
```

### 8.2 Alur Kerja Baru (untuk User UMKM)

```
User membuka aplikasi
    │
    ├─ Upload foto barang
    ├─ Isi modal (HPP): Rp___
    ├─ Pilih platform: [Tokopedia] [Shopee] [Blibli]
    ├─ (Opsional) Biaya packing, berat barang
    │
    ▼
Sistem memproses:
    1. VLM mengenali barang → "kaos polos pria hitam"
    2. TF-IDF mencari produk serupa → 5 tetangga
    3. Kalkulasi harga → breakdown lengkap
    │
    ▼
User melihat:
    ┌────────────────────────────────────────────────┐
    │  Produk: Kaos Polos Pria                       │
    │  Kategori: Fashion & Perawatan                 │
    │                                                │
    │  💰 Harga Rekomendasi: Rp54.900                │
    │                                                │
    │  📊 Opsi Harga:                                │
    │     Agresif (margin rendah):  Rp44.900         │
    │     Rekomendasi:              Rp54.900         │
    │     Premium:                  Rp74.900         │
    │                                                │
    │  📈 Harga Pasar:                               │
    │     Termurah (P25): Rp35.000                   │
    │     Rata-rata:      Rp45.000                   │
    │     Premium (P75):  Rp65.000                   │
    │                                                │
    │  📋 Breakdown:                                 │
    │     Modal + packing:    Rp27.000               │
    │     Komisi platform:    Rp 3.020               │
    │     Program ongkir:     Rp 2.196               │
    │     Pajak (0,5%):       Rp   275               │
    │     Keuntungan bersih:  Rp22.409 (40,8%)       │
    └────────────────────────────────────────────────┘
```

---

## 9. Risiko dan Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| **Kategori salah** → margin salah | Harga terlalu mahal/murah | Selalu tampilkan harga_minimum; user bisa override kategori |
| **Tidak ada tetangga** (produk unik) | Tidak ada benchmark pasar | Pakai margin default + disclaimer "harga berdasarkan kategori umum" |
| **Biaya platform berubah** | Harga minimum salah | Simpan biaya di config, bukan hardcode; update berkala |
| **HPP tidak termasuk semua biaya** | Harga terlalu rendah | Tampilkan checklist: "Sudah termasuk bahan? Tenaga? Listrik?" |
| **Label `kategori_umkm` lemah** | 37,8% jatuh ke `lainnya` | Perbaiki kategori (langkah berikutnya di OPTIMASI.md) |
| **Data harga outlier** | Benchmark terdistorsi | Gunakan IQR filtering: buang harga < P5 dan > P95 |

---

## 10. Langkah Selanjutnya

### Prioritas Tinggi
1. **Implementasi `pricing_engine.py`** — modul baru di `scripts/` yang
   mengimplementasikan formula market-first di atas
2. **Integrasi ke `retrieve_pipeline.py`** — tambahkan parameter `--hpp` ke CLI
3. **Perbaiki `kategori_umkm`** — 37,8% `lainnya` merusak semua estimasi margin

### Prioritas Sedang
4. **CLIP-based similarity search** — pencarian berbasis gambar, bukan teks.
   Bisa membedakan gaun premium vs gaun pasar yang TF-IDF tidak bisa.
5. ~~**Update biaya platform**~~ — ✅ Sudah diverifikasi Agustus 2026
6. **A/B testing** — uji 50–100 produk, bandingkan harga rekomendasi vs harga
   jual sebenarnya

### Prioritas Rendah
7. **UI/Frontend** — form sederhana upload foto + isi HPP + pilih platform
8. **Monitoring margin** — track apakah harga rekomendasi menghasilkan penjualan
9. **Seasonal pricing** — adjust harga berdasarkan tren musiman

---

## 11. Referensi

### Data & Pipeline
- **Data:** 28.443 produk dari merged dataset (`data_drive/merged/merged_local.parquet`)
- **Pipeline:** `scripts/retrieve_pipeline.py` — pipeline foto → listing yang sudah ada
- **Profil platform:** `scripts/build_platform_profiles.py` — harga per kategori per platform
- **Evaluasi:** `docs/OPTIMASI.md` — hasil eksperimen pipeline, termasuk akurasi harga

### Regulasi (Diverifikasi)
- **PP 20/2026** — Perubahan atas PP 55/2022. PPh Final UMKM 0,5% tanpa batas waktu
  untuk WP OP dan PT Perorangan. Omzet ≤ Rp500 juta bebas pajak. Sumber: pajak.go.id,
  ortax.org, umkm.go.id
- **UU HPP No. 7 Tahun 2021** — Tarif PPN 12%, berlaku untuk PKP (omzet > Rp4,8M)

### Biaya Platform (Diverifikasi Agustus 2026)
- **Tokopedia:** Komisi Dinamis per 18 Mei 2026. Fashion 8%, Elektronik 3-4%, FMCG 6,5%.
  Fee cap Rp80.000/item (Juli 2026). Biaya proses Rp1.250/pesanan.
- **Shopee:** Biaya Admin Star/Star+ per 2 Mei 2026. Kat. A (Fashion, F&B) 10%,
  Kat. B (Skincare, Aksesori) 9-9,5%, Kat. D (Elektronik) 5,25-7,5%. Gratis Ongkir
  XTRA 4-9%. Biaya proses Rp1.250/pesanan.
- **Blibli:** Seller Regular 2025-2026. Elektronik 4,25%, Kuliner 5,75%, Home &
  Living 7,5-8%, Fashion hingga 10%.

