"""Bandingkan penilaian manusia dengan metrik otomatis pada listing yang sama.

    python scripts/nilai_penilaian.py penilaian/hasil.json

Menjawab dua pertanyaan yang berbeda, dan jangan tertukar:

1. **Sistem mana yang lebih baik menurut manusia?** Ini hasil yang dikutip di
   laporan. Berdiri sendiri, tidak bergantung metrik otomatis sama sekali.

2. **Apakah metrik otomatisnya bisa dipercaya?** Tiap listing punya dua putusan
   untuk hal yang sama — `merek_ketat`/`spek_karang` dari kode, dan penilaian
   manusia. Kalau keduanya sering berselisih, angka di TABEL_SESI1.md mengukur
   proksinya, bukan halusinasinya.

Yang dilaporkan untuk pertanyaan kedua bukan sekadar "berapa persen cocok".
Metrik yang selalu menjawab "tidak ada halusinasi" akan terlihat 90% cocok
kalau halusinasinya memang jarang, padahal ia tidak mendeteksi apa pun. Jadi
yang dihitung: berapa halusinasi nyata yang tertangkap (recall), dan berapa
tuduhannya yang dibenarkan manusia (presisi).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Konsol Windows cp1252 tidak bisa mencetak em-dash dan sejenisnya, dan
# print yang gagal mematikan seluruh proses. Sama seperti di
# retrieve_pipeline.py: ganti karakternya, jangan hentikan prosesnya.
for _aliran in (sys.stdout, sys.stderr):
    if hasattr(_aliran, "reconfigure"):
        try:
            _aliran.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

PROJECT = Path(__file__).resolve().parent.parent
SUMBER = {
    "pipeline": PROJECT / "hasil_sesi2" / "S4_bersih.jsonl",
    "baseline12b": PROJECT / "hasil_sesi2" / "S3_baseline_12b.jsonl",
    "murid_vlm": PROJECT / "hasil_sesi2" / "murid_vlm.jsonl",
}
NAMA_TAMPIL = {"pipeline": "RAG pipeline", "baseline12b": "Baseline 12B",
               "murid_vlm": "Student VLM 3B"}


def muat_indeks() -> dict:
    """(sistem, product_id) -> baris hasil. Dibaca sekali, bukan per listing."""
    idx = {}
    for nama, path in SUMBER.items():
        if not path.exists():
            print(f"  peringatan: tidak ada {path}", file=sys.stderr)
            continue
        for l in path.open(encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                idx[(nama, str(r["product_id"]))] = r
    return idx


def putusan_otomatis(ev, r: dict, platform: str) -> dict | None:
    """Hitung ulang putusan metrik untuk satu listing, memakai fungsi penilai
    yang sama supaya benar-benar sebanding dengan angka di tabel."""
    h = (r.get("hasil") or {}).get(platform)
    if not isinstance(h, dict) or "_mentah" in h:
        return None

    terlihat = ev.kata(r.get("vlm", ""))
    katalog = ev.kata(" ".join(r.get("tetangga", [])))
    angka_terlihat = {a.lower() for a in ev.ANGKA.findall(str(r.get("vlm", "")))}
    lex = ev.LEX

    kj = ev.kata(str(h.get("judul", "")))
    ketat = (bool(any(w in lex["merek"] or w not in lex["umum"]
                      for w in kj - terlihat)) if lex else None)
    spek = bool([a for a in ev.ANGKA.findall(str(h.get("judul", "")))
                 if a.lower() not in angka_terlihat])
    kd = ev.kata(str(h.get("deskripsi", "")))
    asing_d = kd - terlihat - katalog
    desk = (bool(any(w in lex["merek"] or w not in lex["umum"] for w in asing_d))
            if lex else None)
    return {"merek_ketat": ketat, "spek_karang": spek, "desk_asing": desk}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hasil", help="berkas JSON dari penilaian/penilaian.html")
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import eval_listing as ev

    baris = json.loads(Path(args.hasil).read_text(encoding="utf-8"))
    lengkap = [b for b in baris if b.get("layak")]
    print(f"{len(lengkap)} dari {len(baris)} listing sudah dinilai")
    if not lengkap:
        sys.exit("belum ada yang dinilai")

    # ---------------------------------------------------- 1. penilaian manusia
    per_sistem: dict[str, list] = {}
    for b in lengkap:
        per_sistem.setdefault(b["sistem"], []).append(b)

    print("\n" + "=" * 70)
    print("1. PENILAIAN MANUSIA — berdiri sendiri, tanpa metrik otomatis")
    print("=" * 70)
    print(f"\n  {'sistem':18} {'n':>3} {'judul':>9} {'deskripsi':>10} "
          f"{'kategori':>9} {'layak':>8}")
    print(f"  {'':18} {'':>3} {'dikarang':>9} {'dikarang':>10} "
          f"{'tepat':>9} {'dipakai':>8}")
    for nama, v in sorted(per_sistem.items(),
                          key=lambda x: -sum(b.get("layak") == "ya" for b in x[1])):
        n = len(v)
        jk = 100 * sum(b.get("judul_karang") == "ya" for b in v) / n
        dk = 100 * sum(b.get("desk_karang") == "ya" for b in v) / n
        kt = 100 * sum(b.get("kategori_nilai") == "tepat" for b in v) / n
        ly = 100 * sum(b.get("layak") == "ya" for b in v) / n
        print(f"  {NAMA_TAMPIL.get(nama, nama):18} {n:3} {jk:8.1f}% {dk:9.1f}% "
              f"{kt:8.1f}% {ly:7.1f}%")

    # -------------------------------------------- 2. metrik otomatis vs manusia
    print("\n" + "=" * 70)
    print("2. APAKAH METRIK OTOMATISNYA BISA DIPERCAYA")
    print("=" * 70)

    idx = muat_indeks()
    pasang = {"merek_ketat": ("judul_karang", []),
              "spek_karang": ("judul_karang", []),
              "desk_asing": ("desk_karang", [])}
    n_gagal = 0
    for b in lengkap:
        r = idx.get((b["sistem"], str(b["product_id"])))
        oto = putusan_otomatis(ev, r, b.get("platform", "")) if r else None
        if not oto:
            n_gagal += 1
            continue
        for metrik, (tanya, kumpul) in pasang.items():
            if oto.get(metrik) is not None:
                kumpul.append((bool(oto[metrik]), b.get(tanya) == "ya"))

    if n_gagal:
        print(f"\n  {n_gagal} listing tak bisa dicocokkan ke berkas hasil")

    print(f"\n  {'metrik':13} {'n':>4} {'sepakat':>8} {'recall':>8} {'presisi':>8}   catatan")
    for metrik, (_, v) in pasang.items():
        if not v:
            continue
        n = len(v)
        sepakat = 100 * sum(a == m for a, m in v) / n
        tp = sum(a and m for a, m in v)
        fp = sum(a and not m for a, m in v)
        fn = sum((not a) and m for a, m in v)
        rec = 100 * tp / (tp + fn) if tp + fn else float("nan")
        pre = 100 * tp / (tp + fp) if tp + fp else float("nan")
        if tp + fn == 0:
            catatan = "manusia tak menemukan halusinasi — sampel terlalu kecil"
        elif tp + fp == 0:
            catatan = "metrik tak pernah menuduh apa pun"
        elif rec < 50:
            catatan = "melewatkan lebih dari separuh"
        elif pre < 50:
            catatan = "lebih dari separuh tuduhannya keliru"
        else:
            catatan = "sejalan"
        print(f"  {metrik:13} {n:4} {sepakat:7.1f}% {rec:7.1f}% {pre:7.1f}%   {catatan}")

    print("\n  recall  = halusinasi nyata yang tertangkap metrik")
    print("  presisi = tuduhan metrik yang dibenarkan manusia")
    print("  'sepakat' sendirian menyesatkan: metrik yang selalu bilang 'bersih'")
    print("  tetap terlihat tinggi kalau halusinasinya memang jarang.")

    # ------------------------------------------------ 3. mutu label kategori
    print("\n" + "=" * 70)
    print("3. MUTU LABEL KATALOG")
    print("=" * 70)
    tak_ada = sum(1 for b in lengkap if b.get("kategori_nilai") == "tak_ada")
    print(f"\n  {tak_ada} dari {len(lengkap)} listing dinilai "
          f"'tak ada kategori yang cocok' ({100*tak_ada/len(lengkap):.0f}%)")
    print("  Kalau angka ini besar, taksonomi tujuh kelasnya yang kurang —")
    print("  bukan sistemnya yang salah menebak.")

    # Kalau manusia membenarkan kategori yang ditulis sistem TAPI label katalog
    # berbeda, yang keliru labelnya. Itu langsung mengukur cacat yang ditemukan
    # pada produk `tidak_terpetakan`.
    label_salah = benar_dua_duanya = 0
    for b in lengkap:
        if b.get("kategori_nilai") != "tepat":
            continue
        label = str(b.get("kategori_asli", "")).strip().lower()
        tulis = str(b.get("kategori", "")).strip().lower()
        if not label or not tulis:
            continue
        if label == tulis:
            benar_dua_duanya += 1
        else:
            label_salah += 1

    n_cek = label_salah + benar_dua_duanya
    if n_cek:
        print()
        print(f"  dari {n_cek} listing yang kategorinya dibenarkan manusia:")
        print(f"    {benar_dua_duanya:3} label katalog setuju")
        print(f"    {label_salah:3} label katalog BERBEDA -> labelnya yang keliru")
        print()
        print(f"  artinya category_correct% menghukum sistem di "
              f"{100*label_salah/n_cek:.0f}% kasus ini, padahal jawabannya")
        print("  tepat menurut manusia.")


if __name__ == "__main__":
    main()
