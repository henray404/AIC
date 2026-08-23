"""Nilai keluaran pipeline listing dengan ukuran yang sama tiap kali.

Tanpa ini, "sudah lebih baik" cuma perasaan. Semua metrik dihitung dari berkas
hasil `retrieve_pipeline.py`, jadi dua konfigurasi bisa diadu pada sampel identik.

    python scripts/eval_listing.py data_drive/eval/pipeline_demo.jsonl
    python scripts/eval_listing.py A.jsonl B.jsonl      # bandingkan dua versi

Metrik yang dipakai:
  json_valid      keluaran bisa diurai jadi JSON dan ada judulnya
  harga_err       |tebakan - asli| / asli, median. ASIMETRIS -- pakai
                  harga_logerr dan harga_2x untuk membandingkan sistem
  harga_logerr    median |log(tebakan/asli)|, simetris. 0,69 = meleset 2x
  harga_2x        porsi tebakan dalam rentang setengah sampai dua kali
  harga_cakupan   porsi listing yang berani menyebut harga
  kategori_sah    kategori ada di taksonomi tujuh kelas
  kategori_benar  kategori sama dengan label katalog. BATAS BAWAH -- sebagian
                  label katalognya sendiri keliru, lihat CACAT_LABEL_KATEGORI.md
  kata_asing      judul memuat kata yang tidak ada di bacaan foto. Satu-satunya
                  ukuran halusinasi yang tervalidasi manusia (recall 93,3%,
                  presisi 35%). Presisi 35% berarti angka mutlaknya BUKAN kadar
                  halusinasi -- yang bermakna selisih antar sistem
  panjang_patuh   panjang judul masuk rentang target platform
  inti_f1         kecocokan judul dengan judul asli, seimbang antara menyebut
                  ulang dan tidak menggelembungkan. INI yang dipakai
                  membandingkan sistem
  inti            recall murni. Tidak menghukum kata tambahan sama sekali,
                  jadi bisa dinaikkan dengan keyword stuffing -- menempelkan
                  12 kata tersering katalog ke tiap judul menaikkannya +0,022
                  sementara inti_f1 turun 0,184
  inti_presisi    berapa bagian kata judul buatan yang benar-benar ada di
                  judul asli

Metrik yang GUGUR, disembunyikan kecuali dengan --semua:
  spek_karang, merek_sempit, merek_ketat, desk_spek, desk_asing

Penilaian manusia pada 51 listing mengukur recall ketiganya 0-9%: semuanya
hanya mencari nama merek dan istilah langka, sehingga melewatkan warna,
aroma, rasa, dan sifat produk -- kata Indonesia lazim yang justru paling
sering dikarang. Tetap dihitung supaya angka lama bisa direproduksi.
Lihat docs/PENILAIAN_MANUSIA.md.
"""

from __future__ import annotations

import argparse
import json
import math
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


# Taksonomi UMKM yang dipakai seluruh katalog. Disalin, bukan diimpor dari
# retrieve_pipeline: penilai sengaja tidak berbagi berkas dengan yang dinilai,
# supaya perubahan diam-diam di sana tidak ikut menggeser ukurannya.
KATEGORI_UMKM = {"bumbu_masak", "camilan_olahan", "fashion_perawatan",
                 "kriya_rumah", "minuman_herbal", "pokok_tani", "lainnya"}

LEKSIKON = PROJECT / "data_drive" / "merged" / "lexicon.json"


def muat_profil() -> dict:
    return json.loads(PROFIL.read_text(encoding="utf-8")) if PROFIL.exists() else {}


def _muat_lex() -> dict:
    if not LEKSIKON.exists():
        return {}
    lex = json.loads(LEKSIKON.read_text(encoding="utf-8"))
    return {"merek": set(lex.get("merek", [])), "umum": set(lex.get("umum", []))}


LEX = _muat_lex()


def id_berharga(path: Path) -> set[str]:
    """product_id yang berkas ini benar-benar berani menyebutkan harganya.

    Dipakai untuk menyamakan cakupan: membandingkan galat harga pipeline yang
    mengundurkan diri di 71 dari 100 produk dengan baseline yang menjawab
    semuanya bukan membandingkan ketepatan, melainkan membandingkan keberanian.
    """
    ids = set()
    for l in path.open(encoding="utf-8"):
        if not l.strip():
            continue
        r = json.loads(l)
        hasil = r.get("hasil", {})
        if hasil and not any(isinstance(v, dict) for v in hasil.values()):
            hasil = {"umum": hasil}
        for h in hasil.values():
            if not isinstance(h, dict):
                continue
            try:
                if float(h.get("perkiraan_harga") or 0) > 0:
                    ids.add(str(r.get("product_id")))
                    break
            except (TypeError, ValueError):
                pass
    return ids


