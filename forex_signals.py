"""
Sinyal Entry Forex Intraday (M15 / H1) untuk akun Exness cent:
XAUUSD, EURUSD, GBPUSD.

Alur analisis:
1. Bias H1   : EMA50 vs EMA200 + kemiringan EMA50.
2. Trigger M15: pullback ke EMA20 lalu RSI kembali melewati 50 searah bias,
                atau break swing high/low 20 candle terakhir.
3. Sesi      : setup di jam London / New York dinilai lebih tinggi.
Level SL di balik swing terakhir +/- 0.5 ATR(M15), TP1 = 1R, TP2 = 2R.
"""
import time
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd

from data_provider import get_stock_data, get_current_price
from datetime import timedelta

from market_session import now_wib, fx_sessions, next_m15_close, next_prime_start
from user_settings import load_settings

INSTRUMENTS = [
    # pip = ukuran 1 pip/poin yang ditampilkan; contract_key = setting ukuran kontrak per lot
    {"symbol": "XAUUSD", "ticker": "GC=F", "name": "Emas", "pip": 0.1, "digits": 2, "contract_key": "xau_contract_size"},
    {"symbol": "EURUSD", "ticker": "EURUSD=X", "name": "Euro / Dolar", "pip": 0.0001, "digits": 5, "contract_key": "fx_contract_size"},
    {"symbol": "GBPUSD", "ticker": "GBPUSD=X", "name": "Pound / Dolar", "pip": 0.0001, "digits": 5, "contract_key": "fx_contract_size"},
]

