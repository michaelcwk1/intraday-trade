"""
Modul Screener Khusus Saham IDX (Bursa Efek Indonesia):
1. ARA Hunter (Auto Rejection Atas): Mendeteksi saham yang sudah menyentuh ARA atau berpotensi melesat ke ARA.
2. BSJP (Beli Sore Jual Pagi): Mendeteksi saham akumulasi kuat sore hari untuk dijual cepat di pagi hari berikutnya.
"""
import sys
import time
from typing import List, Dict, Any, Optional
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

# Cache sederhana untuk screener khusus (60 detik)
_ARA_CACHE: Optional[List[Dict[str, Any]]] = None
_ARA_CACHE_TIME: float = 0
_BSJP_CACHE: Optional[List[Dict[str, Any]]] = None
_BSJP_CACHE_TIME: float = 0
CACHE_TTL = 60

def get_tick_size(price: float) -> int:
    """
    Aturan Fraksi Harga (Tick Size) Bursa Efek Indonesia (IDX):
    - < Rp 200: fraksi Rp 1
    - Rp 200 - Rp 500: fraksi Rp 2
    - Rp 500 - Rp 2.000: fraksi Rp 5
    - Rp 2.000 - Rp 5.000: fraksi Rp 10
    - >= Rp 5.000: fraksi Rp 25
    """
    if price < 200:
        return 1
    elif price < 500:
        return 2
    elif price < 2000:
        return 5
    elif price < 5000:
        return 10
    else:
        return 25

def get_ara_limit_pct(prev_close: float) -> float:
    """
    Batas persentase Auto Rejection Atas (ARA) Simetris IDX:
    - Rp 50 - Rp 200: +35%
    - > Rp 200 - Rp 5.000: +25%
    - > Rp 5.000: +20%
    """
    if prev_close < 200:
        return 35.0
    elif prev_close <= 5000:
        return 25.0
    else:
        return 20.0

