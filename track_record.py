"""
Rekam Jejak Rekomendasi
Mengevaluasi snapshot rekomendasi lama: apakah TP1 atau SL yang tersentuh lebih dulu.

Aturan evaluasi (konservatif):
- Dianggap terisi jika harga low <= batas atas zona entry dalam masa berlaku.
- Jika TP1 dan SL tersentuh di candle yang sama, dihitung kena SL.
- Masa berlaku: scalp 2 hari bursa, invest 20 hari bursa, forex 24 jam.
- Belum kena TP/SL saat masa berlaku habis -> dinilai dari harga penutupan terakhir.
"""
import json
import time
from datetime import timedelta
from typing import Dict, Any, List

import pandas as pd
import yfinance as yf

import config
from data_provider import get_stock_data
from market_session import now_wib
from recommender import list_snapshots

# harian: 1 hari bursa, mingguan: Senin-Jumat. scalp/invest = format lama, tetap dihitung.
HOLD_DAYS = {"harian": 1, "mingguan": 5, "scalp": 2, "invest": 20}
FX_LOG = config.DATA_DIR / "fx_signals.jsonl"
FX_HOLD_HOURS = 24

_CACHE: Dict[str, Any] = {"time": 0.0, "data": None}
CACHE_TTL = 300


def _evaluate(bars: pd.DataFrame, side: str, entry: float, sl: float, tp1: float) -> Dict[str, Any]:
    """Jalan candle per candle dan tentukan hasil pertama yang tersentuh."""
    risk = abs(entry - sl)
    filled = False
    for _, bar in bars.iterrows():
        hi, lo = float(bar["High"]), float(bar["Low"])
        if not filled:
            filled = lo <= entry if side == "buy" else hi >= entry
            if not filled:
                continue
        hit_sl = lo <= sl if side == "buy" else hi >= sl
        hit_tp = hi >= tp1 if side == "buy" else lo <= tp1
        if hit_sl:
            return {"status": "sl", "r": -1.0}
        if hit_tp:
            return {"status": "tp", "r": round(abs(tp1 - entry) / risk, 2) if risk else 0.0}
    if not filled:
        return {"status": "tidak terisi", "r": 0.0}
    last = float(bars["Close"].iloc[-1])
    move = (last - entry) if side == "buy" else (entry - last)
    return {"status": "berjalan", "r": round(move / risk, 2) if risk else 0.0}


def _stock_results() -> List[Dict[str, Any]]:
    today = now_wib().strftime("%Y-%m-%d")
    snaps = [s for s in list_snapshots() if s.get("valid_for", today) <= today]
    symbols = sorted({p["symbol"] for s in snaps for k in HOLD_DAYS for p in s.get(k, [])})
    if not symbols:
        return []

    tickers = [f"{s}.JK" for s in symbols]
    raw = yf.download(tickers, period="6mo", interval="1d", progress=False, auto_adjust=True)
    results = []
    for snap in snaps:
        start = pd.Timestamp(snap["valid_for"])
        for kind, hold in HOLD_DAYS.items():
            for p in snap.get(kind, []):
                try:
                    t = f"{p['symbol']}.JK"
                    if len(tickers) == 1:
                        bars = raw[["High", "Low", "Close"]].copy()
                        bars.columns = ["High", "Low", "Close"]
                    else:
                        bars = pd.DataFrame({c: raw[c][t] for c in ["High", "Low", "Close"]})
                    bars = bars.dropna()
                    bars.index = bars.index.tz_localize(None) if bars.index.tz is not None else bars.index
                    window = bars[bars.index >= start].head(hold)
                    if window.empty:
                        continue
                    res = _evaluate(window, "buy", p["entry_high"], p["sl"], p["tp1"])
                    if res["status"] == "berjalan" and len(window) >= hold:
                        res["status"] = "kedaluwarsa"
                    results.append({
                        "date": snap["valid_for"], "session": snap.get("session", kind), "kind": kind,
                        "symbol": p["symbol"], "grade": p["grade"],
                        "entry": p["entry_high"], "sl": p["sl"], "tp1": p["tp1"], **res,
                    })
                except Exception:
                    continue
    return results


