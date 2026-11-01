"""
Strategi Trading: Momentum & Volume Spike Scanner untuk Saham IDX
Mendeteksi lonjakan volume akumulasi yang disertai momentum pergerakan harga positif.
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from config import (
    RVOL_THRESHOLD, MIN_PRICE_CHANGE_PCT, MIN_TURNOVER_IDR,
    MA_FAST, MA_SLOW, MA_TREND, RSI_PERIOD,
    DEFAULT_TP1_PCT, DEFAULT_TP2_PCT, DEFAULT_TP3_PCT, DEFAULT_SL_PCT
)

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Menghitung indikator teknikal utama pada DataFrame OHLCV:
    - Moving Average (MA10, MA20, MA50)
    - Volume Moving Average (MA20_Vol)
    - Relative Volume (RVol)
    - Turnover Harian (Nilai Transaksi dalam Rupiah)
    - RSI (Relative Strength Index)
    - ATR (Average True Range)
    - Resistance Breakout (20-day high)
    """
    if df.empty or len(df) < 20:
        return df

    data = df.copy()

    # 1. Moving Averages
    data['MA10'] = data['Close'].rolling(window=MA_FAST).mean()
    data['MA20'] = data['Close'].rolling(window=MA_SLOW).mean()
    data['MA50'] = data['Close'].rolling(window=min(MA_TREND, len(data))).mean()

    # 2. Volume & Turnover
    data['MA20_Vol'] = data['Volume'].rolling(window=MA_SLOW).mean()
    data['RVol'] = np.where(data['MA20_Vol'] > 0, data['Volume'] / data['MA20_Vol'], 0.0)
    data['Turnover'] = data['Close'] * data['Volume']
    data['MA20_Turnover'] = data['Turnover'].rolling(window=MA_SLOW).mean()

    # 3. Perubahan Harga (%)
    data['Change_Pct'] = data['Close'].pct_change() * 100

    # 4. Highest High (Breakout Level)
    data['High_20d'] = data['High'].shift(1).rolling(window=MA_SLOW).max()

    # 5. RSI (Relative Strength Index)
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss.replace(0, np.nan)
    data['RSI'] = 100 - (100 / (1 + rs))
    data['RSI'] = data['RSI'].fillna(50.0)

    # 6. ATR (Average True Range)
    high_low = data['High'] - data['Low']
    high_prev_close = (data['High'] - data['Close'].shift(1)).abs()
    low_prev_close = (data['Low'] - data['Close'].shift(1)).abs()
    true_range = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    data['ATR'] = true_range.rolling(window=14).mean()

    return data