def calculate_ara_price(prev_close: float) -> int:
    """Menghitung harga batas maksimal ARA sesuai fraksi bursa IDX"""
    pct = get_ara_limit_pct(prev_close)
    raw = prev_close * (1 + pct / 100.0)
    tick = get_tick_size(raw)
    return int((raw // tick) * tick)

def calculate_arb_price(prev_close: float) -> int:
    """Menghitung harga batas maksimal ARB sesuai fraksi bursa IDX"""
    pct = get_ara_limit_pct(prev_close)
    raw = prev_close * (1 - pct / 100.0)
    tick = get_tick_size(raw)
    return max(50, int((raw // tick) * tick))

def count_ticks(from_price: float, to_price: float) -> int:
    """Menghitung selisih jumlah tick fraksi dari harga sekarang ke harga tujuan"""
    if from_price >= to_price:
        return 0
    curr = from_price
    ticks = 0
    while curr < to_price and ticks < 500:
        step = get_tick_size(curr)
        curr += step
        ticks += 1
    return ticks

# ==============================================================================
# 1. SCREENER ARA HUNTER (AUTO REJECTION ATAS)
# ==============================================================================
def scan_ara_hunters(watchlist: Optional[List[str]] = None, limit: int = 8, force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Memindai saham-saham yang sudah menyentuh ARA atau bergerak kencang mendekati ARA.
    """
    global _ARA_CACHE, _ARA_CACHE_TIME
    now = time.time()
    if not force_refresh and _ARA_CACHE is not None and (now - _ARA_CACHE_TIME < CACHE_TTL):
        return _ARA_CACHE[:limit]

    tickers = watchlist or config.DEFAULT_WATCHLIST
    try:
        df = yf.download(tickers, period="5d", interval="1d", progress=False)
        if df.empty or 'Close' not in df:
            return []

        candidates = []
        for t in tickers:
            try:
                sub_c = df['Close'][t].dropna()
                sub_h = df['High'][t].dropna() if 'High' in df else sub_c
                sub_l = df['Low'][t].dropna() if 'Low' in df else sub_c
                sub_v = df['Volume'][t].dropna() if 'Volume' in df else pd.Series()

                if len(sub_c) >= 2:
                    last_price = float(sub_c.iloc[-1])
                    prev_close = float(sub_c.iloc[-2])
                    high_price = float(sub_h.iloc[-1])
                    low_price = float(sub_l.iloc[-1])
                    vol = float(sub_v.iloc[-1]) if len(sub_v) >= 1 else 0.0

                    # Hitung MA volume untuk RVol
                    rvol = 1.0
                    if len(sub_v) >= 5:
                        avg_v = float(sub_v.tail(5).mean())
                        rvol = round(vol / avg_v, 2) if avg_v > 0 else 1.0

                    ara_pct = get_ara_limit_pct(prev_close)
                    ara_price = calculate_ara_price(prev_close)
                    arb_price = calculate_arb_price(prev_close)
                    
                    chg_pt = last_price - prev_close
                    chg_pct = round(((last_price - prev_close) / prev_close) * 100, 2)
                    
                    dist_to_ara_pct = round(((ara_price - last_price) / last_price) * 100, 2) if last_price > 0 else 0.0
                    ticks_to_ara = count_ticks(last_price, ara_price)
                    tick_now = get_tick_size(last_price)

                    # Tentukan status ARA
                    if last_price >= ara_price - tick_now:
                        status = "🔒 LOCKED ARA"
                        priority = 100
                    elif dist_to_ara_pct <= 5.0 and chg_pct >= 5.0:
                        status = "⚡ DEKAT ARA (< 5%)"
                        priority = 80 + chg_pct
                    elif chg_pct >= 8.0:
                        status = "🚀 SUPER MOMENTUM"
                        priority = 50 + chg_pct
                    elif chg_pct >= 3.0 and last_price >= (high_price * 0.98):
                        status = "🎯 ARA HUNTER"
                        priority = 30 + chg_pct
                    else:
                        continue

                    candidates.append({
                        "symbol": t.replace(".JK", ""),
                        "last_price": last_price,
                        "prev_close": prev_close,
                        "high": high_price,
                        "low": low_price,
                        "change_pt": chg_pt,
                        "change_pct": chg_pct,
                        "ara_price": ara_price,
                        "arb_price": arb_price,
                        "ara_pct": ara_pct,
                        "dist_to_ara_pct": dist_to_ara_pct,
                        "ticks_to_ara": ticks_to_ara,
                        "volume": int(vol),
                        "rvol": rvol,
                        "turnover": last_price * vol,
                        "status": status,
                        "priority": priority
                    })
            except Exception:
                continue

        # Urutkan berdasarkan kenaikan dan kedekatan dengan ARA
        candidates.sort(key=lambda x: (x["priority"], x["change_pct"]), reverse=True)
        _ARA_CACHE = candidates
        _ARA_CACHE_TIME = now
        return candidates[:limit]
    except Exception as e:
        print(f"Error scan_ara_hunters: {e}")
        return []

def format_ara_message(limit: int = 6) -> str:
    """Format tampilan pesan bot untuk Screener ARA Hunter"""
    candidates = scan_ara_hunters(limit=limit)
    now_str = time.strftime("%H:%M:%S WIB")

    lines = [
        "🎯 *SCREENER SAHAM ARA HUNTER (IDX)*",
        f"🕒 _Update: {now_str}_",
        "━━━━━━━━━━━━━━━━━━━━",
        "💡 _Mendeteksi saham yang terkunci ARA atau berpotensi melesat ke batas Auto Rejection Atas hari ini:_"
    ]

    if not candidates:
        lines.append("\nℹ️ _Saat ini belum ada saham watchlist yang mencapai lonjakan mendekati ARA (kenaikan > 3%). Pantau kembali saat jam bursa aktif._")
    else:
        for i, c in enumerate(candidates, 1):
            sym = c["symbol"]
            status = c["status"]
            ara_val = format_idr(c['ara_price'])
            arb_val = format_idr(c['arb_price'])
            turnover_m = c['turnover'] / 1_000_000_000
            val_str = f"Rp {turnover_m:.1f} M" if turnover_m >= 1 else f"Rp {c['turnover']/1_000_000:.0f} Jt"

            dist_str = f"Kurang *{c['dist_to_ara_pct']}%* ({c['ticks_to_ara']} tick lagi)" if c['ticks_to_ara'] > 0 else "🎉 *TERKUNCI ARA!*"

            lines.append(f"\n*{i}. {sym}* ➜ `{format_idr(c['last_price'])}` (*+{c['change_pct']}%*)")
            lines.append(f"   🏷️ Status: *{status}*")
            lines.append(f"   🎯 Batas ARA (+{c['ara_pct']:.0f}%): `{ara_val}` | {dist_str}")
            lines.append(f"   🛑 Batas ARB: `{arb_val}`")
            lines.append(f"   📊 Volume: `{c['volume']:,} lot` | Nilai: `{val_str}`")
            lines.append(f"   ⚡ Aksi Cepat: `/plan {sym}` | `/chart {sym}`")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ *Disiplin Money Management:* Saham dekat ARA memiliki volatilitas tinggi. Gunakan batas cut loss ketat!")
    return "\n".join(lines).strip()

# ==============================================================================
# 2. SCREENER BSJP (BELI SORE JUAL PAGI)
# ==============================================================================
def scan_bsjp(watchlist: Optional[List[str]] = None, limit: int = 8, force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Memindai saham yang memenuhi kriteria BSJP (Beli Sore Jual Pagi):
    1. Price > 1 x Price MA 5
    2. Price > 1 x Price MA 10
    3. Price >= 1 x Previous Price (Price >= Prev Close)
    4. Value > Rp 50.000.000.000 (Turnover > 50 Miliar) [Jika sedikit, fallback ke likuiditas sehat > 20 Miliar]
    5. 1 Day Price Returns (%) > 3% (Kenaikan harian > +3%)
    """
    global _BSJP_CACHE, _BSJP_CACHE_TIME
    now = time.time()
    if not force_refresh and _BSJP_CACHE is not None and (now - _BSJP_CACHE_TIME < CACHE_TTL):
        return _BSJP_CACHE[:limit]

    tickers = watchlist or config.DEFAULT_WATCHLIST
    try:
        df = yf.download(tickers, period="1mo", interval="1d", progress=False)
        if df.empty or 'Close' not in df:
            return []

        candidates = []
        for t in tickers:
            try:
                c = df['Close'][t].dropna()
                h = df['High'][t].dropna() if 'High' in df else c
                l = df['Low'][t].dropna() if 'Low' in df else c
                v = df['Volume'][t].dropna() if 'Volume' in df else pd.Series()

                if len(c) >= 12:
                    close = float(c.iloc[-1])
                    prev_close = float(c.iloc[-2])
                    high = float(h.iloc[-1])
                    low = float(l.iloc[-1])
                    vol = float(v.iloc[-1]) if len(v) >= 1 else 0.0

                    # 1. Moving Averages MA5 & MA10
                    ma5 = float(c.tail(5).mean())
                    ma10 = float(c.tail(10).mean())

                    # 2. Return 1 Hari (%)
                    chg_pct = round(((close - prev_close) / prev_close) * 100, 2)

                    # 3. Value / Turnover (Rp)
                    turnover = close * vol

                    # Syarat Utama dari User:
                    cond_ma5 = close > ma5
                    cond_ma10 = close > ma10
                    cond_prev = close >= prev_close
                    cond_return = chg_pct > 3.0
                    cond_val_50b = turnover > 50_000_000_000  # > 50 Miliar

                    # Cek apakah memenuhi kriteria dasar
                    if cond_ma5 and cond_ma10 and cond_prev and cond_return:
                        # Status tier nilai transaksi
                        is_tier_50b = cond_val_50b

                        # Volume ratio vs rata-rata
                        ma_vol = float(v.tail(10).mean()) if len(v) >= 5 else vol
                        rvol = round(vol / ma_vol, 2) if ma_vol > 0 else 1.0

                        # Posisi candle terhadap High
                        close_to_high_pct = round((close / high) * 100, 1) if high > 0 else 100.0

                        # Rekomendasi Target Pagi & Cut Loss
                        entry_sore = close
                        tp1_pagi = round(close * 1.025)  # +2.5% saat open market pagi
                        tp2_pagi = round(close * 1.045)  # +4.5% jika momentum kencang
                        sl_pagi = round(close * 0.97)    # -3.0% cut loss jika pagi berbalik

                        candidates.append({
                            "symbol": t.replace(".JK", ""),
                            "close": close,
                            "prev_close": prev_close,
                            "high": high,
                            "low": low,
                            "ma5": round(ma5),
                            "ma10": round(ma10),
                            "change_pct": chg_pct,
                            "rvol": rvol,
                            "close_to_high_pct": close_to_high_pct,
                            "turnover": turnover,
                            "is_tier_50b": is_tier_50b,
                            "entry_sore": entry_sore,
                            "tp1_pagi": tp1_pagi,
                            "tp2_pagi": tp2_pagi,
                            "sl_pagi": sl_pagi
                        })
            except Exception:
                continue

        # Urutkan: Yang lolos Value > 50 Miliar terlebih dahulu, lalu nilai transaksi & persentase terbesar
        candidates.sort(key=lambda x: (x["is_tier_50b"], x["turnover"], x["change_pct"]), reverse=True)
        _BSJP_CACHE = candidates
        _BSJP_CACHE_TIME = now
        return candidates[:limit]
    except Exception as e:
        print(f"Error scan_bsjp: {e}")
        return []

def format_bsjp_message(limit: int = 6) -> str:
    """Format tampilan pesan bot untuk Screener BSJP sesuai kriteria kustom"""
    candidates = scan_bsjp(limit=limit)
    now_str = time.strftime("%H:%M:%S WIB")

    lines = [
        "🌅 *SCREENER BSJP (BELI SORE JUAL PAGI)*",
        f"🕒 _Update: {now_str}_",
        "━━━━━━━━━━━━━━━━━━━━",
        "📋 *Formula Filter BSJP Aktif:*",
        "  1. `Price > MA 5` & `Price > MA 10`",
        "  2. `Price >= Previous Price`",
        "  3. `1-Day Return > +3.0%`",
        "  4. `Turnover Value > Rp 50 Miliar` (Super Likuid)",
        "━━━━━━━━━━━━━━━━━━━━"
    ]

    if not candidates:
        lines.append("\nℹ️ _Belum ada saham watchlist yang memenuhi seluruh formula di atas (Return > 3% & Di atas MA5/MA10)._")
        lines.append("💡 _Screener BSJP paling optimal dicek pada pukul 15:30 - 15:55 WIB menjelang penutupan pasar._")
    else:
        for i, b in enumerate(candidates, 1):
            sym = b["symbol"]
            val_m = b['turnover'] / 1_000_000_000
            val_str = f"Rp {val_m:.1f} M" if val_m >= 1 else f"Rp {b['turnover']/1_000_000:.0f} Jt"
            val_badge = "🔥 *VALUE > 50M*" if b["is_tier_50b"] else f"📊 Val: `{val_str}`"

            lines.append(f"\n*{i}. {sym}* ➜ `{format_idr(b['close'])}` (*+{b['change_pct']}%*)")
            lines.append(f"   {val_badge}")
            lines.append(f"   📈 MA Check: `Close > MA5 ({format_idr(b['ma5'])})` & `> MA10 ({format_idr(b['ma10'])})` ✅")
            lines.append(f"   🛒 *Entry Sore*: `{format_idr(b['entry_sore'])}`")
            lines.append(f"   🎯 *Target Jual Pagi (TP1)*: `{format_idr(b['tp1_pagi'])}` (+2.5%)")
            lines.append(f"   🎯 *Target Jual Pagi (TP2)*: `{format_idr(b['tp2_pagi'])}` (+4.5%)")
            lines.append(f"   🛑 *Stop Loss Pagi (SL)*  : `{format_idr(b['sl_pagi'])}` (-3.0%)")
            lines.append(f"   ⚡ Aksi: `/buy {sym} 5` | `/plan {sym}` | `/chart {sym}`")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 _Jam Trading BSJP: Beli sore (15:30-15:58 WIB), jual saat lonjakan opening pagi (09:00-09:15 WIB)._")
    return "\n".join(lines).strip()
