"""Siapkan berkas penilaian manusia — buta, satu listing per layar.

    python scripts/buat_penilaian.py
    python scripts/buat_penilaian.py --n 20 --seed 3
    -> penilaian/penilaian.html, buka di browser

Kenapa perlu. Tiga metrik halusinasi di `eval_listing.py` (`merek_ketat`,
`spek_karang`, `desk_asing`) adalah proksi irisan kata buatan sendiri. Tidak ada
yang membuktikan ia sejalan dengan penilaian manusia. Berkas ini menghasilkan
data untuk mengujinya: nilai manusia per listing, lalu dibandingkan dengan
tebakan metrik pada listing yang sama.

Rancangan yang menjaga hasilnya tetap sah:

- **Buta.** Nama sistem tidak muncul di layar dan tidak terbaca di teks HTML
  sambil menilai; ia disimpan terenkode dan baru terbuka saat diekspor.
- **Satu per satu.** Membandingkan berdampingan membuat penilai mengurutkan,
  bukan menilai. Yang dibutuhkan penilaian mutlak per listing.
- **Acak.** Urutannya diacak supaya tidak ada sistem yang selalu dinilai saat
  penilai masih segar.
- **Produk sama.** Ketiga sistem menjawab 492 produk yang identik, jadi tiap
  produk terpilih menyumbang satu listing dari tiap sistem.

Pertanyaannya sengaja dipetakan satu-satu ke metrik yang mau diuji, supaya
hasilnya bisa langsung disandingkan.
"""

from __future__ import annotations

import argparse
import base64
import json
import random
import sys
from pathlib import Path

import pandas as pd

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
KELUARAN = PROJECT / "penilaian" / "penilaian.html"

# Label ini masuk ke berkas hasil, tidak pernah ke layar.
#
# Student SENGAJA tidak ikut. Ia tidak pernah menghasilkan kategori maupun
# harga, jadi barisnya tampil sebagai "kategori: - . tanpa harga" -- penanda
# yang membuat penilai bisa mengenalinya seketika, dan penilaian butanya
# batal. Pipeline dan baseline sama-sama punya keempat kolom, jadi
# benar-benar tak terbedakan.
#
# Student tetap perlu dinilai manusia, tapi lewat ronde terpisah yang hanya
# menanyakan judul dan deskripsi -- dua hal yang memang ia hasilkan.
SUMBER = {
    "pipeline": PROJECT / "hasil_sesi2" / "S4_bersih.jsonl",
    "baseline12b": PROJECT / "hasil_sesi2" / "S3_baseline_12b.jsonl",
}


