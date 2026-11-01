# 🤖 Bot Trading Saham Indonesia (IDX / BEI) - Edisi Pro

Aplikasi bot trading kuantitatif modular untuk Bursa Efek Indonesia (IDX) yang berfokus pada strategi **Momentum & Volume Spike Accumulation**. Dilengkapi dengan fitur **Screener Otomatis**, **Backtesting Engine Historis**, **Simulasi Akun Paper Trading (Virtual Rupiah)**, **Grafik Candlestick Visual**, **Price Alert**, **Deteksi Bandarmology**, dan integrasi **Bot Telegram Interaktif 2-Arah**.

---

## 🌟 Fitur-Fitur Unggulan

1. **🌐 Screener Akumulasi Smart Money & Bandar Hunter (`/akumulasi` / `/bandar`)**:
   - Memindai seluruh watchlist saham IDX untuk mendeteksi emiten yang sedang diakumulasi masif oleh bandar/institusi (*Big Inflow*).
   - Menyaring berdasarkan **Skor Akumulasi (≥60 s/d 100)**, **Chaikin Money Flow (CMF > 0)**, **OBV Uptrend**, dan lonjakan volume.

2. **🗺️ Radar Rotasi Sektor & Heatmap IDX (`/sektor` / `/heatmap`)**:
   - Menghitung performa harian rata-rata di 8 sektor utama BEI (Perbankan, Energi, Bahan Baku, Industri, Konsumsi, Teknologi, Properti, Ritel).
   - Menampilkan sektor pemimpin (*Leader*), sektor tertinggal (*Laggard*), dan saham penggerak utama (*Top Mover*) di tiap sektor untuk mendeteksi rotasi aliran dana pasar.

3. **🚨 Radar Real-Time Lonjakan Volume Breakout (`/breakout`) & Auto Volume Alert**:
   - Mendeteksi lonjakan volume mendadak (*RVol ≥ 2.0x / 3.0x*) yang disertai kenaikan harga (*≥ +2.0%*) dan breakout resistensi 20 hari.
   - Dilengkapi **Auto Volume Breakout Alert** yang otomatis mengirim notifikasi instan ke Telegram saat jam bursa sedang aktif (09:00 - 16:00 WIB).

4. **📊 Grafik Candlestick Visual Otomatis (`/chart <KODE>`)**:
   - Menghasilkan dan mengirimkan gambar grafik candlestick berlatar gelap (*dark mode*) langsung ke Telegram.
   - Dilengkapi garis tren **MA20 & MA50**, garis **Entry**, batas hijau **Target TP (+5%)**, batas merah **Stop Loss (-3%)**, serta bar volume.

2. **🚨 Alarm Pengingat Harga / Price Alert (`/alert <KODE> <HARGA>`)**:
   - Pasang alarm harga untuk saham incaran (contoh: `/alert BBCA 6000`).
   - Bot otomatis memantau harga setiap 30 detik dan membunyikan alarm instan begitu target tersentuh!

3. **🪙 Pasar Cryptocurrency Global (`/crypto`)**:
   - Memantau harga real-time & pergerakan 24 jam untuk koin teratas: **BTC**, **ETH**, **SOL**, **BNB**, **XRP**, **DOGE**, **ADA**, **AVAX**.
   - Analisis teknikal & trading plan lengkap dengan format USD: `/plan BTC`, `/chart BTC`, `/news BTC`.

4. **🌍 Pasar Forex & Logam Mulia Dunia (`/forex`)**:
   - Memantau komoditas global: **Gold / Emas (XAU/USD)**, **Silver / Perak (XAG/USD)**, **Crude Oil (WTI)**.
   - Memantau pasangan mata uang utama: **EUR/USD**, **GBP/USD**, **USD/JPY**, **AUD/USD**.
   - Dilengkapi chart candlestick & Trading Plan: `/chart XAU`, `/plan EURUSD`.

