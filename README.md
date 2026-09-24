# Dashboard Return Rate RTS

Dashboard statis (GitHub Pages). Data diambil dari Google Spreadsheet oleh GitHub Actions
dan disimpan di `data.json`.

## Isi repo
- `index.html` : dashboard
- `scripts/export_data.py` : baca Google Sheets, hitung, tulis `data.json`
- `.github/workflows/update-data.yml` : jalan tiap 3 jam atau manual
- `requirements.txt`

## Setup (sekali saja)

### 1. Buat service account Google
1. Buka https://console.cloud.google.com, buat project (atau pakai yang ada).
2. Aktifkan **Google Sheets API** dan **Google Drive API** (APIs & Services > Library).
3. IAM & Admin > Service Accounts > Create. Beri nama bebas.
4. Buka service account tadi > tab **Keys** > Add key > JSON. File JSON akan ter-download.
5. Salin alamat email service account (bentuknya `nama@project.iam.gserviceaccount.com`).

### 2. Share kedua spreadsheet
Buka spreadsheet RTS dan spreadsheet Outbound, klik Share, tambahkan email service account
sebagai **Viewer**.

### 3. Isi secrets di GitHub
Repo > Settings > Secrets and variables > Actions > **New repository secret**:

| Nama | Isi |
|---|---|
| `GCP_SA_KEY` | seluruh isi file JSON service account |
| `ID_RTS` | ID spreadsheet RTS (bagian antara `/d/` dan `/edit` di URL) |
| `ID_OUTBOUND` | ID spreadsheet Outbound |

Opsional, di tab **Variables**: `SHEET_OUTBOUND` = nama sheet outbound bulan berjalan
(default `Sep`). Ganti tiap ganti bulan, misalnya `Okt`.

### 4. Aktifkan GitHub Pages
Settings > Pages > Source: **Deploy from a branch** > Branch: `main` / `(root)` > Save.

### 5. Jalankan pertama kali
Tab **Actions** > Update data > **Run workflow**. Setelah hijau, `data.json` muncul di repo
dan dashboard bisa dibuka di `https://<username>.github.io/<nama-repo>/`.

## Catatan
- Sheet RTS yang judulnya diawali `RTS Tiktok` / `RTS Shopee` digabung otomatis, jadi sheet
  baru (misal "RTS Tiktok 21-30 sep") ikut terbaca tanpa ubah kode.
- Repo public = `data.json` bisa dibaca siapa saja. Isinya hanya angka agregat (jumlah
  kirim/RTS per gudang, provinsi, kota) tanpa data pembeli, tapi kalau angka bisnis ini
  sensitif, pakai repo private (GitHub Pages untuk repo private butuh plan berbayar) atau
  host di tempat yang bisa diberi login.
- Jadwal cron memakai UTC. GitHub bisa menunda run terjadwal beberapa menit.
