# ==============================================================================
# EXPORT DATA RTS -> data.json (dijalankan otomatis oleh GitHub Actions)
# Bisa juga dijalankan lokal:  python scripts/export_data.py
# ==============================================================================
import os
import re
import json
import gspread
import pandas as pd

# ------------------------------------------------------------------------------
# 0. PENGATURAN
# ------------------------------------------------------------------------------
ID_RTS = os.environ["ID_RTS"]
ID_OUTBOUND = os.environ["ID_OUTBOUND"]

# Sheet outbound bulan berjalan (mis. "Sep", "Okt"). Bisa diubah lewat variable GitHub.
SHEET_OUTBOUND = os.environ.get("SHEET_OUTBOUND", "Sep")

# Semua sheet RTS yang judulnya diawali teks ini akan digabung otomatis,
# jadi nama seperti "RTS Tiktok 1-20 sep" atau "RTS Tiktok 21-30 sep" ikut terbaca.
PREFIX_RTS_TIKTOK = "rts tiktok"
PREFIX_RTS_SHOPEE = "rts shopee"

KOLOM_TGL_TIKTOK = ['Cancelled Time', 'Cancel Time', 'Cancelled_Time']
KOLOM_TGL_SHOPEE = ['Waktu Pesanan Dibuat', 'Order Creation Date']

GUDANG_MAP = {
    'cirebon': 'Monacruz Cirebon',
    'medan': 'Monacruz Medan',
    'makassar': 'Monacruz Makasar',
    'makasar': 'Monacruz Makasar',
    'banjarmasin': 'Monacruz Banjarmasin',
}

OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "data.json")

# ------------------------------------------------------------------------------
# 1. AUTENTIKASI (service account dari secret GCP_SA_KEY)
# ------------------------------------------------------------------------------
print("1. Autentikasi service account...")
gc = gspread.service_account_from_dict(json.loads(os.environ["GCP_SA_KEY"]))
sh_rts = gc.open_by_key(ID_RTS)
sh_outbound = gc.open_by_key(ID_OUTBOUND)


def norm_gudang(x):
    """Normalisasi nama gudang berdasarkan kata kunci (bukan exact match)."""
    s = str(x).strip().lower()
    for k, v in GUDANG_MAP.items():
        if k in s:
            return v
    return None


def get_column(df, target_names, fallback_idx=None):
    clean_cols = {str(col).strip().lower(): col for col in df.columns}
    for target in target_names:
        key = target.strip().lower()
        if key in clean_cols:
            return df[clean_cols[key]]
    if fallback_idx is not None and fallback_idx < len(df.columns):
        return df.iloc[:, fallback_idx]
    print(f"   ! Kolom {target_names} tidak ditemukan, diisi 'Unknown'")
    return pd.Series(['Unknown'] * len(df), index=df.index)


def to_int(v):
    v = re.sub(r'[^\d]', '', str(v).strip())
    return int(v) if v else 0


# ------------------------------------------------------------------------------
# 2. OUTBOUND PER GUDANG (tidak lagi digabung global!)
# ------------------------------------------------------------------------------
print("2. Membaca outbound per gudang...")
data_matrix = sh_outbound.worksheet(SHEET_OUTBOUND).get_all_values()
num_rows = len(data_matrix)
raw_outbound = []

for r_idx in range(num_rows):
    row = data_matrix[r_idx]
    for c_idx in range(len(row)):
        if 'tanggal' not in str(row[c_idx]).strip().lower():
            continue

        # cari tanggal di sel ini atau 2 sel di kanannya
        tgl = pd.NaT
        for offset in range(0, 3):
            if c_idx + offset < len(row):
                cand = re.sub(r'(?i)tanggal|:', '', str(row[c_idx + offset])).strip()
                parsed = pd.to_datetime(cand, errors='coerce', dayfirst=True)
                if pd.notna(parsed):
                    tgl = parsed
                    break
        if pd.isna(tgl):
            continue

        # nama gudang di 4 baris atas
        gudang = 'Indonesia'
        found = False
        for cr in range(max(0, r_idx - 4), r_idx):
            for cc in range(max(0, c_idx - 1), min(c_idx + 6, len(data_matrix[cr]))):
                g = norm_gudang(data_matrix[cr][cc])
                if g:
                    gudang, found = g, True
                    break
            if found:
                break

        # cari header Tiktok/Shopee dan baris TOTAL di bawahnya
        col_tt = col_sp = None
        tot_tt = tot_sp = 0
        found_total = False
        for sr in range(r_idx + 1, min(r_idx + 25, num_rows)):
            sub = data_matrix[sr]
            rng = range(max(0, c_idx - 1), min(c_idx + 6, len(sub)))
            for sc in rng:
                h = str(sub[sc]).strip().lower()
                if h == 'tiktok':
                    col_tt = sc
                elif h == 'shopee':
                    col_sp = sc
            for sc in rng:
                if str(sub[sc]).strip().upper() == 'TOTAL':
                    if col_tt is not None and col_tt < len(sub):
                        tot_tt = to_int(sub[col_tt])
                    if col_sp is not None and col_sp < len(sub):
                        tot_sp = to_int(sub[col_sp])
                    found_total = True
                    break
            if found_total:
                break

        if found_total:
            raw_outbound.append({
                'Tanggal': tgl.date(), 'Gudang': gudang,
                'tt': tot_tt, 'sp': tot_sp,
            })

