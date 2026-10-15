# Signal Engine — Spesifikasi Logika Trading

Dokumen ini adalah **sumber kebenaran** untuk indikator, skor, filter, dan risk. Semua parameter default di sini harus muncul di `config/settings.example.yaml` agar bisa diubah tanpa ubah kode.

Konvensi:
- `df` = DataFrame candle **closed** (kolom `open, high, low, close, volume, taker_buy_volume*`), indeks waktu UTC, urut naik.
- Semua indikator **hanya** memakai data sampai bar `t` (tanpa lookahead). Pivot/divergensi yang butuh bar kanan dikonfirmasi `k` bar kemudian dan baru boleh dipakai di bar `t+k`.
- Setiap indikator mengembalikan `IndicatorResult` (lihat `BLUEPRINT.md` §5.2). `strength` di 0..1.
- `*` `taker_buy_volume` tersedia di kline Binance (field index 9). Untuk sumber OANDA/PAXG-spot tanpa taker volume, kolom kosong → CVD diganti OBV.

---

## 1. Timeframe

| Peran | TF | Dipakai untuk |
|---|---|---|
| Entry | **M15** | Semua 10 indikator, trigger sinyal |
| Konfirmasi | **H1** | EMA Ribbon + Supertrend + RSI harus tidak berlawanan |
| Bias/Macro | **H4 & D1** | Filter tren besar (EMA200 H4, Supertrend D1) |

Sinyal dievaluasi setiap candle **M15 close**. Analisis H1/H4 juga dihitung saat close-nya untuk ditampilkan.

---

## 2. Kapabilitas per simbol

| Indikator | Crypto (Binance Futures) | Gold — `XAUUSDT` perp (default) | Gold — fallback PAXG spot / OANDA |
|---|---|---|---|
| 1 VWAP | ✅ | ✅ | ✅ (OANDA: tick volume) |
| 2 EMA Ribbon | ✅ | ✅ | ✅ |
| 3 Supertrend | ✅ | ✅ | ✅ |
| 4 RSI Divergence | ✅ | ✅ | ✅ |
| 5 Bollinger Bands | ✅ | ✅ | ✅ |
| 6 CVD / OBV | CVD (taker buy) | CVD (taker buy) | PAXG: CVD · OANDA: OBV |
| 7 Funding & OI | ✅ | ✅ (bila endpoint OI tersedia untuk simbol ini) | NA |
| 8 Order Book Imbalance | ✅ (live only) | ✅ (live only, bobot ×0,5 — likuiditas lebih tipis) | PAXG: ✅ · OANDA: NA |
| 9 LightGBM | ✅ setelah model dilatih | ✅ (training dgn histori Dukascopy bila histori Binance < 12 bln) | ✅ |
| 10 Sentiment | Fear&Greed + Long/Short ratio | Long/Short ratio saja (F&G crypto tidak relevan) | NA |

Kapabilitas ditentukan otomatis saat start dari respons endpoint (bukan di-hardcode): bila endpoint OI/LS untuk simbol mengembalikan error/kosong → indikator terkait NA.

Indikator `NA` dikeluarkan dari penyebut skor (bobot dinormalisasi ulang). Jika total bobot tersedia < 50% → verdict maksimal `LONG/SHORT` (tidak boleh `STRONG`).

---

## 3. Spesifikasi 10 Indikator (Strategi A: Konfluensi-10)

### 1) VWAP — kategori `order_flow`
- Session VWAP, reset 00:00 UTC. `tp = (h+l+c)/3`, `vwap = Σ(tp·v)/Σv`. Deviasi standar tertimbang volume → band ±1σ, ±2σ.
- `z = (close − vwap) / σ`, `slope = vwap_t − vwap_{t−4}`.
- BULL: `z > 0.25` dan `slope > 0`. BEAR: `z < −0.25` dan `slope < 0`. Selain itu NEUTRAL.
- Overextended: `|z| > 2` → state tetap, `strength` dikali 0.5 (rawan mean-reversion), reason menyebut "terlalu jauh dari VWAP".
- `strength = min(|z|/2, 1)`.
- Catatan: 4 bar pertama setelah reset → NEUTRAL (VWAP belum stabil).

### 2) EMA Ribbon — `trend`
- EMA 8, 13, 21, 34, 55 pada close.
- BULL: EMA tersusun naik sempurna (8>13>21>34>55) dan `close > EMA8`. BEAR: kebalikannya.
- Susunan parsial (≥4 dari 4 pasangan berurutan benar searah) → state searah dengan `strength` 0.5. Selain itu NEUTRAL.
- `strength` penuh = `clip((EMA8−EMA55)/ATR14 / 2, 0, 1)` (lebar ribbon relatif volatilitas).

