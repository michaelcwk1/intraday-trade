"""
Status sesi pasar saat ini (WIB): Bursa Efek Indonesia & sesi forex global.
"""
from datetime import datetime, timedelta, timezone, date
from typing import Dict, Any

WIB = timezone(timedelta(hours=7))


def now_wib() -> datetime:
    return datetime.now(WIB)


def _minutes(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def idx_session(dt: datetime) -> Dict[str, Any]:
    """Jadwal reguler BEI. Jumat sesi 1 s/d 11:30, sesi 2 mulai 14:00."""
    m = _minutes(dt)
    if dt.weekday() >= 5:
        return {"code": "closed", "label": "Tutup (akhir pekan)"}
    is_friday = dt.weekday() == 4
    s1_end = 11 * 60 + 30 if is_friday else 12 * 60
    s2_start = 14 * 60 if is_friday else 13 * 60 + 30
    if m < 8 * 60 + 45:
        return {"code": "closed", "label": "Belum buka"}
    if m < 9 * 60:
        return {"code": "pre", "label": "Pra-pembukaan"}
    if m < s1_end:
        return {"code": "s1", "label": "Sesi 1"}
    if m < s2_start:
        return {"code": "break", "label": "Istirahat"}
    if m < 15 * 60 + 50:
        return {"code": "s2", "label": "Sesi 2"}
    if m < 16 * 60 + 15:
        return {"code": "post", "label": "Pra-penutupan / penutupan"}
    return {"code": "closed", "label": "Tutup"}


def fx_sessions(dt: datetime) -> Dict[str, Any]:
    """Perkiraan jam sesi forex dalam WIB (tanpa koreksi daylight saving)."""
    h = dt.hour
    active = []
    if 6 <= h < 15:
        active.append("Asia")
    if 14 <= h < 23:
        active.append("London")
    if h >= 19 or h < 4:
        active.append("New York")
    weekend = dt.weekday() == 5 and h >= 4 or dt.weekday() == 6 or (dt.weekday() == 0 and h < 5)
    return {
        "active": [] if weekend else active,
        "is_prime": (not weekend) and ("London" in active or "New York" in active),
        "label": "Pasar forex tutup (akhir pekan)" if weekend else (" + ".join(active) or "Sepi"),
    }


def next_m15_close(dt: datetime) -> datetime:
    """Waktu tutup candle M15 berikutnya (kelipatan 15 menit)."""
    base = dt.replace(second=0, microsecond=0)
    return base + timedelta(minutes=15 - base.minute % 15)


def next_prime_start(dt: datetime) -> datetime:
    """Kapan jam ramai (London/New York) berikutnya dimulai, dalam WIB."""
    cand = dt.replace(hour=14, minute=0, second=0, microsecond=0)
    if dt >= cand:
        cand += timedelta(days=1)
    # Lewati akhir pekan (pasar tutup Sabtu 04:00 s/d Senin 05:00 WIB)
    while cand.weekday() >= 5:
        cand += timedelta(days=1)
    return cand


def next_trading_day(d: date) -> date:
    nd = d + timedelta(days=1)
    while nd.weekday() >= 5:
        nd += timedelta(days=1)
    return nd


def prev_trading_day(d: date) -> date:
    pd_ = d - timedelta(days=1)
    while pd_.weekday() >= 5:
        pd_ -= timedelta(days=1)
    return pd_


def get_market_status() -> Dict[str, Any]:
    dt = now_wib()
    return {
        "now": dt.strftime("%Y-%m-%d %H:%M"),
        "idx": idx_session(dt),
        "fx": fx_sessions(dt),
    }
