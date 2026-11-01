"""
Modul Ringkasan Fundamental & Kalender Aksi Korporasi Emiten IDX
Menampilkan valuasi PER, PBV, ROE, Dividend Yield, Market Cap, serta jadwal Cum-Date Dividen & Rilis Kinerja.
"""
import sys
import time
from datetime import datetime, date
from typing import Dict, Any, List, Optional
import yfinance as yf

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import config
from config import format_price, get_display_name, get_asset_type
from data_provider import normalize_ticker, get_clean_symbol

_CALENDAR_CACHE: Optional[List[Dict[str, Any]]] = None
_CALENDAR_CACHE_TIME: float = 0
CALENDAR_CACHE_TTL = 600  # 10 menit

def _format_market_cap(val: Optional[float], is_idr: bool = True) -> str:
    if not val:
        return "-"
    if is_idr:
        if val >= 1e12:
            return f"Rp {val / 1e12:.1f} Triliun"
        elif val >= 1e9:
            return f"Rp {val / 1e9:.1f} Miliar"
        else:
            return f"Rp {val:,.0f}"
    else:
        if val >= 1e12:
            return f"${val / 1e12:.2f} Trillion"
        elif val >= 1e9:
            return f"${val / 1e9:.2f} Billion"
        elif val >= 1e6:
            return f"${val / 1e6:.2f} Million"
        return f"${val:,.0f}"

def get_fundamental_summary(ticker: str) -> Dict[str, Any]:
    """
    Mengambil data fundamental emiten atau aset dari Yahoo Finance
    """
    actual = normalize_ticker(ticker)
    sym = get_clean_symbol(ticker)
    atype = get_asset_type(actual)
    
    try:
        t = yf.Ticker(actual)
        info = t.info
        if not info:
            return {"valid": False, "symbol": sym, "error": "Data fundamental tidak tersedia"}
            
        is_idr = (atype == "stock")
        curr_price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        pe = info.get("trailingPE")
        fwd_pe = info.get("forwardPE")
        pbv = info.get("priceToBook")
        roe = info.get("returnOnEquity")
        npm = info.get("profitMargins")
        div_yield = info.get("dividendYield")
        div_rate = info.get("dividendRate")
        mcap = info.get("marketCap")
        sector = info.get("sector", "Umum / Global")
        industry = info.get("industry", "-")
        h52 = info.get("fiftyTwoWeekHigh")
        l52 = info.get("fiftyTwoWeekLow")
        
        # Penilaian Valuasi
        if pe and pbv:
            if pe < 12 and pbv < 1.5:
                val_status = "🟢 Undervalued (Diskon/Murah)"
            elif pe < 20 and pbv < 3.0:
                val_status = "🟡 Fair Value (Valuasi Wajar)"
            else:
                val_status = "🔴 Premium / Growth (Valuasi Tinggi)"
        else:
            val_status = "⚪ Netral"
            
        return {
            "valid": True,
            "symbol": sym,
            "ticker": actual,
            "display_name": get_display_name(actual),
            "asset_type": atype,
            "price": curr_price,
            "pe": round(pe, 2) if pe else None,
            "fwd_pe": round(fwd_pe, 2) if fwd_pe else None,
            "pbv": round(pbv, 2) if pbv else None,
            "roe_pct": round(roe * 100, 2) if roe else None,
            "npm_pct": round(npm * 100, 2) if npm else None,
            "div_yield_pct": round(div_yield * 100, 2) if div_yield and div_yield < 1 else (round(div_yield, 2) if div_yield else None),
            "div_rate": div_rate,
            "market_cap_str": _format_market_cap(mcap, is_idr=is_idr),
            "sector": sector,
            "industry": industry,
            "high_52w": h52,
            "low_52w": l52,
            "valuation_status": val_status
        }
    except Exception as e:
        return {"valid": False, "symbol": sym, "error": str(e)}