### 3) Supertrend — `trend`
- ATR periode 10 (Wilder), multiplier 3.0, sumber `hl2`.
- State = arah supertrend. `strength = 0.6 + 0.4·[flip terjadi ≤ 3 bar lalu dan searah]` — flip baru memberi konfirmasi tambahan.
- Jarak `close` ke garis supertrend < 0.3·ATR → `strength` × 0.5 (mudah tembus).

### 4) RSI Divergence — `momentum`
- RSI 14 (Wilder). Pivot dengan `left=5, right=3` (pivot dikonfirmasi 3 bar kemudian). Rentang antar pivot 5–60 bar.
- Bullish regular divergence: low harga lebih rendah, low RSI lebih tinggi, RSI pivot < 40. Bearish regular: high harga lebih tinggi, high RSI lebih rendah, RSI pivot > 60. Divergensi valid 10 bar setelah konfirmasi.
- Tanpa divergensi: BULL bila RSI cross naik 50 dalam 3 bar dan RSI < 70; BEAR bila cross turun 50 dan RSI > 30; RSI > 75 → BEAR lemah (strength 0.3, "overbought"); RSI < 25 → BULL lemah. Selain itu NEUTRAL.
- `strength`: divergensi = 0.9, cross 50 = 0.6.

### 5) Bollinger Bands — `momentum`
- SMA 20, 2σ. `%B = (close−lower)/(upper−lower)`, `bw = (upper−lower)/mid`.
- Squeeze: `bw` ≤ persentil 20 dari 120 bar terakhir.
- BULL: (a) keluar squeeze dengan close > upper (breakout, strength 0.8), atau (b) tren H1 bullish dan close memantul dari mid/lower (`%B` naik dari < 0.2 ke > 0.3, strength 0.5).
- BEAR: simetris. Selain itu NEUTRAL (termasuk saat squeeze berlangsung — reason: "Volatilitas menyempit, tunggu breakout").

### 6) CVD / OBV — `order_flow`
- Bila ada taker volume (semua sumber Binance): `delta = 2·taker_buy_volume − volume`; `cvd = cumsum(delta)` direset tiap 00:00 UTC.
- Tanpa taker volume (OANDA): `obv` dari volume yang tersedia.
- `cvd_slope` = slope regresi linier 20 bar dinormalisasi oleh std 100 bar; `price_slope` sama untuk close.
- BULL: `cvd_slope > 0.5` dan `price_slope ≥ 0` (pembeli agresif mengonfirmasi). BEAR: kebalikan.
- Divergensi (harga naik tapi CVD turun signifikan) → state berlawanan dengan arah harga, strength 0.6, reason "Kenaikan tidak didukung pembeli agresif".
- `strength = min(|cvd_slope|/2, 1)`.

### 7) Funding & Open Interest — `derivatives` (semua simbol Binance Futures, termasuk XAUUSDT)
- Funding rate terkini (`lastFundingRate`), OI perubahan 4 jam (`ΔOI%`), perubahan harga 4 jam (`ΔP%`).
- Matriks:

| ΔP | ΔOI | Interpretasi | State |
|---|---|---|---|
| naik | naik (> +1%) | Long baru masuk | BULL |
| naik | turun (< −1%) | Short covering, rapuh | NEUTRAL |
| turun | naik | Short baru masuk | BEAR |
| turun | turun | Long likuidasi/keluar | NEUTRAL |

- Override funding ekstrem: funding > +0.05% per 8 jam → kurangi BULL jadi NEUTRAL ("long terlalu ramai, rawan long squeeze"); funding < −0.03% sementara harga naik → BULL strength +0.2 (potensi short squeeze).
- `strength = min(|ΔOI%|/5, 1)`.
- Backtest: OI history Binance hanya ~30 hari → di luar itu NA.

### 8) Order Book Imbalance — `microstructure` (sumber Binance, `live_only=True`)
- Stream depth20. Ambil level dalam ±0.5% dari mid. `obi = (Σbid − Σask)/(Σbid + Σask)`.
- Haluskan EMA 60 detik. Snapshot saat candle close.
- BULL `obi > 0.15`, BEAR `obi < −0.15`, selain itu NEUTRAL. `strength = min(|obi|/0.4, 1)`.
- Bobot kecil (mudah dimanipulasi/spoofing). Tidak dipakai di backtest.

