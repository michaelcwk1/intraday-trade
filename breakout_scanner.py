"""
Modul Deteksi Real-Time Volume Breakout Saham IDX
Mendeteksi lonjakan volume mendadak (Volume Spike / Breakout) yang disertai kenaikan harga:
- RVOL >= 2.0x (Volume perdagangan > 2x rata-rata 20 hari)
- Kenaikan harga >= +2.0%
- Nilai transaksi (Turnover) >= Rp 2 Miliar
- Breakout resistance / MA20
"""
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import config
from config import format_idr
from data_provider import get_stock_data, get_clean_symbol

_BREAKOUT_CACHE: Dict[str, Any] = {
    "timestamp": 0,
    "results": []
}
BREAKOUT_CACHE_EXPIRY = 60  # 1 menit cache

# Menyimpan riwayat sinyal yang telah dikirim agar tidak spam di background scheduler
# Format: {symbol: "YYYY-MM-DD"}
_SENT_BREAKOUT_ALERTS: Dict[str, str] = {}

def scan_single_breakout(ticker: str) -> Optional[Dict[str, Any]]:
    try:
        clean = get_clean_symbol(ticker)
        df = get_stock_data(ticker, period="3mo", interval="1d")
        if df.empty or len(df) < 21:
            return None

        data = df.copy()
        close = float(data['Close'].iloc[-1])
        prev_close = float(data['Close'].iloc[-2])
        change_pct = ((close - prev_close) / prev_close) * 100.0
        volume = float(data['Volume'].iloc[-1])
        turnover = close * volume

        # Hitung RVol (Volume hari ini dibanding rata-rata 20 hari sebelumnya)
        vol_ma20 = float(data['Volume'].iloc[-21:-1].mean())
        if vol_ma20 <= 0:
            return None
        rvol = volume / vol_ma20

        # Moving Average
        ma20 = float(data['Close'].iloc[-20:].mean())
        ma50 = float(data['Close'].iloc[-50:].mean()) if len(data) >= 50 else ma20
        high_20d = float(data['High'].iloc[-21:-1].max())

        is_break_ma20 = close > ma20 and data['Close'].iloc[-2] <= ma20
        is_break_high20 = close >= (high_20d * 0.99) # Mendekati atau menembus resist 20 hari

        # Kriteria Breakout: RVol >= 2.0x dan harga naik >= 2.0% dan turnover >= Rp 2 Miliar
        is_breakout = (rvol >= 2.0) and (change_pct >= 2.0) and (turnover >= 2_000_000_000)

        if not is_breakout:
            # Toleransi jika RVol luar biasa tinggi (>= 3.0x) walau harga naik >= 1.5%
            if rvol >= 3.0 and change_pct >= 1.5 and turnover >= 2_000_000_000:
                is_breakout = True

        if is_breakout:
            return {
                "symbol": clean,
                "ticker": ticker,
                "close": close,
                "change_pct": round(change_pct, 2),
                "volume": volume,
                "turnover": turnover,
                "rvol": round(rvol, 2),
                "ma20": round(ma20),
                "high_20d": round(high_20d),
                "is_break_high20": is_break_high20,
                "is_break_ma20": is_break_ma20
            }
        return None
    except Exception:
        return None

def get_breakout_stocks(force_refresh: bool = False) -> List[Dict[str, Any]]:
    now = time.time()
    if not force_refresh and (now - _BREAKOUT_CACHE["timestamp"]) < BREAKOUT_CACHE_EXPIRY and _BREAKOUT_CACHE["results"]:
        return _BREAKOUT_CACHE["results"]

    watchlist = config.DEFAULT_WATCHLIST
    results = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        fut_map = {executor.submit(scan_single_breakout, t): t for t in watchlist}
        for fut in as_completed(fut_map):
            res = fut.result()
            if res:
                results.append(res)

    # Urutkan berdasarkan lonjakan RVol tertinggi
    results.sort(key=lambda x: (x["rvol"], x["change_pct"]), reverse=True)

    _BREAKOUT_CACHE["timestamp"] = now
    _BREAKOUT_CACHE["results"] = results
    return results