def format_fundamental_message(ticker: str) -> str:
    """Format kartu metrik fundamental ke Markdown Telegram"""
    f = get_fundamental_summary(ticker)
    if not f.get("valid"):
        return f"❌ Gagal memuat data fundamental `{ticker}`: {f.get('error', 'Data tidak ditemukan')}"
        
    disp = f["display_name"]
    act = f["ticker"]
    pe_str = f"`{f['pe']}x`" if f['pe'] else "`-`"
    pbv_str = f"`{f['pbv']}x`" if f['pbv'] else "`-`"
    roe_str = f"`{f['roe_pct']}%`" if f['roe_pct'] else "`-`"
    npm_str = f"`{f['npm_pct']}%`" if f['npm_pct'] else "`-`"
    div_str = f"`{f['div_yield_pct']}%`" if f['div_yield_pct'] else "`-`"
    price_str = format_price(f['price'], act) if f['price'] else "-"
    h52_str = format_price(f['high_52w'], act) if f['high_52w'] else "-"
    l52_str = format_price(f['low_52w'], act) if f['low_52w'] else "-"
    
    msg = f"""
🏢 *PROFIL FUNDAMENTAL & VALUASI: {disp}*
━━━━━━━━━━━━━━━━━━━━
📌 *Sektor:* `{f['sector']}`
🏭 *Industri:* `{f['industry']}`
💵 *Harga Saat Ini:* `{price_str}`
🏆 *Kapitalisasi Pasar:* `{f['market_cap_str']}`

📊 *Metrik Valuasi & Profitabilitas:*
  • *PER (Price to Earnings)* : {pe_str}
  • *PBV (Price to Book)*     : {pbv_str}
  • *ROE (Return on Equity)*  : {roe_str}
  • *NPM (Net Profit Margin)* : {npm_str}
  • *Dividend Yield*          : {div_str}
  • *Rentang 52 Minggu*       : `{l52_str} - {h52_str}`

💡 *Status Valuasi:* {f['valuation_status']}
━━━━━━━━━━━━━━━━━━━━
_Ketik `/ta {f['symbol']}` untuk teknikal atau `/plan {f['symbol']}` untuk trading plan._
"""
    return msg.strip()

def get_idx_calendar() -> List[Dict[str, Any]]:
    """
    Mengambil jadwal agenda dividen dan tanggal rilis kinerja terdekat dari watchlist
    """
    global _CALENDAR_CACHE, _CALENDAR_CACHE_TIME
    now = time.time()
    if _CALENDAR_CACHE and (now - _CALENDAR_CACHE_TIME < CALENDAR_CACHE_TTL):
        return _CALENDAR_CACHE
        
    tickers = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "ASII.JK", "TLKM.JK", "ADRO.JK", "PTBA.JK", "ITMG.JK", "UNVR.JK", "ICBP.JK"]
    events = []
    
    for t in tickers:
        try:
            ticker_obj = yf.Ticker(t)
            cal = ticker_obj.calendar
            sym = t.replace(".JK", "")
            
            if cal and isinstance(cal, dict):
                ex_div = cal.get("Ex-Dividend Date") or cal.get("Dividend Date")
                earn_date = cal.get("Earnings Date")
                
                if ex_div:
                    ex_str = ex_div.strftime("%d %b %Y") if hasattr(ex_div, "strftime") else str(ex_div)
                    events.append({
                        "symbol": sym,
                        "type": "💰 Dividen (Ex-Date)",
                        "date_str": ex_str,
                        "date_val": ex_div
                    })
                if earn_date:
                    if isinstance(earn_date, list) and len(earn_date) > 0:
                        ed = earn_date[0]
                    else:
                        ed = earn_date
                    ed_str = ed.strftime("%d %b %Y") if hasattr(ed, "strftime") else str(ed)
                    events.append({
                        "symbol": sym,
                        "type": "📑 Rilis Laporan Keuangan",
                        "date_str": ed_str,
                        "date_val": ed
                    })
        except Exception:
            continue
            
    _CALENDAR_CACHE = events
    _CALENDAR_CACHE_TIME = now
    return events

def format_calendar_message() -> str:
    """Format jadwal aksi korporasi & dividen ke Markdown Telegram"""
    events = get_idx_calendar()
    now_str = time.strftime("%d %b %Y")
    
    if not events:
        return f"""
📅 *KALENDER AKSI KORPORASI & DIVIDEN IDX* 🏛️
━━━━━━━━━━━━━━━━━━━━
⏰ *Per Tanggal:* `{now_str}`
ℹ️ Belum ada agenda Cum-Date dividen atau rilis laporan keuangan resmi yang terdaftar untuk minggu ini.
_Gunakan `/fund <KODE>` (contoh: `/fund BBCA`) untuk melihat riwayat dividen emiten tertentu._
"""

    msg = f"""
📅 *KALENDER AKSI KORPORASI & DIVIDEN IDX* 🏛️
━━━━━━━━━━━━━━━━━━━━
⏰ *Tanggal Hari Ini:* `{now_str}`
📋 *Agenda & Jadwal Emiten Terdekat:*

"""
    for ev in events[:8]:
        msg += f"• *{ev['symbol']}* — {ev['type']}\n  🗓️ Tanggal: `{ev['date_str']}`\n"
        
    msg += """━━━━━━━━━━━━━━━━━━━━
💡 *Tip:* Ketik `/fund <KODE>` untuk rincian Dividend Yield dan rasio fundamental emiten.
"""
    return msg.strip()

if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "BBCA"
    print(format_fundamental_message(t))
    print()
    print(format_calendar_message())