### 9) LightGBM — `ml`
- **Label (triple-barrier):** dari close bar `t`, dalam `N=16` bar M15 ke depan: +1 bila high menyentuh `close + 1.5·ATR` lebih dulu, −1 bila low menyentuh `close − 1.5·ATR` lebih dulu, 0 bila tidak keduanya. Latih dua model biner: P(up-barrier) dan P(down-barrier) — atau satu multikelas.
- **Fitur:** return 1/4/16 bar, ATR%, nilai mentah semua indikator 1–7 & 10 (z VWAP, spread ribbon/ATR, arah supertrend, RSI, %B, bw, cvd_slope, funding, ΔOI), jam UTC (sin/cos), hari, jarak ke EMA200 H4, state H1. **Tanpa** fitur orderbook (tidak ada histori).
- **Training:** minimal 12 bulan data M15; walk-forward split berbasis waktu (tanpa shuffle), purge 16 bar di batas train/test. Hyperparameter default: `num_leaves=31, learning_rate=0.03, n_estimators=600, min_child_samples=50, subsample=0.8, colsample_bytree=0.8`, early stopping di validation.
- **Output ke engine:** `p_up`, `p_down`. BULL bila `p_up ≥ 0.58` dan `p_up − p_down ≥ 0.15`; BEAR simetris; else NEUTRAL. `strength = clip((p − 0.5)/0.25, 0, 1)`.
- Model registry: simpan file + metrik (AUC, precision@threshold out-of-sample). Model hanya **diaktifkan** bila AUC OOS ≥ 0.55; kalau tidak → NA dan UI menyebut "model belum cukup akurat".
- Retrain otomatis mingguan (Minggu 02:00 WIB) + tombol manual.

### 10) Sentiment — `sentiment`
- Crypto: Fear & Greed Index (harian) — kontrarian: ≤ 20 → BULL (0.5), ≥ 80 → BEAR (0.5). Long/Short account ratio global Binance: > 2.5 → BEAR (0.4), < 0.7 → BULL (0.4). Gabungkan: rata-rata bertanda; |nilai| < 0.2 → NEUTRAL.
- Gold (XAUUSDT): hanya Long/Short account ratio (kontrarian, ambang sama). F&G crypto tidak dipakai. Sumber tanpa LS ratio → NA.

---

## 4. Skor Konfluensi

```
s_i = +1 (BULL) | −1 (BEAR) | 0 (NEUTRAL) ; NA dibuang
score = 100 · Σ(w_i · s_i · strength_i) / Σ(w_i)   # Σ hanya atas indikator yang tersedia
```

### Bobot default (total 100)
| Kategori | Indikator | Bobot |
|---|---|---|
| Trend (25) | EMA Ribbon | 12 |
| | Supertrend | 13 |
| Momentum (15) | RSI Divergence | 8 |
| | Bollinger | 7 |
| Order flow (25) | VWAP | 12 |
| | CVD/OBV | 13 |
| Derivatif (10) | Funding & OI | 10 |
| Mikro (5) | Order Book | 5 |
| ML (15) | LightGBM | 15 |
| Sentimen (5) | Sentiment | 5 |

Bobot dapat dikalibrasi lewat menu Jurnal (akurasi per indikator) atau walk-forward backtest — **perubahan bobot harus dicatat versi-nya** (`weights_version`) di setiap sinyal.

### Suara kategori
Untuk tiap kategori: jumlahkan `w·s·strength`; > 0 → BULL, < 0 → BEAR, = 0 → NEUTRAL.

### Verdict
| Verdict | Syarat (semua harus terpenuhi) |
|---|---|
| **STRONG_LONG** | `score ≥ 55` · ≥ 3 kategori BULL · kategori Trend = BULL · konfirmasi H1 tidak BEAR · Macro filter PASS · bobot tersedia ≥ 50% |
| **LONG** (pantau) | `score ≥ 30` dan kategori Trend tidak BEAR |
| **NEUTRAL** | lainnya |
| **SHORT** / **STRONG_SHORT** | simetris |

Konfirmasi H1 = mayoritas dari {EMA Ribbon H1, Supertrend H1, RSI H1 di sisi 50} searah atau netral.

Hanya `STRONG_*` yang memicu paper trade & notifikasi push. `LONG/SHORT` muncul di UI dan bisa diaktifkan notifikasinya di setelan.

**Cooldown:** setelah sinyal `STRONG` pada simbol X, sinyal searah berikutnya di X diabaikan 4 bar; sinyal berlawanan boleh (dan menutup posisi paper yang ada).

---

## 5. Macro Filter (gerbang — semua harus PASS)