def analyze_ticker_momentum(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Menganalisis baris data terakhir suatu saham dan mengevaluasi sinyal Momentum & Volume Spike.
    """
    if df.empty or len(df) < 20:
        return {
            "has_signal": False,
            "signal": "NEUTRAL",
            "reason": "Data historis tidak mencukupi (< 20 bar)"
        }

    df_ind = calculate_indicators(df)
    latest = df_ind.iloc[-1]
    prev = df_ind.iloc[-2]

    close = float(latest['Close'])
    rvol = float(latest['RVol'])
    change_pct = float(latest['Change_Pct'])
    turnover = float(latest['Turnover'])
    rsi = float(latest['RSI'])
    ma20 = float(latest['MA20'])
    high_20d = float(latest['High_20d']) if not np.isnan(latest['High_20d']) else close

    # Kondisi-kondisi strategi
    is_volume_spike = rvol >= RVOL_THRESHOLD
    is_price_momentum = change_pct >= MIN_PRICE_CHANGE_PCT
    is_liquid = turnover >= MIN_TURNOVER_IDR
    is_above_ma20 = close > ma20
    is_breakout = close >= high_20d
    is_rsi_safe = rsi < 80.0  # Menghindari saham yang sudah kelewat overbought/pucuk

    # Evaluasi Sinyal
    has_buy_signal = is_volume_spike and is_price_momentum and is_liquid and is_above_ma20 and is_rsi_safe

    # Target Price dan Stop Loss
    tp1 = round(close * (1 + DEFAULT_TP1_PCT / 100))
    tp2 = round(close * (1 + DEFAULT_TP2_PCT / 100))
    tp3 = round(close * (1 + DEFAULT_TP3_PCT / 100))
    sl = round(close * (1 - DEFAULT_SL_PCT / 100))

    # Rasio Risk to Reward (berdasarkan TP2)
    risk = max(close - sl, 1)
    reward = max(tp2 - close, 0)
    rrr = round(reward / risk, 2)

    # Label sinyal
    signal = "STRONG BUY" if (has_buy_signal and is_breakout) else ("BUY" if has_buy_signal else "NEUTRAL")

    # Deskripsi / Alasan sinyal
    reasons = []
    if is_volume_spike:
        reasons.append(f"Volume Spike ({rvol:.2f}x)")
    if is_price_momentum:
        reasons.append(f"Momentum Kenaikan (+{change_pct:.2f}%)")
    if is_breakout:
        reasons.append("Breakout Resistance 20 Hari")
    if is_above_ma20:
        reasons.append("Uptrend di atas MA20")
    if not is_liquid:
        reasons.append(f"Turnover kecil (< Rp {MIN_TURNOVER_IDR/1e9:.1f}M)")

    return {
        "has_signal": has_buy_signal,
        "signal": signal,
        "close": close,
        "change_pct": round(change_pct, 2),
        "volume": int(latest['Volume']),
        "rvol": round(rvol, 2),
        "turnover": turnover,
        "rsi": round(rsi, 1),
        "ma20": round(ma20, 1),
        "is_breakout": is_breakout,
        "is_liquid": is_liquid,
        "entry_price": close,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "sl": sl,
        "rrr": rrr,
        "reasons": reasons
    }

def smart_round(val: float, base_price: float) -> float:
    """Pembulatan adaptif sesuai skala harga aset (Crypto, Forex, Saham)"""
    if base_price < 2.0:
        return round(val, 4)
    elif base_price < 500.0:
        return round(val, 2)
    elif base_price < 10000.0:
        return round(val, 1) if (val % 1 != 0) else round(val)
    else:
        return round(val)

def get_trading_plan(ticker: str, custom_tp_pct: Optional[float] = None, custom_sl_pct: Optional[float] = None) -> Dict[str, Any]:
    """
    Menghitung Trading Plan lengkap untuk suatu saham / crypto / forex:
    - Area Beli (Entry Area)
    - Level Stop Loss (SL)
    - Target Profit (TP1, TP2, TP3)
    - Support & Resistance
    - Risk to Reward Ratio
    """
    import config
    from data_provider import get_stock_data, get_clean_symbol, normalize_ticker
    norm_ticker = normalize_ticker(ticker)
    symbol = get_clean_symbol(norm_ticker)
    df = get_stock_data(norm_ticker, period="3mo", interval="1d")
    if df.empty or len(df) < 15:
        return {"valid": False, "symbol": symbol, "error": "Data historis tidak mencukupi"}
    
    analysis = analyze_ticker_momentum(df)
    close = analysis['close']
    tp_pct = custom_tp_pct or DEFAULT_TP2_PCT
    sl_pct = custom_sl_pct or DEFAULT_SL_PCT
    
    support = smart_round(float(df['Low'].tail(15).min()), close)
    resistance = smart_round(float(df['High'].tail(20).max()), close)
    
    buy_min = smart_round(close * 0.99, close)
    buy_max = smart_round(close * 1.005, close)
    
    sl_price = smart_round(close * (1 - sl_pct / 100), close)
    tp1 = smart_round(close * (1 + DEFAULT_TP1_PCT / 100), close)
    tp2 = smart_round(close * (1 + tp_pct / 100), close)
    tp3 = smart_round(close * (1 + DEFAULT_TP3_PCT / 100), close)
    
    risk = max(close - sl_price, 0.0001)
    reward = max(tp2 - close, 0)
    rrr = round(reward / risk, 2)
    
    return {
        "valid": True,
        "symbol": symbol,
        "ticker": norm_ticker,
        "asset_type": config.get_asset_type(norm_ticker),
        "close": close,
        "change_pct": analysis['change_pct'],
        "rvol": analysis['rvol'],
        "rsi": analysis['rsi'],
        "signal": analysis['signal'],
        "buy_entry_ideal": close,
        "buy_min": buy_min,
        "buy_max": buy_max,
        "sl_price": sl_price,
        "sl_pct": sl_pct,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "support": support,
        "resistance": resistance,
        "rrr": rrr,
        "reasons": analysis.get('reasons', [])
    }