5. **🌐 Analisis Arus Dana & Bandarmology (`/flow <KODE>`)**:
   - Mendeteksi aliran dana pemain besar (*Smart Money / Bandar*):
     - **Chaikin Money Flow (CMF 20)**: Mengukur tekanan akumulasi/distribusi.
     - **On-Balance Volume (OBV)** & arah tren akumulasi.
     - **Skor Akumulasi (0 - 100)**: Menentukan status *Akumulasi Masif*, *Netral*, atau *Distribusi/Dumping*.

6. **🎯 Screener ARA Hunter (`/ara`)**:
   - Memindai saham-saham yang terkunci ARA (*Auto Rejection Atas*) atau melesat mendekati batas ARA (+20%, +25%, +35% sesuai aturan IDX).
   - Menghitung sisa jarak persentase dan sisa tick fraksi harga menuju ARA, serta batas ARB.

7. **🌅 Screener BSJP / Beli Sore Jual Pagi (`/bsjp`)**:
   - Strategi khusus mencari saham dengan pola candle Marubozu (harga ditutup di dekat High harian), akumulasi volume sehat, dan kenaikan stabil (+1% s/d +15%).
   - Dilengkapi panduan jam entry sore (15:30 - 15:58 WIB), target profit cepat pagi hari (+2.5% s/d +4.5% pada pukul 09:00 - 09:15 WIB), dan batas cut loss ketat (-2.0%).

8. **📰 Berita Saham & Pasar Modal Terkini (`/news [KODE]`)**:
   - Menarik 5 berita finansial terhangat secara real-time dari portal berita bisnis terpercaya.
   - Mendukung pencarian berita saham (`/news BBCA`), crypto (`/news BTC`), dan emas dunia (`/news XAU`).

9. **🔥 Pemantau Top Movers IDX (`/topmovers`, `/topgain`, `/toploss`)**:
   - Memantau pergerakan saham likuid paling agresif di bursa:
     - **`/topgain`**: Daftar saham dengan persentase kenaikan tertinggi (*Top Gainers*).
     - **`/toploss`**: Daftar saham dengan penurunan terdalam (*Top Losers*).
     - **`/topmovers`**: Rangkuman Top Gainers, Losers, dan emiten dengan nilai transaksi (*Turnover*) terbesar.

10. **⭐ Watchlist Saham Favorit Pribadi (`/watch` & `/watchlist`)**:
   - Simpan saham-saham pilihan pribadi Anda secara persisten.
   - Ketik `/watchlist` untuk memindai hanya saham-saham favorit Anda.

11. **🧮 Kalkulator Money Management & Lot Sizing (`/calc <KODE> <RISIKO>`)**:
   - Hitung ukuran lot ideal berdasarkan risiko rupiah yang siap Anda tanggung (contoh: `/calc BBCA 500000`).

12. **⏰ Auto-Scheduler Jam Buka Bursa (WIB)**:
   - Bot otomatis menyaring saham dan mengirim update ke Telegram setiap sesi bursa IDX dibuka (09:05 WIB, 13:35 WIB, 16:05 WIB).

13. **💼 Paper Trading Virtual Account (Rp 50.000.000)**:
   - Simulasi jual beli saham dengan aturan resmi BEI (**1 Lot = 100 lembar**), fee beli 0.15%, fee jual 0.25%, dan pengawalan otomatis Trailing Stop 2%.

---

## 📱 Daftar Perintah Chat Telegram (@bilnabil_bot)