| # | Cek | Default | Gagal bila |
|---|---|---|---|
| M1 | Tren besar | H4 close vs EMA200 H4, Supertrend D1 | Kedua-duanya berlawanan dengan arah sinyal |
| M2 | Berita | USD impact High | Ada event dalam −30 / +30 menit dari sekarang |
| M3 | Volatilitas | ATR14 M15 persentil 30 hari | < P10 (pasar mati) atau > P95 (terlalu liar) |
| M4 | Sesi (Gold) | Kalender sesi FX (`core/time.py`) | Pasar emas tutup (Jumat 21:00 UTC → Minggu 22:00 UTC, sesuaikan DST AS), atau 20:45–01:15 UTC (rollover, spread broker melebar) |
| M5 | Likuiditas | spread best bid/ask dari orderbook Binance | > 2× median spread 24 jam (tanda pasar tipis) |
| M6 | Kesegaran data | umur candle terakhir, sumber aktif | > 2× durasi TF, WS putus, atau Gold sedang memakai sumber fallback < 60 menit (indikator belum stabil) |
| M7 | Funding ekstrem (crypto) | `|funding|` | > 0.1% per 8 jam |
| M8 | Risk paper | daily loss / posisi terbuka | daily loss limit tercapai atau sudah ada posisi di simbol |

`MacroFilterResult = {passed: bool, checks: [{id, passed, detail}]}`. Sinyal yang gagal tetap disimpan dengan `blocked_by` untuk analisis "sinyal terblokir".

---

## 6. Strategi B — Triple-EMA (dari video Ruang Scalper, diadaptasi ke intraday)

- EMA cepat **9** (close), EMA tengah **21 applied to Open** (sesuai video), EMA lambat **50** (close). Semua configurable.
- LONG: EMA9 cross ke atas EMA21(open) pada bar close, `close > EMA50`, EMA50 naik (slope 5 bar > 0), dan di H1 `EMA9 > EMA21 > EMA50`. SHORT simetris.
- Filter: sama dengan Macro Filter M2–M6.
- Exit: SL = di bawah swing low 10 bar terakhir atau 1.2·ATR (yang lebih dekat tapi ≥ 0.8·ATR); TP = **1R** (default sesuai video, RR 1:1) — configurable `rr_target`.
- Dijalankan paralel dengan Strategi A, paper trade terpisah (`strategy="triple_ema"`) agar winrate kedua strategi bisa dibandingkan di Jurnal. Sinyal B **tidak** dikirim ke Telegram kecuali diaktifkan; bila A dan B searah pada bar yang sama, pesan Telegram A diberi tag "✅ Dikonfirmasi Triple-EMA".

---

## 7. Risk Management (Strategi A)

```
ATR = ATR14 M15
SL  = entry − 1.5·ATR (LONG), atau di bawah swing low 10 bar bila lebih jauh tapi ≤ 2.5·ATR
R   = |entry − SL|
TP1 = entry + 1.0·R   (tutup 50%, SL → breakeven)
TP2 = entry + 2.0·R   (tutup sisa)
size = (equity · risk_pct) / R            # dalam unit aset (paper trading)
```

### 7b. Trade Ticket (eksekusi manual)
- Level dari rumus di atas, dibulatkan ke tick size simbol sumber.
- **Zona entry** = entry ± 0,1·ATR. Ticket berlaku `ticket_valid_bars` (default 3 bar M15) atau batal bila harga keluar zona > 0,5·ATR searah (ketinggalan) / menyentuh SL sebelum dieksekusi.
- **Jarak relatif** selalu disertakan: `SL −14,5 (1,5×ATR)`, `TP1 +14,5 (1R)` → user bisa memasang di broker manapun.
- **Offset broker:** `level_broker = level_sumber + offset`, offset dari kalibrasi user (berlaku 30 mnt; setelah itu ticket memakai harga sumber dan menampilkan peringatan "kalibrasi kedaluwarsa").
- **Lot (profil broker di `settings.brokers`):** `lot = floor_to_step(risk_usd / (|entry−SL| × contract_size))`. Bila `< min_lot` → tampilkan lot minimum + peringatan risiko aktual. Untuk crypto di broker CFD, `contract_size` sesuai profil (default 1).
- **Invalidasi:** level struktur terdekat yang membatalkan tesis (garis Supertrend M15, atau swing low/high 10 bar) — ditulis sebagai kondisi close, bukan hanya harga.
- Ticket menyimpan snapshot `Analysis`, sehingga hasil eksekusi nyata bisa dianalisis per indikator seperti paper trade.

