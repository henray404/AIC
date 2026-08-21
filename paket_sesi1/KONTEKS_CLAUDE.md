# Konteks untuk Claude Code di server

Kamu bekerja di server sewaan (Vast.ai, GPU 24GB) di `/workspace/paket_sesi1`.
Mesin ini **baru, belum disetup sama sekali**. Semua perintah python pakai
`./.venv/bin/python`, bukan `python`.

---

## Proyek

Pipeline pembuat listing produk UMKM Indonesia: satu foto produk jadi judul +
deskripsi + kategori + perkiraan harga, untuk tiga platform (blibli, tokopedia,
shopee). Berjalan lokal lewat Ollama, tanpa API berbayar.

```
foto ─┬─► gemma3:4b        "barang apa ini?" -> kalimat
      └─► CLIP ViT-B-32    -> 5 produk termirip di katalog 28.093 produk
                              │
              ringkasan katalog (kategori, kisaran harga, kosakata)
                              │
                     qwen2.5:7b -> judul + deskripsi per platform
                              │
              4 penjaga pasca-generasi -> buang merek & ukuran tak berdasar
```

Kunci rancangannya: **model kecil + retrieval**, bukan model besar. Pengetahuan
produk datang dari katalog yang dicari saat inferensi, bukan dari bobot model.
Kalau skor kemiripan CLIP < 0,80, produk dianggap ASING: konteks katalog dibuang
dan sistem menolak menebak harga.

## Tugas sesi ini

Dapatkan angka pembanding: **pipeline (4B+7B+retrieval) lawan gemma3:12b yang
bekerja sendirian**, pada 100 produk yang sama. Tanpa angka ini tidak ada dasar
untuk mengklaim model kecil menyamai model 3x lebih besar.

Empat berkas hasil di `data_drive/eval/`:

| berkas | isi |
|---|---|
| `S1_pipeline_diri.jsonl` | hanya produk itu dibuang dari indeks — bocor, batas atas saja |
| `S1_pipeline_lini.jsonl` | semua produk lini/merek sama dibuang — **angka utama** |
| `S1_pipeline_kategori.jsonl` | seluruh kategori dibuang — uji barang asing |
| `S1_baseline_12b.jsonl` | gemma3:12b sendirian, tanpa katalog, tanpa penjaga |

---

## Jalankan berurutan

### 1. Setup (~15 menit, unduh ~11 GB model)

```bash
cd /workspace/paket_sesi1
bash setup.sh
```

Harus berakhir dengan `torch ... cuda True` dan daftar 3 model. Kalau `cuda False`,
berhenti dan laporkan — jangan lanjut.

### 2. Data (~15 menit)

```bash
# --skip-images melewati folder images/ blibli (5.500 subfolder, lambat
# ditelusuri) -- isinya sudah ada sebagai images.zip
./.venv/bin/python scripts/fetch_drive_iac.py --only merged blibli --skip-images

./.venv/bin/python -c "import zipfile;zipfile.ZipFile('data_drive/blibli/images.zip').extractall('data_drive/blibli')"
ls data_drive/blibli/images | wc -l                       # harus 8761

./.venv/bin/python scripts/fetch_drive_iac.py --only "data/external/tokopedia2025"
ls data_drive/data/external/tokopedia2025/images | wc -l   # ~2109

# gambar tokopedia datang dari tar yang di-scp, bukan dari Drive
mkdir -p data_drive/tokopedia_dataset
tar -xf tokopedia_gambar1.tar -C data_drive/tokopedia_dataset
ls data_drive/tokopedia_dataset/images | wc -l             # harus 18443
```

### 3. Sesuaikan path lalu bangun indeks (~5 menit)

```bash
./.venv/bin/python - <<'PY'
import pathlib
p = pathlib.Path('scripts/localize_merged.py'); s = p.read_text(encoding='utf-8')
s = s.replace('"/content/drive/MyDrive/IAC/tokopedia_dataset": PROJECT / "data"',
              '"/content/drive/MyDrive/IAC/tokopedia_dataset": DRIVE / "tokopedia_dataset"')
p.write_text(s, encoding='utf-8'); print('ROOT_MAP disesuaikan')
PY

./.venv/bin/python scripts/localize_merged.py
./.venv/bin/python scripts/build_lexicon.py
./.venv/bin/python scripts/build_platform_profiles.py
./.venv/bin/python scripts/build_image_index.py
```

`localize_merged.py` harus menunjukkan:

```
tokopedia       18443 gambar ketemu, 0 hilang
blibli           8761 ketemu, 0 hilang
tokopedia2025    ~2217 ketemu, ~9614 hilang     <- NORMAL, gambarnya memang tak ada
```

Kalau tokopedia 0 ketemu, ROOT_MAP belum tersuntik. Ulangi blok penyesuaian.

### 4. Eksperimen

```bash
N=20 bash sesi1.sh                     # uji kecil dulu, ~20 menit
```

Kalau tabel di akhir keluar wajar, hapus `data_drive/eval/S1_*.jsonl` lalu:

```bash
bash sesi1.sh 2>&1 | tee log.txt       # penuh, ~1,5-2 jam
```

---

## Jebakan yang sudah diketahui

1. **CUDA maksimal 12.6 di server ini** — torch harus cu124. Wheel cu128 terpasang
   tapi gagal melihat GPU. Sudah benar di `setup.sh`, jangan diubah.
2. **`fetch_drive_iac.py` tanpa `--only` sangat lambat** — menelusuri seluruh pohon
   Drive termasuk `shopee/images` (ribuan subfolder) hanya untuk membaca daftar.
   Selalu pakai `--only`.
3. **Berkas Google-native** (Sheet bernama `merged`, id 44 karakter) membalas HTTP
   500. Wajar, tidak merugikan — isinya sama dengan `merged.csv`.
4. **Gambar tokopedia hanya yang pertama per produk** (18.443, bukan 126.583). Itu
   memang cukup: pipeline dan indeks CLIP hanya membaca `local_image_paths[0]`.
5. **Semua tahap aman diulang.** Berkas yang sudah ada dilewati.

## Yang dibaca dari hasil

```bash
./.venv/bin/python scripts/eval_listing.py data_drive/eval/S1_*.jsonl
```

Bandingkan `S1_pipeline_lini` lawan `S1_baseline_12b`:

- `merek_sempit%`, `spek_karang%` — pipeline harus 0%, baseline diduga jauh lebih tinggi
- `inti` — kecocokan judul; kalau setara, klaim "4B menyamai 12B" berdiri
- `detik` — pipeline harus lebih cepat
- `desk_klaim%` — baseline tanpa penjaga, klaim "ampuh/khasiat" akan lolos

Di `S1_pipeline_kategori`, hitung baris ber-`"dikenal": false`. Baseline tidak
punya mekanisme abstain sama sekali.

## Sebelum instance dimatikan

Semua yang perlu diselamatkan ada di `./hasil` (puluhan MB). Beri tahu kalau sudah
selesai supaya bisa ditarik dengan scp. Data mentah 13 GB tidak perlu dibawa pulang.

## Aturan kerja

- Jangan mengubah metrik atau ambang supaya angkanya terlihat bagus. Kalau hasilnya
  jelek, laporkan apa adanya — sesi ini gunanya untuk tahu, bukan untuk menang.
- Kalau ada tahap gagal, tunjukkan pesan errornya persis, jangan diringkas.
- Jangan mengulang tahap yang sudah selesai tanpa alasan; sewa dihitung per jam.
- Laporkan tiap tahap selesai dengan angka yang keluar, jangan cuma "sudah".
