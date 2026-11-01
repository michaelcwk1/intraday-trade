"""
Modul Radar Rotasi Sektor & Heatmap Saham IDX (BEI)
Menghitung rata-rata performa harian dan aliran dana pada 8 sektor utama di BEI:
- Perbankan (Finance)
- Energi & Minyak Gas (Energy)
- Tambang Logam & Bahan Baku (Basic Materials)
- Konglomerasi & Perindustrian (Industrial)
- Konsumsi & Farmasi (Consumer Goods)
- Teknologi & Telekomunikasi (Tech & Telco)
- Properti & Semen/Infrastruktur (Property & Infra)
- Ritel, Dagang & Kertas (Retail & Trade)
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
from data_provider import get_stock_data, get_clean_symbol, normalize_ticker

# Pemetaan Sektor Resmi Watchlist IDX
SECTOR_MAP = {
    "🏦 Perbankan & Keuangan": [
        "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "BRIS.JK", "BBTN.JK", "ARTO.JK"
    ],
    "⚡ Energi & Migas": [
        "ADRO.JK", "PTBA.JK", "ITMG.JK", "MEDC.JK", "PGAS.JK", "AKRA.JK"
    ],
    "⛏️ Tambang & Bahan Baku": [
        "ANTM.JK", "INCO.JK", "MDKA.JK", "MBMA.JK", "HRUM.JK", "BUMI.JK", "DEWA.JK"
    ],
    "🏗️ Industri & Konglomerasi": [
        "ASII.JK", "AMMN.JK", "BREN.JK", "TPIA.JK", "BRPT.JK", "UNTR.JK", "PANI.JK", "CUAN.JK"
    ],
    "🛒 Konsumsi & Farmasi": [
        "ICBP.JK", "INDF.JK", "MYOR.JK", "KLBF.JK", "CPIN.JK", "JPFA.JK", "SIDO.JK", "UNVR.JK"
    ],
    "📡 Teknologi & Telko": [
        "TLKM.JK", "ISAT.JK", "EXCL.JK", "GOTO.JK", "BUKA.JK", "EMTK.JK"
    ],
    "🏢 Properti & Infrastruktur": [
        "SMGR.JK", "INTP.JK", "BSDE.JK", "CTRA.JK", "PWON.JK", "JSMR.JK"
    ],
    "🛍️ Ritel & Kertas/Perdagangan": [
        "ACES.JK", "ERAA.JK", "MAPI.JK", "MAPA.JK", "INKP.JK", "TKIM.JK"
    ]
}

_SECTOR_CACHE: Dict[str, Any] = {
    "timestamp": 0,
    "data": {}
}
SECTOR_CACHE_EXPIRY = 120  # 2 menit cache

def fetch_single_ticker_perf(ticker: str) -> Optional[Dict[str, Any]]:
    """Mengambil performa 1 hari dan turnover untuk satu ticker."""
    try:
        clean = get_clean_symbol(ticker)
        df = get_stock_data(ticker, period="5d", interval="1d")
        if df.empty or len(df) < 2:
            return None
        close = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2])
        chg_pct = ((close - prev_close) / prev_close) * 100.0
        volume = float(df['Volume'].iloc[-1])
        turnover = close * volume
        return {
            "symbol": clean,
            "ticker": ticker,
            "close": close,
            "change_pct": round(chg_pct, 2),
            "turnover": turnover
        }
    except Exception:
        return None

def get_sector_performance(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Menghitung performa seluruh sektor dan emiten penggeraknya.
    """
    now = time.time()
    if not force_refresh and (now - _SECTOR_CACHE["timestamp"]) < SECTOR_CACHE_EXPIRY and _SECTOR_CACHE["data"]:
        return _SECTOR_CACHE["data"]

    # Kumpulkan semua emiten unik
    all_tickers = []
    for tickers in SECTOR_MAP.values():
        all_tickers.extend(tickers)
    all_tickers = list(dict.fromkeys(all_tickers))

    ticker_data_map: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        fut_map = {executor.submit(fetch_single_ticker_perf, t): t for t in all_tickers}
        for fut in as_completed(fut_map):
            res = fut.result()
            if res:
                ticker_data_map[res["ticker"]] = res

    sector_results = []

    for sector_name, tickers in SECTOR_MAP.items():
        stocks_in_sector = [ticker_data_map[t] for t in tickers if t in ticker_data_map]
        if not stocks_in_sector:
            continue

        changes = [s["change_pct"] for s in stocks_in_sector]
        avg_change = sum(changes) / len(changes) if changes else 0.0
        total_turnover = sum(s["turnover"] for s in stocks_in_sector)

        # Cari Top Gainer & Top Loser di sektor ini
        sorted_by_change = sorted(stocks_in_sector, key=lambda x: x["change_pct"], reverse=True)
        top_gainer = sorted_by_change[0]
        top_loser = sorted_by_change[-1]

        green_count = sum(1 for c in changes if c > 0)
        red_count = sum(1 for c in changes if c < 0)
        flat_count = sum(1 for c in changes if c == 0)

        # Status badge
        if avg_change >= 0.8:
            status = "🔥 INFLOW KUAT"
        elif avg_change > 0.0:
            status = "🟢 MENGUAT"
        elif avg_change <= -0.8:
            status = "🔴 OUTFLOW/TEKANAN"
        else:
            status = "⚪ NETRAL/FLAT"

        sector_results.append({
            "name": sector_name,
            "avg_change": round(avg_change, 2),
            "status": status,
            "total_turnover": total_turnover,
            "green_count": green_count,
            "red_count": red_count,
            "flat_count": flat_count,
            "total_stocks": len(stocks_in_sector),
            "top_gainer": top_gainer,
            "top_loser": top_loser
        })

    # Urutkan sektor berdasarkan avg_change tertinggi (Sektor Leader ke Laggard)
    sector_results.sort(key=lambda x: x["avg_change"], reverse=True)

    result_payload = {
        "timestamp": now,
        "sectors": sector_results,
        "leader_sector": sector_results[0] if sector_results else None,
        "laggard_sector": sector_results[-1] if sector_results else None
    }

    _SECTOR_CACHE["timestamp"] = now
    _SECTOR_CACHE["data"] = result_payload
    return result_payload

