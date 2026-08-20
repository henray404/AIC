#!/usr/bin/env bash
# Ambil dataset LANGSUNG dari Drive, jangan diunggah dari rumah.
# Server punya 6,5 Gbps; koneksi rumah yang jadi penghambat.
set -e
cd "$(dirname "$0")"

echo "=== dataset + gambar blibli & tokopedia2025 (~0,9 GB) ==="
./.venv/bin/python scripts/fetch_drive_iac.py

echo "=== ekstrak gambar blibli ==="
./.venv/bin/python -c "import zipfile;zipfile.ZipFile('data_drive/blibli/images.zip').extractall('data_drive/blibli')"

echo "=== gambar tokopedia (~12 GB, folder yang dilewati fetch) ==="
# tokopedia_dataset ada di Drive; di laptop dilewati karena sudah lokal,
# di sini harus diambil supaya path gambarnya bisa diresolusi
./.venv/bin/python - <<'PY'
import sys; sys.path.insert(0,'scripts')
import fetch_drive_iac as f
f.LEWATI = set()                       # jangan lewati tokopedia_dataset
import requests
sess = requests.Session()
berkas = f.telusuri(sess, f.ROOT_ID, only=["tokopedia_dataset"])
print(f"{len(berkas):,} berkas")
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=16) as pool:
    for n, (st, path, info) in enumerate(pool.map(lambda x: f.unduh(sess, *x), berkas), 1):
        if n % 2000 == 0: print(f"  {n:,}/{len(berkas):,}", flush=True)
PY

echo "=== sesuaikan path ke lokasi server ==="
./.venv/bin/python - <<'PY'
import pathlib, re
p = pathlib.Path('scripts/localize_merged.py'); s = p.read_text(encoding='utf-8')
# di server, gambar tokopedia ada di data_drive/tokopedia_dataset, bukan data/
s = s.replace('"/content/drive/MyDrive/IAC/tokopedia_dataset": PROJECT / "data"',
              '"/content/drive/MyDrive/IAC/tokopedia_dataset": DRIVE / "tokopedia_dataset"')
p.write_text(s, encoding='utf-8'); print('ROOT_MAP disesuaikan')
PY

./.venv/bin/python scripts/localize_merged.py
./.venv/bin/python scripts/build_lexicon.py
./.venv/bin/python scripts/build_platform_profiles.py
./.venv/bin/python scripts/build_image_index.py
echo "DATA SIAP"
