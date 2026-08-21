"""Isikan bukti penglihatan ke berkas baseline supaya penilaiannya sah.

`baseline_besar.py` menulis `vlm: ""` — niatnya adil, karena baseline memang
tidak punya tahap penglihatan terpisah. Efeknya kebalikannya. `eval_listing.py`
menilai kata karangan dengan `asing = kata(judul) - kata(vlm) - kata(tetangga)`,
jadi `vlm` kosong membuat SELURUH kata judul terhitung karangan, dan baseline
mendapat halusinasi 100% secara konstruksi, bukan hasil pengukuran.

Perbaikannya: pakai bacaan penglihatan yang sudah ada di berkas pipeline sebagai
bukti bersama. Sah karena sampelnya identik — sumber, filter `n_gambar_lokal>0`,
`reset_index(drop=True)`, dan `sample(n, random_state=7)` sama persis di kedua
skrip, jadi `product_id`-nya cocok satu-satu. Bacaan itu juga bebas dari siapa
yang menulis judulnya: ia menggambarkan foto, bukan keluaran model mana pun.

`tetangga` sengaja dibiarkan kosong. Baseline memang tidak diberi katalog, jadi
tidak ada yang bisa membenarkan katanya dari sana.

    python scripts/patch_baseline_vlm.py \
        --baseline data_drive/eval/S1_baseline_12b.jsonl \
        --sumber   data_drive/eval/S1_pipeline_diri.jsonl

Aman diulang. Jalankan SETELAH baseline selesai, bukan saat masih menulis.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def muat(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()]


def tambal(baseline: list[dict], vlm_per_id: dict[str, str]) -> tuple[list[dict], int, int]:
    """Balikan (baris, jumlah_tertambal, jumlah_tak_ketemu)."""
    kena = hilang = 0
    for r in baseline:
        if r.get("vlm"):            # sudah terisi -> jangan timpa
            continue
        v = vlm_per_id.get(str(r.get("product_id")))
        if v:
            r["vlm"] = v
            kena += 1
        else:
            hilang += 1
    return baseline, kena, hilang


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--sumber", required=True,
                    help="berkas pipeline yang punya kolom vlm terisi")
    args = ap.parse_args()

    bp, sp = Path(args.baseline), Path(args.sumber)
    baseline, sumber = muat(bp), muat(sp)
    vlm_per_id = {str(r["product_id"]): r.get("vlm", "")
                  for r in sumber if r.get("vlm")}
    print(f"baseline {len(baseline)} baris, sumber {len(sumber)} baris, "
          f"{len(vlm_per_id)} punya vlm")

    baseline, kena, hilang = tambal(baseline, vlm_per_id)
    if hilang:
        print(f"PERINGATAN: {hilang} baris tanpa pasangan — jangan nilai berkas ini "
              "sampai penyebabnya jelas (sampelnya mungkin tidak identik)")

    with bp.open("w", encoding="utf-8") as f:
        for r in baseline:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    kosong = sum(1 for r in baseline if not r.get("vlm"))
    print(f"{kena} baris ditambal, {kosong} masih kosong -> {bp}")


def _selfcheck():
    base = [{"product_id": "a", "vlm": ""},
            {"product_id": "b", "vlm": "sudah ada"},
            {"product_id": "c", "vlm": ""}]
    src = {"a": "botol plastik bening", "b": "lain"}
    out, kena, hilang = tambal(base, src)
    assert kena == 1 and hilang == 1, (kena, hilang)
    assert out[0]["vlm"] == "botol plastik bening"
    assert out[1]["vlm"] == "sudah ada"      # tidak ditimpa
    assert out[2]["vlm"] == ""               # tidak dikarang
    # idempoten: jalan kedua tidak mengubah apa pun
    _, kena2, _ = tambal(out, src)
    assert kena2 == 0
    print("selfcheck ok")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        main()
