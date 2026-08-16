"""Unduh folder Drive `IAC` ke `data_drive/`, kecuali `tokopedia_dataset`.

Folder itu dilewati karena isinya ekspor milik repo ini sendiri (`data/exports`),
jadi tidak perlu diunduh balik.

    python scripts/fetch_drive_iac.py --dry-run          # hitung dulu, jangan unduh
    python scripts/fetch_drive_iac.py                    # unduh semua
    python scripts/fetch_drive_iac.py --only blibli data # batasi ke cabang tertentu
    python scripts/fetch_drive_iac.py --skip-images      # lewati semua folder gambar

Aman diulang: berkas yang sudah ada dan ukurannya > 0 dilewati.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests
from gdown.download_folder import _parse_embedded_folder_view

ROOT_ID = "1rUTMMD1rNW7Y_gE3cFIOEmT7IitcneJf"   # folder "IAC"
FOLDER_MIME = "application/vnd.google-apps.folder"
LEWATI = {"tokopedia_dataset"}                   # ekspor milik repo ini sendiri
DEST = Path(__file__).resolve().parent.parent / "data_drive"
UNDUH_URL = "https://drive.usercontent.google.com/download?id={id}&export=download&confirm=t"

_cetak = threading.Lock()


def _dalam_lingkup(path, only):
    """True kalau path masih mungkin memuat target `only`, atau berada di dalamnya.

    Dipakai untuk memangkas saat menelusuri, bukan menyaring setelahnya —
    menelusuri seluruh pohon Drive butuh ribuan request.
    """
    if not only:
        return True
    p = path.rstrip("/")
    return any(p.startswith(pre.rstrip("/")) or pre.rstrip("/").startswith(p) for pre in only)


def telusuri(sess, folder_id, prefix="", skip_images=False, only=None):
    """Jalan rekursif lewat embeddedfolderview. Hasil: list (path, file_id)."""
    _, anak = _parse_embedded_folder_view(sess, folder_id)
    berkas, subfolder = [], []
    for fid, nama, mime in anak:
        path = f"{prefix}{nama}"
        if mime == FOLDER_MIME:
            if nama in LEWATI:
                continue
            if skip_images and nama in {"images", "thumbnails"}:
                continue
            if not _dalam_lingkup(path + "/", only):
                continue
            subfolder.append((fid, path + "/"))
        elif _dalam_lingkup(path, only):
            berkas.append((path, fid))

    for fid, path in subfolder:
        with _cetak:
            print(f"  telusuri {path}", file=sys.stderr)
        berkas.extend(telusuri(sess, fid, path, skip_images, only))
    return berkas


def unduh(sess, path, file_id):
    tujuan = DEST / path
    if tujuan.exists() and tujuan.stat().st_size > 0:
        return ("lewat", path, tujuan.stat().st_size)

    tujuan.parent.mkdir(parents=True, exist_ok=True)
    sementara = tujuan.with_suffix(tujuan.suffix + ".part")
    try:
        with sess.get(UNDUH_URL.format(id=file_id), stream=True, timeout=300) as r:
            r.raise_for_status()
            with sementara.open("wb") as f:
                for potongan in r.iter_content(chunk_size=1 << 20):
                    f.write(potongan)
        sementara.replace(tujuan)
        return ("unduh", path, tujuan.stat().st_size)
    except Exception as e:
        sementara.unlink(missing_ok=True)
        return ("gagal", path, f"{type(e).__name__}: {e}"[:150])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true", help="hanya daftar berkas, jangan unduh")
    p.add_argument("--only", nargs="*", default=None,
                   help="batasi ke cabang yang path-nya diawali salah satu nilai ini")
    p.add_argument("--skip-images", action="store_true", help="lewati folder images/ dan thumbnails/")
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args()

    sess = requests.Session()
    print("menelusuri folder Drive IAC ...", file=sys.stderr)
    berkas = telusuri(sess, ROOT_ID, skip_images=args.skip_images, only=args.only)
    print(f"{len(berkas):,} berkas dalam lingkup")
    if args.dry_run:
        for path, _ in berkas[:40]:
            print("  ", path)
        if len(berkas) > 40:
            print(f"   ... dan {len(berkas) - 40:,} lagi")
        return

    DEST.mkdir(parents=True, exist_ok=True)
    hasil = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(unduh, sess, path, fid) for path, fid in berkas]
        for i, fut in enumerate(futures, 1):
            status, path, info = fut.result()
            hasil.append((status, path, info))
            if status != "lewat" or i % 200 == 0:
                with _cetak:
                    print(f"[{i}/{len(berkas)}] {status:6} {path} {info}")

    n = {s: sum(1 for x in hasil if x[0] == s) for s in ("unduh", "lewat", "gagal")}
    byte_total = sum(x[2] for x in hasil if isinstance(x[2], int))
    print(f"\nselesai: {n['unduh']:,} diunduh, {n['lewat']:,} sudah ada, {n['gagal']:,} gagal, "
          f"{byte_total / 1e6:,.0f} MB")

    manifes = DEST / "_manifest.json"
    lama = json.loads(manifes.read_text(encoding="utf-8")) if manifes.exists() else []
    sudah = {x["path"] for x in lama}
    waktu = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for status, path, info in hasil:
        if status != "gagal" and path not in sudah:
            lama.append({"path": path, "bytes": info, "waktu": waktu})
    manifes.write_text(json.dumps(lama, indent=2, ensure_ascii=False), encoding="utf-8")
    print("manifes ->", manifes)

    for status, path, info in hasil:
        if status == "gagal":
            print("GAGAL", path, info)


if __name__ == "__main__":
    main()
