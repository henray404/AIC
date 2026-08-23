# Penilaian manusia — dan apa yang dibantahnya

Ronde pertama, 23 Agustus 2026. **51 listing, 1 penilai, buta.** Penilai tidak
diberi tahu sistem mana yang membuat tiap listing.

Hasilnya membantah tiga metrik yang selama ini jadi klaim terkuat, dan itu
sebabnya halaman ini ada.

## Temuan utama: tiga metrik halusinasi tidak mengukur halusinasi

| metrik | sepakat | recall | presisi |
|---|---:|---:|---:|
| `brand_strict%` | 72,5% | **6,7%** | 100% |
| `spec_halluc%` | 52,9% | **0,0%** | — |
| `desc_ungrounded%` | 80,4% | **9,1%** | 100% |

**recall** = halusinasi nyata yang tertangkap metrik.
**presisi** = tuduhan metrik yang dibenarkan manusia.

Presisi 100% terlihat bagus sampai disandingkan dengan recall: metrik itu
**hampir tidak pernah menuduh**. Detektor yang selalu menjawab "bersih" tetap
sepakat 72–80% dengan manusia semata karena halusinasinya memang jarang. Angka
"sepakat" sendirian menyesatkan, dan itu sebabnya ia tidak boleh dilaporkan
tanpa recall.

### Kenapa dilewatkan

Ketiganya hanya mencari **nama merek dan istilah langka** — aturannya
`w in lex["merek"] or w not in lex["umum"]`. Yang dilewatkan adalah warna,
aroma, rasa, dan sifat produk, semuanya kata Indonesia lazim:

| judul yang dihasilkan | yang terlihat di foto | kata dikarang |
|---|---|---|
| Sepatu Lari Pria **Hitam** | sepatu Puma Future | Hitam |
| Sabun Mandi **Aroma Citrus Segar** | sabun cuci beras SEZA | hampir seluruhnya |
| Cheek & Lip Tint **Warna Merah Muda** | Implora liptint | Merah Muda |
| Flip Flop Wanita **Model Trendi** | flip-flop polos | Trendi, Model |

14 dari 15 kasus yang manusia sebut mengarang lolos dari metrik.

Ini **bukan bug**, melainkan ketidakcocokan nama dengan isi. `brand_strict%`
memang cuma dirancang menjawab *"apakah ada nama merek tak berdasar"* —
pertanyaan sempit yang sah. Menyebutnya ukuran halusinasi yang membuatnya
menyesatkan.

## Penilaian manusia per sistem

| sistem | n | judul dikarang | deskripsi dikarang | kategori tepat | layak dipakai |
|---|---:|---:|---:|---:|---:|
| Baseline 12B | 17 | **3 (17,6%)** | 4 (23,5%) | **16 (94,1%)** | **8 (47,1%)** |
| RAG pipeline | 17 | 6 (35,3%) | **2 (11,8%)** | 6 (35,3%) | 5 (29,4%) |
| Student VLM 3B | 17 | 6 (35,3%) | 5 (29,4%) | 0 (0,0%) | 3 (17,6%) |

**Baseline menang di tiga dari empat kolom.** Itu berlawanan dengan seluruh
tabel otomatis, dan tidak boleh diabaikan.

Tapi juga tidak boleh langsung dipercaya — tiga hal membatasinya:

1. **Satu penilai.** Tidak ada pembanding untuk tahu apakah penilaiannya
   konsisten atau punya kecenderungan tertentu. Kesepakatan antar penilai belum
   pernah diukur.
2. **17 listing per sistem.** Selisih 35,3% lawan 17,6% itu **6 kasus lawan 3**.
   Terlalu kecil untuk membedakan sistem dengan yakin.
3. **Kategori mengukur hal lain.** Lihat bagian berikut.

## Kategori: 94,1% lawan 35,3% mengukur taksonomi, bukan sistem

Baseline mengarang kategorinya sendiri dan manusia membenarkannya:

| produk | pipeline | baseline | putusan manusia |
|---|---|---|---|
| Implora Cheek & Lip Tint | `lainnya` | Makeup & Perawatan Tubuh | pipeline salah, baseline tepat |
| Smartwatch Apple Series 9 | `lainnya` | Elektronik > Jam Tangan | pipeline salah, baseline tepat |
| Triple Care Sunscreen | `lainnya` | Perawatan Wajah | pipeline salah, baseline tepat |

