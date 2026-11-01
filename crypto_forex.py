"""
Modul Pemantau Pasar Cryptocurrency & Forex / Komoditas Dunia
Menghasilkan ringkasan harga real-time, perubahan 24 jam, dan format pesan Telegram interaktif.
"""
import sys
import time
from typing import Dict, Any, List, Optional
import yfinance as yf
import pandas as pd

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import config
from config import format_price, get_display_name

_CRYPTO_CACHE: Optional[List[Dict[str, Any]]] = None
_CRYPTO_CACHE_TIME: float = 0
_FOREX_CACHE: Optional[List[Dict[str, Any]]] = None
_FOREX_CACHE_TIME: float = 0
CACHE_TTL = 60

def get_crypto_overview(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Mengambil ringkasan koin cryptocurrency teratas"""
    global _CRYPTO_CACHE, _CRYPTO_CACHE_TIME
    now = time.time()
    if not force_refresh and _CRYPTO_CACHE and (now - _CRYPTO_CACHE_TIME < CACHE_TTL):
        return _CRYPTO_CACHE

    tickers = config.CRYPTO_WATCHLIST
    results = []
    try:
        df = yf.download(tickers, period="5d", interval="1d", progress=False)
        if not df.empty and 'Close' in df:
            for t in tickers:
                try:
                    c_series = df['Close'][t].dropna()
                    if len(c_series) >= 2:
                        last_c = float(c_series.iloc[-1])
                        prev_c = float(c_series.iloc[-2])
                        chg_pt = last_c - prev_c
                        chg_pct = (chg_pt / prev_c) * 100 if prev_c > 0 else 0.0
                        sym_clean = t.replace("-USD", "")
                        results.append({
                            "ticker": t,
                            "symbol": sym_clean,
                            "name": get_display_name(t),
                            "price": last_c,
                            "prev_price": prev_c,
                            "change_pt": chg_pt,
                            "change_pct": round(chg_pct, 2),
                            "formatted_price": format_price(last_c, t)
                        })
                except Exception:
                    continue
    except Exception as e:
        print(f"Error fetching crypto overview: {e}")

    if results:
        _CRYPTO_CACHE = results
        _CRYPTO_CACHE_TIME = now
    return results or (_CRYPTO_CACHE or [])

def get_forex_overview(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Mengambil ringkasan komoditas dan pasangan mata uang utama"""
    global _FOREX_CACHE, _FOREX_CACHE_TIME
    now = time.time()
    if not force_refresh and _FOREX_CACHE and (now - _FOREX_CACHE_TIME < CACHE_TTL):
        return _FOREX_CACHE

    tickers = config.FOREX_WATCHLIST
    results = []
    try:
        df = yf.download(tickers, period="5d", interval="1d", progress=False)
        if not df.empty and 'Close' in df:
            for t in tickers:
                try:
                    c_series = df['Close'][t].dropna()
                    if len(c_series) >= 2:
                        last_c = float(c_series.iloc[-1])
                        prev_c = float(c_series.iloc[-2])
                        chg_pt = last_c - prev_c
                        chg_pct = (chg_pt / prev_c) * 100 if prev_c > 0 else 0.0
                        results.append({
                            "ticker": t,
                            "name": get_display_name(t),
                            "price": last_c,
                            "prev_price": prev_c,
                            "change_pt": chg_pt,
                            "change_pct": round(chg_pct, 2),
                            "formatted_price": format_price(last_c, t)
                        })
                except Exception:
                    continue
    except Exception as e:
        print(f"Error fetching forex overview: {e}")

    if results:
        _FOREX_CACHE = results
        _FOREX_CACHE_TIME = now
    return results or (_FOREX_CACHE or [])

def format_crypto_message() -> str:
    """Format ringkasan pasar crypto ke Markdown Telegram"""
    items = get_crypto_overview()
    if not items:
        return "⚠️ Gagal memuat data cryptocurrency dari bursa global. Coba beberapa saat lagi."

    now_str = time.strftime("%H:%M:%S WIB")
    msg = f"""
🪙 *PASAR CRYPTOCURRENCY TERATAS (GLOBAL)* 🌐
━━━━━━━━━━━━━━━━━━━━
⏰ *Pembaruan:* `{now_str}`
📊 *Harga Terkini & Perubahan 24 Jam:*

"""
    icon_map = {
        "BTC": "🥇", "ETH": "🥈", "SOL": "🟣", "BNB": "🟡",
        "XRP": "⚡", "DOGE": "🐶", "ADA": "🔵", "AVAX": "🔺"
    }
    for item in items:
        sym = item['symbol']
        icon = icon_map.get(sym, "💎")
        chg_sign = "+" if item['change_pct'] >= 0 else ""
        chg_badge = "🟢" if item['change_pct'] >= 0 else "🔴"
        msg += f"{icon} *{sym}/USD:* `{item['formatted_price']}` ({chg_badge} `{chg_sign}{item['change_pct']:.2f}%`)\n"

    msg += """━━━━━━━━━━━━━━━━━━━━
💡 *Tip:* Ketik `/plan BTC` atau `/chart BTC` untuk analisis teknikal, garis Entry, TP, & Stop Loss.
"""
    return msg.strip()

def format_forex_message() -> str:
    """Format ringkasan komoditas dan forex ke Markdown Telegram"""
    items = get_forex_overview()
    if not items:
        return "⚠️ Gagal memuat data forex/komoditas dari bursa global. Coba beberapa saat lagi."

    now_str = time.strftime("%H:%M:%S WIB")
    msg = f"""
🌍 *PASAR FOREX & KOMODITAS DUNIA* 📈
━━━━━━━━━━━━━━━━━━━━
⏰ *Pembaruan:* `{now_str}`

🏆 *Logam Mulia & Energi:*
"""
    commodities = [it for it in items if it['ticker'] in ["GC=F", "SI=F", "CL=F"]]
    currencies = [it for it in items if it['ticker'] not in ["GC=F", "SI=F", "CL=F"]]

    c_icons = {"GC=F": "🥇", "SI=F": "🥈", "CL=F": "🛢️"}
    for c in commodities:
        icon = c_icons.get(c['ticker'], "📦")
        chg_sign = "+" if c['change_pct'] >= 0 else ""
        chg_badge = "🟢" if c['change_pct'] >= 0 else "🔴"
        msg += f"{icon} *{c['name']}:* `{c['formatted_price']}` ({chg_badge} `{chg_sign}{c['change_pct']:.2f}%`)\n"

    msg += "\n💱 *Pasangan Mata Uang Utama (Forex):*\n"
    fx_icons = {"EURUSD=X": "💶", "GBPUSD=X": "💷", "USDJPY=X": "💴", "AUDUSD=X": "🇦🇺"}
    for fx in currencies:
        icon = fx_icons.get(fx['ticker'], "💱")
        chg_sign = "+" if fx['change_pct'] >= 0 else ""
        chg_badge = "🟢" if fx['change_pct'] >= 0 else "🔴"
        msg += f"{icon} *{fx['name']}:* `{fx['formatted_price']}` ({chg_badge} `{chg_sign}{fx['change_pct']:.2f}%`)\n"

    msg += """━━━━━━━━━━━━━━━━━━━━
💡 *Tip:* Ketik `/chart XAU` atau `/plan EURUSD` untuk grafik teknikal & Trading Plan lengkap!
"""
    return msg.strip()

if __name__ == "__main__":
    print(format_crypto_message())
    print()
    print(format_forex_message())