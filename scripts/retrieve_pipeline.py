"""Pipeline dua tahap: foto -> fakta terlihat -> cari di dataset -> judul + deskripsi.

Datasetnya dipakai **saat model bekerja**, bukan dilebur jadi bobot lewat latihan.
Uji sebelumnya menunjukkan model dasar sudah 90% benar menyebut jenis barang tapi
sering salah merek. Merek tidak bisa ditebak dari foto buram — tapi ada di 28 ribu
judul milikmu. Jadi: model melihat, dataset mengingat.

    python scripts/retrieve_pipeline.py --n 20
    python scripts/retrieve_pipeline.py --hanya-cari "sunscreen tube biru"

Indeksnya TF-IDF murni numpy/pandas — tanpa unduhan, tanpa GPU tambahan.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
import re
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd
import requests
from PIL import Image

from build_train_pairs import clean_title

PROJECT = Path(__file__).resolve().parent.parent
SUMBER = PROJECT / "data_drive" / "merged" / "merged_local.parquet"
KELUARAN = PROJECT / "data_drive" / "eval" / "pipeline_demo.jsonl"
OLLAMA = "http://localhost:11434/api/generate"

# gemma3 dipilih setelah diadu di 100 gambar yang sama: skor inti 0,483 lawan 0,371,
# dan nol keluaran yang bocor jadi teks penalaran (qwen3-vl bocor 11 dari 100).
MODEL_VISI = "gemma3:4b"
MODEL_TEKS = "qwen2.5:7b"

# "Langsung ke jawaban" perlu: gemma3 suka membuka dengan "Berikut adalah barang
# yang ada di foto tersebut:" dan menghabiskan anggaran sebelum sampai ke isinya.
PROMPT_VISI = ("Barang apa di foto ini? Sebut jenis dan mereknya saja, satu baris, "
               "langsung ke jawaban tanpa kalimat pembuka.")

# blok basa-basi toko yang tidak boleh dicontoh gayanya
SAMPAH = re.compile(
    r"(?i)selamat datang|happy shopping|budayakan membaca|wajib baca|mohon dibaca|"
    r"tidak menerima komplain|no complain|bukan tanggung jawab|gratis ongkir|"
    r"ongkos kirim|bubble wrap|harga dapat berubah|chat admin|whatsapp|0[0-9]{9,12}"
)
STOP = {"dan", "untuk", "yang", "dengan", "atau", "the", "for", "with", "pcs", "set"}


def token(teks) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", str(teks).lower())
            if len(w) >= 3 and w not in STOP]


class Indeks:
    """TF-IDF ringkas di atas judul produk. 28 ribu judul pendek — cukup dict."""

    def __init__(self, judul: list[str]):
        self.n = len(judul)
        self.inverted: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.panjang = []
        for i, j in enumerate(judul):
            t = token(j)
            self.panjang.append(math.sqrt(len(t)) or 1.0)
            hitung: dict[str, int] = defaultdict(int)
            for w in t:
                hitung[w] += 1
            for w, c in hitung.items():
                self.inverted[w].append((i, c))
        self.idf = {w: math.log(1 + self.n / len(post))
                    for w, post in self.inverted.items()}

    def cari(self, kueri: str, k: int = 5) -> list[tuple[int, float]]:
        skor: dict[int, float] = defaultdict(float)
        for w in set(token(kueri)):
            if w not in self.inverted:
                continue
            bobot = self.idf[w]
            for i, c in self.inverted[w]:
                skor[i] += bobot * (1 + math.log(c)) / self.panjang[i]
        return sorted(skor.items(), key=lambda x: -x[1])[:k]


INDEKS_GAMBAR = PROJECT / "data_drive" / "merged" / "image_index.npz"


class IndeksGambar:
    """Pencarian tetangga lewat kemiripan visual, bukan kata.

    Pencarian teks menemukan jenis barang yang benar tapi salah kelas harga:
    gaun Eprise Rp479.800 ditetanggai gaun pasar karena kata-katanya sama.
    Foto membedakan keduanya; teks tidak bisa.

    Dimuat malas — kalau berkas indeksnya belum dibuat, pipeline tetap jalan
    dengan pencarian teks saja.
    """

    def __init__(self, path: Path = INDEKS_GAMBAR):
        import numpy as np
        import torch
        import open_clip

        d = np.load(path, allow_pickle=True)
        self.emb = d["emb"].astype("float32")
        self.pid = list(d["pid"])
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k", device=self.device)
        self.model.eval()
        self.torch, self.np = torch, np

    def vektor(self, path: Path):
        with Image.open(path) as im:
            x = self.preprocess(im.convert("RGB")).unsqueeze(0).to(self.device)
        with self.torch.no_grad():
            v = self.model.encode_image(x)
            v = v / v.norm(dim=-1, keepdim=True)
        return v.cpu().numpy().astype("float32")[0]

    def cari(self, path: Path, k: int = 5) -> list[tuple[str, float]]:
        v = self.vektor(path)
        skor = self.emb @ v                      # vektor sudah dinormalkan
        atas = self.np.argsort(-skor)[:k]
        return [(self.pid[i], float(skor[i])) for i in atas]


def bersih_deskripsi(teks: str, maks: int = 320) -> str:
    kalimat = [s.strip() for s in re.split(r"[.\n]+", str(teks)) if s.strip()]
    baik = [s for s in kalimat if not SAMPAH.search(s)]
    return " ".join(baik)[:maks]


def muat_gambar(path: Path, sisi_maks: int = 640) -> str:
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((sisi_maks, sisi_maks))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def panggil(model: str, prompt: str, images=None, timeout=300, num_predict=500,
            minta_json=False) -> str:
    body = {"model": model, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.2, "num_predict": num_predict}}
    if images:
        body["images"] = images
    if minta_json:
        body["format"] = "json"
    r = requests.post(OLLAMA, timeout=timeout, json=body)
    r.raise_for_status()
    j = r.json()
    jawab = (j.get("response") or "").strip()
    if not jawab:
        # model thinking kehabisan anggaran: isinya masih ada di `thinking`
        jawab = (j.get("thinking") or "").strip()[-300:]
    return jawab


ANGKA = re.compile(r"\d+(?:[.,]\d+)?\s*(?:ml|l|gr|g|kg|liter|pcs|cm|mm|inch|watt|w)?\b",
                   re.IGNORECASE)


def samar_angka(teks: str) -> str:
    """Buang angka dan satuan dari contoh gaya, supaya tidak ikut tersalin."""
    return ANGKA.sub("…", str(teks))


def ringkas_konteks(tetangga: pd.DataFrame) -> str:
    """Ringkasan katalog: kosakata, kategori, kisaran harga — BUKAN judul utuh.

    Versi pertama menyodorkan judul tetangga apa adanya, dan model menyalin
    varian serta nomor model dari produk lain ("Sabun 5 Liter Lemongrass" untuk
    foto sabun blueberry). Yang boleh menular hanya kosakata dan harga.
    """
    harga = pd.to_numeric(tetangga["price"], errors="coerce").dropna()
    kat = tetangga["kategori_umkm"].mode()
    istilah: dict[str, int] = defaultdict(int)
    for j in tetangga["title_bersih"]:
        for w in token(j):
            if not any(c.isdigit() for c in w):
                istilah[w] += 1
    # Syarat muncul di >=2 tetangga. Nama merek khas hampir selalu muncul sekali,
    # jadi tersaring sendiri; kosakata umum ("keripik", "pisang") tetap lolos.
    # Tanpa ini merek tetangga menular: foto madu -> "Beverage Almaidani Nutrindo".
    umum = [w for w, c in sorted(istilah.items(), key=lambda x: -x[1])[:12] if c >= 2]
    gaya = [samar_angka(bersih_deskripsi(d, 130))
            for d in tetangga["description"].head(2) if str(d).strip()]

    bagian = [f"Kategori lazim: {kat.iloc[0] if len(kat) else 'tidak jelas'}"]
    if len(harga):
        bagian.append(
            f"Kisaran harga pasar untuk barang serupa: Rp{int(harga.quantile(0.25)):,} "
            f"- Rp{int(harga.quantile(0.75)):,} (tengah Rp{int(harga.median()):,})")
    bagian.append(f"Istilah yang lazim dipakai penjual: {', '.join(umum)}")
    if gaya:
        bagian.append("Contoh nada kalimat penjual (tiru nadanya saja, JANGAN salin isinya): "
                      + " | ".join(gaya))
    return "\n".join(bagian)


PROFIL_PATH = PROJECT / "data_drive" / "merged" / "platform_profiles.json"


def muat_profil() -> dict:
    if not PROFIL_PATH.exists():
        return {}
    return json.loads(PROFIL_PATH.read_text(encoding="utf-8"))


def aturan_platform(profil: dict, nama: str, kategori: str | None) -> str:
    """Aturan gaya khas satu platform, diturunkan dari data nyata.

    Judul blibli median 9 kata, Tokopedia 15, Shopee 11 dan gemar tanda '/'.
    Harga fashion di blibli 3x Tokopedia untuk kategori yang sama. Tanpa ini,
    satu gaya dipaksakan ke semua lapak.
    """
    p = profil.get(nama)
    if not p:
        return ""
    j = p["judul"]
    lo, hi = j["target_kata"]
    baris = [f"Platform tujuan: {nama}.",
             f"- Panjang judul yang lazim di sini: {lo}-{hi} kata (median {j['median_kata']})."]
    if j["pct_garis_miring"] >= 20:
        baris.append("- Penjual di sini biasa memisahkan kata kunci dengan tanda '/'.")
    desk = p["deskripsi"]["median_char"]
    if desk:
        baris.append(f"- Panjang deskripsi lazim sekitar {desk} karakter.")
    else:
        baris.append("- Platform ini tidak punya data deskripsi; tulis ringkas saja.")

    h = p["harga_per_kategori"].get(kategori or "") or p["harga_per_kategori"].get("SEMUA")
    if h:
        # Sengaja TIDAK menyuruh "pakai tengah rentang ini". Rentang per kategori
        # sangat lebar (kategori 'lainnya' membentang Rp21rb-Rp969rb), dan ketika
        # dijadikan dasar, model membuang bukti yang jauh lebih tepat: harga produk
        # kembar di katalog. Rentang ini hanya untuk arah, bukan sumber angka.
        baris.append(f"- Sebagai arah saja, harga di platform ini untuk kategori serupa "
                     f"berkisar Rp{h['p25']:,} - Rp{h['p75']:,}. Tetap utamakan harga "
                     "produk serupa dari katalog di atas.")
    else:
        baris.append("- Tidak ada data harga untuk platform ini; isi perkiraan_harga dengan 0.")

    kk = p["kosakata_khas"].get(kategori or "")
    if kk:
        baris.append(f"- Kata yang khas dipakai di platform ini: {', '.join(kk[:8])}.")
    return "\n".join(baris)


ATURAN = (
    "Tulis listing untuk produk di foto. Aturan:\n"
    # Panjang judul diserahkan ke aturan platform kalau ada. Batas keras 12 kata
    # di sini pernah bertabrakan dengan target Tokopedia (10-20 kata) dan model
    # selalu menurut ke yang lebih ketat, jadi judul Tokopedia keluar terlalu pendek.
    "- Panjang judul: ikuti bagian 'Gaya listing platform tujuan' bila ada; "
    "kalau tidak ada, maksimal 12 kata. Sebut jenis barang lebih dulu.\n"
    "- Deskripsi 2-3 kalimat, menarik tapi hanya menyebut hal yang terlihat.\n"
    "- DILARANG menyebut ukuran, isi, berat, rasa, varian, atau nomor model "
    "kecuali benar-benar terbaca di foto.\n"
    "- Jangan mengarang garansi, izin BPOM, atau klaim khasiat.\n"
    "{LARANGAN_TAMBAHAN}"
    "- Kalau merek tidak terbaca di foto, jangan sebut merek apa pun.\n\n"
    'Jawab JSON: {"judul": "...", "deskripsi": "...", "kategori": "...", '
    '"perkiraan_harga": 0}'
)


LEXICON_PATH = PROJECT / "data_drive" / "merged" / "lexicon.json"


def muat_lexicon() -> dict:
    if not LEXICON_PATH.exists():
        return {}
    lex = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
    return {"merek": set(lex.get("merek", [])), "jenis": set(lex.get("jenis", [])),
            "umum": set(lex.get("umum", []))}


def saring_merek(judul: str, fakta: str, tetangga: pd.DataFrame | None,
                 lex: dict) -> tuple[str, list[str]]:
    """Buang kata spesifik di judul yang tidak didukung foto maupun katalog.

    Verifikasi pasca-generasi, bukan pencegahan lewat prompt: larangan di prompt
    sudah dicoba dan tetap bocor ("Tas Longchamp" untuk tas tanpa merek). Kata
    jenis barang tetap lolos supaya kalimatnya tidak rusak; yang disaring hanya
    kata spesifik yang tidak ada dasarnya.
    """
    if not lex or not judul:
        return judul, []
    # model kadang menulis "merek tidak tertera"; potongannya menyisakan
    # judul rusak seperti "Gaun Floral Merek Tidak", jadi dibuang utuh
    # tanda baca ikut dilangkahi: model menulis "Merek: Tidak Tertera", dan pola
    # tanpa [:,-] hanya memotong ekornya sehingga tersisa "... Merek Tidak"
    judul = re.sub(r"(?i)\bmerek\s*[:,\-]?\s*(tidak|belum|no)\b[\w\s]*", " ", judul)
    judul = re.sub(r"\s+", " ", judul).strip()

    # Dua tingkat bukti. Untuk kata biasa, katalog cukup. Untuk MEREK, hanya foto
    # yang sah: tetangga katalog boleh bermerek ZARA tanpa membuat gaun di foto
    # jadi ZARA — dan itu persis yang lolos sebelum pemisahan ini dibuat.
    dukungan_foto = set(token(fakta))
    dukungan = set(dukungan_foto)
    if tetangga is not None and len(tetangga):
        for t in tetangga["title_bersih"]:
            dukungan |= set(token(t))

    # Angka & satuan hanya sah kalau terbaca di foto. Katalog TIDAK berlaku sebagai
    # bukti di sini: tetangga boleh 500ml sementara botol di foto 200ml. Ukuran
    # salah di judul bukan sekadar cacat mutu — pembeli bisa menuntut penjual.
    angka_terlihat = set(re.findall(r"\d+", fakta or ""))

    simpan, dibuang = [], []
    for w in judul.split():
        bersih = re.sub(r"[^\w\.\-/]", "", w).lower()
        angka_kata = re.findall(r"\d+", bersih)
        if angka_kata and not all(a in angka_terlihat for a in angka_kata):
            dibuang.append(w)                      # ukuran/isi/jumlah yang dikarang
        elif not bersih or len(bersih) < 3 or not bersih.isalpha():
            simpan.append(w)                       # tanda baca & kode varian sah
        elif bersih in dukungan_foto or bersih in lex["jenis"]:
            simpan.append(w)                       # terbaca di foto, atau kata jenis
        elif bersih in lex.get("umum", ()) and bersih not in lex["merek"]:
            # kata Indonesia lazim -> aman. Kecuali kalau ia juga nama merek:
            # "fantech" sering muncul di katalog, tapi tetap merek milik orang lain
            simpan.append(w)
        else:
            # Kata langka. Sengaja TIDAK disahkan oleh judul tetangga: merek milik
            # produk lain lolos lewat celah itu ("ZARA" pada gaun tanpa merek),
            # dan kamus merek tidak bisa diandalkan menampung semua nama.
            dibuang.append(w)

    # sisa kata penghubung yang menggantung setelah penyaringan, mis. judul yang
    # berakhir "... Gaun Floral Merek" karena penjelasnya sudah dibuang
    while simpan and re.sub(r"\W", "", simpan[-1]).lower() in {
            "merek", "tidak", "belum", "dan", "untuk", "dengan", "no", "brand"}:
        simpan.pop()
    return " ".join(simpan).strip(" -/&,"), dibuang


# Daftar sisi-generator. `eval_listing.py` menyimpan daftarnya sendiri dengan
# sengaja: kalau keduanya berbagi satu berkas, penyaring dan pengukurnya jadi
# sirkular — apa pun yang lupa dilarang otomatis lolos juga dari penilaian.
KLAIM_TERLARANG = re.compile(
    r"(?i)\b(garansi|bergaransi|bpom|halal|mui|sni|fda|original|ori|asli|resmi|"
    r"menyembuhkan|mengobati|ampuh|khasiat|terbukti|dijamin|jaminan)\b|100\s*%")


def pelanggaran_deskripsi(desk: str, fakta: str, tetangga: pd.DataFrame | None,
                          lex: dict) -> list[str]:
    """Daftar hal bermasalah di deskripsi: klaim, angka karangan, istilah asing."""
    if not desk:
        return []
    salah = [m.group(0) for m in KLAIM_TERLARANG.finditer(desk)]

    angka_foto = set(re.findall(r"\d+", fakta or ""))
    salah += [a for a in re.findall(r"\d+", desk) if a not in angka_foto]

    if lex:
        dukungan = set(token(fakta))
        if tetangga is not None and len(tetangga):
            for t in tetangga["title_bersih"]:
                dukungan |= set(token(t))
        salah += [w for w in token(desk)
                  if w.isalpha() and w not in dukungan
                  and (w in lex["merek"] or w not in lex.get("umum", ()))]
    return sorted(set(salah))


def saring_kalimat(desk: str, fakta: str, tetangga: pd.DataFrame | None,
                   lex: dict) -> str:
    """Cara (a): buang kalimat yang memuat pelanggaran, sisanya dibiarkan utuh."""
    kalimat = [s for s in re.split(r"(?<=[.!?])\s+", desk) if s.strip()]
    aman = [s for s in kalimat if not pelanggaran_deskripsi(s, fakta, tetangga, lex)]
    return " ".join(aman).strip()


def tulis_ulang_deskripsi(desk: str, salah: list[str], fakta: str) -> str:
    """Cara (b): minta model menulis ulang, pelanggarannya disebut satu per satu."""
    prompt = (
        f"Deskripsi produk ini memuat hal yang tidak boleh ada: {', '.join(salah)}.\n\n"
        f"Yang benar-benar terlihat di foto: {fakta}\n"
        f"Deskripsi lama: {desk}\n\n"
        "Tulis ulang jadi 2-3 kalimat menarik TANPA kata-kata bermasalah itu, "
        "tanpa menyebut ukuran, merek, sertifikasi, atau khasiat yang tidak "
        'terlihat di foto. Jawab JSON: {"deskripsi": "..."}')
    try:
        mentah = panggil(MODEL_TEKS, prompt, num_predict=250, minta_json=True)
        return str(json.loads(mentah).get("deskripsi", "")).strip() or desk
    except Exception:
        return desk


def panjangkan_judul(judul: str, tetangga: pd.DataFrame | None, profil: dict,
                     plat: str | None, lex: dict) -> tuple[str, list[str]]:
    """Tambahkan kata kunci pendukung sampai judul mencapai panjang lazim platform.

    Tokopedia median 15 kata, tapi model 4B/7B tetap menulis 6 kata betapapun
    dimintanya — tiga putaran prompt tidak menggesernya. Jadi dikerjakan di luar
    model: kata diambil dari judul produk kembar di katalog, yang menurut definisi
    sudah didukung bukti, jadi tidak menambah risiko halusinasi.
    """
    if not plat or tetangga is None or not len(tetangga):
        return judul, []
    target = profil.get(plat, {}).get("judul", {}).get("target_kata")
    if not target:
        return judul, []
    lo = target[0]
    ada = set(token(judul))
    if len(judul.split()) >= lo:
        return judul, []

    # kata yang muncul di >=2 produk kembar; merek unik tersaring sendiri
    hitung: dict[str, int] = defaultdict(int)
    for t in tetangga["title_bersih"]:
        for w in set(token(t)):
            hitung[w] += 1
    kandidat = [w for w, c in sorted(hitung.items(), key=lambda x: -x[1])
                if c >= 2 and w not in ada and w.isalpha() and len(w) > 2]

    tambah = []
    kata = judul.split()
    for w in kandidat:
        if len(kata) >= lo:
            break
        kata.append(w.capitalize() if w not in lex.get("merek", ()) else w.upper())
        tambah.append(w)
    return " ".join(kata), tambah


def harga_deterministik(tetangga: pd.DataFrame, profil: dict, plat: str | None,
                        kategori: str | None, faktor_global: dict) -> int | None:
    """Saran harga dihitung, bukan ditebak model.

    Dasarnya harga tengah produk kembar di katalog — bukti paling tepat yang kita
    punya. Lalu digeser oleh faktor platform: fashion di blibli median 3x Tokopedia,
    jadi barang yang sama pantas dipasang lebih tinggi di sana.

    Model bahasa buruk dalam aritmatika dan gampang tergoda memakai angka bulat
    dari rentang kategori; perhitungan ini menutup celah itu.
    """
    if tetangga is None or not len(tetangga):
        return None
    h = pd.to_numeric(tetangga["price"], errors="coerce").dropna()
    h = h[h > 0]
    if not len(h):
        return None
    acuan = float(h.median())

    # Faktor dihitung terhadap platform ASAL tetangga, bukan rata-rata global.
    # Tetangga hampir selalu berasal dari satu platform (pencarian menarik produk
    # kembar), jadi memakai pembagi global berarti menggeser dua kali: harga
    # sampo Tokopedia Rp55.100 sempat jatuh ke Rp42.800 padahal sudah benar.
    if plat and kategori:
        asal = tetangga["source"].mode()
        asal = str(asal.iloc[0]) if len(asal) else None
        tuj = profil.get(plat, {}).get("harga_per_kategori", {}).get(kategori)
        src = profil.get(asal, {}).get("harga_per_kategori", {}).get(kategori)
        if tuj and src and src["median"]:
            faktor = tuj["median"] / src["median"]
            # dikunci 0,5x-2x supaya kategori sampah seperti 'lainnya' tidak meledak
            acuan *= min(max(faktor, 0.5), 2.0)
    return int(round(acuan / 100) * 100)


SHOPEE_CSV = PROJECT / "data_drive" / "data" / "external" / "shopee" / "data_products_id_small.csv"


def indeks_per_platform(df: pd.DataFrame, maks_shopee: int = 40_000) -> dict:
    """Indeks judul terpisah per platform, untuk contoh pola yang sepadan.

    Menyodorkan judul Tokopedia sebagai contoh untuk listing blibli justru
    mengajarkan gaya yang salah — panjangnya beda 6 kata. Contoh harus datang
    dari lapak yang sama.
    """
    idx = {}
    for plat, g in df.groupby("source"):
        judul = g["title_bersih"].tolist()
        idx[str(plat)] = (Indeks(judul), judul)
    if SHOPEE_CSV.exists():
        nama = pd.read_csv(SHOPEE_CSV, usecols=["name"])["name"].astype(str)
        nama = nama.sample(min(maks_shopee, len(nama)), random_state=0).tolist()
        idx["shopee"] = (Indeks(nama), nama)
    return idx


def contoh_pola(idx_platform: dict, plat: str | None, fakta: str, n: int = 2) -> list[str]:
    """Dua judul nyata dari platform itu untuk produk semirip mungkin."""
    if not plat or plat not in idx_platform:
        return []
    indeks, judul = idx_platform[plat]
    return [samar_angka(judul[i]) for i, _ in indeks.cari(fakta, n)]


# Cara (c): larangan diperluas dan disebut satu per satu. Versi lama hanya
# menyebut "garansi, BPOM, khasiat" secara umum, dan kata seperti "ampuh" atau
# "terbukti" lolos karena tidak ada di daftar.
LARANGAN_KATA = (
    "- DILARANG memakai kata: ampuh, khasiat, terbukti, dijamin, original, asli, "
    "resmi, halal, BPOM, SNI, garansi, menyembuhkan, mengobati, 100%.\n"
    "- Di deskripsi pun jangan sebut merek yang tidak terbaca di foto.\n")


def susun_prompt(fakta: str, tetangga: pd.DataFrame | None,
                 profil: dict | None = None, platform: str | None = None,
                 idx_platform: dict | None = None,
                 larangan: bool = False) -> str:
    kepala = ("Kamu penulis listing marketplace Indonesia.\n\n"
              f"Yang terlihat di foto produk: {fakta}\n\n")

    kategori = None
    bagian = []
    if tetangga is not None and len(tetangga):
        modus = tetangga["kategori_umkm"].mode()
        kategori = str(modus.iloc[0]) if len(modus) else None
        bagian.append("Rujukan dari katalog produk nyata (hanya untuk kosakata, "
                      "kategori, dan harga — bukan untuk menyalin spesifikasi):\n"
                      + ringkas_konteks(tetangga))
    if profil and platform:
        aturan = aturan_platform(profil, platform, kategori)
        if aturan:
            bagian.append("Gaya listing platform tujuan (patuhi ini):\n" + aturan)
    if idx_platform and platform:
        pola = contoh_pola(idx_platform, platform, fakta)
        if pola:
            bagian.append("Contoh pola judul nyata dari platform ini — tiru panjang dan "
                          "susunannya, JANGAN salin produknya (angka sudah disamarkan):\n"
                          + "\n".join(f"  - {p}" for p in pola))

    aturan_akhir = ATURAN.replace("{LARANGAN_TAMBAHAN}",
                                  LARANGAN_KATA if larangan else "")
    if not bagian:
        # tetangga terlalu jauh: lebih baik keluaran umum daripada salah meyakinkan
        return kepala + aturan_akhir
    return kepala + "\n\n".join(bagian) + "\n\n" + aturan_akhir


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--k", type=int, default=5, help="berapa tetangga diambil")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--min-skor", type=float, default=2.0,
                    help="ambang skor teks; di bawah ini konteks katalog tidak dipakai")
    # Ambang dari sebaran nyata: produk yang punya padanan di katalog semuanya
    # >=0,91, yang tidak punya jatuh di 0,67-0,77. Jurangnya lebar di sekitar 0,80.
    ap.add_argument("--ambang-visual", type=float, default=0.80,
                    help="di bawah ini barang dianggap ASING: tulis hanya dari foto, "
                         "tanpa merek dan harga dari katalog")
    ap.add_argument("--platform", default=None,
                    help="blibli | tokopedia | shopee | all (satu foto, satu listing per platform)")
    ap.add_argument("--hanya-cari", default=None,
                    help="lewati model, cuma tunjukkan hasil pencarian untuk teks ini")
    # sakelar ablasi: mematikan satu perbaikan supaya efeknya bisa diukur sendiri
    ap.add_argument("--tanpa-harga-hitung", action="store_true",
                    help="pakai tebakan harga dari model, jangan dihitung dari katalog")
    ap.add_argument("--tanpa-saring-merek", action="store_true",
                    help="jangan buang kata bermerek yang tak didukung foto/katalog")
    ap.add_argument("--tanpa-contoh-pola", action="store_true",
                    help="jangan beri contoh judul nyata dari platform yang sama")
    ap.add_argument("--mode-cari", default="hibrida",
                    choices=("teks", "gambar", "hibrida"),
                    help="tetangga dicari lewat kata, kemiripan foto, atau keduanya")
    ap.add_argument("--desk-mode", default="kombinasi",
                    choices=("none", "kalimat", "tulis-ulang", "prompt", "kombinasi"),
                    help="cara menangani pelanggaran di deskripsi. Bawaan 'kombinasi': "
                         "larangan di prompt, lalu tulis ulang, lalu buang kalimat "
                         "kalau masih melanggar")
    ap.add_argument("--panjangkan", action="store_true",
                    help="tambah kata kunci dari katalog sampai judul mencapai panjang lazim")
    ap.add_argument("--keluaran", default=None, help="tulis ke berkas ini")
    # Irisan dipakai supaya satu konfigurasi bisa dikerjakan beberapa kali tanpa
    # mengubah sampelnya: seed sama -> urutan sama -> potongan a:b selalu produk
    # yang sama. Perlu karena satu run penuh kena batas waktu proses latar.
    ap.add_argument("--iris", default=None, help="proses sebagian sampel saja, mis. 0:5")
    args = ap.parse_args()

    df = pd.read_parquet(SUMBER)
    df = df[df["n_gambar_lokal"] > 0].reset_index(drop=True)
    df["title_bersih"] = [clean_title(t) for t in df["title"].astype(str)]
    df["description"] = df["description"].astype("object").fillna("").astype(str)
    print(f"katalog: {len(df):,} produk")

    indeks = Indeks(df["title_bersih"].tolist())
    print(f"indeks: {len(indeks.inverted):,} istilah unik")

    if args.hanya_cari:
        for i, s in indeks.cari(args.hanya_cari, args.k):
            r = df.iloc[i]
            print(f"  {s:6.2f}  {r['title_bersih'][:70]}  | {r['kategori_umkm']} | "
                  f"Rp{int(r['price']):,}")
        return

    idx_gambar = None
    if args.mode_cari in ("gambar", "hibrida"):
        if INDEKS_GAMBAR.exists():
            idx_gambar = IndeksGambar()
            print(f"indeks gambar: {len(idx_gambar.pid):,} produk, "
                  f"perangkat {idx_gambar.device}")
        else:
            print(f"peringatan: {INDEKS_GAMBAR} belum ada — "
                  "jalankan scripts/build_image_index.py dulu; pakai pencarian teks")

    profil = muat_profil()
    lex = muat_lexicon()
    print(f"kamus merek: {len(lex.get('merek', ())):,} merek, "
          f"{len(lex.get('jenis', ())):,} kata jenis" if lex else "kamus merek: tidak ada")
    # median harga tiap kategori lintas platform, jadi pembagi faktor platform
    faktor_global = (pd.to_numeric(df["price"], errors="coerce")
                     .groupby(df["kategori_umkm"]).median().to_dict())
    if args.platform == "all":
        platform_list = [p for p in ("blibli", "tokopedia", "shopee") if p in profil]
    elif args.platform:
        platform_list = [args.platform]
    else:
        platform_list = [None]          # satu listing generik, seperti sebelumnya
    if args.platform and not profil:
        print("peringatan: platform_profiles.json belum ada — "
              "jalankan scripts/build_platform_profiles.py dulu")
    print(f"platform: {[p or 'umum' for p in platform_list]}")
    if args.tanpa_saring_merek:
        lex = {}
    idx_platform = ({} if args.tanpa_contoh_pola
                    else indeks_per_platform(df) if any(platform_list) else {})
    keluaran = Path(args.keluaran) if args.keluaran else KELUARAN
    if idx_platform:
        print("indeks contoh pola per platform: "
              + ", ".join(f"{k}={len(v[1]):,}" for k, v in idx_platform.items()))

    sampel = df.sample(args.n, random_state=args.seed)
    mode = "w"
    if args.iris:
        a, b = (int(x) for x in args.iris.split(":"))
        sampel = sampel.iloc[a:b]
        mode = "a" if a > 0 else "w"
        print(f"irisan {a}:{b} -> {len(sampel)} produk")
    keluaran.parent.mkdir(parents=True, exist_ok=True)

    # DUA FASE, bukan satu loop. VRAM 8 GB tidak muat gemma3 4B + qwen 7B
    # sekaligus, jadi loop campur memaksa Ollama menukar model tiap produk dan
    # sebagian besar waktu habis untuk memuat bobot, bukan berpikir.
    t0 = time.time()
    fase1 = []
    for i, (idx, r) in enumerate(sampel.iterrows(), 1):
        mulai = time.time()
        try:
            fakta = panggil(MODEL_VISI, PROMPT_VISI,
                            images=[muat_gambar(Path(r["local_image_paths"][0]))])
            galat = ""
        except Exception as e:
            fakta, galat = "", f"{type(e).__name__}: {e}"[:150]
        cocok = [(j, s) for j, s in indeks.cari(fakta, args.k + 1) if j != idx][:args.k]
        skor_teratas = cocok[0][1] if cocok else 0.0
        skor_visual = None

        if idx_gambar is not None:
            # Skor CLIP (0-1) tidak sebanding dengan skor TF-IDF (tak terbatas),
            # jadi keduanya tidak dijumlahkan. Untuk 'gambar' tetangga diganti;
            # untuk 'hibrida' hasil foto ditaruh di depan lalu sisanya dari teks.
            visual = idx_gambar.cari(Path(r["local_image_paths"][0]), args.k + 1)
            peta = {str(v): n for n, v in enumerate(df["product_id"])}
            baris_visual = [(peta[pid], sk) for pid, sk in visual
                            if pid in peta and peta[pid] != idx][:args.k]
            if baris_visual:
                skor_visual = baris_visual[0][1]
                if args.mode_cari == "gambar":
                    cocok = baris_visual
                else:
                    ada = {j for j, _ in baris_visual}
                    cocok = (baris_visual + [(j, sk) for j, sk in cocok
                                             if j not in ada])[:args.k]
        # Barang asing: kalau tidak ada padanan visual yang meyakinkan, konteks
        # katalog justru berbahaya — dari situ lahir "Tas Longchamp" dan
        # "teknologi altraze", merek yang dipinjam dari produk yang kebetulan
        # mirip rupanya. Lebih baik menulis apa adanya dari foto.
        if skor_visual is not None:
            pakai = skor_visual >= args.ambang_visual
        else:
            pakai = skor_teratas >= args.min_skor
        tetangga = df.iloc[[j for j, _ in cocok]] if pakai else df.iloc[[]]
        kat_modus = None
        if pakai and len(tetangga):
            mm = tetangga["kategori_umkm"].mode()
            kat_modus = str(mm.iloc[0]) if len(mm) else None
        fase1.append(dict(r=r, fakta=fakta, tetangga=tetangga, pakai=pakai,
                          skor=skor_teratas, skor_visual=skor_visual,
                          kat=kat_modus, galat=galat,
                          detik=time.time() - mulai))
        print(f"[lihat {i}/{len(sampel)}] {time.time() - mulai:.1f}s  {fakta[:48]}")
    print(f"fase 1 selesai: {time.time() - t0:.0f}s\n")

    hasil = []
    with keluaran.open(mode, encoding="utf-8") as f:
        for i, s in enumerate(fase1, 1):
            mulai = time.time()
            r, fakta, tetangga, pakai = s["r"], s["fakta"], s["tetangga"], s["pakai"]
            keluar, galat = {}, s["galat"]
            for plat in platform_list:
                try:
                    mentah = panggil(
                        MODEL_TEKS,
                        susun_prompt(fakta, tetangga if pakai else None, profil, plat,
                                     idx_platform, larangan=args.desk_mode in ("prompt", "kombinasi")),
                        num_predict=400, minta_json=True)
                    h = json.loads(mentah)
                except json.JSONDecodeError:
                    h = {"_mentah": mentah[:300]}
                except Exception as e:
                    h, galat = {}, f"{type(e).__name__}: {e}"[:150]
                if isinstance(h, dict) and h and "_mentah" not in h:
                    h["harga_model"] = h.get("perkiraan_harga")
                    if not pakai:
                        # barang asing: tidak ada pembanding, jadi tidak ada dasar
                        # untuk menyebut harga sama sekali
                        h["perkiraan_harga"] = 0
                        h["catatan"] = ("produk belum ada padanannya di katalog; "
                                        "judul & deskripsi murni dari foto, "
                                        "harga perlu ditentukan penjual")
                    hitung = (None if args.tanpa_harga_hitung else
                              harga_deterministik(tetangga if pakai else None, profil,
                                                  plat, s["kat"], faktor_global))
                    if hitung:
                        h["perkiraan_harga"] = hitung
                    if lex and h.get("judul"):
                        bersih, dibuang = saring_merek(
                            str(h["judul"]), fakta, tetangga if pakai else None, lex)
                        if dibuang:
                            h["judul_mentah"] = h["judul"]
                            h["dibuang"] = dibuang
                            h["judul"] = bersih
                    if args.desk_mode != "none" and h.get("deskripsi"):
                        tet = tetangga if pakai else None
                        desk = str(h["deskripsi"])
                        salah = pelanggaran_deskripsi(desk, fakta, tet, lex)
                        if salah and args.desk_mode != "prompt":
                            h["deskripsi_mentah"] = desk
                            h["desk_salah"] = salah
                            if args.desk_mode == "kalimat":
                                h["deskripsi"] = saring_kalimat(desk, fakta, tet, lex)
                            else:
                                baru = tulis_ulang_deskripsi(desk, salah, fakta)
                                # Kombinasi: tulis ulang dulu supaya isinya utuh, lalu
                                # periksa lagi. Model kecil kadang mengulang pelanggaran
                                # yang sama; kalau begitu kalimatnya baru dibuang, jadi
                                # jaminannya tetap mutlak seperti cara (a).
                                if args.desk_mode == "kombinasi":
                                    sisa = pelanggaran_deskripsi(baru, fakta, tet, lex)
                                    if sisa:
                                        h["desk_sisa"] = sisa
                                        baru = (saring_kalimat(baru, fakta, tet, lex)
                                                or saring_kalimat(desk, fakta, tet, lex))
                                h["deskripsi"] = baru
                    if args.panjangkan and h.get("judul"):
                        panjang, tambah = panjangkan_judul(
                            str(h["judul"]), tetangga if pakai else None,
                            profil, plat, lex)
                        if tambah:
                            h.setdefault("judul_mentah", h["judul"])
                            h["ditambah"] = tambah
                            h["judul"] = panjang
                keluar[plat or "umum"] = h

            rec = {
                "product_id": r["product_id"], "source": r["source"],
                "judul_asli": r["title_bersih"], "harga_asli": int(r["price"]),
                "kategori_asli": r["kategori_umkm"], "vlm": fakta,
                "skor_teratas": round(float(s["skor"]), 2), "pakai_konteks": bool(pakai),
                "skor_visual": (round(float(s["skor_visual"]), 3)
                                if s["skor_visual"] is not None else None),
                "dikenal": bool(pakai),
                "tetangga": tetangga["title_bersih"].tolist() if len(tetangga) else [],
                "platform": platform_list, "hasil": keluar,
                "detik": round(s["detik"] + time.time() - mulai, 1), "galat": galat,
            }
            hasil.append(rec)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[tulis {i}/{len(fase1)}] {rec['detik']}s  {r['title_bersih'][:42]}")

    h = pd.DataFrame(hasil)
    print(f"\n{len(h)} produk, {h['detik'].mean():.1f} detik/produk, "
          f"total {time.time() - t0:.0f}s, {int((h['galat'] != '').sum())} galat")
    print(f"-> {keluaran}")


if __name__ == "__main__":
    main()
