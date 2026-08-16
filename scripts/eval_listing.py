"""Nilai keluaran pipeline listing dengan ukuran yang sama tiap kali.

Tanpa ini, "sudah lebih baik" cuma perasaan. Semua metrik dihitung dari berkas
hasil `retrieve_pipeline.py`, jadi dua konfigurasi bisa diadu pada sampel identik.

    python scripts/eval_listing.py data_drive/eval/pipeline_demo.jsonl
    python scripts/eval_listing.py A.jsonl B.jsonl      # bandingkan dua versi

Metrik:
  json_valid      keluaran bisa diurai jadi JSON dan ada judulnya
  harga_err       |tebakan - asli| / asli, median (0 = sempurna)
  spek_karang     judul memuat angka/satuan yang tidak terbaca model di foto
  merek_karang    judul memuat kata yang tidak ada di foto maupun di katalog
  panjang_patuh   panjang judul masuk rentang target platform
  inti            berapa bagian kata judul asli yang berhasil disebut ulang
"""

from __future__ import annotations

import argparse
import json
import re
import statistics as st
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
PROFIL = PROJECT / "data_drive" / "merged" / "platform_profiles.json"

ANGKA = re.compile(r"\d+[a-zA-Z]*")
KATA = re.compile(r"[a-zA-Z][a-zA-Z0-9]{3,}")
STOP = {"dan", "untuk", "yang", "dengan", "atau", "the", "for", "with", "dari",
        "pcs", "set", "isi", "pria", "wanita", "anak", "size", "all", "free"}


def kata(teks) -> set[str]:
    return {w.lower() for w in KATA.findall(str(teks)) if w.lower() not in STOP}


LEKSIKON = PROJECT / "data_drive" / "merged" / "lexicon.json"


def muat_profil() -> dict:
    return json.loads(PROFIL.read_text(encoding="utf-8")) if PROFIL.exists() else {}


def _muat_lex() -> dict:
    if not LEKSIKON.exists():
        return {}
    lex = json.loads(LEKSIKON.read_text(encoding="utf-8"))
    return {"merek": set(lex.get("merek", [])), "umum": set(lex.get("umum", []))}


LEX = _muat_lex()


def nilai(path: Path, profil: dict) -> dict:
    baris = [json.loads(l) for l in path.open(encoding="utf-8")]
    m: dict[str, list] = {k: [] for k in
                          ("json_valid", "harga_err", "harga_model_err", "spek_karang",
                           "merek_karang", "merek_sempit", "panjang_patuh", "inti",
                           "desk_char", "detik")}
    per_platform: dict[str, list] = {}

    for r in baris:
        hasil = r.get("hasil", {})
        # bentuk lama: satu listing langsung; bentuk baru: dict per platform
        if hasil and not any(isinstance(v, dict) for v in hasil.values()):
            hasil = {"umum": hasil}
        m["detik"].append(r.get("detik", 0))

        terlihat = kata(r.get("vlm", ""))
        angka_terlihat = {a.lower() for a in ANGKA.findall(str(r.get("vlm", "")))}
        katalog = kata(" ".join(r.get("tetangga", [])))

        for plat, h in hasil.items():
            if not isinstance(h, dict):
                continue
            valid = "_mentah" not in h and bool(h.get("judul"))
            m["json_valid"].append(valid)
            if not valid:
                continue

            judul = str(h.get("judul", ""))
            kj = kata(judul)

            karang_angka = [a for a in ANGKA.findall(judul) if a.lower() not in angka_terlihat]
            m["spek_karang"].append(bool(karang_angka))
            asing = kj - terlihat - katalog
            m["merek_karang"].append(bool(asing))
            # Ukuran sempit: dari kata tak berdasar, hanya hitung yang benar-benar
            # bermasalah — nama merek nyata milik produk lain, atau istilah langka
            # yang tidak ada di kosakata katalog. Ukuran lebar di atas menghukum
            # kata Indonesia lazim ("pesta", "jogging") yang sebenarnya sah.
            if LEX:
                m["merek_sempit"].append(
                    any(w in LEX["merek"] or w not in LEX["umum"] for w in asing))

            harga = h.get("perkiraan_harga")
            try:
                harga = float(harga)
            except (TypeError, ValueError):
                harga = 0.0
            asli = float(r.get("harga_asli") or 0)
            # Harga hanya adil dinilai pada platform ASAL produk. Saran untuk
            # platform lain memang sengaja berbeda — fashion di blibli median 3x
            # Tokopedia — jadi menghukumnya karena tidak sama dengan harga asli
            # justru menghukum perilaku yang benar.
            # shopee sengaja 0 (tidak punya data harga) -> juga tidak dihitung.
            if harga > 0 and asli > 0 and plat in (r.get("source"), "umum"):
                m["harga_err"].append(abs(harga - asli) / asli)
                # tebakan mentah model, disimpan sebelum ditimpa hitungan katalog
                hm = h.get("harga_model")
                try:
                    hm = float(hm)
                except (TypeError, ValueError):
                    hm = 0.0
                if hm > 0:
                    m["harga_model_err"].append(abs(hm - asli) / asli)

            p = profil.get(plat, {}).get("judul", {})
            if p.get("target_kata"):
                lo, hi = p["target_kata"]
                m["panjang_patuh"].append(lo <= len(judul.split()) <= hi)

            emas = kata(r.get("judul_asli", ""))
            if emas:
                m["inti"].append(len(emas & kj) / len(emas))
            m["desk_char"].append(len(str(h.get("deskripsi", ""))))
            per_platform.setdefault(plat, []).append(len(judul.split()))

    def rata(k):
        v = m[k]
        return sum(v) / len(v) if v else float("nan")

    return {
        "berkas": path.name,
        "n_baris": len(baris),
        "n_listing": len(m["json_valid"]),
        "json_valid%": round(100 * rata("json_valid"), 1),
        "harga_err%": round(100 * st.median(m["harga_err"]), 1) if m["harga_err"] else float("nan"),
        "harga_model_err%": (round(100 * st.median(m["harga_model_err"]), 1)
                             if m["harga_model_err"] else float("nan")),
        "spek_karang%": round(100 * rata("spek_karang"), 1),
        "merek_karang%": round(100 * rata("merek_karang"), 1),
        "merek_sempit%": round(100 * rata("merek_sempit"), 1),
        "panjang_patuh%": round(100 * rata("panjang_patuh"), 1),
        "inti": round(rata("inti"), 3),
        "desk_char": round(rata("desk_char")),
        "detik": round(rata("detik"), 1),
        "kata_judul": {k: round(st.median(v), 1) for k, v in sorted(per_platform.items())},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("berkas", nargs="+")
    args = ap.parse_args()

    profil = muat_profil()
    hasil = [nilai(Path(b), profil) for b in args.berkas]

    kunci = ["berkas", "n_listing", "json_valid%", "harga_err%", "harga_model_err%",
             "spek_karang%", "merek_karang%", "merek_sempit%", "panjang_patuh%", "inti", "desk_char", "detik"]
    lebar = {k: max([len(k)] + [len(str(h[k])) for h in hasil]) for k in kunci}
    print(" | ".join(k.ljust(lebar[k]) for k in kunci))
    print("-+-".join("-" * lebar[k] for k in kunci))
    for h in hasil:
        print(" | ".join(str(h[k]).ljust(lebar[k]) for k in kunci))
    print()
    for h in hasil:
        print(f"{h['berkas']}: median kata judul per platform {h['kata_judul']}")


if __name__ == "__main__":
    main()