def log_fx_signals(signals: List[Dict[str, Any]], generated_at: str) -> None:
    """Simpan sinyal forex grade A/B (maks. 1 per simbol per jam) untuk dievaluasi nanti."""
    try:
        existing = set()
        if FX_LOG.exists():
            for line in FX_LOG.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                existing.add((row["symbol"], row["time"][:13]))
        rows = []
        for s in signals:
            if not s.get("valid") or s.get("grade") not in ("A", "B") or not s.get("plan"):
                continue
            if (s["symbol"], generated_at[:13]) in existing:
                continue
            p = s["plan"]
            rows.append({"time": generated_at, "symbol": s["symbol"], "grade": s["grade"], "offset": s.get("offset", 0.0),
                         "side": p["side"], "entry": p["entry"], "sl": p["sl"], "tp1": p["tp1"]})
        if rows:
            config.DATA_DIR.mkdir(parents=True, exist_ok=True)
            with FX_LOG.open("a", encoding="utf-8") as f:
                for row in rows:
                    f.write(json.dumps(row) + "\n")
    except Exception:
        pass


def _fx_results() -> List[Dict[str, Any]]:
    from forex_signals import INSTRUMENTS
    if not FX_LOG.exists():
        return []
    tickers = {i["symbol"]: i["ticker"] for i in INSTRUMENTS}
    results = []
    for line in FX_LOG.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            bars = get_stock_data(tickers[row["symbol"]], period="1mo", interval="15m")
            if bars.empty:
                continue
            start = pd.Timestamp(row["time"]).tz_localize("Asia/Jakarta")
            idx = bars.index.tz_convert("Asia/Jakarta")
            window = bars[(idx > start) & (idx <= start + timedelta(hours=FX_HOLD_HOURS))]
            if window.empty:
                continue
            off = row.get("offset", 0.0)
            res = _evaluate(window, row["side"], row["entry"] - off, row["sl"] - off, row["tp1"] - off)
            if res["status"] == "berjalan" and idx[-1] >= start + timedelta(hours=FX_HOLD_HOURS):
                res["status"] = "kedaluwarsa"
            results.append({"date": row["time"], "session": "-", "kind": "forex", "symbol": row["symbol"],
                            "grade": row["grade"], "entry": row["entry"], "sl": row["sl"], "tp1": row["tp1"], **res})
        except Exception:
            continue
    return results


def _summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    closed = [r for r in rows if r["status"] in ("tp", "sl", "kedaluwarsa")]
    wins = [r for r in closed if r["r"] > 0]
    return {
        "total": len(rows),
        "closed": len(closed),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "avg_r": round(sum(r["r"] for r in closed) / len(closed), 2) if closed else None,
    }


def get_track_record(force_refresh: bool = False) -> Dict[str, Any]:
    now = time.time()
    if not force_refresh and _CACHE["data"] and now - _CACHE["time"] < CACHE_TTL:
        return _CACHE["data"]
    rows = _stock_results() + _fx_results()
    summary = {}
    kinds = ["harian", "mingguan"] + [k for k in ("scalp", "invest") if any(r["kind"] == k for r in rows)] + ["forex"]
    for kind in kinds:
        kr = [r for r in rows if r["kind"] == kind]
        summary[kind] = {
            **_summarize(kr),
            "by_grade": {g: _summarize([r for r in kr if r["grade"] == g]) for g in sorted({r["grade"] for r in kr})},
        }
    rows.sort(key=lambda r: r["date"], reverse=True)
    data = {"summary": summary, "rows": rows[:200]}
    _CACHE.update(time=now, data=data)
    return data


if __name__ == "__main__":
    out = get_track_record(force_refresh=True)
    for kind, s in out["summary"].items():
        print(kind, s)
    for r in out["rows"][:15]:
        print(r)
