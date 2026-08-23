# Cara menilai — panduan untuk penilai

Terima kasih sudah mau membantu. Ini butuh sekitar **20 menit**.

## Yang sedang diuji

Kami membuat sistem yang menghasilkan listing marketplace otomatis dari foto
produk — judul, deskripsi, kategori, harga. Ada beberapa sistem berbeda, dan
kami sudah punya angka dari program penilai otomatis.

Masalahnya: **program itu buatan kami sendiri.** Ia menilai halusinasi dengan
mencocokkan kata, bukan memahami makna. Tidak ada yang membuktikan angkanya
sejalan dengan penilaian manusia.

Di situlah kamu masuk. Penilaianmu jadi pembanding — kalau program dan manusia
sering berselisih, angka kami mengukur proksinya, bukan halusinasinya.

**Kamu tidak diberi tahu sistem mana yang membuat tiap listing.** Itu disengaja.
Jangan mencoba menebaknya dari kode sumber halaman — hasilnya jadi tidak sah.

## Cara membuka

Klik dua kali `penilaian.html`. Tidak perlu memasang apa pun, tidak perlu
internet.

Kemajuanmu tersimpan otomatis di browser, jadi boleh berhenti dan lanjut nanti.
Tapi **pakai browser dan komputer yang sama**, dan jangan bersihkan data situs
di tengah jalan — kemajuannya ikut terhapus.

50 listing, satu per layar. Foto di kiri, listing di kanan.

## Aturan utama

> **Nilai terhadap FOTO, bukan terhadap pengetahuanmu tentang produknya.**

Kalau kamu kebetulan tahu merek itu memang menjual ukuran 250 gram, tapi
ukurannya tidak terlihat di foto — itu tetap **dikarang**. Sistemnya cuma
melihat foto, jadi ia harus dinilai atas dasar yang sama.

## Empat pertanyaannya

### 1. Judulnya menyebut sesuatu yang TIDAK ada di foto?

Yang dihitung mengarang: merek, ukuran, isi, berat, warna, rasa, bahan, atau
nomor model yang **tidak bisa kamu lihat sendiri** di foto.

| judul | yang terlihat di foto | jawab |
|---|---|---|
| Minyak Goreng Sunco 2 Liter | botol bertuliskan "Sunco 2L" | tidak |
| Minyak Goreng Sunco 1 Liter | botol "Sunco", ukuran tak terbaca | **ya** — "1 Liter" |
| Keripik Pisang Coklat | bungkus keripik pisang coklat | tidak |
| Keripik Pisang Coklat Strawberry | bungkus yang sama, tak ada strawberry | **ya** — "Strawberry" |
| Sepatu Sneakers Pria Hitam Putih | sepatu hitam putih | tidak |
| Headset Gaming Fantech | headset tanpa merek terbaca | **ya** — "Fantech" |

Kalau menjawab **ya**, tulis kata mana di kotak isian. Itu sangat membantu —
dari situ kami tahu jenis kesalahan apa yang paling sering lolos.

**Jangan hitung sebagai mengarang:** kata umum yang jelas benar dari bentuknya
("Sepatu", "Botol", "Tas"), atau kata jualan biasa ("Praktis", "Nyaman").

### 2. Deskripsinya menyebut sesuatu yang TIDAK ada di foto?

Aturan sama. Tambahan yang selalu dihitung mengarang kalau tidak tercetak jelas
di kemasan:

- garansi, BPOM, halal, SNI, izin apa pun
- klaim khasiat: "menyembuhkan", "ampuh", "terbukti"
- "100% original", "asli", "resmi"

Kalimat jualan biasa seperti "cocok untuk keluarga" **bukan** mengarang.

### 3. Kategorinya tepat untuk barang ini?

Sistem hanya punya tujuh pilihan:

```
bumbu_masak        camilan_olahan     fashion_perawatan   kriya_rumah
minuman_herbal     pokok_tani         lainnya
```

- **Tepat** — kategorinya masuk akal untuk barang di foto
- **Salah** — ada kategori lain di daftar itu yang jelas lebih pas
- **Tak ada yang cocok** — barangnya memang tidak muat di tujuh pilihan itu

Pilihan ketiga penting, jangan dihindari. Elektronik, alat olahraga, dan
perkakas memang tidak punya wadah di daftar ini. Kalau kamu sering memilihnya,
itu memberi tahu kami taksonomi kami yang kurang — bukan sistemnya yang salah.

Sebagai patokan: `kriya_rumah` mencakup peralatan rumah tangga dan dapur;
`fashion_perawatan` mencakup pakaian, sepatu, tas, dan produk perawatan diri.

### 4. Layak dipasang penjual apa adanya?

Bayangkan kamu penjualnya dan listing ini muncul otomatis.

- **Langsung pakai** — tinggal pasang, tidak perlu disentuh
- **Perlu sedikit edit** — dasarnya benar, ada satu dua hal yang mau diubah
- **Tidak layak** — salah barang, atau harus ditulis ulang

Nilai kegunaannya, bukan keindahan bahasanya.

## Kalau ragu

Ikuti kesan pertama. Kami butuh penilaian yang konsisten, bukan yang sempurna —
dan terlalu lama menimbang satu listing justru membuat penilaianmu bergeser di
tengah jalan.

Kalau listingnya jelas rusak (kosong, terpotong, atau berisi JSON mentah), jawab
apa adanya: mengarang **tidak**, kategori **salah** atau **tak ada**, layak
**tidak layak**.

## Setelah selesai

Di layar terakhir muncul tombol **Salin ke papan klip**.

1. Klik tombolnya
2. Buka Notepad, tempel
3. Simpan sebagai `hasil.json`
4. Kirim berkas itu balik

Kalau tombolnya tidak bekerja, isi kotak teks di bawahnya bisa disalin manual
(Ctrl+A lalu Ctrl+C).

## Satu hal terakhir

Jangan cocokkan penilaianmu dengan apa yang kamu kira "jawaban yang diharapkan".
Kalau menurutmu semua listing jelek, katakan begitu. Penilaian yang sopan justru
merusak gunanya — kami ingin tahu di mana sistemnya gagal, bukan mendengar bahwa
ia bagus.
