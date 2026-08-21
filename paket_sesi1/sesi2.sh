#!/usr/bin/env bash
# Sesi 2: SEMUA sistem diuji di SATU himpunan produk yang sama.
#
# Sesi 1 punya cacat yang tidak bisa ditambal setelahnya: tiap tabel memakai
# sampel produk yang berbeda. S1 mengambil 100 produk lewat sample(seed=7),
# S2 mengambil 500, sementara kedua student diuji pada 492 produk belahan uji
# distilasi. Angkanya tidak boleh disandingkan lintas tabel, dan lebih buruk
# lagi, sampel S1/S2 kemungkinan bertumpang tindih dengan 6.000 produk yang
# dipakai melatih student -- menilai student di sana berarti mengujinya pada
# data latihnya sendiri.
#
# Himpunan uji di sini adalah 492 produk yang ditahan dari latihan student,
# diambil dari berkas keluaran student yang sudah ada. Semua sistem dan semua
# ablasi dijalankan di situ, jadi setiap angka boleh dibandingkan dengan angka
# mana pun di tabel yang sama.
#
# Aman diulang: tahap yang berkasnya sudah lengkap dilewati.
set -e
cd "$(dirname "$0")"
PY=./.venv/bin/python
UJI=${UJI:-hasil/murid_vlm.jsonl}     # sumber daftar 492 product_id
N=$(grep -c . "$UJI")
mkdir -p data_drive/eval hasil

echo "himpunan uji: $UJI ($N produk)"
echo

jalan () {  # $1 nama berkas, $2.. perintah
  local out="data_drive/eval/$1"; shift
  local ada; ada=$(wc -l < "$out" 2>/dev/null || echo 0)
  if [ "$ada" -ge "$N" ]; then echo "  lewat (lengkap, $ada baris): $out"; return; fi
  echo "=== $out"
  # Dipotong 100-an karena fase 1 retrieve_pipeline.py menahan seluruh irisan
  # di memori. Irisan pertama menimpa berkasnya, sisanya menyambung.
  local i=0
  while [ "$i" -lt "$N" ]; do
    "$@" --ids-dari "$UJI" --iris "$i:$((i+100))" --keluaran "$out"
    i=$((i+100))
  done
}

echo "########## PIPELINE - TIGA TINGKAT EXCLUSION ##########"
for lv in diri lini kategori; do
  jalan "S3_pipeline_$lv.jsonl" $PY scripts/retrieve_pipeline.py \
        --platform all --panjangkan --eksklusi "$lv"
done

echo "########## PIPELINE - ABLASI AMBANG ##########"
# 0,75 sudah dijalankan di atas sebagai S3_pipeline_lini (bawaan sekarang)
for a in 0.70 0.80; do
  jalan "S3_ambang_$a.jsonl" $PY scripts/retrieve_pipeline.py \
        --platform all --panjangkan --eksklusi lini --ambang-visual "$a"
done

echo "########## PIPELINE - ABLASI PEMANJANG JUDUL ##########"
jalan "S3_panjangkan_merek.jsonl" $PY scripts/retrieve_pipeline.py \
      --platform all --panjangkan --panjangkan-merek --eksklusi lini

echo "########## BASELINE MODEL BESAR ##########"
jalan "S3_baseline_12b.jsonl" $PY scripts/baseline_besar.py --model gemma3:12b

echo "########## TAMBAL BUKTI PENGLIHATAN BASELINE ##########"
# Tanpa ini baseline mencatat halusinasi 100% karena kolom vlm-nya kosong,
# bukan karena mutunya. Lihat komentar di baseline_besar.py.
$PY scripts/patch_baseline_vlm.py \
    --baseline data_drive/eval/S3_baseline_12b.jsonl \
    --sumber   data_drive/eval/S3_pipeline_lini.jsonl

echo "########## PENILAIAN ##########"
# Student tidak dijalankan ulang: keluarannya sudah ada dari sesi 1, dan
# himpunan ujinya memang himpunan ini.
cp -n hasil/murid_vlm.jsonl hasil/murid.jsonl data_drive/eval/ 2>/dev/null || true

$PY scripts/eval_listing.py \
  data_drive/eval/S3_pipeline_diri.jsonl \
  data_drive/eval/S3_pipeline_lini.jsonl \
  data_drive/eval/S3_pipeline_kategori.jsonl \
  data_drive/eval/S3_ambang_0.70.jsonl \
  data_drive/eval/S3_ambang_0.80.jsonl \
  data_drive/eval/S3_panjangkan_merek.jsonl \
  data_drive/eval/S3_baseline_12b.jsonl \
  data_drive/eval/murid_vlm.jsonl \
  data_drive/eval/murid.jsonl | tee hasil/S3_semua.txt

echo
echo "--- cakupan disamakan ke pipeline lini ---"
$PY scripts/eval_listing.py \
  data_drive/eval/S3_pipeline_diri.jsonl \
  data_drive/eval/S3_pipeline_lini.jsonl \
  data_drive/eval/S3_pipeline_kategori.jsonl \
  data_drive/eval/S3_baseline_12b.jsonl \
  --samakan-cakupan data_drive/eval/S3_pipeline_lini.jsonl \
  | tee hasil/S3_cakupan_lini.txt

cp data_drive/eval/S3_*.jsonl hasil/ 2>/dev/null || true
echo
echo "SELESAI. Semua di ./hasil"
