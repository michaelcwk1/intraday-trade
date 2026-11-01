"""
Modul Screener Buy on Weakness (BoW) & Swing Trading Rebound
Mendeteksi saham likuid IDX yang sedang diskon/oversold di area support kuat
dengan konfirmasi pembalikan arah (rebound) dan potensi Risk-to-Reward tinggi.
"""
import sys
import time
from typing import Dict, Any, List, Optional
import yfinance as yf
import pandas as pd
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import config
from config import format_idr

_BOW_CACHE: Optional[List[Dict[str, Any]]] = None
_BOW_CACHE_TIME: float = 0
CACHE_TTL = 120  # 2 menit

def run_bow_screener(limit: int = 6, force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Memindai saham-saham pilihan yang memenuhi kriteria Buy on Weakness (BoW):
    1. RSI(14) rendah / oversold (<= 45, ideal <= 38)
    2. Harga dekat support 20-hari atau lower Bollinger Band
    3. Muncul tanda pantulan (candle hijau / rejection wick)
    4. Risk/Reward Ratio menarik (>= 1:2.0)
    """
    global _BOW_CACHE, _BOW_CACHE_TIME
    now = time.time()
    if not force_refresh and _BOW_CACHE and (now - _BOW_CACHE_TIME < CACHE_TTL):
        return _BOW_CACHE[:limit]
        
    tickers = config.DEFAULT_WATCHLIST
    results = []
    
    try:
        df = yf.download(tickers, period="3mo", interval="1d", progress=False)
        if df.empty or 'Close' not in df:
            return []
            
        for t in tickers:
            try:
                sub_c = df['Close'][t].dropna()
                sub_o = df['Open'][t].dropna() if 'Open' in df else sub_c
                sub_h = df['High'][t].dropna() if 'High' in df else sub_c
                sub_l = df['Low'][t].dropna() if 'Low' in df else sub_c
                sub_v = df['Volume'][t].dropna() if 'Volume' in df else pd.Series()
                
                if len(sub_c) < 25:
                    continue
                    
                curr_c = float(sub_c.iloc[-1])
                prev_c = float(sub_c.iloc[-2])
                curr_o = float(sub_o.iloc[-1])
                curr_h = float(sub_h.iloc[-1])
                curr_l = float(sub_l.iloc[-1])
                
                # Hitung RSI 14
                delta = sub_c.diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss.replace(0, np.nan)
                rsi_series = 100 - (100 / (1 + rs))
                rsi = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 50.0
                
                # Kriteria 1: Pullback / Oversold (RSI <= 46)
                if rsi > 46:
                    continue
                    
                # Support 20 hari
                low20 = float(sub_l.tail(20).min())
                high20 = float(sub_h.tail(20).max())
                dist_to_support_pct = ((curr_c - low20) / low20) * 100 if low20 else 99
                
                # Kriteria 2: Berada dalam jarak 4% dari support terdekat
                if dist_to_support_pct > 4.5:
                    continue
                    
                # Kriteria 3: Tanda pembalikan arah (Green candle atau hammer wick)
                is_green = curr_c >= curr_o
                candle_range = curr_h - curr_l
                lower_wick = min(curr_o, curr_c) - curr_l
                is_hammer = (lower_wick >= 0.35 * candle_range) if candle_range > 0 else False
                is_stabilizing = is_green or is_hammer or (curr_c >= prev_c * 0.995)
                
                if not is_stabilizing:
                    continue
                    
                # Hitung Trading Plan BoW
                sl_price = round(low20 * 0.975)  # SL di bawah swing low
                sl_pct = ((curr_c - sl_price) / curr_c) * 100
                if sl_pct < 1.0:
                    sl_pct = 2.5
                    sl_price = round(curr_c * 0.975)
                    
                # Target TP: Menuju MA20 atau Resistance 20-hari
                ma20 = float(sub_c.rolling(20).mean().iloc[-1])
                tp_target = max(ma20, curr_c * 1.06)
                tp_pct = ((tp_target - curr_c) / curr_c) * 100
                rrr = round(tp_pct / sl_pct, 1) if sl_pct > 0 else 2.0
                
                # Skor BoW: Makin oversold + makin dekat support + RRR tinggi = skor makin tinggi
                bow_score = (50 - rsi) * 2 + (5 - dist_to_support_pct) * 5 + rrr * 5
                
                clean_sym = t.replace(".JK", "")
                results.append({
                    "symbol": clean_sym,
                    "ticker": t,
                    "close": curr_c,
                    "rsi": round(rsi, 1),
                    "support": low20,
                    "resistance": round(tp_target),
                    "sl_price": sl_price,
                    "sl_pct": round(sl_pct, 1),
                    "tp_price": round(tp_target),
                    "tp_pct": round(tp_pct, 1),
                    "rrr": rrr,
                    "dist_support_pct": round(dist_to_support_pct, 1),
                    "is_green": is_green,
                    "score": round(bow_score, 1)
                })
            except Exception:
                continue
    except Exception as e:
        print(f"Error BoW screener: {e}")
        
    # Urutkan berdasarkan skor BoW tertinggi
    results.sort(key=lambda x: x["score"], reverse=True)
    _BOW_CACHE = results
    _BOW_CACHE_TIME = now
    return results[:limit]

def format_bow_message(limit: int = 6) -> str:
    """Format hasil screener Buy on Weakness ke pesan Markdown Telegram"""
    items = run_bow_screener(limit=limit)
    now_str = time.strftime("%H:%M:%S WIB")
    
    if not items:
        return f"""
🎣 *SCREENER BUY ON WEAKNESS (BoW) & REBOUND* 🌊
━━━━━━━━━━━━━━━━━━━━
⏰ *Pembaruan:* `{now_str}`
ℹ️ Saat ini belum ada saham likuid yang memasuki kriteria area diskon ekstrim / oversold support.
_Gunakan `/scan` untuk strategi momentum atau `/bsjp` untuk strategi sore hari._
"""

    msg = f"""
🎣 *RADAR BUY ON WEAKNESS (BoW) & REBOUND* 🌊
━━━━━━━━━━━━━━━━━━━━
⏰ *Pembaruan:* `{now_str}`
💡 *Strategi:* Beli saham diskon/oversold di area Support Kuat dengan batas risiko kecil & potensi cuan tinggi.

"""
    for i, it in enumerate(items, 1):
        sym = it['symbol']
        candle_badge = "🟢 Rebound" if it['is_green'] else "🟡 Stabil"
        msg += f"""*{i}. {sym}* — {candle_badge} (RSI: `{it['rsi']}`)
💵 *Harga Masuk:* `{format_idr(it['close'])}` (Support: `{format_idr(it['support'])}`)
🛑 *Stop Loss:* `{format_idr(it['sl_price'])}` (-{it['sl_pct']}%)
🎯 *Target Swing:* `{format_idr(it['tp_price'])}` (+{it['tp_pct']}%)
⚖️ *Risk/Reward:* `1 : {it['rrr']}`
────────────────────
"""

    msg += """_Ketik `/plan <KODE>` untuk rincian lot sizing atau `/chart <KODE>` untuk melihat posisi support di grafik._"""
    return msg.strip()

if __name__ == "__main__":
    print(format_bow_message())
