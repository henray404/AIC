"""Antarmuka web untuk mencoba tiap sistem satu per satu.

    .venv/Scripts/python scripts/gui_coba.py
    -> buka http://localhost:8080 di browser

Empat sistem bisa dipilih, dan semuanya memakai kode yang sama persis dengan
yang diukur di sesi 1 dan 2 — `retrieve_pipeline.py` diimpor, bukan disalin,
supaya yang kamu lihat di layar memang yang menghasilkan angka di tabel.

Dua cara memberi masukan:

- unggah foto sendiri. Tidak ada kebenaran pembanding, tapi paling mirip
  pemakaian nyata penjual.
- ambil produk acak dari katalog. Judul dan harga aslinya ikut ditampilkan,
  jadi kamu bisa menilai hasilnya benar atau tidak. Tingkat eksklusi baru
  berarti di sini: produk katalog memang bisa dibuang dari indeks.

Sengaja memakai http.server bawaan, bukan Flask atau Gradio: `.venv` punya
torch dan open_clip tapi tidak punya keduanya, dan menambah dependensi demi
satu halaman uji tidak sepadan.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import tempfile
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

import retrieve_pipeline as rp

PROJECT = Path(__file__).resolve().parent.parent
ADAPTER_TEKS = PROJECT / "model_sulingan" / "murid_teks_0.5b"
ADAPTER_VLM = PROJECT / "model_sulingan" / "murid_vlm_3b"
DASAR_TEKS = "Qwen/Qwen2.5-0.5B-Instruct"
DASAR_VLM = "Qwen/Qwen2.5-VL-3B-Instruct"

_P: dict = {}          # bahan pipeline, dimuat malas
_MURID: dict = {}      # model sulingan, dimuat malas


# --------------------------------------------------------------- ketersediaan

def model_ollama() -> set[str]:
    import urllib.request
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
            nama = set()
            for m in json.load(r).get("models", []):
                bagian = m.get("name", "").split(":")
                if len(bagian) >= 2:
                    nama.add(f"{bagian[0]}:{bagian[1]}")
            return nama
    except Exception:
        return set()


def punya(modul: str) -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec(modul) is not None
    except (ImportError, ValueError):
        return False


def ketersediaan() -> list[dict]:
    """Status tiap sistem, plus perintah persis untuk melengkapi yang kurang."""
    ada = model_ollama()
    hf = punya("transformers") and punya("peft")
    return [
        {"id": "pipeline", "nama": "Pipeline RAG",
         "sub": "gemma3:4b + qwen2.5:7b + CLIP + indeks 28.443 produk",
         "siap": {"gemma3:4b", "qwen2.5:7b"} <= ada,
         "kurang": "ollama pull gemma3:4b && ollama pull qwen2.5:7b"},
        {"id": "baseline", "nama": "Baseline 12B",
         "sub": "gemma3:12b sendirian, tanpa katalog, tanpa penjaga",
         "siap": "gemma3:12b" in ada,
         "kurang": "ollama pull gemma3:12b   (~9 GB, sesak di VRAM 8 GB)"},
        {"id": "murid_vlm", "nama": "Murid VLM 3B",
         "sub": "Qwen2.5-VL-3B sulingan, satu model, tanpa katalog",
         "siap": hf and ADAPTER_VLM.exists(),
         "kurang": "pip install transformers peft   (+ unduh ~7 GB saat pertama)"},
        {"id": "murid_teks", "nama": "Murid teks 0,5B",
         "sub": "Qwen2.5-0.5B sulingan, masukan fakta ketikan, tanpa foto",
         "siap": hf and ADAPTER_TEKS.exists(),
         "kurang": "pip install transformers peft   (+ unduh ~1 GB saat pertama)"},
    ]


# ------------------------------------------------------------------- pipeline

def muat_pipeline() -> dict:
    if _P:
        return _P
    t0 = time.time()
    print("memuat katalog ...", flush=True)
    df = pd.read_parquet(rp.SUMBER)
    df = df[df["n_gambar_lokal"] > 0].reset_index(drop=True)
    df["title_bersih"] = [rp.clean_title(t) for t in df["title"].astype(str)]
    df["description"] = df["description"].astype("object").fillna("").astype(str)
    df["lini"] = df["title_bersih"].map(lambda t: t.split()[0].lower() if t else "")
    print(f"  {len(df):,} produk", flush=True)

    print("membangun indeks teks ...", flush=True)
    indeks = rp.Indeks(df["title_bersih"].tolist())

    idx_gambar = None
    try:
        print("memuat indeks gambar (CLIP) ...", flush=True)
        idx_gambar = rp.IndeksGambar()
    except Exception as e:
        print(f"  indeks gambar dilewati: {type(e).__name__}: {e}", flush=True)

    _P.update(
        df=df, indeks=indeks, idx_gambar=idx_gambar,
        profil=rp.muat_profil(), lex=rp.muat_lexicon(),
        idx_platform=rp.indeks_per_platform(df),
        faktor=(pd.to_numeric(df["price"], errors="coerce")
                .groupby(df["kategori_umkm"]).median().to_dict()),
        peta_pid={str(v): n for n, v in enumerate(df["product_id"])},
    )
    print(f"siap dalam {time.time() - t0:.0f} detik\n", flush=True)
    return _P


def jalankan_pipeline(foto: Path, platform: str, eksklusi: str,
                      ambang: float, pid: str | None,
                      keterangan: str = "", modal: int = 0) -> dict:
    """Satu produk lewat pipeline penuh. Cerminan dari main() retrieve_pipeline.

    `keterangan` adalah hal yang diketahui penjual tapi tidak terlihat di foto:
    isi bersih, bahan, kemasan. Ia disambung ke string `fakta` hasil bacaan
    foto, dan karena `fakta` dipakai tiga kali -- mencari tetangga, menulis, dan
    sebagai bukti bagi penjaga -- satu sambungan itu cukup.

    Efeknya paling terasa di penjaga. Tanpa keterangan, "1 Liter" yang ditulis
    model dibuang karena angkanya tidak terbaca di foto, dan itu benar. Dengan
    keterangan "1 liter", angkanya jadi berdasar dan dibiarkan. Penjaga memang
    menolak yang DIKARANG, bukan yang diketahui penjual.

    `modal` harga produksi. Tidak masuk ke listing sama sekali -- ia rahasia
    penjual, bukan bahan tulisan. Dipakai hanya untuk menghitung margin
    terhadap saran harga.
    """
    P = muat_pipeline()
    df, k = P["df"], 5
    mulai = time.time()

    # Blokir hanya berarti untuk produk yang memang ada di katalog. Foto
    # unggahan bukan bagian katalog, jadi tidak ada yang perlu dibuang.
    blokir_baris, blokir_pid = set(), set()
    if pid:
        cocok_pid = df[df["product_id"].astype(str) == str(pid)]
        if len(cocok_pid):
            r = cocok_pid.iloc[0]
            if eksklusi == "kategori":
                idxs = df.index[df["kategori_umkm"] == r["kategori_umkm"]]
            elif eksklusi == "lini":
                idxs = df.index[(df["lini"] == r["lini"])
                                | (df["product_id"] == r["product_id"])]
            else:
                idxs = df.index[df["product_id"] == r["product_id"]]
            blokir_baris = {int(x) for x in idxs}
            blokir_pid = set(df.loc[list(blokir_baris), "product_id"].astype(str))

    fakta_foto = rp.panggil(rp.MODEL_VISI, rp.PROMPT_VISI,
                            images=[rp.muat_gambar(foto)])
    t_lihat = time.time() - mulai
    keterangan = (keterangan or "").strip()
    fakta = f"{fakta_foto} | {keterangan}" if keterangan else fakta_foto

    cocok = P["indeks"].cari(fakta, k, blokir=blokir_baris)
    skor_teks = cocok[0][1] if cocok else 0.0
    skor_visual = None
    if P["idx_gambar"] is not None:
        visual = P["idx_gambar"].cari(foto, k, blokir=blokir_pid)
        baris_visual = [(P["peta_pid"][p], s) for p, s in visual
                        if p in P["peta_pid"] and s > 0][:k]
        if baris_visual:
            skor_visual = baris_visual[0][1]
            sudah = {j for j, _ in baris_visual}
            cocok = (baris_visual + [(j, s) for j, s in cocok if j not in sudah])[:k]

    pakai = (skor_visual >= ambang) if skor_visual is not None else (skor_teks >= 2.0)
    tetangga = df.iloc[[j for j, _ in cocok]] if pakai else df.iloc[[]]
    kat = None
    if pakai and len(tetangga):
        mm = tetangga["kategori_umkm"].mode()
        kat = str(mm.iloc[0]) if len(mm) else None

    plat = None if platform == "umum" else platform
    mentah = rp.panggil(rp.MODEL_TEKS, rp.susun_prompt(
        fakta, tetangga if pakai else None, P["profil"], plat,
        P["idx_platform"], larangan=True), num_predict=400, minta_json=True)
    try:
        h = json.loads(mentah)
    except json.JSONDecodeError:
        h = {"_mentah": mentah[:300]}

    # Tiap langkah penjaga dicatat, supaya yang dilakukan pipeline di luar model
    # terlihat di layar dan bukan cuma tersirat di hasil akhirnya.
    jejak = []
    if isinstance(h, dict) and "_mentah" not in h:
        h["kategori_model"] = h.get("kategori")
        h["kategori"] = rp.sahkan_kategori(h.get("kategori"), kat)
        if h["kategori"] != h["kategori_model"]:
            jejak.append(f"kategori ditambatkan: {h['kategori_model']!r} "
                         f"-> {h['kategori']}")
        h["harga_model"] = h.get("perkiraan_harga")
        if not pakai:
            h["perkiraan_harga"] = 0
            h["catatan"] = ("produk belum ada padanannya di katalog; judul & "
                            "deskripsi murni dari foto, harga perlu ditentukan penjual")
        hitung = rp.harga_deterministik(tetangga if pakai else None, P["profil"],
                                        plat, kat, P["faktor"])
        if hitung:
            h["perkiraan_harga"] = hitung
            jejak.append(f"harga dihitung dari tetangga: Rp {hitung:,}")
        if P["lex"] and h.get("judul"):
            bersih, dibuang = rp.saring_merek(str(h["judul"]), fakta,
                                              tetangga if pakai else None, P["lex"])
            if dibuang:
                h["judul_mentah"], h["judul"] = h["judul"], bersih
                h["dibuang"] = dibuang
                jejak.append("penjaga membuang dari judul: " + ", ".join(dibuang))
        if h.get("deskripsi"):
            tet = tetangga if pakai else None
            salah = rp.pelanggaran_deskripsi(str(h["deskripsi"]), fakta, tet, P["lex"])
            if salah:
                asli_desk = str(h["deskripsi"])
                baru = rp.tulis_ulang_deskripsi(asli_desk, salah, fakta)
                if rp.pelanggaran_deskripsi(baru, fakta, tet, P["lex"]):
                    baru = (rp.saring_kalimat(baru, fakta, tet, P["lex"])
                            or rp.saring_kalimat(asli_desk, fakta, tet, P["lex"]))
                h["deskripsi"] = baru
                jejak.append("deskripsi diperbaiki, pelanggaran: " + ", ".join(salah))
        if h.get("judul"):
            panjang, tambah = rp.panjangkan_judul(
                str(h["judul"]), tetangga if pakai else None,
                P["profil"], plat, P["lex"],
                tolak=set(h.get("dibuang") or ()))
            if tambah:
                h["judul"] = panjang
                jejak.append("judul dipanjangkan dengan: " + ", ".join(tambah))

    # Margin dihitung, tidak dimasukkan ke listing. Harga produksi itu rahasia
    # penjual; yang perlu ia lihat cuma apakah saran harganya menutup modal.
    untung = None
    harga_saran = 0
    try:
        harga_saran = int(float(h.get("perkiraan_harga") or 0))
    except (TypeError, ValueError):
        harga_saran = 0
    if modal > 0 and harga_saran > 0:
        untung = {"modal": modal, "saran": harga_saran,
                  "selisih": harga_saran - modal,
                  "persen": round(100 * (harga_saran - modal) / modal, 1)}

    return {
        "hasil": h, "vlm": fakta, "vlm_foto": fakta_foto,
        "keterangan": keterangan, "untung": untung,
        "dikenal": bool(pakai),
        "skor_visual": round(skor_visual, 3) if skor_visual is not None else None,
        "skor_teks": round(float(skor_teks), 2),
        "tetangga": tetangga["title_bersih"].tolist() if len(tetangga) else [],
        "jejak": jejak, "detik": round(time.time() - mulai, 1),
        "detik_lihat": round(t_lihat, 1),
    }


# ------------------------------------------------------------------- baseline

def jalankan_baseline(foto: Path, platform: str) -> dict:
    mulai = time.time()
    prompt = ("Kamu penulis listing marketplace Indonesia. Lihat foto produk ini.\n\n"
              f"Tulis listing untuk platform {platform}. Aturan:\n"
              "- Judul maksimal 12 kata, sebut jenis barang lebih dulu.\n"
              "- Deskripsi 2-3 kalimat, menarik tapi hanya menyebut hal yang terlihat.\n"
              "- Jangan mengarang ukuran, berat, garansi, izin BPOM, atau klaim khasiat.\n"
              "- Kalau merek tidak terbaca di foto, jangan sebut merek apa pun.\n\n"
              'Jawab JSON: {"judul": "...", "deskripsi": "...", '
              '"kategori": "...", "perkiraan_harga": 0}')
    mentah = rp.panggil("gemma3:12b", prompt, images=[rp.muat_gambar(foto)],
                        num_predict=400, minta_json=True)
    try:
        h = json.loads(mentah)
    except json.JSONDecodeError:
        h = {"_mentah": mentah[:300]}
    return {"hasil": h, "vlm": "", "dikenal": None, "skor_visual": None,
            "skor_teks": 0.0, "tetangga": [],
            "jejak": ["tanpa katalog, tanpa penjaga — apa adanya dari model"],
            "detik": round(time.time() - mulai, 1), "detik_lihat": None}


# ---------------------------------------------------------------------- murid

def muat_murid(jenis: str):
    if jenis in _MURID:
        return _MURID[jenis]
    import torch
    from peft import PeftModel
    perangkat = "cuda" if torch.cuda.is_available() else "cpu"
    if jenis == "murid_teks":
        from transformers import AutoModelForCausalLM, AutoTokenizer
        print(f"memuat {DASAR_TEKS} ...", flush=True)
        tok = AutoTokenizer.from_pretrained(DASAR_TEKS)
        m = AutoModelForCausalLM.from_pretrained(
            DASAR_TEKS, torch_dtype=torch.bfloat16, device_map=perangkat)
        _MURID[jenis] = (tok, PeftModel.from_pretrained(m, str(ADAPTER_TEKS)).eval())
    else:
        from transformers import AutoModelForImageTextToText, AutoProcessor
        print(f"memuat {DASAR_VLM} ...", flush=True)
        pro = AutoProcessor.from_pretrained(DASAR_VLM)
        m = AutoModelForImageTextToText.from_pretrained(
            DASAR_VLM, torch_dtype=torch.bfloat16, device_map=perangkat)
        _MURID[jenis] = (pro, PeftModel.from_pretrained(m, str(ADAPTER_VLM)).eval())
    print("  siap\n", flush=True)
    return _MURID[jenis]


def jalankan_murid_teks(fakta_teks: str, platform: str) -> dict:
    import torch
    tok, m = muat_murid("murid_teks")
    mulai = time.time()
    sistem = ("Kamu penulis listing marketplace Indonesia. Dari fakta produk, "
              "tulis judul dan deskripsi. Jangan sebut apa pun yang tidak ada di "
              "fakta — tidak ada ukuran, berat, garansi, izin, atau klaim khasiat "
              "yang dikarang.")
    pesan = [{"role": "system", "content": sistem},
             {"role": "user", "content": f"platform: {platform} | {fakta_teks}"}]
    teks = tok.apply_chat_template(pesan, tokenize=False, add_generation_prompt=True)
    ids = tok(teks, return_tensors="pt").to(m.device)
    with torch.no_grad():
        keluar = m.generate(**ids, max_new_tokens=220, do_sample=False,
                            pad_token_id=tok.pad_token_id or tok.eos_token_id)
    jawab = tok.decode(keluar[0][ids.input_ids.shape[1]:], skip_special_tokens=True)
    try:
        h = json.loads(jawab)
    except json.JSONDecodeError:
        h = {"_mentah": jawab[:300]}
    return {"hasil": h, "vlm": "", "dikenal": None, "skor_visual": None,
            "skor_teks": 0.0, "tetangga": [],
            "jejak": ["tanpa foto, tanpa katalog, tanpa penjaga"],
            "detik": round(time.time() - mulai, 1), "detik_lihat": None}


def jalankan_murid_vlm(foto: Path, platform: str) -> dict:
    import torch
    from PIL import Image
    pro, m = muat_murid("murid_vlm")
    mulai = time.time()
    perintah = (f"Lihat foto produk ini. Tulis listing untuk platform {platform}. "
                "Jawab JSON dengan kunci judul dan deskripsi. Jangan sebut ukuran, "
                "berat, garansi, izin, merek, atau khasiat yang tidak terlihat.")
    pesan = [{"role": "user", "content": [{"type": "image"},
                                          {"type": "text", "text": perintah}]}]
    with Image.open(foto) as im:
        gambar = im.convert("RGB")
        gambar.thumbnail((512, 512))
        teks = pro.apply_chat_template(pesan, tokenize=False,
                                       add_generation_prompt=True)
        enc = pro(text=[teks], images=[gambar], return_tensors="pt").to(m.device)
    with torch.no_grad():
        keluar = m.generate(**enc, max_new_tokens=220, do_sample=False)
    jawab = pro.tokenizer.decode(keluar[0][enc["input_ids"].shape[1]:],
                                 skip_special_tokens=True)
    try:
        h = json.loads(jawab)
    except json.JSONDecodeError:
        h = {"_mentah": jawab[:300]}
    return {"hasil": h, "vlm": "", "dikenal": None, "skor_visual": None,
            "skor_teks": 0.0, "tetangga": [],
            "jejak": ["satu model, tanpa katalog, tanpa penjaga"],
            "detik": round(time.time() - mulai, 1), "detik_lihat": None}


# ------------------------------------------------------------------------ HTTP

def produk_acak() -> dict:
    P = muat_pipeline()
    r = P["df"].sample(1).iloc[0]
    foto = Path(r["local_image_paths"][0])
    b64 = base64.b64encode(foto.read_bytes()).decode()
    jenis = "jpeg" if foto.suffix.lower() in (".jpg", ".jpeg") else "png"
    return {"product_id": str(r["product_id"]), "judul_asli": str(r["title"]),
            "harga_asli": int(r["price"] or 0), "sumber": str(r["source"]),
            "kategori": str(r["kategori_umkm"]),
            "gambar": f"data:image/{jenis};base64,{b64}"}


def fakta_dari_produk(pid: str) -> str:
    """Susun masukan murid teks dari produk katalog, seperti build_text_pairs."""
    P = muat_pipeline()
    baris = P["df"][P["df"]["product_id"].astype(str) == str(pid)]
    if not len(baris):
        return ""
    r = baris.iloc[0]
    kata = re.sub(r"[^\w\s.\-/&+,']", " ", str(r["title_bersih"])).split()
    jenis = next((w for w in kata if len(w) > 2 and not w[0].isdigit()), "")
    bagian = [f"jenis: {jenis}"] if jenis else []
    if r["kategori_umkm"] and r["kategori_umkm"] != "lainnya":
        bagian.append(f"kategori: {r['kategori_umkm']}")
    if r["price"]:
        bagian.append(f"harga: {int(r['price'])}")
    return " | ".join(bagian)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _kirim(self, kode, tipe, isi: bytes):
        self.send_response(kode)
        self.send_header("Content-Type", tipe)
        self.send_header("Content-Length", str(len(isi)))
        self.end_headers()
        self.wfile.write(isi)

    def _json(self, obj, kode=200):
        self._kirim(kode, "application/json; charset=utf-8",
                    json.dumps(obj, ensure_ascii=False).encode())

    def do_GET(self):
        if self.path == "/":
            self._kirim(200, "text/html; charset=utf-8", HALAMAN.encode())
        elif self.path == "/api/sistem":
            self._json(ketersediaan())
        elif self.path == "/api/acak":
            try:
                self._json(produk_acak())
            except Exception as e:
                traceback.print_exc()
                self._json({"galat": f"{type(e).__name__}: {e}"}, 500)
        else:
            self._kirim(404, "text/plain", b"404")

    def do_POST(self):
        if self.path != "/api/jalan":
            return self._kirim(404, "text/plain", b"404")
        tmp = None
        try:
            # Pembacaan badan permintaan ikut di dalam try: badan yang bukan JSON
            # sah dulu melempar di luar penanganan galat, dan koneksinya mati
            # tanpa tanggapan apa pun -- di browser terlihat seperti server hang.
            n = int(self.headers.get("Content-Length", 0))
            try:
                req = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError as e:
                return self._json({"galat": f"badan permintaan bukan JSON: {e}"}, 400)

            sistem = req.get("sistem", "pipeline")
            platform = req.get("platform", "tokopedia")
            pid = req.get("product_id") or None

            if sistem == "murid_teks":
                fakta = (req.get("fakta") or "").strip()
                if not fakta and pid:
                    fakta = fakta_dari_produk(pid)
                if not fakta:
                    return self._json({"galat": "murid teks butuh fakta ketikan "
                                                "atau produk katalog"}, 400)
                return self._json(jalankan_murid_teks(fakta, platform))

            gambar = req.get("gambar") or ""
            if not gambar.startswith("data:"):
                return self._json({"galat": "belum ada foto"}, 400)
            # mkstemp mengembalikan fd yang TERBUKA. Di Windows berkasnya tetap
            # terkunci selama fd itu hidup, jadi unlink di blok finally melempar
            # PermissionError alih-alih diabaikan — tiap permintaan meninggalkan
            # sampah dan menggagalkan tanggapannya.
            fd, nama = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            tmp = Path(nama)
            tmp.write_bytes(base64.b64decode(gambar.split(",", 1)[1]))

            if sistem == "pipeline":
                try:
                    modal = int(float(req.get("modal") or 0))
                except (TypeError, ValueError):
                    modal = 0
                hasil = jalankan_pipeline(tmp, platform,
                                          req.get("eksklusi", "lini"),
                                          float(req.get("ambang", 0.75)), pid,
                                          keterangan=req.get("keterangan", ""),
                                          modal=modal)
            elif sistem == "baseline":
                hasil = jalankan_baseline(tmp, platform)
            elif sistem == "murid_vlm":
                hasil = jalankan_murid_vlm(tmp, platform)
            else:
                return self._json({"galat": f"sistem tak dikenal: {sistem}"}, 400)
            self._json(hasil)
        except Exception as e:
            traceback.print_exc()
            self._json({"galat": f"{type(e).__name__}: {e}"}, 500)
        finally:
            if tmp:
                tmp.unlink(missing_ok=True)


HALAMAN = r"""<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Coba Model Listing</title>
<style>
:root{--bg:#f4f6f5;--kartu:#fff;--tinta:#131d1c;--redup:#56635f;--garis:#d8e0dd;
      --aksen:#0c6460;--aksen-bg:#dcecea;--baik:#2c6b4a;--buruk:#9c3f24}
@media(prefers-color-scheme:dark){:root{--bg:#0c1211;--kartu:#141c1b;--tinta:#e4ebe9;
      --redup:#97a5a1;--garis:#24302e;--aksen:#56c2b6;--aksen-bg:#14312f;
      --baik:#62be88;--buruk:#e08661}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tinta);font:16px/1.55 system-ui,sans-serif}
.bung{max-width:1120px;margin:0 auto;padding:28px 20px 80px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.02em}
.sub{color:var(--redup);margin:0 0 26px;font-size:15px}
.kisi{display:grid;grid-template-columns:1fr 1fr;gap:22px;align-items:start}
@media(max-width:860px){.kisi{grid-template-columns:1fr}}
.kartu{background:var(--kartu);border:1px solid var(--garis);border-radius:8px;padding:18px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--redup);
   margin:0 0 14px;font-weight:600}
label{display:block;font-size:13px;color:var(--redup);margin:14px 0 5px}
select,textarea,input[type=range],input[type=number]{width:100%;font:inherit;font-size:14px}
select,textarea,input[type=number]{padding:9px 11px;border:1px solid var(--garis);border-radius:5px;
   background:var(--bg);color:var(--tinta)}
textarea{resize:vertical;min-height:60px}
button{background:var(--aksen);color:var(--bg);border:0;border-radius:5px;
   padding:11px 18px;font:inherit;font-weight:600;cursor:pointer}
button:disabled{opacity:.45;cursor:not-allowed}
button.tipis{background:transparent;color:var(--aksen);border:1px solid var(--garis);
   font-weight:500;padding:8px 14px;font-size:14px}
.sistem{display:flex;flex-direction:column;gap:8px}
.opsi{display:flex;gap:11px;padding:11px 13px;border:1px solid var(--garis);
   border-radius:6px;cursor:pointer}
.opsi.pilih{border-color:var(--aksen);background:var(--aksen-bg)}
.opsi.mati{opacity:.5;cursor:not-allowed}
.opsi b{font-size:14.5px;display:block}
.opsi span{font-size:12.5px;color:var(--redup)}
.opsi code{font-size:11.5px;color:var(--buruk);word-break:break-all}
img.pratayang{width:100%;max-height:260px;object-fit:contain;border-radius:6px;
   background:var(--bg);margin-top:12px}
.baris{display:flex;gap:9px;flex-wrap:wrap;margin-top:12px}
.hasil{word-break:break-word}
.judul-out{font-size:18px;font-weight:600;margin:0 0 8px;line-height:1.3}
.harga{font-size:15px;color:var(--aksen);font-weight:600;margin:0 0 10px}
.tag{display:inline-block;font-size:11.5px;padding:2px 8px;border-radius:99px;
   background:var(--aksen-bg);color:var(--aksen);font-weight:600}
.tag.no{background:transparent;border:1px solid var(--garis);color:var(--redup)}
.jejak{margin:14px 0 0;padding:0;list-style:none;font-size:13px;color:var(--redup)}
.jejak li{padding:5px 0;border-top:1px solid var(--garis)}
.meta{font-size:12.5px;color:var(--redup);margin-top:12px;
   font-family:ui-monospace,monospace}
.galat{color:var(--buruk);font-size:14px}
.emas{border-left:3px solid var(--baik);padding-left:12px;margin-top:14px;font-size:13.5px}
.emas b{color:var(--baik)}
.emas.abu{border-left-color:var(--garis)}
.emas.abu b{color:var(--redup)}
</style></head><body><div class="bung">
<h1>Coba Model Listing</h1>
<p class="sub">Empat sistem, kode yang sama dengan yang diukur di tabel hasil.</p>
<div class="kisi">
  <div>
    <div class="kartu">
      <h2>Pilih sistem</h2>
      <div class="sistem" id="sistem">memuat…</div>
    </div>
    <div class="kartu" style="margin-top:18px">
      <h2>Masukan</h2>
      <div class="baris">
        <button class="tipis" id="acak">Ambil produk katalog</button>
        <button class="tipis" id="pilihFoto">Unggah foto sendiri</button>
        <input type="file" id="berkas" accept="image/*" hidden>
      </div>
      <div id="emas"></div>
      <img id="pratayang" class="pratayang" hidden alt="pratayang produk">
      <div id="opsiTeks" hidden>
        <label for="fakta">Keterangan produk — murid teks tidak melihat foto,
          inilah satu-satunya masukannya, dan bentuk inilah yang dipakai melatihnya</label>
        <textarea id="fakta" placeholder="jenis: Sepatu | merek: Keeping | kategori: fashion_perawatan | harga: 177550"></textarea>
        <p class="meta" style="margin-top:6px">Kosongkan kalau memakai produk katalog —
          keterangannya disusun otomatis dari judul aslinya.</p>
      </div>
      <label for="platform">Platform tujuan</label>
      <select id="platform">
        <option value="tokopedia">tokopedia</option>
        <option value="blibli">blibli</option>
        <option value="shopee">shopee</option>
        <option value="umum">umum — tanpa gaya platform</option>
      </select>
      <div id="opsiPipeline">
        <label for="keterangan">Keterangan dari penjual — hal yang tidak terlihat di foto
          <span style="color:var(--aksen)">(opsional)</span></label>
        <textarea id="keterangan" placeholder="1 liter, kemasan pouch, isi 12 sachet"></textarea>
        <p class="meta" style="margin-top:6px">Ini jadi bukti sah untuk penjaga.
          Tanpa keterangan, ukuran yang ditulis model dibuang karena tidak terbaca
          di foto.</p>
        <label for="modal">Harga produksi <span style="color:var(--aksen)">(opsional)</span></label>
        <input type="number" id="modal" placeholder="45000" min="0" step="500">
        <p class="meta" style="margin-top:6px">Tidak masuk ke listing — dipakai
          hanya untuk menghitung margin terhadap saran harga.</p>
        <label for="eksklusi">Eksklusi indeks — hanya berlaku untuk produk katalog</label>
        <select id="eksklusi">
          <option value="diri">diri — buang produk itu sendiri</option>
          <option value="lini" selected>lini — buang seluruh lini produknya</option>
          <option value="kategori">kategori — buang sekategori</option>
        </select>
        <label for="ambang">Ambang barang asing: <span id="ambangNilai">0,75</span></label>
        <input type="range" id="ambang" min="0.60" max="0.95" step="0.05" value="0.75">
      </div>
      <div id="alasan"></div>
      <div class="baris"><button id="jalan" disabled>Jalankan</button></div>
    </div>
  </div>
  <div class="kartu"><h2>Hasil</h2><div id="keluar" class="hasil">
    <span style="color:var(--redup)">Pilih sistem dan masukan, lalu Jalankan.</span>
  </div></div>
</div></div>
<script>
const ST={sistem:"pipeline",gambar:null,pid:null};
const SIAP={},KURANG={};
const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[<>&]/g,c=>({"<":"&lt;",">":"&gt;","&":"&amp;"}[c]));

fetch("/api/sistem").then(r=>r.json()).then(list=>{
  $("#sistem").innerHTML=list.map(s=>`
    <div class="opsi ${s.siap?"":"mati"} ${s.id==="pipeline"?"pilih":""}" data-id="${s.id}">
      <div><b>${esc(s.nama)}</b><span>${esc(s.sub)}</span>
      ${s.siap?"":`<code>belum siap — ${esc(s.kurang)}</code>`}</div></div>`).join("");
  list.forEach(s=>{SIAP[s.id]=s.siap;KURANG[s.id]=s.kurang;});
  // Kartu yang perkakasnya belum ada tetap bisa dipilih. Versi pertama menolak
  // kliknya, dan akibatnya kotak "Fakta produk" -- satu-satunya masukan murid
  // teks, dan bentuk yang dipakai melatihnya -- tak pernah bisa dilihat sama
  // sekali di mesin yang belum memasang transformers.
  document.querySelectorAll(".opsi").forEach(el=>el.onclick=()=>{
    document.querySelectorAll(".opsi").forEach(o=>o.classList.remove("pilih"));
    el.classList.add("pilih");ST.sistem=el.dataset.id;sesuaikan();
  });
  sesuaikan();
});

function sesuaikan(){
  const teks=ST.sistem==="murid_teks";
  $("#opsiTeks").hidden=!teks;
  $("#opsiPipeline").hidden=ST.sistem!=="pipeline";
  const b=$("#jalan"),siap=SIAP[ST.sistem]!==false;
  b.disabled=!siap||!(teks||ST.gambar);
  b.textContent=siap?"Jalankan":"Belum terpasang";
  $("#alasan").innerHTML=siap?"":
    `<p class="galat" style="margin:12px 0 0">Belum bisa dijalankan di mesin ini.
     Pasang dulu:<br><code style="color:var(--tinta)">${esc(KURANG[ST.sistem]||"")}</code>
     <br>lalu muat ulang halaman.</p>`;
}
$("#ambang").oninput=e=>{
  $("#ambangNilai").textContent=(+e.target.value).toFixed(2).replace(".",",");
};
$("#pilihFoto").onclick=()=>$("#berkas").click();
$("#berkas").onchange=e=>{
  const f=e.target.files[0];if(!f)return;
  const fr=new FileReader();
  fr.onload=()=>{ST.gambar=fr.result;ST.pid=null;
    $("#pratayang").src=fr.result;$("#pratayang").hidden=false;
    $("#emas").innerHTML="";sesuaikan();};
  fr.readAsDataURL(f);
};
$("#acak").onclick=async()=>{
  $("#acak").disabled=true;$("#acak").textContent="memuat katalog…";
  try{
    const p=await(await fetch("/api/acak")).json();
    if(p.galat)throw new Error(p.galat);
    ST.gambar=p.gambar;ST.pid=p.product_id;
    $("#pratayang").src=p.gambar;$("#pratayang").hidden=false;
    $("#emas").innerHTML=`<div class="emas"><b>Produk asli</b><br>${esc(p.judul_asli)}
      <br>Rp ${p.harga_asli.toLocaleString("id-ID")} · ${esc(p.sumber)} · ${esc(p.kategori)}</div>`;
    sesuaikan();
  }catch(err){$("#emas").innerHTML=`<p class="galat">${esc(err.message)}</p>`;}
  $("#acak").disabled=false;$("#acak").textContent="Ambil produk katalog";
};

$("#jalan").onclick=async()=>{
  $("#jalan").disabled=true;
  $("#keluar").innerHTML='<span style="color:var(--redup)">berjalan… muatan '
    +'pertama bisa satu menit karena katalog dan model baru dimuat</span>';
  try{
    const r=await fetch("/api/jalan",{method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({sistem:ST.sistem,platform:$("#platform").value,
        gambar:ST.gambar,product_id:ST.pid,fakta:$("#fakta").value,
        keterangan:$("#keterangan").value,modal:$("#modal").value,
        eksklusi:$("#eksklusi").value,ambang:$("#ambang").value})});
    const d=await r.json();
    if(d.galat)$("#keluar").innerHTML=`<p class="galat">${esc(d.galat)}</p>`;
    else tampil(d);
  }catch(e){$("#keluar").innerHTML=`<p class="galat">${esc(e.message)}</p>`;}
  $("#jalan").disabled=false;
};

function tampil(d){
  const h=d.hasil||{};
  let s="";
  if(h._mentah){
    s+=`<p class="galat">model tidak mengembalikan JSON sah</p>
        <div class="meta">${esc(h._mentah)}</div>`;
  }else{
    s+=`<p class="judul-out">${esc(h.judul)}</p>`;
    s+=h.perkiraan_harga
      ?`<p class="harga">Rp ${Number(h.perkiraan_harga).toLocaleString("id-ID")}</p>`
      :`<p class="harga" style="color:var(--redup)">tidak menyebut harga</p>`;
    s+=`<p>${esc(h.deskripsi)}</p>`;
    if(h.kategori)s+=`<p class="meta">kategori: ${esc(h.kategori)}</p>`;
    if(h.catatan)s+=`<p class="meta">${esc(h.catatan)}</p>`;
    if(h.judul_mentah)s+=`<div class="emas abu"><b>Judul sebelum penjaga</b><br>
      ${esc(h.judul_mentah)}</div>`;
  }
  if(d.dikenal!==null&&d.dikenal!==undefined)
    s+=`<p style="margin-top:12px"><span class="tag ${d.dikenal?"":"no"}">
      ${d.dikenal?"dikenali katalog":"barang asing"}</span></p>`;
  if(d.untung){
    const u=d.untung,rugi=u.selisih<0;
    s+=`<div class="emas" style="border-color:${rugi?"var(--buruk)":"var(--baik)"}">
      <b style="color:${rugi?"var(--buruk)":"var(--baik)"}">
      ${rugi?"Saran harga DI BAWAH modal":"Margin"}</b><br>
      modal Rp ${u.modal.toLocaleString("id-ID")} ·
      saran Rp ${u.saran.toLocaleString("id-ID")} ·
      ${u.selisih<0?"−":"+"}Rp ${Math.abs(u.selisih).toLocaleString("id-ID")}
      (${u.persen}%)</div>`;
  }
  // bacaan foto dan keterangan penjual dipisah: yang pertama tebakan model,
  // yang kedua fakta yang dijamin penjual
  if(d.vlm_foto)s+=`<div class="emas abu"><b>Yang terbaca dari foto</b><br>${esc(d.vlm_foto)}</div>`;
  else if(d.vlm)s+=`<div class="emas abu"><b>Yang terbaca dari foto</b><br>${esc(d.vlm)}</div>`;
  if(d.keterangan)s+=`<div class="emas abu"><b>Keterangan penjual</b><br>${esc(d.keterangan)}</div>`;
  if(d.tetangga&&d.tetangga.length)
    s+=`<div class="emas abu"><b>Tetangga katalog</b><br>${d.tetangga.map(esc).join("<br>")}</div>`;
  if(d.jejak&&d.jejak.length)
    s+=`<ul class="jejak">${d.jejak.map(j=>`<li>${esc(j)}</li>`).join("")}</ul>`;
  const sk=[];
  if(d.skor_visual!==null&&d.skor_visual!==undefined)sk.push(`kemiripan foto ${d.skor_visual}`);
  if(d.skor_teks)sk.push(`skor teks ${d.skor_teks}`);
  sk.push(`${d.detik} detik`);
  if(d.detik_lihat)sk.push(`baca foto ${d.detik_lihat} dtk`);
  s+=`<p class="meta">${sk.join(" · ")}</p>`;
  $("#keluar").innerHTML=s;
}
</script></body></html>"""


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()

    print("\nsistem yang terdeteksi:")
    for s in ketersediaan():
        tanda = "siap " if s["siap"] else "belum"
        print(f"  [{tanda}] {s['nama']}"
              + ("" if s["siap"] else f"   -> {s['kurang']}"))
    print(f"\n  http://localhost:{args.port}\n"
          "  katalog dimuat saat pipeline pertama kali dipakai (sekitar 1 menit)\n"
          "  Ctrl+C untuk berhenti\n", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
