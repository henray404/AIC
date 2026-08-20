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


# Klaim yang tidak boleh dikarang: penjual yang menuliskannya tanpa dasar bisa
# kena sengketa pembeli atau teguran regulator, dan model tidak punya cara tahu
# apakah produk di foto benar bersertifikat.
KLAIM = re.compile(
    r"(?i)\b(garansi|bergaransi|bpom|halal|mui|sni|fda|original|ori|asli|resmi|"
    r"menyembuhkan|mengobati|ampuh|khasiat|terbukti|dijamin|jaminan|"
    r"bebas efek|tanpa efek samping)\b|100\s*%")

# Basa-basi lapak yang justru ingin kita buang dari dataset asli
SAMPAH_TOKO = re.compile(
    r"(?i)(selamat datang|happy shopping|budayakan membaca|wajib baca|"
    r"tidak menerima komplain|no complain|gratis ongkir|ongkos kirim|bubble wrap|"
    r"chat admin|whatsapp|\bwa\b|0[0-9]{9,12})")


LEKSIKON = PROJECT / "data_drive" / "merged" / "lexicon.json"


def muat_profil() -> dict:
    return json.loads(PROFIL.read_text(encoding="utf-8")) if PROFIL.exists() else {}


def _muat_lex() -> dict:
    if not LEKSIKON.exists():
        return {}
    lex = json.loads(LEKSIKON.read_text(encoding="utf-8"))
    return {"merek": set(lex.get("merek", [])), "umum": set(lex.get("umum", []))}


LEX = _muat_lex()


def nilai(path: Path, profil: dict, hanya: set[str] | None = None) -> dict:
    baris = [json.loads(l) for l in path.open(encoding="utf-8")]
    m: dict[str, list] = {k: [] for k in
                          ("json_valid", "harga_err", "harga_model_err", "spek_karang",
                           "merek_karang", "merek_sempit", "merek_ketat",
                           "panjang_patuh", "inti",
                           "desk_char", "desk_spek", "desk_asing", "desk_klaim",
                           "desk_sampah", "desk_ulang", "desk_potong", "detik")}
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
            if hanya and plat not in hanya:
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
            # Ukuran ketat: bukti penglihatan saja yang memaafkan, katalog tidak.
            # Pipeline punya katalog, baseline tidak — ukuran yang ikut memaafkan
            # lewat katalog memberi pipeline keringanan yang lawannya tidak punya
            # akses ke sana. Angka ini satu-satunya yang dibandingkan setara.
            #
            # Penyempitan leksikonnya sama dengan merek_sempit, dan itu wajib.
            # Tanpa penyempitan, `bool(kj - terlihat)` menandai judul karena satu
            # kata lazim tidak muncul di bacaan foto — "minum", "liter" dihukum
            # sama kerasnya dengan nama merek asing. Yang terukur jadi irisan
            # kosakata, bukan karangan.
            if LEX:
                m["merek_ketat"].append(
                    any(w in LEX["merek"] or w not in LEX["umum"] for w in kj - terlihat))
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

            # --- deskripsi: sebelumnya tidak pernah diperiksa sama sekali ---
            desk = str(h.get("deskripsi", "")).strip()
            if desk:
                kd = kata(desk)
                # ukuran/isi yang tidak terbaca di foto; katalog tidak berlaku
                # sebagai bukti angka, sama seperti aturan pada judul
                m["desk_spek"].append(
                    any(a.lower() not in angka_terlihat for a in ANGKA.findall(desk)))
                asing_d = kd - terlihat - katalog
                if LEX:
                    m["desk_asing"].append(
                        any(w in LEX["merek"] or w not in LEX["umum"] for w in asing_d))
                m["desk_klaim"].append(bool(KLAIM.search(desk)))
                m["desk_sampah"].append(bool(SAMPAH_TOKO.search(desk)))
                # deskripsi yang cuma mengulang judul tidak menambah apa pun
                m["desk_ulang"].append(bool(kj) and len(kd - kj) <= 2)
                # kalimat terpotong karena anggaran token habis
                m["desk_potong"].append(desk[-1] not in ".!?\"'")

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
        "merek_ketat%": round(100 * rata("merek_ketat"), 1),
        "panjang_patuh%": round(100 * rata("panjang_patuh"), 1),
        "inti": round(rata("inti"), 3),
        "desk_char": round(rata("desk_char")),
        "desk_spek%": round(100 * rata("desk_spek"), 1),
        "desk_asing%": round(100 * rata("desk_asing"), 1),
        "desk_klaim%": round(100 * rata("desk_klaim"), 1),
        "desk_sampah%": round(100 * rata("desk_sampah"), 1),
        "desk_ulang%": round(100 * rata("desk_ulang"), 1),
        "desk_potong%": round(100 * rata("desk_potong"), 1),
        "detik": round(rata("detik"), 1),
        "kata_judul": {k: round(st.median(v), 1) for k, v in sorted(per_platform.items())},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("berkas", nargs="+")
    ap.add_argument("--hanya-platform", default=None,
                    help="nilai hanya platform ini, dipisah koma. Perlu kalau dua "
                         "berkas menulis himpunan platform yang berbeda — tanpa ini "
                         "keduanya dibandingkan atas dasar yang tidak sama.")
    args = ap.parse_args()

    hanya = ({p.strip() for p in args.hanya_platform.split(",")}
             if args.hanya_platform else None)
    profil = muat_profil()
    hasil = [nilai(Path(b), profil, hanya) for b in args.berkas]
    if hanya:
        print(f"platform dinilai: {sorted(hanya)}")
        print()

    kunci = ["berkas", "n_listing", "json_valid%", "harga_err%", "spek_karang%",
             "merek_sempit%", "merek_ketat%", "panjang_patuh%", "inti", "detik"]
    kunci_desk = ["berkas", "desk_char", "desk_spek%", "desk_asing%", "desk_klaim%",
                  "desk_sampah%", "desk_ulang%", "desk_potong%"]
    lebar = {k: max([len(k)] + [len(str(h[k])) for h in hasil]) for k in kunci}
    print(" | ".join(k.ljust(lebar[k]) for k in kunci))
    print("-+-".join("-" * lebar[k] for k in kunci))
    for h in hasil:
        print(" | ".join(str(h[k]).ljust(lebar[k]) for k in kunci))
    print()
    print("--- deskripsi ---")
    lebar_d = {k: max([len(k)] + [len(str(h[k])) for h in hasil]) for k in kunci_desk}
    print(" | ".join(k.ljust(lebar_d[k]) for k in kunci_desk))
    print("-+-".join("-" * lebar_d[k] for k in kunci_desk))
    for h in hasil:
        print(" | ".join(str(h[k]).ljust(lebar_d[k]) for k in kunci_desk))
    print()
    for h in hasil:
        print(f"{h['berkas']}: median kata judul per platform {h['kata_judul']}")


if __name__ == "__main__":
    main()