| Perintah | Fungsi | Contoh Penggunaan |
| :--- | :--- | :--- |
| **`/start`** / **`/help`** | Buka menu navigasi & tombol klik interaktif | `/start` |
| **`/akumulasi`** | Screener Akumulasi Smart Money & Bandar Hunter | `/akumulasi` atau `/bandar` |
| **`/sektor`** / **`/heatmap`** | Radar Rotasi Sektor & Heatmap IDX (8 Sektor) | `/sektor` atau `/heatmap` |
| **`/breakout`** | Radar Lonjakan Volume Breakout & Resistance Spike | `/breakout` |
| **`/ai <KODE>`** | Analisis Cerdas AI (Teknikal + Bandar + Berita) | `/ai BBCA` atau `/ai BTC` |
| **`/ta <KODE>`** | Meteran Konsensus Teknikal TradingView Style | `/ta BBCA` atau `/ta XAU` |
| **`/bow`** | Screener Buy on Weakness & Rebound Support | `/bow` |
| **`/fund <KODE>`** | Profil Fundamental, PER, PBV & Dividen | `/fund BBCA` |
| **`/kalender`** | Jadwal Cum-Date Dividen & Laporan Keuangan IDX | `/kalender` |
| **`/scan`** | Pindai saham IDX dengan lonjakan volume & SL/TP | `/scan` |
| **`/ara`** | Screener ARA Hunter (Terkunci & Menuju ARA) | `/ara` |
| **`/bsjp`** | Screener Beli Sore Jual Pagi (Target Cuan Pagi) | `/bsjp` |
| **`/crypto`** | Ringkasan harga & pergerakan 24 jam koin crypto | `/crypto` |
| **`/forex`** | Ringkasan pasar forex & logam mulia (Gold, Oil) | `/forex` |
| **`/plan <KODE>`** | Lihat Trading Plan lengkap (Buy, SL, TP, RRR) | `/plan BBCA` atau `/plan BTC` |
| **`/chart <KODE>`** | Kirim grafik candlestick + MA + TP/SL | `/chart BBCA` atau `/chart XAU` |
| **`/price <KODE>`** | Cek harga instan saham, crypto, emas | `/price BTC` atau `/price XAU` |
| **`/news [KODE]`** | Berita finansial terkini emiten, crypto, emas | `/news BBCA` atau `/news BTC` |
| **`/topmovers`** | Ringkasan Top Gainers, Losers & Nilai Transaksi | `/topmovers` |
| **`/topgain`** | Daftar saham kenaikan tertinggi hari ini | `/topgain` |
| **`/toploss`** | Daftar saham penurunan terdalam hari ini | `/toploss` |
| **`/alert <KODE> <HARGA>`**| Pasang alarm pengingat harga otomatis | `/alert BBCA 6000` |
| **`/alerts`** | Lihat daftar alarm harga yang sedang aktif | `/alerts` |
| **`/delalert <ID>`** | Hapus alarm harga tertentu | `/delalert 1` |
| **`/flow <KODE>`** | Analisis arus dana asing & Bandarmology | `/flow BMRI` |
| **`/calc <KODE> <RISIKO>`**| Kalkulator ukuran lot ideal sesuai batas rugi | `/calc BBCA 500000` |
| **`/watch <KODE>`** | Tambah saham ke watchlist favorit pribadi | `/watch ANTM` |
| **`/unwatch <KODE>`** | Hapus saham dari watchlist | `/unwatch ANTM` |
| **`/watchlist`** | Pantau khusus saham-saham favorit Anda | `/watchlist` |
| **`/buy <KODE> <LOT> [TP] [SL]`** | Beli saham simulasi (kustom TP/SL opsional) | `/buy BBCA 5 5 3` |
| **`/sell <KODE> [LOT]`**| Jual saham dari portofolio simulasi | `/sell BBCA 5` |
| **`/portfolio`** | Cek saldo kas tunai & floating PnL saham | `/portfolio` |
| **`/update`** | Paksa kirim update kondisi bursa saat ini | `/update` |

---

## 🚀 Cara Menjalankan

### Menjalankan Web Dashboard Interaktif (Modern Dark Mode Terminal):
```powershell
python main.py --web
# atau
uvicorn web_app.main:app --reload --host 0.0.0.0 --port 8000
```
*Buka browser di **http://localhost:8000** untuk mengakses terminal trading modern (Interactive TradingView Lightweight Candlestick Charts, Bandar Screener, Volume Breakout Radar, Sektor Heatmap, Crypto & Forex, Simulasi Paper Trading, dan Control Panel Alarm).*

### Menjalankan Bot Telegram Interaktif:
```powershell
python bot_telegram.py
```
*Bot akan aktif mendengarkan perintah dari Telegram, mengecek alarm harga setiap 30 detik, dan otomatis mengirim laporan saat bursa dibuka (09:05 & 13:35 WIB).*

### Menjalankan CLI Interaktif di Laptop:
```powershell
python main.py
```

### Menjalankan Screener Manual:
```powershell
python main.py --scan
```
