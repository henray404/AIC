# Sesi 1 — baseline & tolok ukur

Tujuan: dapat angka pembanding antara pipeline (4B+7B+retrieval) dan satu model
besar 12B yang bekerja sendirian, pada 100 produk yang sama.

Setelah sesi ini kamu bisa menjawab: **apakah menyuling jadi model 4B layak
dikerjakan sama sekali.** Jangan sewa sesi 2 sebelum angka ini ada.

---

## Kirim

```bash
scp -P <PORT> -r paket_sesi1 root@<HOST>:/workspace/
ssh -p <PORT> root@<HOST>
cd /workspace/paket_sesi1
```

## Jalankan berurutan

```bash
bash setup.sh          # ~15 menit, unduh 3 model (~11 GB)
bash ambil_data.sh     # ~30-45 menit, ambil 13 GB dari Drive + bangun indeks
bash sesi1.sh          # ~1,5-2 jam
```

Ketiganya aman diulang. Kalau koneksi putus, jalankan lagi — yang sudah selesai
dilewati.

Untuk memantau tanpa takut putus:

```bash
tmux new -s s1
bash sesi1.sh 2>&1 | tee log_sesi1.txt
# Ctrl-B lalu D untuk lepas; `tmux attach -t s1` untuk kembali
```

## Ambil hasilnya SEBELUM instance dimatikan

```bash
# dari laptop
scp -P <PORT> -r root@<HOST>:/workspace/paket_sesi1/hasil ./hasil_sesi1
```

Isinya puluhan MB: berkas `S1_*.jsonl`, `ringkasan.txt`, profil platform, kamus.
Data mentah 13 GB tidak perlu dibawa pulang — bisa diambil ulang dari Drive.

---

## Yang dijalankan dan kenapa

| berkas | isi |
|---|---|
| `S1_pipeline_diri.jsonl` | pipeline, hanya produk itu dibuang dari indeks — **bocor**, dipakai sebagai batas atas saja |
| `S1_pipeline_lini.jsonl` | semua produk lini/merek sama dibuang — **angka utama yang dilaporkan** |
| `S1_pipeline_kategori.jsonl` | seluruh kategori dibuang — uji barang asing |
| `S1_baseline_12b.jsonl` | gemma3:12b sendirian, tanpa katalog, tanpa penjaga |

Pembandingnya sengaja `gemma3:12b`: satu keluarga dengan `gemma3:4b` di pipeline,
tepat 3x parameter. Kalau memakai model keluarga lain, selisih yang terukur bisa
berasal dari perbedaan data latih, bukan dari ukuran.

## Yang dilihat di hasil

**Angka utama** — bandingkan `S1_pipeline_lini` lawan `S1_baseline_12b`:

- `merek_sempit%` dan `spek_karang%` — dugaan: pipeline 0%, baseline jauh lebih tinggi
- `inti` — kecocokan judul; kalau setara, klaim "4B menyamai 12B" berdiri
- `detik` — pipeline harus lebih cepat
- `desk_klaim%` — baseline tidak punya penjaga, jadi klaim "ampuh/khasiat" akan lolos

**Uji barang asing** — di `S1_pipeline_kategori`, hitung berapa yang ditandai
`dikenal: false`. Baseline tidak punya mekanisme ini sama sekali; ia akan menebak
dengan percaya diri. Itu pembeda yang paling sulit ditandingi.

## Catatan

- Server ini maksimal CUDA 12,6 → `setup.sh` memasang torch **cu124**. Jangan
  menyalin perintah `cu128` dari laptop, akan gagal.
- `N=20 bash sesi1.sh` untuk uji cepat sebelum menjalankan yang 100.