def format_sector_heatmap_message(data: Optional[Dict[str, Any]] = None) -> tuple[str, Optional[Dict[str, Any]]]:
    """
    Format tampilan telegram Heatmap & Radar Rotasi Sektor IDX.
    """
    if data is None:
        data = get_sector_performance()

    sectors = data.get("sectors", [])
    if not sectors:
        return "⚠️ Gagal mengambil data performa sektor IDX saat ini.", None

    leader = data.get("leader_sector")
    laggard = data.get("laggard_sector")

    header = (
        "🗺️ *RADAR ROTASI SEKTOR & HEATMAP PASAR IDX* 🧭\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 *Sektor Pemimpin (Leader):* {leader['name'] if leader else '-'} (`{leader['avg_change']:+.2f}%`)\n"
        f"📉 *Sektor Tertinggal (Laggard):* {laggard['name'] if laggard else '-'} (`{laggard['avg_change']:+.2f}%`)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    body_lines = []
    top_picks = []

    for s in sectors:
        avg = s["avg_change"]
        sign = "+" if avg >= 0 else ""
        bar_icon = "🟩" if avg > 0.5 else ("🟨" if avg >= -0.5 else "🟥")
        
        # Format Top Gainer sektor
        tg = s["top_gainer"]
        tg_sign = "+" if tg["change_pct"] >= 0 else ""
        tg_str = f"`{tg['symbol']}` ({tg_sign}{tg['change_pct']}%)"
        
        if tg["change_pct"] > 0 and len(top_picks) < 3:
            top_picks.append(tg["symbol"])

        line = (
            f"{bar_icon} *{s['name']}* [{sign}{avg:.2f}%]\n"
            f"   • *Status:* {s['status']} ({s['green_count']}🟢 {s['red_count']}🔴 {s['flat_count']}⚪)\n"
            f"   • *Top Mover:* {tg_str}\n"
        )
        body_lines.append(line)

    footer = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Insight Rotasi:* Aliran dana pintar (Smart Money) biasanya merotasi profit dari sektor jenuh ke sektor yang baru mulai menguat (Inflow Kuat).\n"
        "_Klik tombol di bawah untuk melihat Trading Plan saham mover teratas:_"
    )

    full_text = header + "\n".join(body_lines) + "\n" + footer

    inline_keyboard = []
    first_row = []
    for sym in top_picks[:3]:
        first_row.append({"text": f"🎯 Plan {sym}", "callback_data": f"btn_plan_{sym}"})
    if first_row:
        inline_keyboard.append(first_row)

    second_row = [
        {"text": "🌐 Screener Bandar", "callback_data": "btn_akumulasi"},
        {"text": "🚨 Breakout Alert", "callback_data": "btn_breakout"}
    ]
    inline_keyboard.append(second_row)

    markup = {"inline_keyboard": inline_keyboard}
    return full_text, markup

if __name__ == "__main__":
    print("Testing sector heatmap...")
    res = get_sector_performance(force_refresh=True)
    msg, _ = format_sector_heatmap_message(res)
    print(msg)