Lip tint dan smartwatch jatuh ke `lainnya` karena **memang tidak ada wadahnya**
di tujuh kategori UMKM. Baseline bebas menulis apa pun, jadi jawabannya lebih
tepat bagi manusia — bukan karena lebih pintar.

Dua kesalahan pipeline yang **bukan** soal taksonomi, dan ini bug nyata:

```
Sandal jepit Gunung  -> kriya_rumah      seharusnya fashion_perawatan
Tuna Chunk in Oil    -> minuman_herbal   seharusnya pokok_tani / camilan
```

Wadahnya ada, penambatnya yang meleset — `sahkan_kategori` mengambil modus
kategori lima tetangga, dan tetangganya salah.

Dari 51 listing, **16 dinilai "tak ada kategori yang cocok"** (31,4%). Itu angka
besar, dan mendukung temuan di
[`CACAT_LABEL_KATEGORI.md`](CACAT_LABEL_KATEGORI.md): taksonomi tujuh kelas
tidak cocok dengan data marketplace umum.

## Yang masih sah dan yang tidak

**Tidak terpengaruh** — punya definisi objektif yang tidak bergantung penilaian:

```
title_recall      irisan kata dengan judul asli
price_logerr      selisih log harga saran dan harga asli
price_within2x%   porsi tebakan dalam rentang setengah sampai dua kali
category_valid%   apakah keluarannya ada di taksonomi
```

**Tak sah sebagai ukuran halusinasi:** `brand_strict%`, `spec_halluc%`,
`desc_ungrounded%`.

**Sudah ditandai sebelumnya:** `brand_lenient%` melingkar, `harga_model_err%`
tidak berdiri sendiri, `category_correct%` sebagian mengukur mutu label.

## Cacat rancangan di ronde ini

Dua, dan keduanya sudah diperbaiki untuk ronde berikutnya:

**Student membocorkan identitasnya.** Ia tidak pernah menghasilkan kategori
maupun harga, jadi listingnya tampil sebagai `kategori: — · tanpa harga` —
penanda yang membuat penilai bisa mengenalinya seketika. 17 dari 51 listing
terbaca sistemnya, dan penilaian butanya batal untuk baris student.

Ditemukan pengguna saat membuka halamannya, bukan oleh uji asap. Uji itu
memverifikasi nama sistem tidak muncul di teks, tapi tidak memeriksa apakah
**bentuk keluarannya sendiri** membocorkan identitas.

**Kategori sistem hilang saat diekspor.** Id pertanyaan `kategori` menimpa
kolom kategori listing, jadi perbandingan kategori-sistem lawan label-katalog
tidak bisa dihitung dari data ini.

Ronde berikutnya: 50 listing, hanya pipeline lawan baseline (keduanya punya
keempat kolom), id pertanyaan diganti `kategori_nilai`.

## Yang perlu dikerjakan berikutnya

1. **Tambah penilai** — ini yang paling menentukan. Satu penilai dan 17 listing
   per sistem tidak cukup untuk menyimpulkan apa pun tentang perbandingan
   sistem, dan tidak cukup untuk menguji metrik perbaikan.
2. **Perbaiki metrik halusinasi** — aturannya digeser supaya semua kata benda
   dan sifat yang tidak ada di bacaan foto ikut dihitung, bukan hanya yang
   langka. Data penilaian ini jadi pengujinya: ada 14 kasus yang harus
   tertangkap. Risikonya presisi turun dari 100%, dan itu harus diukur bukan
   ditebak.
3. **Perbaiki penambat kategori** untuk kasus sandal→`kriya_rumah`. Bug logika,
   bukan soal taksonomi.

Tidak ada yang butuh melatih model. Semua perbaikan ada di kode aturan.

## Berkas

```
penilaian/hasil.json          51 penilaian, ronde 1
penilaian/penilaian.html      ronde 2, 50 listing (belum dinilai)
penilaian/CARA_MENILAI.md     panduan penilai
scripts/buat_penilaian.py     pembuat halaman penilaian
scripts/nilai_penilaian.py    pembanding manusia lawan metrik
```