_CACHE: Dict[str, Any] = {"time": 0.0, "data": None}
CACHE_TTL = 120


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift()).abs(),
        (df["Low"] - df["Close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _h1_bias(h1: pd.DataFrame) -> Dict[str, Any]:
    close = h1["Close"]
    e50, e200 = _ema(close, 50), _ema(close, 200)
    slope = float(e50.iloc[-1] - e50.iloc[-6])
    last = float(close.iloc[-1])
    if e50.iloc[-1] > e200.iloc[-1] and slope > 0 and last > e200.iloc[-1]:
        bias = "naik"
    elif e50.iloc[-1] < e200.iloc[-1] and slope < 0 and last < e200.iloc[-1]:
        bias = "turun"
    else:
        bias = "sideways"
    return {"bias": bias, "ema50": float(e50.iloc[-1]), "ema200": float(e200.iloc[-1])}


def _m15_trigger(m15: pd.DataFrame, bias: str) -> Dict[str, Any]:
    close = m15["Close"]
    e20 = _ema(close, 20)
    rsi = _rsi(close)
    atr = _atr(m15)
    recent = m15.tail(25)
    last_close = float(close.iloc[-1])
    swing_high = float(recent["High"].iloc[:-1].max())
    swing_low = float(recent["Low"].iloc[:-1].min())

    touched_e20_up = (m15["Low"].tail(6) <= e20.tail(6)).any()
    touched_e20_dn = (m15["High"].tail(6) >= e20.tail(6)).any()
    rsi_now, rsi_prev = float(rsi.iloc[-1]), float(rsi.iloc[-3:-1].min())
    rsi_prev_max = float(rsi.iloc[-3:-1].max())

    trigger, side = None, None
    if bias == "naik":
        if touched_e20_up and last_close > e20.iloc[-1] and rsi_now > 50 >= rsi_prev:
            trigger, side = "Pullback ke EMA20 M15 lalu memantul, RSI naik lewat 50", "buy"
        elif last_close > swing_high:
            trigger, side = "Break high 25 candle M15 searah tren", "buy"
    elif bias == "turun":
        if touched_e20_dn and last_close < e20.iloc[-1] and rsi_now < 50 <= rsi_prev_max:
            trigger, side = "Pullback ke EMA20 M15 lalu tertolak, RSI turun lewat 50", "sell"
        elif last_close < swing_low:
            trigger, side = "Break low 25 candle M15 searah tren", "sell"

    return {
        "trigger": trigger,
        "side": side,
        "close": last_close,
        "ema20": float(e20.iloc[-1]),
        "rsi": round(rsi_now, 1),
        "atr": float(atr.iloc[-1]),
        "swing_high": swing_high,
        "swing_low": swing_low,
        "last_bar": m15.index[-1],
    }


def _usd_idr() -> float:
    rate = get_current_price("USDIDR=X")
    return rate if rate and rate > 1000 else 16_500.0


def _lot_size(risk_usc: float, sl_distance: float, contract: float) -> float:
    """Lot cent: di akun cent P/L dihitung dalam USC = jarak harga x ukuran kontrak."""
    loss_per_lot_usc = sl_distance * contract
    if loss_per_lot_usc <= 0:
        return 0.0
    lots = np.floor(risk_usc / loss_per_lot_usc * 100) / 100
    return float(max(lots, 0.0))


def analyze_instrument(inst: Dict[str, Any], settings: Dict[str, Any], balance_usc: float, prime: bool) -> Dict[str, Any]:
    h1 = get_stock_data(inst["ticker"], period="60d", interval="1h")
    m15 = get_stock_data(inst["ticker"], period="5d", interval="15m")
    base = {"symbol": inst["symbol"], "name": inst["name"], "digits": inst["digits"]}
    if h1.empty or len(h1) < 200 or m15.empty or len(m15) < 40:
        return {**base, "valid": False, "error": "Data intraday belum tersedia"}

    offset = settings["xau_offset"] if inst["symbol"] == "XAUUSD" else 0.0
    bias = _h1_bias(h1)
    trig = _m15_trigger(m15, bias["bias"])
    atr = trig["atr"]
    price = trig["close"]
    pip = inst["pip"]

    checks = {
        "trend_h1": bias["bias"] != "sideways",
        "trigger_m15": trig["side"] is not None,
        "session": prime,
    }
    passed = sum(checks.values())
    if checks["trend_h1"] and checks["trigger_m15"]:
        grade = "A" if prime else "B"
    elif checks["trend_h1"]:
        grade = "Tunggu"
    else:
        grade = "Hindari"

    side = trig["side"] or ("buy" if bias["bias"] == "naik" else "sell" if bias["bias"] == "turun" else None)
    plan = None
    if side:
        word = "Buy" if side == "buy" else "Sell"
        ema_on_right_side = trig["ema20"] < price if side == "buy" else trig["ema20"] > price
        if trig["side"]:
            entry, order_type = price, f"{word} sekarang (market)"
        elif ema_on_right_side:
            # Belum ada trigger: pasang limit di area pullback EMA20 M15
            entry, order_type = trig["ema20"], f"{word} limit di area EMA20 M15"
        else:
            entry, order_type = price, "Tunggu candle konfirmasi M15"
        if side == "buy":
            sl = min(trig["swing_low"], entry - atr) - 0.5 * atr
            sl = max(sl, entry - 3 * atr)
            risk = entry - sl
            tp1, tp2 = entry + risk, entry + 2 * risk
        else:
            sl = max(trig["swing_high"], entry + atr) + 0.5 * atr
            sl = min(sl, entry + 3 * atr)
            risk = sl - entry
            tp1, tp2 = entry - risk, entry - 2 * risk

        risk_usc = balance_usc * settings["fx_risk_pct"] / 100
        lots = _lot_size(risk_usc, risk, settings[inst["contract_key"]])
        actual_risk_usc = lots * risk * settings[inst["contract_key"]]
        d = inst["digits"]
        plan = {
            "side": side,
            "order_type": order_type,
            "entry": round(entry + offset, d),
            "sl": round(sl + offset, d),
            "tp1": round(tp1 + offset, d),
            "tp2": round(tp2 + offset, d),
            "sl_pips": round(risk / pip, 1),
            "tp1_pips": round(risk / pip, 1),
            "tp2_pips": round(2 * risk / pip, 1),
            "lots": lots,
            "risk_usc": round(actual_risk_usc),
            "risk_idr": round(actual_risk_usc / 100 * _usd_idr()),
            "min_lot_too_big": lots < 0.01,
        }

    insight = _insight(inst, bias, trig, prime, grade, plan)
    action = _action(grade, plan, prime)
    return {
        **base,
        "valid": True,
        "price": round(price + offset, inst["digits"]),
        "offset": offset,
        "bias": bias["bias"],
        "rsi_m15": trig["rsi"],
        "atr_pips": round(atr / pip, 1),
        "trigger": trig["trigger"],
        "grade": grade,
        "checks": checks,
        "checks_passed": passed,
        "plan": plan,
        "insight": insight,
        "action": action,
        "last_bar": trig["last_bar"].tz_convert("Asia/Jakarta").strftime("%Y-%m-%d %H:%M") if trig["last_bar"].tzinfo else str(trig["last_bar"]),
    }


def _action(grade: str, plan: Optional[Dict[str, Any]], prime: bool) -> Dict[str, Any]:
    """Instruksi singkat + jam eksekusi (WIB) untuk ringkasan Hari Ini.

    kind: now (eksekusi sekarang), limit (pasang order limit), wait (tunggu jam tertentu), skip.
    at  : jam patokan dalam WIB (ISO); deadline untuk 'now', jam cek ulang untuk lainnya.
    """
    now = now_wib()
    m15 = next_m15_close(now)
    iso = lambda d: d.isoformat(timespec="minutes")
    word = plan["side"].upper() if plan else ""

    if grade == "Hindari":
        nxt = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        return {"kind": "skip", "text": "Jangan entry · sideways", "at": iso(nxt), "at_label": "Cek lagi"}
    if grade in ("A", "B"):
        txt = f"{word} sekarang" + ("" if prime else " · lot kecil")
        return {"kind": "now", "text": txt, "at": iso(m15), "at_label": "Paling lambat"}
    # Tunggu: tren ada, trigger belum muncul
    if not prime:
        start = next_prime_start(now)
        closed = not fx_sessions(now)["active"]
        txt = "Pasar tutup" if closed else "Tunggu jam London"
        return {"kind": "wait", "text": f"{txt} · arah {word}", "at": iso(start), "at_label": "Cek pukul"}
    if plan and "limit" in plan["order_type"]:
        return {"kind": "limit", "text": f"Pasang {word} LIMIT", "at": iso(m15 + timedelta(minutes=45)), "at_label": "Batalkan jika belum kena"}
    return {"kind": "wait", "text": f"Tunggu konfirmasi M15 · arah {word}", "at": iso(m15), "at_label": "Cek pukul"}


def _insight(inst, bias, trig, prime, grade, plan) -> List[str]:
    lines = []
    if bias["bias"] == "naik":
        lines.append("Tren H1 naik (EMA50 di atas EMA200). Cari posisi buy saja, jangan melawan tren.")
    elif bias["bias"] == "turun":
        lines.append("Tren H1 turun (EMA50 di bawah EMA200). Cari posisi sell saja, jangan melawan tren.")
    else:
        lines.append("H1 sideways, EMA50 dan EMA200 berdekatan. Peluang salah arah besar, lebih baik tidak entry.")

    if trig["trigger"]:
        lines.append(f"Trigger M15: {trig['trigger']}.")
    elif bias["bias"] != "sideways" and plan and "limit" in plan["order_type"]:
        lines.append("Belum ada trigger M15. Pasang limit di area EMA20 M15; batalkan jika tren H1 berubah.")
    elif bias["bias"] != "sideways":
        lines.append("Belum ada trigger M15 dan harga sudah melewati EMA20. Tunggu candle M15 yang memantul searah tren sebelum entry.")

    if not prime:
        lines.append("Sekarang di luar jam London/New York. Gerak biasanya lambat dan spread lebih lebar.")
    if trig["rsi"] >= 75 or trig["rsi"] <= 25:
        lines.append(f"RSI M15 {trig['rsi']:.0f} sudah ekstrem. Rawan koreksi, jangan kejar harga.")
    if plan and plan["min_lot_too_big"]:
        lines.append("Saldo terlalu kecil untuk jarak SL ini. Lot minimum 0.01 sudah melebihi batas risiko.")
    return lines[:4]


def get_forex_signals(force_refresh: bool = False) -> Dict[str, Any]:
    now = time.time()
    if not force_refresh and _CACHE["data"] and now - _CACHE["time"] < CACHE_TTL:
        return _CACHE["data"]

    settings = load_settings()
    usd_idr = _usd_idr()
    balance_usc = settings["fx_balance_idr"] / usd_idr * 100
    session = fx_sessions(now_wib())
    results = []
    for inst in INSTRUMENTS:
        try:
            results.append(analyze_instrument(inst, settings, balance_usc, session["is_prime"]))
        except Exception as e:
            results.append({"symbol": inst["symbol"], "name": inst["name"], "valid": False, "error": str(e)})

    data = {
        "generated_at": now_wib().strftime("%Y-%m-%d %H:%M"),
        "session": session,
        "usd_idr": round(usd_idr),
        "balance_usc": round(balance_usc),
        "risk_pct": settings["fx_risk_pct"],
        "signals": results,
    }
    _CACHE.update(time=now, data=data)
    from track_record import log_fx_signals
    log_fx_signals(results, data["generated_at"])
    return data


def set_xau_offset(exness_price: float) -> Dict[str, Any]:
    """Simpan selisih harga XAU Exness (spot) terhadap GC=F (futures) Yahoo."""
    from user_settings import save_settings
    futures = get_current_price("GC=F")
    if not futures:
        return {"success": False, "message": "Harga GC=F tidak tersedia"}
    offset = round(exness_price - futures, 2)
    save_settings({"xau_offset": offset})
    _CACHE["data"] = None
    return {"success": True, "offset": offset, "futures": futures}


if __name__ == "__main__":
    out = get_forex_signals(force_refresh=True)
    print(f"Sesi: {out['session']['label']} | saldo {out['balance_usc']} USC | USD/IDR {out['usd_idr']}")
    for s in out["signals"]:
        if not s.get("valid"):
            print(s["symbol"], "error:", s.get("error"))
            continue
        print(f"\n{s['symbol']} {s['price']} | bias {s['bias']} | grade {s['grade']} | data {s['last_bar']}")
        if s["plan"]:
            p = s["plan"]
            print(f"  {p['side'].upper()} {p['order_type']} @ {p['entry']}  SL {p['sl']} ({p['sl_pips']} pip)  "
                  f"TP {p['tp1']}/{p['tp2']}  lot {p['lots']}  risiko {p['risk_usc']} USC")
        for line in s["insight"]:
            print("  -", line)