def muat(path: Path) -> dict:
    keluar = {}
    for l in path.open(encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            keluar[str(r["product_id"])] = r
    return keluar


def ambil_listing(r: dict) -> dict | None:
    """Satu listing dari satu baris hasil, diutamakan platform asal produk
    supaya ketiga sistem dinilai pada sasaran yang sama."""
    hasil = r.get("hasil") or {}
    urutan = [r.get("source"), "tokopedia", "blibli", "umum", *hasil.keys()]
    for kunci in urutan:
        h = hasil.get(kunci)
        if isinstance(h, dict) and h.get("judul") and "_mentah" not in h:
            return {"judul": str(h["judul"]),
                    "deskripsi": str(h.get("deskripsi", "")),
                    "kategori": str(h.get("kategori", "")),
                    "harga": h.get("perkiraan_harga") or 0,
                    "platform": kunci}
    return None


def foto_base64(path: Path, sisi: int = 560) -> str | None:
    from io import BytesIO

    from PIL import Image
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((sisi, sisi))
            buf = BytesIO()
            im.save(buf, format="JPEG", quality=80)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=25,
                    help="jumlah produk; tiap produk menyumbang 1 listing per sistem")
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()

    data = {}
    for nama, path in SUMBER.items():
        if not path.exists():
            sys.exit(f"tidak ada {path}")
        data[nama] = muat(path)

    bersama = sorted(set.intersection(*(set(d) for d in data.values())))
    print(f"{len(bersama):,} produk dijawab ketiga sistem")

    df = pd.read_parquet(PROJECT / "data_drive" / "merged" / "merged_local.parquet",
                         columns=["product_id", "local_image_paths", "n_gambar_lokal"])
    foto = {str(r.product_id): r.local_image_paths[0]
            for r in df.itertuples() if r.n_gambar_lokal > 0}

    acak = random.Random(args.seed)
    calon = [p for p in bersama if p in foto]
    acak.shuffle(calon)

    butir, dipakai = [], set()
    for pid in calon:
        if len(dipakai) >= args.n:
            break
        satuan = []
        for nama in SUMBER:
            lst = ambil_listing(data[nama][pid])
            if lst:
                satuan.append({"sistem": nama, **lst})
        if len(satuan) < len(SUMBER):
            continue                     # lewati produk yang tidak lengkap
        b64 = foto_base64(Path(foto[pid]))
        if not b64:
            continue
        acuan = data["pipeline"][pid]
        dipakai.add(pid)
        for s in satuan:
            butir.append({
                "pid": pid, "foto": b64,
                "judul_asli": str(acuan.get("judul_asli", "")),
                "kategori_asli": str(acuan.get("kategori_asli", "")),
                "harga_asli": int(acuan.get("harga_asli") or 0),
                **s,
            })

    acak.shuffle(butir)
    print(f"{len(dipakai)} produk x {len(SUMBER)} sistem = {len(butir)} listing")

    # Identitas sistem disembunyikan dari teks yang terbaca sambil menilai.
    # base64 bukan pengamanan -- ia cuma menghalangi mata yang tidak sengaja
    # membaca sumber halaman, dan itu cukup untuk penilaian buta.
    for b in butir:
        b["k"] = base64.b64encode(b.pop("sistem").encode()).decode()

    KELUARAN.parent.mkdir(parents=True, exist_ok=True)
    KELUARAN.write_text(
        HALAMAN.replace("__DATA__", json.dumps(butir, ensure_ascii=False)),
        encoding="utf-8")
    print(f"\n-> {KELUARAN}  ({KELUARAN.stat().st_size / 1e6:.1f} MB)")
    print("   buka di browser, nilai semuanya, lalu salin hasilnya")
    print("   simpan ke penilaian/hasil.json")


