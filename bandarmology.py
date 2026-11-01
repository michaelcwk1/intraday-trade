"""
Modul Analisis Bandarmology & Money Flow Saham Indonesia (IDX / BEI)
Menganalisis arus dana besar (Big Fund / Smart Money / Akumulasi Bandar):
- Chaikin Money Flow (CMF) 20 periode
- On-Balance Volume (OBV) & Trend
- Volume Price Trend (VPT)
- Skor Kekuatan Akumulasi (0 - 100%)
"""
import sys
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


from config import format_idr
from data_provider import get_stock_data, get_clean_symbol

def compute_cmf(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Chaikin Money Flow: positif = tekanan akumulasi, negatif = distribusi"""
    hl_diff = (df['High'] - df['Low']).replace(0, 0.0001)
    mfm = ((df['Close'] - df['Low']) - (df['High'] - df['Close'])) / hl_diff
    mfv = mfm * df['Volume']
    return mfv.rolling(period).sum() / df['Volume'].rolling(period).sum().replace(0, 1)

def analyze_bandarmology(ticker: str) -> Dict[str, Any]:
    """
    Menghitung indikator aliran dana besar dan akumulasi/distribusi.
    """
    symbol = get_clean_symbol(ticker)
    df = get_stock_data(ticker, period="6mo", interval="1d")
    
    if df.empty or len(df) < 25:
        return {"valid": False, "symbol": symbol, "error": "Data historis tidak mencukupi"}

    data = df.copy()

    # 1. (CMF) 20 Hari
    cmf_20 = compute_cmf(data, 20)
    current_cmf = float(cmf_20.iloc[-1])

    # 2. (OBV)
    direction = np.sign(data['Close'].diff()).fillna(0)
    obv = (direction * data['Volume']).cumsum()
    obv_ma20 = obv.rolling(20).mean()
    current_obv = float(obv.iloc[-1])
    is_obv_uptrend = bool(obv.iloc[-1] > obv_ma20.iloc[-1])

    # 3. (RVol)
    vol_ma20 = data['Volume'].rolling(20).mean()
    rvol = float(data['Volume'].iloc[-1] / vol_ma20.iloc[-1]) if vol_ma20.iloc[-1] > 0 else 1.0

    # 4. Perubahan Harga Hari Ini & 5 Hari
    change_1d = float(data['Close'].pct_change().iloc[-1] * 100)
    change_5d = float((data['Close'].iloc[-1] - data['Close'].iloc[-5]) / data['Close'].iloc[-5] * 100)
    
    # 5. Hitung Skor Akumulasi (0 - 100 poin)
    score = 50.0 # Titik netral
    
    # Faktor CMF (-25 s/d +25)
    score += np.clip(current_cmf * 100, -25, 25)
    
    # Faktor OBV Trend (+15 / -15)
    if is_obv_uptrend:
        score += 15
    else:
        score -= 15
        
    # Faktor RVol & Perubahan Harga (+15 / -15)
    if rvol >= 1.5 and change_1d > 0:
        score += 15 # Lonjakan volume di harga naik = Akumulasi Kuat
    elif rvol >= 1.5 and change_1d < 0:
        score -= 15 # Lonjakan volume di harga turun = Distribusi/Buang Barang
        
    score = float(np.clip(score, 0, 100))

    # Kategori Status
    if score >= 75:
        status = "🟢🟢 AKUMULASI BESAR (Big Inflow)"
        sentiment = "Sangat Bullish. Big Fund/Bandar sedang menyerap barang secara masif."
    elif score >= 60:
        status = "🟢 AKUMULASI SEDANG (Net Inflow)"
        sentiment = "Bullish. Terlihat aliran dana masuk secara konsisten."
    elif score >= 40:
        status = "⚪ NETRAL / KONSOLIDASI"
        sentiment = "Netral. Belum ada pergerakan volume signifikan dari pemain besar."
    elif score >= 25:
        status = "🔴 DISTRIBUSI RINGAN (Net Outflow)"
        sentiment = "Bearish. Terindikasi ada tekanan jual atau aksi ambil untung bertahap."
    else:
        status = "🔴🔴 DISTRIBUSI MASIF (Big Dumping)"
        sentiment = "Sangat Bearish. Tekanan distribusi besar terdeteksi, hindari entry spekulatif."

    close_price = float(data['Close'].iloc[-1])
    turnover = close_price * float(data['Volume'].iloc[-1])

    return {
        "valid": True,
        "symbol": symbol,
        "close": close_price,
        "change_1d": round(change_1d, 2),
        "change_5d": round(change_5d, 2),
        "turnover": turnover,
        "rvol": round(rvol, 2),
        "cmf": round(current_cmf, 3),
        "is_obv_uptrend": is_obv_uptrend,
        "score": round(score),
        "status": status,
        "sentiment": sentiment
    }

if __name__ == "__main__":
    test_sym = sys.argv[1] if len(sys.argv) > 1 else "BBCA"
    res = analyze_bandarmology(test_sym)
    print(f"Bandarmology {test_sym}: Skor {res['score']}/100 | {res['status']}")
    print(f"Sentiment: {res['sentiment']}")