### Kenapa bukan cuma winrate
Laporan selalu menampilkan **expectancy (R)** dan **profit factor** di samping winrate. Winrate 70% dengan RR 1:0.3 tetap rugi. Target sehat: winrate ≥ 50% dengan expectancy > +0.2R setelah biaya, minimal 100 trade.

---

## 8. Komentar AI — Prompt & Schema

### System prompt (ringkas, simpan di `ai/prompts.py`)
```
Kamu adalah analis trading senior yang menulis dalam Bahasa Indonesia yang lugas.
Kamu menerima hasil analisis teknikal TERSTRUKTUR (JSON). Tugasmu: menjelaskan konfluensi,
menilai kualitas setup, menyebut risiko, dan memberi skenario. Aturan:
1. Hanya gunakan angka yang ada di input. Jangan mengarang level harga atau data.
2. Jangan mengubah verdict engine; boleh menyatakan setuju/ragu beserta alasannya.
3. Sebut indikator yang bertentangan dan apa artinya.
4. Selalu sertakan kondisi invalidasi.
5. Maksimal 120 kata untuk 'ringkasan'. Tanpa janji profit.
```

### Response schema (Pydantic → `response_schema` Gemini)
```python
class AIComment(BaseModel):
    ringkasan: str
    bias: Literal["bullish","bearish","netral"]
    keyakinan: Literal["rendah","sedang","tinggi"]
    setuju_dengan_engine: bool
    alasan_utama: list[str]      # 2-4 butir
    risiko: list[str]            # 1-3 butir
    skenario_bullish: str
    skenario_bearish: str
    level_penting: list[float]   # harus ada di input (vwap, band, ema, supertrend, sl/tp, swing)
    invalidasi: str
    saran_manajemen: str
```

### Payload input (contoh dipangkas)
```json
{"symbol":"ETHUSDT","tf":"M15","bar_time":"2026-10-15T07:00:00+07:00","price":2650.4,
 "verdict":"STRONG_LONG","score":61.2,"counts":{"BULL":6,"NEUTRAL":3,"BEAR":1,"NA":0},
 "indicators":[{"key":"vwap","state":"BULL","values":{"vwap":2631.2,"z":0.9},"reason":"..."}],
 "macro":{"passed":true,"checks":[...]},
 "plan":{"entry":2651.0,"sl":2622.5,"tp1":2679.5,"tp2":2708.0},
 "htf":{"h1":"BULL","h4":"BULL","d1":"NEUTRAL"},
 "news_24h":[{"time":"...","title":"CPI m/m","impact":"High"}],
 "stats_30d_similar":{"trades":23,"winrate":0.57,"expectancy_r":0.31},
 "strategy_b":{"state":"LONG"}}
```

### Konfigurasi Gemini
- SDK `google-genai`; model dari `GEMINI_MODEL` di `.env` (default `gemini-3.8-flash` — **cek daftar model aktif di Google AI Studio**, nama model Gemini sering berganti/di-deprecate). Fallback model `GEMINI_FALLBACK_MODEL`.
- `temperature=0.3`, `response_mime_type="application/json"`, `response_schema=AIComment`, timeout 30 dtk, retry 2× untuk 429/5xx dengan backoff.
- Rate limit dari `.env` (`AI_MAX_RPM`, `AI_MAX_RPD`). Dengan 4 simbol & hanya sinyal STRONG + on-demand, estimasi < 50 panggilan/hari.

---

## 9. Test Wajib
- Fixture: CSV 2000 bar ETHUSDT M15 dan XAUUSDT M15 dari Binance (diunduh sekali, disimpan di `backend/tests/fixtures/`).
- Test ticket: pembulatan tick size, lot floor & peringatan min lot, offset broker & kedaluwarsanya, ticket expired.
- Test sesi Gold: sinyal di akhir pekan/rollover diblok M4 (termasuk transisi DST).
- Nilai referensi EMA/RSI/ATR/Bollinger/Supertrend dicocokkan dengan TradingView pada 5 timestamp (toleransi 0.1%) — catat nilai referensi di `tests/fixtures/reference_values.json`.
- **Test anti-lookahead:** hitung indikator pada `df[:t]` dan `df[:t+50]`; nilai di bar `t` harus identik.
- Test scoring: kasus semua BULL → 100; NA dibuang; bobot tersedia < 50% → tidak STRONG.
- Test macro filter tiap cek dengan data sintetis.
- Test paper trader: TP1→BE→TP2, SL & TP satu candle (SL dulu), biaya.
- Test AI: provider di-mock; validasi angka AI yang tidak ada di input → fallback template.
