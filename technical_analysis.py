"""
Modul Analisis Konsensus Teknikal Multi-Indikator (TradingView Style)
Menghitung Moving Averages, RSI, MACD, Stochastic, Bollinger Bands, dan ATR
untuk menghasilkan Meteran Konsensus: STRONG BUY, BUY, NEUTRAL, SELL, STRONG SELL.
"""
import sys
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import config
from config import format_price, get_display_name, get_asset_type
from data_provider import get_stock_data, get_clean_symbol, normalize_ticker

def calculate_technical_consensus(ticker: str) -> Dict[str, Any]:
    """
    Menghitung konsensus teknikal lengkap dari berbagai moving average dan osilator.
    """
    sym = get_clean_symbol(ticker)
    actual_ticker = normalize_ticker(ticker)
    df = get_stock_data(actual_ticker, period="1y", interval="1d")
    
    if df.empty or len(df) < 25:
        return {"valid": False, "symbol": sym, "error": "Data historis tidak mencukupi (minimal 25 hari)"}
        
    close = df['Close']
    high = df['High']
    low = df['Low']
    curr_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])
    chg_pct = ((curr_close - prev_close) / prev_close) * 100 if prev_close else 0.0
    
    # 1. MOVING AVERAGES (SMA & EMA)
    ma_signals = {}
    periods_sma = [5, 10, 20, 50, 100, 200]
    for p in periods_sma:
        if len(close) >= p:
            val = float(close.rolling(p).mean().iloc[-1])
            sig = "BUY" if curr_close > val else "SELL"
            ma_signals[f"SMA {p}"] = {"val": val, "signal": sig}
            
    periods_ema = [12, 26, 50]
    for p in periods_ema:
        if len(close) >= p:
            val = float(close.ewm(span=p, adjust=False).mean().iloc[-1])
            sig = "BUY" if curr_close > val else "SELL"
            ma_signals[f"EMA {p}"] = {"val": val, "signal": sig}
            
    # 2. OSCILLATORS
    osc_signals = {}
    
    # RSI (14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))
    rsi_val = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 50.0
    if rsi_val >= 70:
        rsi_sig = "SELL (Overbought)"
    elif rsi_val <= 30:
        rsi_sig = "BUY (Oversold)"
    elif rsi_val > 50:
        rsi_sig = "BUY (Bullish)"
    else:
        rsi_sig = "SELL (Bearish)"
    osc_signals["RSI (14)"] = {"val": round(rsi_val, 1), "signal": rsi_sig}
    
    # Stochastic (14, 3)
    low14 = low.rolling(14).min()
    high14 = high.rolling(14).max()
    denom = (high14 - low14).replace(0, np.nan)
    stoch_k = 100 * ((close - low14) / denom)
    stoch_d = stoch_k.rolling(3).mean()
    k_val = float(stoch_k.iloc[-1]) if not pd.isna(stoch_k.iloc[-1]) else 50.0
    d_val = float(stoch_d.iloc[-1]) if not pd.isna(stoch_d.iloc[-1]) else 50.0
    if k_val >= 80:
        stoch_sig = "SELL (Overbought)"
    elif k_val <= 20:
        stoch_sig = "BUY (Oversold)"
    elif k_val > d_val:
        stoch_sig = "BUY (Golden Cross)"
    else:
        stoch_sig = "SELL (Death Cross)"
    osc_signals["Stochastic (14,3)"] = {"val": round(k_val, 1), "signal": stoch_sig}
    
    # MACD (12, 26, 9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_val = float(macd_line.iloc[-1])
    sig_val = float(signal_line.iloc[-1])
    macd_sig = "BUY (Bullish Cross)" if macd_val > sig_val else "SELL (Bearish Cross)"
    osc_signals["MACD (12,26)"] = {"val": round(macd_val, 2), "signal": macd_sig}
    
    # Bollinger Bands (20, 2)
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    upper_b = sma20 + (std20 * 2)
    lower_b = sma20 - (std20 * 2)
    curr_upper = float(upper_b.iloc[-1])
    curr_lower = float(lower_b.iloc[-1])
    curr_mid = float(sma20.iloc[-1])
    if curr_close > curr_upper:
        bb_sig = "SELL (Tembus Upper)"
    elif curr_close < curr_lower:
        bb_sig = "BUY (Oversold Lower)"
    elif curr_close > curr_mid:
        bb_sig = "BUY (Di Atas Middle)"
    else:
        bb_sig = "SELL (Di Bawah Middle)"
    osc_signals["Bollinger (20,2)"] = {"val": round(curr_mid, 2), "signal": bb_sig}
    
    # Momentum (10)
    mom_val = float(close.diff(10).iloc[-1]) if len(close) >= 11 else 0.0
    mom_sig = "BUY (Positif)" if mom_val > 0 else "SELL (Negatif)"
    osc_signals["Momentum (10)"] = {"val": round(mom_val, 2), "signal": mom_sig}
    
    # ATR (14) Volatilitas
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_val = float(tr.rolling(14).mean().iloc[-1])
    
    # 3. KALKULASI REKAPITULASI SINYAL
    buy_count = 0
    sell_count = 0
    neutral_count = 0
    
    for _, item in {**ma_signals, **osc_signals}.items():
        s = item["signal"].upper()
        if "BUY" in s:
            buy_count += 1
        elif "SELL" in s:
            sell_count += 1
        else:
            neutral_count += 1
            
    total_votes = buy_count + sell_count + neutral_count
    
    if buy_count >= (sell_count + 6) and buy_count >= 9:
        consensus = "STRONG BUY"
        consensus_badge = "🔥 STRONG BUY"
        gauge_art = "[──────|──────|──────|██████]"
    elif buy_count > sell_count + 2:
        consensus = "BUY"
        consensus_badge = "🟢 BUY"
        gauge_art = "[──────|──────|██████|──────]"
    elif sell_count >= (buy_count + 6) and sell_count >= 9:
        consensus = "STRONG SELL"
        consensus_badge = "🩸 STRONG SELL"
        gauge_art = "[██████|──────|──────|──────]"
    elif sell_count > buy_count + 2:
        consensus = "SELL"
        consensus_badge = "🔴 SELL"
        gauge_art = "[──────|██████|──────|──────]"
    else:
        consensus = "NEUTRAL"
        consensus_badge = "⚪ NEUTRAL"
        gauge_art = "[──────|──████|██────|──────]"
        
    return {
        "valid": True,
        "symbol": sym,
        "ticker": actual_ticker,
        "display_name": get_display_name(actual_ticker),
        "asset_type": get_asset_type(actual_ticker),
        "close": curr_close,
        "change_pct": round(chg_pct, 2),
        "consensus": consensus,
        "consensus_badge": consensus_badge,
        "gauge_art": gauge_art,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "neutral_count": neutral_count,
        "total_votes": total_votes,
        "ma_signals": ma_signals,
        "osc_signals": osc_signals,
        "atr": round(atr_val, 2),
        "rsi": round(rsi_val, 1)
    }

