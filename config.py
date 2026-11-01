"""
Konfigurasi Bot Trading Saham Indonesia (IDX / BEI)
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Muat environment variables dari .env jika ada
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)


# ==============================================================================
# 1. ATURAN PASAR BURSA EFEK INDONESIA (IDX)
# ==============================================================================
LOT_SIZE = 100                  # 1 Lot = 100 Lembar saham
BUY_FEE_PCT = 0.0015            # Biaya Beli Sekuritas + IDX + PPN (~0.15%)
SELL_FEE_PCT = 0.0025           # Biaya Jual Sekuritas + IDX + PPh Final 0.1% (~0.25%)

# ==============================================================================
# 2. PARAMETER STRATEGI MOMENTUM & VOLUME SPIKE
# ==============================================================================
# Kriteria Volume Spike & Momentum
RVOL_THRESHOLD = 1.5            # Volume perdagangan minimal 1.5x rata-rata 20 hari
MIN_PRICE_CHANGE_PCT = 1.5      # Kenaikan harga minimal +1.5% pada hari sinyal
MIN_TURNOVER_IDR = 2_000_000_000 # Minimal nilai transaksi Rp 2 Miliar (filter saham tidak likuid)

# Parameter Moving Average & Indikator
MA_FAST = 10
MA_SLOW = 20
MA_TREND = 50
RSI_PERIOD = 14
RSI_OVERBOUGHT = 75
RSI_OVERSOLD = 35

# Target Profit & Stop Loss Default
DEFAULT_TP1_PCT = 3.0           # Target Profit 1: +3%
DEFAULT_TP2_PCT = 5.0           # Target Profit 2: +5%
DEFAULT_TP3_PCT = 8.0           # Target Profit 3: +8%
DEFAULT_SL_PCT = 3.0            # Stop Loss Default: -3%
TRAILING_STOP_PCT = 2.0         # Trailing Stop: 2% dari titik tertinggi setelah profit

# ==============================================================================
# 3. PENGATURAN PAPER TRADING (AKUN VIRTUAL)
# ==============================================================================
INITIAL_BALANCE = 50_000_000    # Saldo modal awal simulasi: Rp 50.000.000
MAX_ALLOCATION_PER_STOCK = 0.20 # Maksimal alokasi 20% modal per saham (diversifikasi)
PORTFOLIO_FILE = Path(__file__).resolve().parent / "portfolio.json"

# ==============================================================================
# 4. PENGATURAN NOTIFIKASI TELEGRAM & AI GEMINI
# ==============================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ENABLE_TELEGRAM = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))

# ==============================================================================
# 5. WATCHLIST SAHAM IDX (KOMPAS100 / LQ45 / SAHAM POPULER)
# ==============================================================================
# Saham likuid dengan volatilitas dan volume transaksi sehat di BEI
DEFAULT_WATCHLIST = [
    # Perbankan (Big Banks)
    "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "BRIS.JK", "BBTN.JK", "ARTO.JK",
    # Komoditas, Energi & Tambang
    "ADRO.JK", "PTBA.JK", "ITMG.JK", "MEDC.JK", "PGAS.JK", "AKRA.JK", 
    "ANTM.JK", "INCO.JK", "MDKA.JK", "MBMA.JK", "HRUM.JK", "BUMI.JK", "DEWA.JK",
    # Konglomerasi & Industri
    "ASII.JK", "AMMN.JK", "BREN.JK", "TPIA.JK", "BRPT.JK", "UNTR.JK", "PANI.JK", "CUAN.JK",
    # Consumer Goods & Farmasi
    "ICBP.JK", "INDF.JK", "MYOR.JK", "KLBF.JK", "CPIN.JK", "JPFA.JK", "SIDO.JK", "UNVR.JK",
    # Telekomunikasi & Teknologi
    "TLKM.JK", "ISAT.JK", "EXCL.JK", "GOTO.JK", "BUKA.JK", "EMTK.JK",
    # Semen, Properti & Infrastruktur
    "SMGR.JK", "INTP.JK", "BSDE.JK", "CTRA.JK", "PWON.JK", "JSMR.JK",
    # Ritel & Kertas
    "ACES.JK", "ERAA.JK", "MAPI.JK", "MAPA.JK", "INKP.JK", "TKIM.JK"
]

# Saham lapis 2 yang cukup likuid & aktif bergerak (kandidat scalping harian)
SECOND_LINER_WATCHLIST = [
    # Bank menengah
    "BNGA.JK", "NISP.JK", "BDMN.JK", "PNBN.JK", "BJBR.JK", "BJTM.JK", "BBYB.JK", "AGRO.JK", "BANK.JK",
    # Tambang, energi & mineral
    "ADMR.JK", "AADI.JK", "NCKL.JK", "TINS.JK", "PSAB.JK", "BRMS.JK", "DOID.JK", "ENRG.JK", "ELSA.JK",
    "RAJA.JK", "PTRO.JK", "INDY.JK", "TOBA.JK", "ESSA.JK", "DSSA.JK", "PGEO.JK", "KKGI.JK", "SGER.JK",
    # Properti & konstruksi
    "SMRA.JK", "LPKR.JK", "ASRI.JK", "APLN.JK", "KIJA.JK", "SSIA.JK", "DMAS.JK", "BKSL.JK", "PTPP.JK", "ADHI.JK",
    # Telko, media & teknologi
    "MTEL.JK", "TOWR.JK", "TBIG.JK", "WIFI.JK", "SCMA.JK", "MNCN.JK", "BMTR.JK", "FILM.JK", "MLPL.JK",
    # Konsumer, ritel & kesehatan
    "AMRT.JK", "MIDI.JK", "LPPF.JK", "RALS.JK", "MDIY.JK", "CMRY.JK", "ULTJ.JK", "GOOD.JK", "ROTI.JK",
    "HEAL.JK", "MIKA.JK", "SILO.JK", "KAEF.JK", "AVIA.JK", "ARNA.JK", "HRTA.JK",
    # Perkebunan & otomotif
    "AALI.JK", "LSIP.JK", "DSNG.JK", "TAPG.JK", "SSMS.JK", "AUTO.JK", "SMSM.JK", "GJTL.JK", "MPMX.JK",
    # Industri lain
    "SRTG.JK", "KPIG.JK", "MARK.JK", "WOOD.JK", "MAIN.JK", "TBLA.JK", "IMAS.JK"
]

# Universe scan rekomendasi scalp = saham besar + lapis 2 (tanpa duplikat)
SCALP_UNIVERSE = list(dict.fromkeys(DEFAULT_WATCHLIST + SECOND_LINER_WATCHLIST))

# Folder data lokal (snapshot rekomendasi, cache fundamental, setting user)
DATA_DIR = Path(__file__).resolve().parent / "data"

# ==============================================================================
# 6. WATCHLIST CRYPTOCURRENCY (TOP MARKET CAP)
# ==============================================================================
CRYPTO_WATCHLIST = [
    "BTC-USD",   # Bitcoin
    "ETH-USD",   # Ethereum
    "SOL-USD",   # Solana
    "BNB-USD",   # Binance Coin
    "XRP-USD",   # Ripple
    "DOGE-USD",  # Dogecoin
    "ADA-USD",   # Cardano
    "AVAX-USD",  # Avalanche
]

# ==============================================================================
# 7. WATCHLIST FOREX & COMMODITIES (LOGAM MULIA & MATA UANG UTAMA)
# ==============================================================================
FOREX_WATCHLIST = [
    "GC=F",      # XAU/USD (Gold / Emas)
    "SI=F",      # XAG/USD (Silver / Perak)
    "CL=F",      # Crude Oil (Minyak Mentah WTI)
    "EURUSD=X",  # Euro vs US Dollar
    "GBPUSD=X",  # British Pound vs US Dollar
    "USDJPY=X",  # US Dollar vs Japanese Yen
    "AUDUSD=X",  # Australian Dollar vs US Dollar
]

# Pemetaan alias simbol input pengguna ke kode Yahoo Finance
SYMBOL_ALIASES = {
    # Crypto
    "BTC": "BTC-USD",
    "BITCOIN": "BTC-USD",
    "BTCUSD": "BTC-USD",
    "BTCUSDT": "BTC-USD",
    "ETH": "ETH-USD",
    "ETHEREUM": "ETH-USD",
    "ETHUSD": "ETH-USD",
    "ETHUSDT": "ETH-USD",
    "SOL": "SOL-USD",
    "SOLANA": "SOL-USD",
    "SOLUSD": "SOL-USD",
    "BNB": "BNB-USD",
    "BINANCE": "BNB-USD",
    "XRP": "XRP-USD",
    "RIPPLE": "XRP-USD",
    "DOGE": "DOGE-USD",
    "DOGECOIN": "DOGE-USD",
    "ADA": "ADA-USD",
    "CARDANO": "ADA-USD",
    "AVAX": "AVAX-USD",
    "AVALANCHE": "AVAX-USD",
    
    # Komoditas & Logam Mulia
    "XAU": "GC=F",
    "XAUUSD": "GC=F",
    "XAU/USD": "GC=F",
    "XAU/USD (GOLD)": "GC=F",
    "GOLD": "GC=F",
    "EMAS": "GC=F",
    "XAG": "SI=F",
    "XAGUSD": "SI=F",
    "XAG/USD": "SI=F",
    "XAG/USD (SILVER)": "SI=F",
    "SILVER": "SI=F",
    "PERAK": "SI=F",
    "OIL": "CL=F",
    "WTI": "CL=F",
    "WTI (CRUDE OIL)": "CL=F",
    "CRUDE": "CL=F",
    "MINYAK": "CL=F",
    "BTC/USD": "BTC-USD",
    "ETH/USD": "ETH-USD",
    "SOL/USD": "SOL-USD",
    "BNB/USD": "BNB-USD",
    "XRP/USD": "XRP-USD",
    "DOGE/USD": "DOGE-USD",
    "ADA/USD": "ADA-USD",
    "AVAX/USD": "AVAX-USD",
    
    # Forex
    "EURUSD": "EURUSD=X",
    "EUR/USD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "USD/JPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "AUD/USD": "AUDUSD=X",
    "USDCHF": "USDCHF=X",
    "USD/CHF": "USDCHF=X",
    "USDCAD": "USDCAD=X",
    "USD/CAD": "USDCAD=X",
}

def get_asset_type(ticker: str) -> str:
    """Mengidentifikasi kelas aset: 'crypto', 'forex', 'commodity', atau 'stock'"""
    t = ticker.strip().upper()
    if t in SYMBOL_ALIASES:
        t = SYMBOL_ALIASES[t]
    if t.endswith("-USD"):
        return "crypto"
    elif t.endswith("=F") or t in ["GC=F", "SI=F", "CL=F"]:
        return "commodity"
    elif t.endswith("=X"):
        return "forex"
    else:
        return "stock"

def get_display_name(ticker: str) -> str:
    """Nama tampilan ramah pengguna untuk simbol atau emiten"""
    t = ticker.strip().upper()
    if t in SYMBOL_ALIASES:
        t = SYMBOL_ALIASES[t]
    if t == "GC=F":
        return "XAU/USD (Gold)"
    elif t == "SI=F":
        return "XAG/USD (Silver)"
    elif t == "CL=F":
        return "WTI (Crude Oil)"
    elif t.endswith("=X"):
        base = t.replace("=X", "")
        if len(base) == 6:
            return f"{base[:3]}/{base[3:]}"
        return base
    elif t.endswith("-USD"):
        return f"{t.replace('-USD', '')}/USD"
    elif t.endswith(".JK"):
        return t.replace(".JK", "")
    return t

def format_idr(amount: float) -> str:
    """Format angka menjadi representasi Rupiah (contoh: Rp 5.250)"""
    return f"Rp {amount:,.0f}".replace(",", ".")

def format_price(amount: float, ticker: str = "") -> str:
    """Format harga dinamis sesuai kelas aset (IDR, USD, JPY, Forex pip)"""
    atype = get_asset_type(ticker) if ticker else "stock"
    t_clean = ticker.strip().upper()
    
    if atype == "stock":
        return format_idr(amount)
    elif atype == "forex":
        if "JPY" in t_clean:
            return f"¥ {amount:,.2f}"
        return f"{amount:,.4f}"
    elif "JPY" in t_clean:
        return f"¥ {amount:,.2f}"
    else:
        # USD base untuk Crypto & Komoditas
        if amount >= 1000:
            return f"${amount:,.2f}"
        elif amount >= 1:
            return f"${amount:,.2f}"
        elif amount >= 0.01:
            return f"${amount:,.4f}"
        else:
            return f"${amount:,.6f}"

