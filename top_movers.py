"""
Modul Pemantau Saham Top Movers IDX (Bursa Efek Indonesia)
Menghitung Top Gainers, Top Losers, dan Most Active (Nilai Transaksi Tertinggi)
berdasarkan saham-saham likuid pilihan (Watchlist).
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
from config import format_idr

# Cache hasil komputasi top movers agar respon bot secepat kilat (2 menit)
_MOVERS_CACHE: Optional[Dict[str, Any]] = None
_CACHE_TIMESTAMP: float = 0
CACHE_TTL = 120  # 120 detik

def get_top_movers(limit: int = 5, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Mengambil data Top Gainers, Top Losers, dan Most Active Turnover dari watchlist IDX.
    """
    global _MOVERS_CACHE, _CACHE_TIMESTAMP
    now = time.time()
    
    if not force_refresh and _MOVERS_CACHE and (now - _CACHE_TIMESTAMP < CACHE_TTL):
        return _MOVERS_CACHE
        
    tickers = config.DEFAULT_WATCHLIST
    try:
        df = yf.download(tickers, period="5d", interval="1d", progress=False)
        if df.empty or 'Close' not in df:
            return {"gainers": [], "losers": [], "most_active": [], "updated_at": time.strftime("%H:%M:%S WIB")}
            
        results = []
        for t in tickers:
            try:
                sub_c = df['Close'][t].dropna()
                sub_v = df['Volume'][t].dropna() if 'Volume' in df else pd.Series()
                if len(sub_c) >= 2:
                    last_price = float(sub_c.iloc[-1])
                    prev_price = float(sub_c.iloc[-2])
                    vol = float(sub_v.iloc[-1]) if len(sub_v) >= 1 else 0.0
                    chg_pt = last_price - prev_price
                    chg_pct = ((last_price - prev_price) / prev_price) * 100 if prev_price > 0 else 0.0
                    turnover = last_price * vol
                    
                    results.append({
                        "symbol": t.replace(".JK", ""),
                        "last_price": last_price,
                        "prev_price": prev_price,
                        "change_pt": chg_pt,
                        "change_pct": round(chg_pct, 2),
                        "volume": int(vol),
                        "turnover": turnover,
                    })
            except Exception:
                continue
                
        if not results:
            return {"gainers": [], "losers": [], "most_active": [], "updated_at": time.strftime("%H:%M:%S WIB")}
            
        gainers = sorted(results, key=lambda x: x["change_pct"], reverse=True)[:limit]
        losers = sorted(results, key=lambda x: x["change_pct"])[:limit]
        most_active = sorted(results, key=lambda x: x["turnover"], reverse=True)[:limit]
        
        data = {
            "gainers": gainers,
            "losers": losers,
            "most_active": most_active,
            "updated_at": time.strftime("%H:%M:%S WIB")
        }
        
        _MOVERS_CACHE = data
        _CACHE_TIMESTAMP = now
        return data
        
    except Exception as e:
        print(f"Error computing top movers: {e}")
        return {"gainers": [], "losers": [], "most_active": [], "updated_at": time.strftime("%H:%M:%S WIB")}

def format_top_movers_summary(limit: int = 5) -> str:
    """Format ringkasan Top Gainers, Losers, dan Most Active dalam 1 tampilan chat"""
    data = get_top_movers(limit=limit)
    gainers = data.get("gainers", [])
    losers = data.get("losers", [])
    most_active = data.get("most_active", [])
    updated = data.get("updated_at", "")
    
    lines = [
        "🔥 *RINGKASAN TOP MOVERS SAHAM IDX*",
        f"🕒 _Update: {updated}_",
        "━━━━━━━━━━━━━━━━━━━━",
        "🚀 *TOP GAINERS (Kenaikan Tertinggi)*"
    ]
    if gainers:
        for i, g in enumerate(gainers, 1):
            lines.append(f"{i}. *{g['symbol']}*: `{format_idr(g['last_price'])}` (*+{g['change_pct']}%*)")
    else:
        lines.append("_Data tidak tersedia_")
        
    lines.append("")
    lines.append("🔻 *TOP LOSERS (Penurunan Terdalam)*")
    if losers:
        for i, l in enumerate(losers, 1):
            lines.append(f"{i}. *{l['symbol']}*: `{format_idr(l['last_price'])}` (*{l['change_pct']}%*)")
    else:
        lines.append("_Data tidak tersedia_")
        
    lines.append("")
    lines.append("💎 *MOST ACTIVE (Turnover Tertinggi)*")
    if most_active:
        for i, a in enumerate(most_active, 1):
            val_m = a['turnover'] / 1_000_000_000
            val_str = f"Rp {val_m:.1f} M" if val_m >= 1 else f"Rp {a['turnover']/1_000_000:.0f} Jt"
            sign = "+" if a['change_pct'] > 0 else ""
            lines.append(f"{i}. *{a['symbol']}*: `{format_idr(a['last_price'])}` ({sign}{a['change_pct']}%) | Val: `{val_str}`")
    else:
        lines.append("_Data tidak tersedia_")
        
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 _Gunakan `/plan <KODE>` atau `/chart <KODE>` untuk analisa mendalam._")
    return "\n".join(lines).strip()

def format_top_gainers_only(limit: int = 8) -> str:
    """Format daftar Top Gainers lengkap"""
    data = get_top_movers(limit=limit)
    gainers = data.get("gainers", [])
    updated = data.get("updated_at", "")
    
    lines = [
        "🚀 *TOP GAINERS SAHAM IDX (HARI INI)*",
        f"🕒 _Update: {updated}_",
        "━━━━━━━━━━━━━━━━━━━━"
    ]
    if not gainers:
        lines.append("⚠️ _Data belum tersedia atau bursa sedang tutup._")
    else:
        for i, g in enumerate(gainers, 1):
            lines.append(
                f"*{i}. {g['symbol']}* ➜ `{format_idr(g['last_price'])}`\n"
                f"   📈 Naik: *+{g['change_pct']}%* ({g['change_pt']:+.0f} pt)\n"
                f"   📊 Volume: `{g['volume']:,}` lot\n"
                f"   🎯 Tindakan: `/plan {g['symbol']}` | `/chart {g['symbol']}`\n"
            )
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚡ _Klik kode di atas untuk melihat trading plan dan chart._")
    return "\n".join(lines).strip()

def format_top_losers_only(limit: int = 8) -> str:
    """Format daftar Top Losers lengkap"""
    data = get_top_movers(limit=limit)
    losers = data.get("losers", [])
    updated = data.get("updated_at", "")
    
    lines = [
        "🔻 *TOP LOSERS SAHAM IDX (HARI INI)*",
        f"🕒 _Update: {updated}_",
        "━━━━━━━━━━━━━━━━━━━━"
    ]
    if not losers:
        lines.append("⚠️ _Data belum tersedia atau bursa sedang tutup._")
    else:
        for i, l in enumerate(losers, 1):
            lines.append(
                f"*{i}. {l['symbol']}* ➜ `{format_idr(l['last_price'])}`\n"
                f"   📉 Turun: *{l['change_pct']}%* ({l['change_pt']:+.0f} pt)\n"
                f"   📊 Volume: `{l['volume']:,}` lot\n"
                f"   🎯 Cek Pantauan: `/flow {l['symbol']}` | `/plan {l['symbol']}`\n"
            )
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 _Saham oversold yang mendekati support kuat berpotensi teknikal rebound._")
    return "\n".join(lines).strip()
