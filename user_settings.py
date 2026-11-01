"""
Setting pribadi user (modal saham, saldo akun forex cent, batas risiko).
Disimpan di data/settings.json agar tidak ikut ter-commit.
"""
import json
from typing import Dict, Any

import config

SETTINGS_FILE = config.DATA_DIR / "settings.json"

DEFAULT_SETTINGS: Dict[str, Any] = {
    # Modal saham 3 jt dibagi dua: harian (beli buka, jual sore) & mingguan (beli Senin, jual Jumat)
    "daily_capital": 1_500_000,      # Modal trading harian (Rp)
    "weekly_capital": 1_500_000,     # Modal trading mingguan (Rp)
    "daily_positions": 2,            # Jumlah saham yang dibeli per hari
    "weekly_positions": 2,           # Jumlah saham yang dibeli per minggu
    "stock_risk_pct": 2.0,           # Risiko maksimal per posisi saham (% modal jenisnya)
    "fx_balance_idr": 2_000_000,     # Saldo akun Exness cent dalam Rupiah
    "fx_risk_pct": 1.0,              # Risiko per entry forex (% saldo)
    "xau_offset": 0.0,               # Selisih harga XAU Exness (spot) - Yahoo (futures GC=F)
    # Spesifikasi kontrak 1 lot di akun cent (cek di MT5: klik kanan simbol > Specification)
    "xau_contract_size": 100,        # 1 lot XAUUSD = 100 oz -> gerak $1 = 100 USC per lot
    "fx_contract_size": 100_000,     # 1 lot EURUSD/GBPUSD = 100.000 unit -> 1 pip = 10 USC per lot
}


def load_settings() -> Dict[str, Any]:
    settings = dict(DEFAULT_SETTINGS)
    try:
        if SETTINGS_FILE.exists():
            settings.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return settings


def save_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    settings = load_settings()
    for key, val in updates.items():
        if key in DEFAULT_SETTINGS and val is not None:
            num = float(val)
            settings[key] = int(num) if isinstance(DEFAULT_SETTINGS[key], int) else num
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except Exception:
        # Filesystem read-only (mis. Vercel): setting tetap berlaku untuk request ini saja
        pass
    return settings