def nilai(path: Path, profil: dict, hanya: set[str] | None = None,
          hanya_id: set[str] | None = None) -> dict:
    baris = [json.loads(l) for l in path.open(encoding="utf-8")]
    m: dict[str, list] = {k: [] for k in
                          ("json_valid", "harga_err", "harga_model_err", "spek_karang",
                           "merek_karang", "merek_sempit", "merek_ketat",
                           "kata_asing",
                           "harga_cakupan", "harga_logerr", "harga_2x",
                           "kategori_sah", "kategori_benar",
                           "panjang_patuh", "inti", "inti_presisi", "inti_f1",
                           "desk_char", "desk_spek", "desk_asing", "desk_klaim",
                           "desk_sampah", "desk_ulang", "desk_potong", "detik")}
    per_platform: dict[str, list] = {}
    n_listing_penuh = 0      # sebelum saringan platform; penyebut detik/listing
    n_baris_dipakai = 0      # baris yang lolos --samakan-cakupan

    for r in baris:
        if hanya_id is not None and str(r.get("product_id")) not in hanya_id:
            continue
        n_baris_dipakai += 1
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
            n_listing_penuh += 1
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

            # Satu-satunya ukuran halusinasi yang tervalidasi manusia. Aturannya
            # sesederhana mungkin -- ADA kata di judul yang tidak muncul di
            # bacaan foto -- dan justru itu yang paling sejalan dengan penilaian
            # manusia dari semua varian yang diuji pada 51 listing berlabel:
            #
            #   aturan                          recall  presisi    F1
            #   merek/istilah langka (lama)        6,7    100,0   12,5
            #   ADA kata asing                    93,3     35,0   50,9  <- dipakai
            #   kata asing >= 3                   60,0     39,1   47,4
            #   porsi kata asing > 40% judul      66,7     34,5   45,5
            #   daftar atribut warna/rasa/bahan   26,7     33,3   29,6
            #
            # Presisi 35% berarti dua dari tiga tuduhannya tidak dibenarkan
            # manusia -- kata jenis dan kata jualan ("kaleng", "praktis") ikut
            # terhukum. Itu HARUS dilaporkan bersama angkanya. Metrik ini sah
            # untuk MEMBANDINGKAN sistem karena semuanya dihukum dengan cara
            # yang sama, bukan sebagai kadar halusinasi mutlak.
            #
            # Katalog sengaja tidak memaafkan: pipeline punya katalog dan
            # pembanding tidak. Lihat docs/PENILAIAN_MANUSIA.md.
            m["kata_asing"].append(bool(kj - terlihat))

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
            if asli > 0 and plat in (r.get("source"), "umum"):
                # Cakupan dicatat terpisah dari galat. Pipeline menyetel harga 0
                # untuk barang yang tidak dikenalnya, jadi baris itu keluar dari
                # harga_err -- ia mengundurkan diri dari kasus sulit lalu dinilai
                # di kasus mudah. Tanpa kolom cakupan, penarikan diri itu tidak
                # terlihat sama sekali dan galatnya tampak lebih baik dari nyatanya.
                m["harga_cakupan"].append(harga > 0)
            if harga > 0 and asli > 0 and plat in (r.get("source"), "umum"):
                m["harga_err"].append(abs(harga - asli) / asli)
                # harga_err ASIMETRIS: menebak 100rb untuk barang 20rb = 400%,
                # sebaliknya cuma 80%. Model yang menebak angka bulat (baseline
                # 12b memakai hanya 34 nilai unik untuk 397 tebakan, kebanyakan
                # 100rb-200rb) selalu kelebihan pada barang murah, dan 54% produk
                # di katalog ini di bawah Rp 50rb -- galatnya jadi terlihat jauh
                # lebih besar dari kesalahannya yang sebenarnya.
                #
                # Dua ukuran simetris ini menghukum kelebihan dan kekurangan
                # sama berat. |log| 0,69 berarti meleset tepat dua kali lipat.
                m["harga_logerr"].append(abs(math.log(harga / asli)))
                m["harga_2x"].append(0.5 <= harga / asli <= 2.0)
                # tebakan mentah model, disimpan sebelum ditimpa hitungan katalog
                # PERINGATAN: harga_model BUKAN tebakan yang berdiri sendiri.
                # ringkas_konteks menaruh median harga tetangga langsung di
                # prompt ("tengah Rp53.470"), jadi model menuliskan angka yang
                # praktis sama dengan yang nanti dihitung katalog -- sama persis
                # di 70% baris S3. Metrik ini tidak boleh dikutip sebagai bukti
                # bahwa harga_deterministik menambah nilai. Lihat OPTIMASI.md.
                hm = h.get("harga_model")
                try:
                    hm = float(hm)
                except (TypeError, ValueError):
                    hm = 0.0
                if hm > 0:
                    m["harga_model_err"].append(abs(hm - asli) / asli)

            # Kategori adalah satu dari empat keluaran tapi tidak pernah diukur
            # sampai sesi 3. Tanpa batasan, model mengarang bebas: "Minuman /
            # Teh / Teh Celup", "Sepatu Pria" -- hanya 1 dari 4 percobaan
            # menghasilkan nilai yang benar-benar ada di taksonomi.
            kat = str(h.get("kategori", "")).strip().lower()
            m["kategori_sah"].append(kat in KATEGORI_UMKM)
            asli_kat = str(r.get("kategori_asli", "")).strip().lower()
            if asli_kat in KATEGORI_UMKM:
                m["kategori_benar"].append(kat == asli_kat)

            p = profil.get(plat, {}).get("judul", {})
            if p.get("target_kata"):
                lo, hi = p["target_kata"]
                m["panjang_patuh"].append(lo <= len(judul.split()) <= hi)

            # `inti` itu RECALL murni: berapa bagian kata judul asli yang
            # berhasil disebut ulang. Ia tidak menghukum kata tambahan sama
            # sekali, jadi bisa dinaikkan dengan menggelembungkan judul --
            # persis kebiasaan keyword stuffing yang justru ingin dihindari.
            #
            # Diuji dengan menempelkan 12 kata tersering di katalog ke SETIAP
            # judul, tanpa melihat produknya:
            #
            #   kata sampah   inti (recall)   inti_f1
            #             0          0,346     0,398
            #             4          0,355     0,306
            #            12          0,368     0,214
            #
            # Recall naik +0,022 -- cukup untuk membalik selisih pipeline lawan
            # student (0,346 lawan 0,315). F1 turun 0,184 pada serangan yang
            # sama. Karena itu inti_f1 yang dipakai membandingkan sistem.
            #
            # `inti` dipertahankan supaya angka lama bisa direproduksi.
            emas = kata(r.get("judul_asli", ""))
            if emas and kj:
                irisan = len(emas & kj)
                m["inti"].append(irisan / len(emas))
                m["inti_presisi"].append(irisan / len(kj))
                m["inti_f1"].append(2 * irisan / (len(emas) + len(kj)))
            elif emas:
                m["inti"].append(0.0)
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
        "harga_cakupan%": round(100 * rata("harga_cakupan"), 1),
        "harga_logerr": (round(st.median(m["harga_logerr"]), 3)
                         if m["harga_logerr"] else float("nan")),
        "harga_2x%": round(100 * rata("harga_2x"), 1),
        "kategori_sah%": round(100 * rata("kategori_sah"), 1),
        "kategori_benar%": round(100 * rata("kategori_benar"), 1),
        "n_harga": len(m["harga_err"]),
        "harga_model_err%": (round(100 * st.median(m["harga_model_err"]), 1)
                             if m["harga_model_err"] else float("nan")),
        "spek_karang%": round(100 * rata("spek_karang"), 1),
        "merek_karang%": round(100 * rata("merek_karang"), 1),
        "merek_sempit%": round(100 * rata("merek_sempit"), 1),
        "merek_ketat%": round(100 * rata("merek_ketat"), 1),
        "kata_asing%": round(100 * rata("kata_asing"), 1),
        "panjang_patuh%": round(100 * rata("panjang_patuh"), 1),
        "inti": round(rata("inti"), 3),
        "inti_presisi": round(rata("inti_presisi"), 3),
        "inti_f1": round(rata("inti_f1"), 3),
        "desk_char": round(rata("desk_char")),
        "desk_spek%": round(100 * rata("desk_spek"), 1),
        "desk_asing%": round(100 * rata("desk_asing"), 1),
        "desk_klaim%": round(100 * rata("desk_klaim"), 1),
        "desk_sampah%": round(100 * rata("desk_sampah"), 1),
        "desk_ulang%": round(100 * rata("desk_ulang"), 1),
        "desk_potong%": round(100 * rata("desk_potong"), 1),
        "detik": round(rata("detik"), 1),
        # detik dicatat per PRODUK, sedangkan tiap produk menghasilkan beberapa
        # listing -- dan jumlahnya berbeda antar berkas (pipeline mengikuti
        # platform_profiles.json, baseline mengunci tiga). Membandingkan detik
        # per produk berarti membandingkan dua satuan yang berbeda. Penyebutnya
        # dihitung sebelum --hanya-platform, karena menyaring platform saat
        # menilai tidak membuat pekerjaannya jadi lebih sedikit.
        "detik_listing": (round(rata("detik") / (n_listing_penuh / n_baris_dipakai), 2)
                          if n_baris_dipakai and n_listing_penuh else float("nan")),
        "kata_judul": {k: round(st.median(v), 1) for k, v in sorted(per_platform.items())},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("berkas", nargs="+")
    ap.add_argument("--hanya-platform", default=None,
                    help="nilai hanya platform ini, dipisah koma. Perlu kalau dua "
                         "berkas menulis himpunan platform yang berbeda — tanpa ini "
                         "keduanya dibandingkan atas dasar yang tidak sama.")
    ap.add_argument("--semua", action="store_true",
                    help="tampilkan juga metrik yang sudah GUGUR "
                         "(spek_karang, merek_sempit, merek_ketat, desk_spek, "
                         "desk_asing) -- hanya untuk mereproduksi angka lama")
    ap.add_argument("--samakan-cakupan", default=None, metavar="BERKAS",
                    help="nilai semua berkas hanya pada produk yang BERKAS ini "
                         "berani beri harga. Perlu karena pipeline mengundurkan "
                         "diri dari barang tak dikenal, jadi harga_err-nya diukur "
                         "di kasus mudah saja sementara baseline menjawab semua.")
    args = ap.parse_args()

    hanya = ({p.strip() for p in args.hanya_platform.split(",")}
             if args.hanya_platform else None)
    hanya_id = id_berharga(Path(args.samakan_cakupan)) if args.samakan_cakupan else None
    profil = muat_profil()
    hasil = [nilai(Path(b), profil, hanya, hanya_id) for b in args.berkas]
    if hanya_id is not None:
        print(f"cakupan disamakan ke {Path(args.samakan_cakupan).name}: "
              f"{len(hanya_id)} produk")
    if hanya:
        print(f"platform dinilai: {sorted(hanya)}")
        print()

    # Metrik yang GUGUR setelah penilaian manusia tidak lagi dicetak secara
    # bawaan. Ia tetap dihitung dan tetap ada di dict keluaran supaya angka lama
    # bisa direproduksi, tapi mencetaknya berdampingan dengan metrik yang sah
    # membuatnya terbaca sebagai ukuran biasa -- dan itu jalan paling mungkin
    # angka gugur terkutip ke laporan. Pakai --semua untuk menampilkannya.
    GUGUR = {"spek_karang%", "merek_sempit%", "merek_ketat%",
             "desk_spek%", "desk_asing%"}

    kunci = ["berkas", "n_listing", "json_valid%", "harga_err%",
             "harga_logerr", "harga_2x%", "harga_cakupan%", "n_harga",
             "kategori_sah%", "kategori_benar%", "kata_asing%",
             "spek_karang%", "merek_sempit%", "merek_ketat%",
             "panjang_patuh%", "inti", "inti_presisi", "inti_f1",
             "detik", "detik_listing"]
    kunci_desk = ["berkas", "desk_char", "desk_spek%", "desk_asing%", "desk_klaim%",
                  "desk_sampah%", "desk_ulang%", "desk_potong%"]
    if not args.semua:
        kunci = [k for k in kunci if k not in GUGUR]
        kunci_desk = [k for k in kunci_desk if k not in GUGUR]
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

    print()
    print("  kata_asing%   satu-satunya ukuran halusinasi yang tervalidasi manusia")
    print("                (recall 93,3%, presisi 35% pada 51 listing berlabel).")
    print("                PRESISI 35% berarti dua dari tiga tuduhannya sebenarnya")
    print("                sah -- angka mutlaknya BUKAN kadar halusinasi. Yang")
    print("                bermakna selisih antar sistem. Lihat")
    print("                docs/PENILAIAN_MANUSIA.md.")
    if args.semua:
        print()
        print("  PERINGATAN: spek_karang, merek_sempit, merek_ketat, desk_spek,")
        print("  dan desk_asing sudah GUGUR -- recall-nya 0-9% terhadap penilaian")
        print("  manusia. Ditampilkan hanya untuk mereproduksi angka lama; jangan")
        print("  dikutip sebagai ukuran halusinasi.")