def format_ta_message(ticker: str) -> str:
    """Format hasil analisis konsensus teknikal ke Markdown Telegram"""
    res = calculate_technical_consensus(ticker)
    if not res.get("valid"):
        return f"❌ Gagal memuat data teknikal untuk `{ticker}`: {res.get('error', 'Instrumen tidak ditemukan')}"
        
    disp = res["display_name"]
    act = res["ticker"]
    chg_sign = "+" if res["change_pct"] >= 0 else ""
    chg_badge = "🟢" if res["change_pct"] >= 0 else "🔴"
    
    msg = f"""
🧭 *KONSENSUS TEKNIKAL: {disp}*
━━━━━━━━━━━━━━━━━━━━
📊 *Konsensus Utama:* {res['consensus_badge']}
`{res['gauge_art']}`
`  JUAL     NETRAL     BELI   KUAT BELI `

💵 *Harga Terkini:* `{format_price(res['close'], act)}` ({chg_badge} `{chg_sign}{res['change_pct']:.2f}%`)
📈 *Skor Sinyal ({res['total_votes']} Indikator):*
  • 🟢 *Beli (Buy)*     : `{res['buy_count']}`
  • ⚪ *Netral*         : `{res['neutral_count']}`
  • 🔴 *Jual (Sell)*    : `{res['sell_count']}`

📐 *Moving Averages:*
"""
    for name, item in list(res["ma_signals"].items())[:6]:
        sig_badge = "🟢" if "BUY" in item["signal"] else "🔴"
        msg += f"  • *{name}*: `{format_price(item['val'], act)}` ({sig_badge} {item['signal']})\n"
        
    msg += "\n🌊 *Osilator & Momentum:*\n"
    for name, item in res["osc_signals"].items():
        sig_badge = "🟢" if "BUY" in item["signal"] else ("🔴" if "SELL" in item["signal"] else "⚪")
        msg += f"  • *{name}*: `{item['val']}` ({sig_badge} {item['signal']})\n"
        
    msg += f"""
⚡ *Volatilitas Rata-rata (ATR 14):* `{format_price(res['atr'], act)}`
━━━━━━━━━━━━━━━━━━━━
_Ketik `/plan {res['symbol']}` untuk trading plan atau `/chart {res['symbol']}` untuk candlestick._
"""
    return msg.strip()

if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "BBCA"
    print(format_ta_message(t))