HALAMAN = r"""<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Penilaian Listing</title>
<style>
:root{--bg:#f4f6f5;--kartu:#fff;--tinta:#131d1c;--redup:#56635f;--garis:#d8e0dd;
      --aksen:#0c6460;--buruk:#9c3f24;--baik:#2c6b4a}
@media(prefers-color-scheme:dark){:root{--bg:#0c1211;--kartu:#141c1b;--tinta:#e4ebe9;
      --redup:#97a5a1;--garis:#24302e;--aksen:#56c2b6;--buruk:#e08661;--baik:#62be88}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tinta);font:16px/1.55 system-ui,sans-serif}
.bung{max-width:1000px;margin:0 auto;padding:24px 20px 80px}
h1{font-size:22px;margin:0 0 4px;letter-spacing:-.02em}
.sub{color:var(--redup);font-size:14px;margin:0 0 20px}
.bar{height:5px;background:var(--garis);border-radius:99px;overflow:hidden;margin-bottom:20px}
.bar div{height:100%;background:var(--aksen);width:0;transition:width .2s}
.kisi{display:grid;grid-template-columns:1fr 1fr;gap:22px;align-items:start}
@media(max-width:820px){.kisi{grid-template-columns:1fr}}
.kartu{background:var(--kartu);border:1px solid var(--garis);border-radius:8px;padding:18px}
img{width:100%;max-height:420px;object-fit:contain;border-radius:6px;background:var(--bg)}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.08em;
   color:var(--redup);margin:0 0 12px;font-weight:600}
.judul{font-size:18px;font-weight:600;line-height:1.3;margin:0 0 10px}
.desk{margin:0 0 12px}
.meta{font-size:13px;color:var(--redup);font-family:ui-monospace,monospace}
.tanya{margin-top:20px;padding-top:16px;border-top:1px solid var(--garis)}
.tanya p{margin:0 0 8px;font-size:15px;font-weight:500}
.tanya .bantu{font-weight:400;font-size:13px;color:var(--redup);margin-bottom:8px}
.pil{display:flex;gap:8px;flex-wrap:wrap}
.pil button{flex:1;min-width:90px;padding:10px 8px;border:1px solid var(--garis);
  background:transparent;color:var(--tinta);border-radius:6px;cursor:pointer;
  font:inherit;font-size:14px}
.pil button:hover{border-color:var(--aksen)}
.pil button.on{background:var(--aksen);border-color:var(--aksen);color:var(--bg);font-weight:600}
.pil button.on.no{background:var(--buruk);border-color:var(--buruk)}
.pil button.on.ya{background:var(--baik);border-color:var(--baik)}
input[type=text]{width:100%;margin-top:8px;padding:9px 11px;border:1px solid var(--garis);
  border-radius:6px;background:var(--bg);color:var(--tinta);font:inherit;font-size:14px}
.kaki{display:flex;gap:10px;justify-content:space-between;align-items:center;
      margin-top:24px;flex-wrap:wrap}
button.utama{background:var(--aksen);color:var(--bg);border:0;border-radius:6px;
  padding:12px 22px;font:inherit;font-weight:600;cursor:pointer}
button.utama:disabled{opacity:.4;cursor:not-allowed}
button.tipis{background:transparent;color:var(--aksen);border:1px solid var(--garis);
  border-radius:6px;padding:10px 16px;font:inherit;cursor:pointer}
.selesai{text-align:center;padding:48px 20px}
.selesai h2{font-size:20px;text-transform:none;letter-spacing:0;color:var(--tinta)}
textarea{width:100%;height:240px;margin-top:12px;font-family:ui-monospace,monospace;
  font-size:12px;padding:10px;border:1px solid var(--garis);border-radius:6px;
  background:var(--bg);color:var(--tinta)}
</style></head><body><div class="bung">

<h1>Penilaian Listing</h1>
<p class="sub">Nilai tiap listing terhadap fotonya. Kamu tidak diberi tahu sistem
mana yang membuatnya — itu memang disengaja.</p>
<div class="bar"><div id="bar"></div></div>

<div id="isi"></div>

<div class="kaki">
  <span class="meta" id="posisi"></span>
  <span>
    <button class="tipis" id="mundur">Kembali</button>
    <button class="utama" id="maju" disabled>Lanjut</button>
  </span>
</div>
</div>
<script>
const BUTIR = __DATA__;
const KUNCI = "penilaian_listing_v1";
let jawab = {};
try { jawab = JSON.parse(localStorage.getItem(KUNCI) || "{}"); } catch (e) {}
let i = 0;

const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[<>&]/g, c => ({"<":"&lt;",">":"&gt;","&":"&amp;"}[c]));

const TANYA = [
  {id:"judul_karang", t:"Judulnya menyebut sesuatu yang TIDAK ada di foto?",
   b:"Merek, ukuran, warna, rasa, atau bahan yang tidak bisa kamu lihat sendiri di foto.",
   pil:[["tidak","Tidak, semua berdasar","ya"],["ya","Ya, ada yang dikarang","no"]],
   isian:"Kata mana? (opsional)"},
  {id:"desk_karang", t:"Deskripsinya menyebut sesuatu yang TIDAK ada di foto?",
   b:"Termasuk klaim seperti garansi, BPOM, atau khasiat.",
   pil:[["tidak","Tidak","ya"],["ya","Ya","no"]]},
  // id-nya BUKAN "kategori": jawaban disebar ke objek hasil yang sudah punya
  // kolom kategori dari listing, dan nama yang sama akan menimpanya -- kategori
  // yang ditulis sistem hilang, padahal itu yang mau dinilai.
  {id:"kategori_nilai", t:"Kategorinya tepat untuk barang ini?",
   b:"Pilihan yang ada cuma tujuh: bumbu_masak, camilan_olahan, fashion_perawatan, kriya_rumah, minuman_herbal, pokok_tani, lainnya. Pilih \"tak ada yang cocok\" kalau memang tidak satu pun pas.",
   pil:[["tepat","Tepat","ya"],["salah","Salah","no"],["tak_ada","Tak ada yang cocok",""]]},
  {id:"layak", t:"Layak dipasang penjual apa adanya?",
   b:"Bayangkan kamu penjualnya dan ini muncul otomatis.",
   pil:[["ya","Langsung pakai","ya"],["edit","Perlu sedikit edit",""],["tidak","Tidak layak","no"]]},
];

function gambar() {
  if (i >= BUTIR.length) return selesai();
  const b = BUTIR[i], j = jawab[i] || {};
  $("#isi").innerHTML = `
    <div class="kisi">
      <div class="kartu">
        <h2>Foto produk</h2>
        <img src="${b.foto}" alt="foto produk">
      </div>
      <div class="kartu">
        <h2>Listing yang dinilai</h2>
        <p class="judul">${esc(b.judul)}</p>
        <p class="desk">${esc(b.deskripsi) || "<span style='color:var(--redup)'>(tanpa deskripsi)</span>"}</p>
        <p class="meta">kategori: ${esc(b.kategori) || "—"}${
          b.harga ? " · harga: Rp " + Number(b.harga).toLocaleString("id-ID") : " · tanpa harga"}</p>
        ${TANYA.map(q => `
          <div class="tanya">
            <p>${q.t}</p>
            <p class="bantu">${q.b}</p>
            <div class="pil" data-q="${q.id}">
              ${q.pil.map(([v,l,c]) => `<button data-v="${v}" class="${c} ${j[q.id]===v?"on":""}">${l}</button>`).join("")}
            </div>
            ${q.isian ? `<input type="text" data-q="${q.id}_kata" placeholder="${q.isian}"
                          value="${esc(j[q.id+"_kata"] || "")}">` : ""}
          </div>`).join("")}
      </div>
    </div>`;

  document.querySelectorAll(".pil").forEach(gp => {
    gp.querySelectorAll("button").forEach(bt => bt.onclick = () => {
      gp.querySelectorAll("button").forEach(x => x.classList.remove("on"));
      bt.classList.add("on");
      (jawab[i] = jawab[i] || {})[gp.dataset.q] = bt.dataset.v;
      simpan();
    });
  });
  document.querySelectorAll("input[type=text]").forEach(inp => {
    inp.oninput = () => { (jawab[i] = jawab[i] || {})[inp.dataset.q] = inp.value; simpan(); };
  });
  perbarui();
}

const lengkap = n => TANYA.every(q => (jawab[n] || {})[q.id]);
function simpan() {
  try { localStorage.setItem(KUNCI, JSON.stringify(jawab)); } catch (e) {}
  perbarui();
}
function perbarui() {
  const n = BUTIR.map((_, k) => k).filter(lengkap).length;
  $("#bar").style.width = (100 * n / BUTIR.length) + "%";
  $("#posisi").textContent = `listing ${i+1} dari ${BUTIR.length} · ${n} selesai`;
  $("#maju").disabled = !lengkap(i);
  $("#mundur").disabled = i === 0;
  $("#maju").textContent = i === BUTIR.length - 1 ? "Selesai" : "Lanjut";
}
$("#maju").onclick = () => { i++; gambar(); };
$("#mundur").onclick = () => { if (i > 0) { i--; gambar(); } };

function selesai() {
  const hasil = BUTIR.map((b, n) => ({
    urutan: n, product_id: b.pid, sistem: atob(b.k), platform: b.platform,
    judul: b.judul, kategori: b.kategori, kategori_asli: b.kategori_asli,
    judul_asli: b.judul_asli, ...(jawab[n] || {}),
  }));
  const teks = JSON.stringify(hasil, null, 1);
  $("#isi").innerHTML = `
    <div class="kartu selesai">
      <h2>Selesai — ${BUTIR.length} listing dinilai</h2>
      <p style="color:var(--redup)">Simpan isi kotak di bawah ke
      <code>penilaian/hasil.json</code></p>
      <p><button class="utama" id="salin">Salin ke papan klip</button></p>
      <textarea id="keluaran">${esc(teks)}</textarea>
    </div>`;
  $("#posisi").textContent = "";
  $("#maju").style.display = $("#mundur").style.display = "none";
  $("#salin").onclick = async () => {
    try { await navigator.clipboard.writeText(teks); $("#salin").textContent = "Tersalin"; }
    catch (e) { $("#keluaran").select(); $("#salin").textContent = "Tekan Ctrl+C"; }
  };
}

gambar();
</script></body></html>"""


if __name__ == "__main__":
    main()