def _selfcheck():
    """Dua artefak yang pernah membuat pipeline menang tanpa mengukur apa pun."""
    import tempfile

    def rec(pid, harga, plats, detik):
        return {"product_id": pid, "source": "tokopedia", "judul_asli": "Botol Minum",
                "harga_asli": 100, "kategori_asli": "kriya_rumah", "vlm": "botol minum",
                "tetangga": [], "detik": detik,
                "hasil": {p: {"judul": "Botol Minum", "deskripsi": "Botol minum praktis.",
                              "perkiraan_harga": harga} for p in plats}}

    def tulis(d, nama, baris):
        p = Path(d) / nama
        p.write_text(chr(10).join(json.dumps(r) for r in baris), encoding="utf-8")
        return p

    with tempfile.TemporaryDirectory() as d:
        dua = ["blibli", "tokopedia"]
        # (1) penarikan diri: pipeline hanya menjawab produk 'a', dan tepat.
        # Baseline menjawab semuanya dan meleset di dua yang sulit.
        pipe = tulis(d, "pipe.jsonl", [rec("a", 100, dua, 3.0),
                                       rec("b", 0, dua, 3.0), rec("c", 0, dua, 3.0)])
        base = tulis(d, "base.jsonl", [rec("a", 100, dua, 6.0),
                                       rec("b", 300, dua, 6.0), rec("c", 400, dua, 6.0)])
        hp, hb = nilai(pipe, {}), nilai(base, {})
        assert hp["harga_err%"] == 0.0 and hb["harga_err%"] == 200.0, (hp, hb)
        # Asimetri harga_err: dua tebakan yang sama salahnya secara berlipat
        # -- 2x kelebihan dan 2x kekurangan -- harus dinilai sama oleh ukuran
        # simetris, tapi TIDAK oleh harga_err.
        lebih = tulis(d, "lebih.jsonl", [rec("a", 200, dua, 1.0)])   # asli 100
        kurang = tulis(d, "kurang.jsonl", [rec("a", 50, dua, 1.0)])
        hl, hk = nilai(lebih, {}), nilai(kurang, {})
        assert hl["harga_err%"] == 100.0 and hk["harga_err%"] == 50.0, (hl, hk)
        assert hl["harga_logerr"] == hk["harga_logerr"], (hl, hk)
        assert hl["harga_2x%"] == hk["harga_2x%"] == 100.0, (hl, hk)
        assert hp["harga_cakupan%"] == 33.3 and hb["harga_cakupan%"] == 100.0, (hp, hb)
        # cakupan disamakan -> selisih 200 poin tadi lenyap seluruhnya
        ids = id_berharga(pipe)
        assert ids == {"a"}, ids
        hp2, hb2 = nilai(pipe, {}, None, ids), nilai(base, {}, None, ids)
        assert hp2["harga_err%"] == hb2["harga_err%"] == 0.0, (hp2, hb2)

        # (2) detik per listing tidak boleh berubah karena saringan platform:
        # menyaring saat menilai tidak membuat pekerjaannya jadi lebih sedikit.
        tiga = ["blibli", "tokopedia", "shopee"]
        p2 = tulis(d, "p2.jsonl", [rec(x, 100, dua, 3.0) for x in "abc"])
        b3 = tulis(d, "b3.jsonl", [rec(x, 100, tiga, 6.0) for x in "abc"])
        assert nilai(p2, {})["detik_listing"] == 1.5
        assert nilai(b3, {})["detik_listing"] == 2.0
        assert nilai(b3, {}, {"blibli", "tokopedia"})["detik_listing"] == 2.0
    print("selfcheck ok")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        main()
