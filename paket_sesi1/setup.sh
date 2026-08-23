#!/usr/bin/env bash
# Pasang semua kebutuhan di server sewaan. Aman diulang.
set -e
cd "$(dirname "$0")"

echo "=== 1/5 sistem ==="
apt-get update -qq && apt-get install -y -qq python3-venv python3-pip curl git unzip >/dev/null

echo "=== 2/5 venv + pustaka ==="
python3 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
# PENTING: server ini maksimal CUDA 12.6, jadi WAJIB wheel cu124.
# Wheel cu128 (yang dipakai di laptop) akan gagal memuat driver di sini.
./.venv/bin/pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cu124
./.venv/bin/pip install -q pandas pyarrow pillow requests gdown open_clip_torch numpy

echo "=== 3/5 ollama ==="
if ! command -v ollama >/dev/null; then curl -fsSL https://ollama.com/install.sh | sh; fi
(ollama serve >/tmp/ollama.log 2>&1 &) ; sleep 8

echo "=== 4/5 unduh model (~11 GB) ==="
ollama pull gemma3:4b       # tahap 1 pipeline
ollama pull qwen2.5:7b      # tahap 2 pipeline
ollama pull gemma3:12b      # BASELINE - 3x parameter, satu keluarga

echo "=== 5/5 periksa ==="
./.venv/bin/python -c "import torch;print('torch',torch.__version__,'| cuda',torch.cuda.is_available(),'|',torch.cuda.get_device_name(0) if torch.cuda.is_available() else '-')"
ollama list
echo "SETUP SELESAI"