def format_breakout_message(stocks: Optional[List[Dict[str, Any]]] = None) -> tuple[str, Optional[Dict[str, Any]]]:
    """
    Format pesan Telegram untuk hasil pemindaian Breakout Volume.
    """
    if stocks is None:
        stocks = get_breakout_stocks()

    header = (
        "🚨 *RADAR REAL-TIME: VOLUME BREAKOUT & SPIKE HUNTER* ⚡\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Saham dengan lonjakan volume tidak wajar (*RVol ≥ 2.0x*) dan kenaikan harga signifikan (*≥ +2%*) likuiditas prima:\n\n"
    )

    if not stocks:
        body = (
            "⚪ *Belum ada saham yang memenuhi kriteria Volume Breakout saat ini.*\n"
            "_Sistem auto-alert terus memantau di background selama jam bursa berlangsung._\n"
        )
        return header + body, None

    body_lines = []
    top_tickers = []

    for idx, s in enumerate(stocks[:6], 1):
        sym = s["symbol"]
        top_tickers.append(sym)
        close = s["close"]
        chg = s["change_pct"]
        rvol = s["rvol"]
        turnover = s["turnover"]
        
        # Format turnover
        if turnover >= 1_000_000_000_000:
            turn_str = f"Rp {turnover / 1_000_000_000_000:.2f} T"
        elif turnover >= 1_000_000_000:
            turn_str = f"Rp {turnover / 1_000_000_000:.1f} M"
        else:
            turn_str = format_idr(turnover)

        extra_tags = []
        if rvol >= 3.0:
            extra_tags.append("💥 *SUPER SPIKE*")
        if s.get("is_break_high20"):
            extra_tags.append("🎯 *BREAK 20D HIGH*")

        tag_str = f" [{' | '.join(extra_tags)}]" if extra_tags else ""

        line = (
            f"*{idx}. {sym}* — `{format_idr(close)}` (+{chg}%){tag_str}\n"
            f"   • *Lonjakan Volume:* `{rvol:.1f}x Lipat Normal`\n"
            f"   • *Nilai Transaksi:* `{turn_str}`\n"
            f"   • *Resistensi 20H:* `{format_idr(s['high_20d'])}`\n"
        )
        body_lines.append(line)

    footer = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ *Catatan:* Lonjakan volume besar di awal sesi adalah konfirmasi minat institusi/bandar. Pasang trailing stop disiplin!\n"
        "_Klik tombol di bawah untuk melihat Trading Plan & Grafik:_"
    )

    full_text = header + "\n".join(body_lines) + "\n" + footer

    inline_keyboard = []
    first_row = []
    for sym in top_tickers[:3]:
        first_row.append({"text": f"🎯 Plan {sym}", "callback_data": f"btn_plan_{sym}"})
    if first_row:
        inline_keyboard.append(first_row)

    second_row = []
    for sym in top_tickers[:3]:
        second_row.append({"text": f"📊 Chart {sym}", "callback_data": f"btn_chart_{sym}"})
    if second_row:
        inline_keyboard.append(second_row)

    markup = {"inline_keyboard": inline_keyboard}
    return full_text, markup

def check_new_breakout_alerts(current_date_str: str) -> List[Dict[str, Any]]:
    """
    Dipanggil oleh background scheduler setiap 60 detik selama jam bursa.
    Hanya mengembalikan saham breakout yang belum pernah dikirim notifikasinya pada hari ini.
    """
    stocks = get_breakout_stocks(force_refresh=True)
    new_alerts = []

    for s in stocks:
        sym = s["symbol"]
        # Hanya picu jika lonjakan sangat signifikan (rvol >= 2.5x)
        if s["rvol"] >= 2.5 and s["change_pct"] >= 2.0:
            last_date = _SENT_BREAKOUT_ALERTS.get(sym)
            if last_date != current_date_str:
                _SENT_BREAKOUT_ALERTS[sym] = current_date_str
                new_alerts.append(s)

    return new_alerts
