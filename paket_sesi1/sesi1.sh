#!/usr/bin/env bash
# Eksperimen sesi 1: pipeline 3 tingkat eksklusi + baseline model besar.
# Aman diulang: tiap tahap melewati berkas yang sudah ada.
set -e
cd "$(dirname "$0")"
PY=./.venv/bin/python
N=${N:-100}
mkdir -p data_drive/eval hasil

jalan () {  # $1 nama berkas, $2.. argumen
  local out="data_drive/eval/$1"; shift
  if [ -s "$out" ]; then echo "  lewat (sudah ada): $out"; return; fi
  echo "=== $out"
  for iris in 0:25 25:50 50:75 75:100; do
    $PY "$@" --n "$N" --iris "$iris" --keluaran "$out"
  done
}

echo "########## PIPELINE 3 TINGKAT ##########"
for lv in diri lini kategori; do
  jalan "S1_pipeline_$lv.jsonl" scripts/retrieve_pipeline.py \
        --platform all --panjangkan --eksklusi "$lv"
done

echo "########## BASELINE MODEL BESAR ##########"
jalan "S1_baseline_12b.jsonl" scripts/baseline_besar.py --model gemma3:12b

echo "########## PENILAIAN ##########"
$PY scripts/eval_listing.py \
  data_drive/eval/S1_pipeline_diri.jsonl \
  data_drive/eval/S1_pipeline_lini.jsonl \
  data_drive/eval/S1_pipeline_kategori.jsonl \
  data_drive/eval/S1_baseline_12b.jsonl | tee hasil/ringkasan.txt

cp data_drive/eval/S1_*.jsonl hasil/ 2>/dev/null || true
cp data_drive/merged/platform_profiles.json data_drive/merged/lexicon.json hasil/ 2>/dev/null || true
echo
echo "SELESAI. Semua yang perlu diselamatkan ada di ./hasil (kecil, puluhan MB)"