df_out = pd.DataFrame(raw_outbound)
if df_out.empty:
    raise SystemExit("Tidak ada data outbound terbaca. Cek nama sheet & format tanggal.")

df_out = df_out.drop_duplicates(subset=['Tanggal', 'Gudang', 'tt', 'sp'])

# Peringatan kalau ada tanggal+gudang yang muncul 2x dengan angka beda (bisa double count)
dup = df_out[df_out.duplicated(subset=['Tanggal', 'Gudang'], keep=False)]
if not dup.empty:
    print("   ! PERINGATAN: ada tanggal+gudang dengan lebih dari 1 angka, cek manual:")
    print(dup.sort_values(['Tanggal', 'Gudang']).to_string(index=False))

# Blok 'Indonesia' biasanya total semua gudang -> jangan dijumlah bareng gudang
# (kalau dijumlah, sent jadi 2x lipat). Dipakai hanya bila tanggal itu tidak punya gudang.
tgl_punya_gudang = set(df_out.loc[df_out['Gudang'] != 'Indonesia', 'Tanggal'])
df_out = df_out[(df_out['Gudang'] != 'Indonesia') | (~df_out['Tanggal'].isin(tgl_punya_gudang))]
df_out = df_out.groupby(['Tanggal', 'Gudang'], as_index=False)[['tt', 'sp']].sum()
print(f"   {len(df_out)} baris outbound, {df_out['Tanggal'].nunique()} tanggal, "
      f"gudang: {sorted(df_out['Gudang'].unique())}")

# ------------------------------------------------------------------------------
# 3. RTS TIKTOK & SHOPEE
# ------------------------------------------------------------------------------
print("3. Membaca RTS TikTok & Shopee...")


def load_sheets(prefix):
    frames = []
    for ws in sh_rts.worksheets():
        if ws.title.strip().lower().startswith(prefix):
            raw = ws.get_all_values()
            if len(raw) > 1:
                frames.append(pd.DataFrame(raw[1:], columns=[str(c).strip() for c in raw[0]]))
                print(f"   sheet '{ws.title}': {len(raw) - 1} baris")
    if not frames:
        raise SystemExit(f"Tidak ada sheet RTS dengan awalan '{prefix}'.")
    return pd.concat(frames, ignore_index=True)


df_tt = load_sheets(PREFIX_RTS_TIKTOK)
df_sp = load_sheets(PREFIX_RTS_SHOPEE)

tt = pd.DataFrame({
    'Platform': 'TikTok',
    'Tanggal': pd.to_datetime(get_column(df_tt, KOLOM_TGL_TIKTOK), errors='coerce', format='mixed').dt.date,
    'Gudang': get_column(df_tt, ['Warehouse Name'], fallback_idx=38).map(norm_gudang),
    'Provinsi': get_column(df_tt, ['Province', 'Provinsi']).astype(str).str.strip(),
    'Kota': get_column(df_tt, ['Regency and City', 'City and Regency', 'Regency/City']).astype(str).str.strip(),
})
sp = pd.DataFrame({
    'Platform': 'Shopee',
    'Tanggal': pd.to_datetime(get_column(df_sp, KOLOM_TGL_SHOPEE), errors='coerce', format='mixed').dt.date,
    'Gudang': get_column(df_sp, ['Nama Gudang', 'Gudang'], fallback_idx=27).map(norm_gudang),
    'Provinsi': get_column(df_sp, ['Provinsi', 'Province']).astype(str).str.strip(),
    'Kota': get_column(df_sp, ['Kota/Kabupaten', 'Kota / Kabupaten', 'Kota', 'Kabupaten']).astype(str).str.strip(),
})

df_rts = pd.concat([tt, sp], ignore_index=True)
n_awal = len(df_rts)
df_rts = df_rts.dropna(subset=['Tanggal', 'Gudang'])   # gudang tak dikenal / tanggal invalid dibuang
print(f"   {len(df_rts)} baris RTS valid dari {n_awal} (sisanya tanggal/gudang tidak terbaca)")

# Agregasi supaya file kecil
rts_agg = (df_rts.groupby(['Tanggal', 'Platform', 'Gudang', 'Provinsi', 'Kota'])
           .size().reset_index(name='n'))

# ------------------------------------------------------------------------------
# 4. EXPORT JSON
# ------------------------------------------------------------------------------
payload = {
    'meta': {
        'generated': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M'),
        'rts_start': str(df_rts['Tanggal'].min()),
        'rts_end': str(df_rts['Tanggal'].max()),
    },
    'outbound': [
        {'d': str(r.Tanggal), 'g': r.Gudang, 'tt': int(r.tt), 'sp': int(r.sp)}
        for r in df_out.itertuples()
    ],
    'rts': [
        {'d': str(r.Tanggal), 'p': r.Platform, 'g': r.Gudang,
         'prov': r.Provinsi, 'kota': r.Kota, 'n': int(r.n)}
        for r in rts_agg.itertuples()
    ],
}

with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False)

print(f"\nSelesai. Data ditulis ke {OUTPUT_PATH}")
