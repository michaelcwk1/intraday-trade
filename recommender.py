"""
Rekomendasi Saham (IDX / BEI) dengan modal dibagi dua:
- Harian   : beli saat bursa buka, jual sore di hari yang sama (intraday).
- Mingguan : beli Senin, jual Jumat sore (swing 1 minggu).

Daftar dibuat setelah bursa tutup (16:30 WIB) dari rekap harian:
- Harian   : setiap hari bursa, untuk hari bursa berikutnya.
- Mingguan : setiap Jumat, untuk minggu berikutnya.

Setiap rekomendasi berisi zona entry, stop loss, target, jumlah lot sesuai
modal masing-masing, dan risiko dalam Rupiah. Snapshot disimpan di data/picks/
supaya bisa dievaluasi di Rekam Jejak.
"""
import json
import math
import os
import sys
import threading
import time
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

import config
from bandarmology import compute_cmf
from market_session import now_wib, next_trading_day, prev_trading_day, WIB
from special_screeners import get_tick_size
from strategy import calculate_indicators
from user_settings import load_settings

PICKS_DIR = config.DATA_DIR / "picks"
TOP_N = 10
KINDS = ("harian", "mingguan")
UPDATE_HM = (16, 30)      # Jam daftar baru dibuat setelah bursa tutup (WIB)
SELL_HM = "15:45"         # Batas jual posisi yang belum kena TP/SL (sebelum pra-penutupan 15:50)
RETRY_UNTIL_HOUR = 19     # Jika data penutupan belum masuk, coba lagi tiap 15 menit sampai jam ini

_generate_lock = threading.Lock()


# ----------------------------------------------------------------------------
# Pembulatan harga ke fraksi BEI
# ----------------------------------------------------------------------------
def tick_floor(price: float) -> int:
    tick = get_tick_size(price)
    return int(math.floor(price / tick) * tick)


def tick_ceil(price: float) -> int:
    tick = get_tick_size(price)
    return int(math.ceil(price / tick) * tick)


# ----------------------------------------------------------------------------
# Money management
# ----------------------------------------------------------------------------
def bucket(settings: Dict[str, Any], kind: str) -> Dict[str, Any]:
    """Modal & jumlah posisi untuk satu jenis (harian / mingguan)."""
    key = "daily" if kind == "harian" else "weekly"
    return {"capital": settings[f"{key}_capital"], "positions": max(int(settings[f"{key}_positions"]), 1)}


