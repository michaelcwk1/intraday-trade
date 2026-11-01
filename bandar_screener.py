"""
Modul Screener Akumulasi Smart Money & Bandar Hunter Saham IDX
Menganalisis dan menyaring seluruh saham watchlist untuk mendeteksi emiten
yang sedang mengalami akumulasi besar oleh Big Fund / Smart Money / Bandar:
- Skor Akumulasi (0-100)
- Chaikin Money Flow (CMF 20) > 0
- On-Balance Volume (OBV) Uptrend
- Volume Spike (RVol) & Inflow Turnover
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
from bandarmology import analyze_bandarmology

_BANDAR_CACHE: Dict[str, Any] = {
    "timestamp": 0,
    "results": []
}
BANDAR_CACHE_EXPIRY = 120  # 2 menit cache

def scan_single_bandar(ticker: str) -> Optional[Dict[str, Any]]:
    try:
        res = analyze_bandarmology(ticker)
        if res.get("valid", False):
            return res
        return None
    except Exception:
        return None

def run_bandar_screener(limit: int = 6, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Menjalankan screener akumulasi bandar di seluruh saham watchlist.
    """
    now = time.time()
    if not force_refresh and (now - _BANDAR_CACHE["timestamp"]) < BANDAR_CACHE_EXPIRY and _BANDAR_CACHE["results"]:
        return {
            "accumulations": _BANDAR_CACHE["results"][:limit],
            "total_scanned": _BANDAR_CACHE.get("total_scanned", len(config.DEFAULT_WATCHLIST)),
            "big_inflow_count": _BANDAR_CACHE.get("big_inflow_count", 0),
            "net_inflow_count": _BANDAR_CACHE.get("net_inflow_count", 0),
            "distribution_count": _BANDAR_CACHE.get("distribution_count", 0),
            "from_cache": True
        }

    watchlist = config.DEFAULT_WATCHLIST
    all_results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        future_map = {executor.submit(scan_single_bandar, t): t for t in watchlist}
        for fut in as_completed(future_map):
            res = fut.result()
            if res:
                all_results.append(res)

    big_inflow = [r for r in all_results if r.get("score", 0) >= 75]
    net_inflow = [r for r in all_results if 60 <= r.get("score", 0) < 75]
    distribution = [r for r in all_results if r.get("score", 0) < 40]

    # Filter yang memenuhi kriteria akumulasi (skor >= 60 dan CMF > 0)
    accum_stocks = [r for r in all_results if r.get("score", 0) >= 60 and r.get("cmf", 0) >= 0]
    # Urutkan berdasarkan Skor Akumulasi tertinggi, lalu RVol dan Turnover
    accum_stocks.sort(key=lambda x: (x.get("score", 0), x.get("rvol", 0), x.get("turnover", 0)), reverse=True)

    _BANDAR_CACHE["timestamp"] = now
    _BANDAR_CACHE["results"] = accum_stocks
    _BANDAR_CACHE["total_scanned"] = len(all_results)
    _BANDAR_CACHE["big_inflow_count"] = len(big_inflow)
    _BANDAR_CACHE["net_inflow_count"] = len(net_inflow)
    _BANDAR_CACHE["distribution_count"] = len(distribution)

    return {
        "accumulations": accum_stocks[:limit],
        "total_scanned": len(all_results),
        "big_inflow_count": len(big_inflow),
        "net_inflow_count": len(net_inflow),
        "distribution_count": len(distribution),
        "from_cache": False
    }

def format_bandar_screener_message(data: Optional[Dict[str, Any]] = None) -> tuple[str, Optional[Dict[str, Any]]]:
    """
    Format pesan Telegram untuk hasil screener bandar hunter.
    Mengembalikan (text, inline_reply_markup).
    """
    if data is None:
        data = run_bandar_screener(limit=6)

    stocks = data.get("accumulations", [])
    total_scanned = data.get("total_scanned", 0)
    big_inflow_cnt = data.get("big_inflow_count", 0)
    net_inflow_cnt = data.get("net_inflow_count", 0)
    dist_cnt = data.get("distribution_count", 0)

    header = (
        "🌐 *SCREENER AKUMULASI SMART MONEY & BANDAR IDX* 🦈\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Statistik Pasar ({total_scanned} Saham Dipindai):*\n"
        f"  • 🟢🟢 Akumulasi Masif (Skor ≥75): `{big_inflow_cnt} emiten`\n"
        f"  • 🟢 Akumulasi Sedang (Skor 60-74): `{net_inflow_cnt} emiten`\n"
        f"  • 🔴 Terindikasi Distribusi: `{dist_cnt} emiten`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if not stocks:
        body = (
            "⚪ *Belum ada emiten dengan akumulasi kuat terdeteksi saat ini.*\n"
            "_Pasar cenderung konsolidasi atau distribusi merata. Disarankan menunggu konfirmasi inflow volume baru._\n"
        )
        return header + body, None

    body_items = []
    top_tickers = []

    for idx, s in enumerate(stocks, 1):
        sym = s["symbol"]
        top_tickers.append(sym)
        score = s["score"]
        status = s["status"]
        close = s["close"]
        chg_1d = s["change_1d"]
        chg_5d = s["change_5d"]
        cmf = s["cmf"]
        rvol = s["rvol"]
        turnover = s["turnover"]
        obv_icon = "📈 Bullish" if s.get("is_obv_uptrend") else "📉 Bearish"

        # Tanda panah perubahan
        chg_sign = "+" if chg_1d >= 0 else ""
        chg_5d_sign = "+" if chg_5d >= 0 else ""

        # Format turnover singkat
        if turnover >= 1_000_000_000_000:
            turn_str = f"Rp {turnover / 1_000_000_000_000:.2f} T"
        elif turnover >= 1_000_000_000:
            turn_str = f"Rp {turnover / 1_000_000_000:.1f} M"
        else:
            turn_str = format_idr(turnover)

        item = (
            f"*{idx}. {sym}* — `{format_idr(close)}` ({chg_sign}{chg_1d}% | 5H: {chg_5d_sign}{chg_5d}%)\n"
            f"   • *Status:* {status}\n"
            f"   • *Skor Bandar:* `{score}/100` | *RVol:* `{rvol:.1f}x` | *Turnover:* `{turn_str}`\n"
            f"   • *Money Flow:* CMF `{cmf:+.3f}` | OBV: {obv_icon}\n"
            f"   • _Catatan: {s['sentiment']}_\n"
        )
        body_items.append(item)

    footer = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Tips Hunter:* Saham dengan skor akumulasi ≥75 dan OBV Uptrend cocok dimasukkan watchlist untuk swing/momentum entry saat pullback!\n"
        "_Gunakan tombol di bawah untuk Trading Plan & Analisis AI:_"
    )

    full_text = header + "\n".join(body_items) + "\n" + footer

    # Buat inline buttons untuk emiten top
    inline_keyboard = []
    first_row = []
    for sym in top_tickers[:3]:
        first_row.append({"text": f"🎯 Plan {sym}", "callback_data": f"btn_plan_{sym}"})
    if first_row:
        inline_keyboard.append(first_row)

    second_row = []
    for sym in top_tickers[:3]:
        second_row.append({"text": f"🤖 AI {sym}", "callback_data": f"btn_ai_{sym}"})
    if second_row:
        inline_keyboard.append(second_row)

    markup = {"inline_keyboard": inline_keyboard} if inline_keyboard else None
    return full_text, markup

if __name__ == "__main__":
    print("Testing bandar screener...")
    res = run_bandar_screener(limit=5, force_refresh=True)
    msg, _ = format_bandar_screener_message(res)
    print(msg)