def size_position(entry: float, sl: float, settings: Dict[str, Any], kind: str) -> Dict[str, Any]:
    """Hitung lot dari batas risiko & batas alokasi modal per posisi (per jenis)."""
    b = bucket(settings, kind)
    capital = b["capital"]
    risk_budget = capital * settings["stock_risk_pct"] / 100
    alloc = capital / b["positions"]
    lot_cost = entry * config.LOT_SIZE * (1 + config.BUY_FEE_PCT)
    loss_per_lot = (entry - sl) * config.LOT_SIZE + entry * config.LOT_SIZE * (config.BUY_FEE_PCT + config.SELL_FEE_PCT)

    lots_by_alloc = int(alloc // lot_cost) if lot_cost > 0 else 0
    lots_by_risk = int(risk_budget // loss_per_lot) if loss_per_lot > 0 else 0
    affordable = lots_by_alloc >= 1
    lots = max(min(lots_by_alloc, lots_by_risk), 1) if affordable else 0
    return {
        "lots": lots,
        "affordable": affordable,
        "cost": round(lots * lot_cost),
        "risk_rp": round(lots * loss_per_lot),
        "risk_over_budget": affordable and lots_by_risk < 1,
    }


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
_DL_CACHE: Dict[str, Any] = {"time": 0.0, "frames": None}


def _download(tickers: List[str], max_age: float = 600) -> Dict[str, pd.DataFrame]:
    """Unduh rekap harian 1 tahun. Di-cache 10 menit agar harian & mingguan cukup sekali unduh."""
    if _DL_CACHE["frames"] is not None and time.time() - _DL_CACHE["time"] < max_age:
        return _DL_CACHE["frames"]
    frames = _download_fresh(tickers)
    if frames:
        _DL_CACHE.update(time=time.time(), frames=frames)
    return frames


def _download_fresh(tickers: List[str]) -> Dict[str, pd.DataFrame]:
    raw = yf.download(tickers, period="1y", interval="1d", progress=False, auto_adjust=True, threads=True)
    frames = {}
    if raw is None or raw.empty:
        return frames
    for t in tickers:
        try:
            df = pd.DataFrame({col: raw[col][t] for col in ["Open", "High", "Low", "Close", "Volume"]}).dropna()
            df = df[df["Volume"] > 0]
            if len(df) >= 60:
                frames[t] = df
        except Exception:
            continue
    return frames


def _base_metrics(df: pd.DataFrame) -> Dict[str, float]:
    d = calculate_indicators(df)
    d["MA5"] = d["Close"].rolling(5).mean()
    d["MA200"] = d["Close"].rolling(200).mean()
    d["CMF"] = compute_cmf(d, 20)
    last = d.iloc[-1]
    prev = d.iloc[-2]
    high, low, close = float(last["High"]), float(last["Low"]), float(last["Close"])
    rng = high - low
    ma50_series = d["MA50"].dropna()
    ma20_series = d["MA20"].dropna()
    return {
        "close": close,
        "open": float(last["Open"]),
        "high": high,
        "low": low,
        "prev_close": float(prev["Close"]),
        "change_pct": (close / float(prev["Close"]) - 1) * 100 if prev["Close"] else 0.0,
        "atr": float(last["ATR"]),
        "atr_pct": float(last["ATR"]) / close * 100 if close else 0.0,
        "rvol": float(last["RVol"]),
        "rsi": float(last["RSI"]),
        "ma5": float(last["MA5"]),
        "ma10": float(last["MA10"]),
        "ma20": float(last["MA20"]),
        "ma50": float(last["MA50"]),
        "ma50_prev20": float(ma50_series.iloc[-21]) if len(ma50_series) > 21 else float("nan"),
        "ma20_prev5": float(ma20_series.iloc[-6]) if len(ma20_series) > 6 else float("nan"),
        "change_5d": (close / float(d["Close"].iloc[-6]) - 1) * 100 if len(d) > 6 else 0.0,
        "ma200": float(last["MA200"]) if not pd.isna(last["MA200"]) else float("nan"),
        "cmf": float(last["CMF"]) if not pd.isna(last["CMF"]) else 0.0,
        "avg_turnover": float(d["Turnover"].tail(20).mean()),
        "close_pos": (close - low) / rng if rng > 0 else 0.5,
        "high_20d": float(d["High"].tail(21).iloc[:-1].max()),
        "low_10d": float(d["Low"].tail(10).min()),
    }


def _grade(score: float) -> str:
    return "A" if score >= 70 else ("B" if score >= 55 else "C")


# ----------------------------------------------------------------------------
# Harian (intraday): beli saat buka, jual sore hari yang sama
# ----------------------------------------------------------------------------
def _pick(symbol: str, kind: str, score: float, m: Dict[str, float], entry_low: int, entry_high: int,
          sl: int, reasons: List[str], settings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if entry_low >= entry_high:
        entry_low = entry_high - get_tick_size(entry_high)
    if sl >= entry_low:
        sl = entry_low - get_tick_size(entry_low)
    risk = entry_high - sl
    if risk <= 0:
        return None
    tp1 = tick_ceil(entry_high + risk)
    tp2 = tick_ceil(entry_high + 2 * risk)
    return {
        "symbol": symbol.replace(".JK", ""),
        "kind": kind,
        "score": round(score, 1),
        "grade": _grade(score),
        "close": m["close"],
        "change_pct": round(m["change_pct"], 2),
        "entry_low": entry_low,
        "entry_high": entry_high,
        "sl": sl,
        "sl_pct": round((sl / entry_high - 1) * 100, 1),
        "tp1": tp1,
        "tp1_pct": round((tp1 / entry_high - 1) * 100, 1),
        "tp2": tp2,
        "tp2_pct": round((tp2 / entry_high - 1) * 100, 1),
        "rvol": round(m["rvol"], 2),
        "atr_pct": round(m["atr_pct"], 1),
        "turnover_avg": round(m["avg_turnover"]),
        "reasons": reasons[:3],
        **size_position(entry_high, sl, settings, kind),
    }


def _daily_candidate(symbol: str, m: Dict[str, float], settings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    close = m["close"]
    # Intraday butuh saham ramai (mudah keluar sore hari) dan cukup bergerak dalam sehari
    if close < 50 or m["avg_turnover"] < 15e9:
        return None
    if not (2.0 <= m["atr_pct"] <= 7.0):
        return None
    if close <= m["ma5"] or close <= m["ma10"] or m["rsi"] >= 78:
        return None
    if not (0 <= m["change_pct"] <= 15) or m["close_pos"] < 0.5:
        return None

    score = 0.0
    score += min(m["rvol"], 3.0) / 3.0 * 25
    score += m["close_pos"] * 25
    score += float(np.clip(m["cmf"], 0, 0.3)) / 0.3 * 20
    score += 10 if close > m["ma20"] else 0
    score += 10 if m["ma5"] > m["ma10"] else 0
    score += float(np.clip(m["change_pct"], 0, 5)) / 5 * 10

    atr = m["atr"]
    # Boleh beli sedikit di atas close kemarin (gap kecil), tapi jangan kejar gap besar
    entry_high = tick_floor(min(close + 0.1 * atr, close * 1.01))
    entry_high = max(entry_high, tick_floor(close))
    entry_low = tick_floor(close - 0.25 * atr)
    # SL intraday ketat: 0,6 ATR dan maksimal -3%
    sl = tick_floor(max(entry_high - 0.6 * atr, entry_high * 0.97))

    reasons = []
    if m["rvol"] >= 1.5:
        reasons.append(f"Volume {m['rvol']:.1f}x rata-rata 20 hari")
    if m["close_pos"] >= 0.75:
        reasons.append("Ditutup dekat harga tertinggi hari ini")
    if m["cmf"] > 0.1:
        reasons.append("Uang masuk lebih besar dari uang keluar (CMF positif)")
    if close >= m["high_20d"]:
        reasons.append("Menembus harga tertinggi 20 hari")
    elif close > m["ma20"]:
        reasons.append("Tren pendek naik (di atas MA20)")
    return _pick(symbol, "harian", score, m, entry_low, entry_high, sl, reasons, settings)


# ----------------------------------------------------------------------------
# Mingguan (swing): beli Senin, jual Jumat sore
# ----------------------------------------------------------------------------
def _weekly_candidate(symbol: str, m: Dict[str, float], settings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    close = m["close"]
    if close < 50 or m["avg_turnover"] < 5e9:
        return None
    if not (1.5 <= m["atr_pct"] <= 6.0):
        return None
    if math.isnan(m["ma20_prev5"]):
        return None
    # Tren naik yang rapi: harga > MA20 > MA50, MA20 menanjak, belum kepanasan
    if not (close > m["ma20"] > m["ma50"] and m["ma20"] > m["ma20_prev5"]):
        return None
    dist_ma20 = (close / m["ma20"] - 1) * 100
    if not (50 <= m["rsi"] <= 72) or dist_ma20 > 8 or not (-3 <= m["change_5d"] <= 12):
        return None

    ma20_slope = (m["ma20"] / m["ma20_prev5"] - 1) * 100
    score = 0.0
    score += 10 if close > m["ma50"] else 0
    score += 10 if not math.isnan(m["ma50_prev20"]) and m["ma50"] > m["ma50_prev20"] else 0
    score += float(np.clip(ma20_slope, 0, 3)) / 3 * 10
    score += float(np.clip(m["cmf"], 0, 0.25)) / 0.25 * 20
    score += 15 if 55 <= m["rsi"] <= 65 else 8
    # Paling enak dibeli saat dekat MA20 (belum lari jauh)
    score += 20 if dist_ma20 <= 3 else (10 if dist_ma20 <= 6 else 0)
    score += min(m["rvol"], 2.0) / 2.0 * 10
    score += float(np.clip(m["change_5d"], 0, 6)) / 6 * 5

    atr = m["atr"]
    entry_high = tick_floor(close)
    entry_low = tick_floor(max(m["ma20"], close - 0.5 * atr))
    # SL di bawah swing low 10 hari / MA20, minimal 0,8 ATR dan sebisa mungkin tidak lebih dari -5%
    stop = min(m["low_10d"], m["ma20"]) - 0.3 * atr
    stop = min(max(stop, entry_high * 0.95), entry_high - 0.8 * atr)
    sl = tick_floor(stop)

    reasons = ["Tren naik: harga > MA20 > MA50, MA20 menanjak"]
    if dist_ma20 <= 3:
        reasons.append("Dekat MA20, area beli yang wajar")
    if m["cmf"] > 0.1:
        reasons.append("Uang masuk lebih besar dari uang keluar (CMF positif)")
    if 55 <= m["rsi"] <= 65:
        reasons.append(f"RSI {m['rsi']:.0f}: momentum sehat, belum jenuh beli")
    return _pick(symbol, "mingguan", score, m, entry_low, entry_high, sl, reasons, settings)


def _rank(cands: List[Optional[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    ok = [c for c in cands if c and c["affordable"]]
    ok.sort(key=lambda c: c["score"], reverse=True)
    return ok[:TOP_N]


# ----------------------------------------------------------------------------
# Jadwal: untuk hari/minggu apa daftar ini berlaku
# ----------------------------------------------------------------------------
def _at(d: date, hm=UPDATE_HM) -> datetime:
    return datetime(d.year, d.month, d.day, hm[0], hm[1], tzinfo=WIB)


def _after_update(dt: datetime) -> bool:
    return (dt.hour, dt.minute) >= UPDATE_HM


def daily_target(dt: datetime) -> date:
    """Hari bursa yang sedang dipersiapkan: hari ini sampai daftar baru terbit 16:30, lalu besok."""
    if dt.weekday() < 5 and not _after_update(dt):
        return dt.date()
    return next_trading_day(dt.date())


def weekly_target(dt: datetime) -> date:
    """Senin dari minggu yang sedang dipersiapkan: minggu ini sampai Jumat 16:30, lalu minggu depan."""
    d = dt.date()
    if d.weekday() < 4 or (d.weekday() == 4 and not _after_update(dt)):
        return d - timedelta(days=d.weekday())
    return d + timedelta(days=7 - d.weekday())


def _next_update(kind: str, dt: datetime) -> datetime:
    d = dt.date()
    if kind == "harian":
        if d.weekday() < 5 and not _after_update(dt):
            return _at(d)
        return _at(next_trading_day(d))
    friday = d + timedelta(days=(4 - d.weekday()) % 7)
    if friday == d and _after_update(dt):
        friday += timedelta(days=7)
    return _at(friday)


# ----------------------------------------------------------------------------
# Snapshot
# ----------------------------------------------------------------------------
def _snapshot_path(valid_for: str, kind: str):
    return PICKS_DIR / f"{valid_for}_{kind}.json"


def generate_picks(kind: str, valid_for: date) -> Dict[str, Any]:
    settings = load_settings()
    dt = now_wib()
    frames = _download(config.SCALP_UNIVERSE)
    metrics = {}
    for t, df in frames.items():
        try:
            metrics[t] = _base_metrics(df)
        except Exception:
            continue

    fn = _daily_candidate if kind == "harian" else _weekly_candidate
    picks = _rank([fn(t, m, settings) for t, m in metrics.items()])

    last_bar = max((df.index[-1] for df in frames.values()), default=None)
    snap = {
        "kind": kind,
        "generated_at": dt.strftime("%Y-%m-%d %H:%M"),
        "data_date": last_bar.strftime("%Y-%m-%d") if last_bar is not None else None,
        "valid_for": valid_for.isoformat(),
        "sell_on": (valid_for if kind == "harian" else valid_for + timedelta(days=4)).isoformat(),
        "scanned": len(metrics),
        kind: picks,
    }
    try:
        PICKS_DIR.mkdir(parents=True, exist_ok=True)
        _snapshot_path(snap["valid_for"], kind).write_text(json.dumps(snap, indent=1, default=str), encoding="utf-8")
    except Exception:
        pass  # filesystem read-only (Vercel)
    return snap


def list_snapshots(kind: Optional[str] = None) -> List[Dict[str, Any]]:
    out = []
    if not PICKS_DIR.exists():
        return out
    for p in sorted(PICKS_DIR.glob("*.json")):
        if kind and not p.stem.endswith(f"_{kind}"):
            continue
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def _data_ok(snap: Dict[str, Any]) -> bool:
    """Data sudah memakai penutupan hari bursa terakhir sebelum tanggal berlaku?"""
    need = prev_trading_day(date.fromisoformat(snap["valid_for"]))
    return bool(snap.get("data_date")) and snap["data_date"] >= need.isoformat()


def _finalize(snap: Dict[str, Any], kind: str) -> Dict[str, Any]:
    """Hitung ulang lot dengan setting modal terbaru, tandai yang dibeli, tambah info jadwal."""
    settings = load_settings()
    b = bucket(settings, kind)
    picks = snap.get(kind, [])
    for p in picks:
        p.update(size_position(p["entry_high"], p["sl"], settings, kind))
        p["buy"] = False
    chosen = [p for p in picks if p["affordable"] and p["grade"] in ("A", "B")][:b["positions"]]
    for p in chosen:
        p["buy"] = True

    dt = now_wib()
    snap["picks"] = picks
    snap["capital"] = b["capital"]
    snap["positions"] = b["positions"]
    snap["plan"] = {
        "symbols": [p["symbol"] for p in chosen],
        "cost": sum(p["cost"] for p in chosen),
        "risk": sum(p["risk_rp"] for p in chosen),
    }
    snap["data_ok"] = _data_ok(snap)
    snap["late"] = snap["generated_at"][:10] > snap["valid_for"]
    snap["next_update"] = _next_update(kind, dt).isoformat(timespec="minutes")
    snap["sell_time"] = SELL_HM
    snap["today"] = dt.date().isoformat()
    return snap


def _target(kind: str) -> date:
    return daily_target(now_wib()) if kind == "harian" else weekly_target(now_wib())


def get_picks(kind: str = "harian", force_refresh: bool = False) -> Dict[str, Any]:
    kind = kind if kind in KINDS else "harian"
    target = _target(kind)
    path = _snapshot_path(target.isoformat(), kind)
    stale = False
    with _generate_lock:
        if not force_refresh and path.exists():
            snap = json.loads(path.read_text(encoding="utf-8"))
        elif not force_refresh and os.getenv("VERCEL") and list_snapshots(kind):
            # Vercel tidak bisa menyimpan file & scan penuh rawan timeout:
            # tampilkan daftar terakhir dari GitHub Actions, tandai belum diperbarui.
            snap, stale = list_snapshots(kind)[-1], True
        else:
            if force_refresh:
                _DL_CACHE["frames"] = None
            snap = generate_picks(kind, target)
    out = _finalize(snap, kind)
    out["stale"] = stale
    if stale:
        out["data_ok"] = False
    return out


def run_scheduled_snapshots() -> None:
    """Dipanggil tiap menit oleh scheduler web: buat daftar baru setelah bursa tutup."""
    dt = now_wib()
    if dt.weekday() >= 5 or not _after_update(dt) or dt.hour >= RETRY_UNTIL_HOUR:
        return
    kinds = ["harian"] + (["mingguan"] if dt.weekday() == 4 else [])
    for kind in kinds:
        target = _target(kind)
        path = _snapshot_path(target.isoformat(), kind)
        with _generate_lock:
            if path.exists():
                snap = json.loads(path.read_text(encoding="utf-8"))
                # Data penutupan hari ini belum masuk dari Yahoo: ulangi tiap 15 menit
                age = dt - datetime.strptime(snap["generated_at"], "%Y-%m-%d %H:%M").replace(tzinfo=WIB)
                if _data_ok(snap) or age < timedelta(minutes=15):
                    continue
                _DL_CACHE["frames"] = None
            generate_picks(kind, target)


def update_for_cron() -> List[str]:
    """Dipanggil GitHub Actions setelah bursa tutup. Membuat daftar yang belum ada / datanya belum
    memakai penutupan terakhir. Mengembalikan daftar file yang dibuat."""
    dt = now_wib()
    made = []
    for kind in KINDS:
        target = _target(kind)
        path = _snapshot_path(target.isoformat(), kind)
        if path.exists() and _data_ok(json.loads(path.read_text(encoding="utf-8"))):
            print(f"{kind}: {path.name} sudah lengkap, lewati")
            continue
        snap = generate_picks(kind, target)
        made.append(path.name)
        buys = [p["symbol"] for p in snap[kind] if p["grade"] in ("A", "B")][:3]
        print(f"{kind}: {path.name} dibuat {dt:%H:%M} WIB · data {snap['data_date']} · teratas {buys}")
    return made


if __name__ == "__main__" and "--cron" in sys.argv:
    update_for_cron()
elif __name__ == "__main__":
    for kind in KINDS:
        snap = get_picks(kind, force_refresh=True)
        print(f"\n{kind.upper()} untuk {snap['valid_for']} (jual {snap['sell_on']}) · data {snap['data_date']} · modal {snap['capital']:,}")
        for p in snap["picks"]:
            flag = "BELI" if p["buy"] else "    "
            print(f"  {flag} {p['symbol']:5} {p['grade']} skor {p['score']:5.1f}  entry {p['entry_low']}-{p['entry_high']}  "
                  f"SL {p['sl']} ({p['sl_pct']}%)  TP1 {p['tp1']} ({p['tp1_pct']}%)  {p['lots']} lot  Rp{p['cost']:,}")
