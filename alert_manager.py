"""
Modul Pengelola Alarm Harga Saham (Price Alert Manager)
Memantau pergerakan harga saham IDX dan mengirimkan notifikasi instan saat harga menyentuh target.
"""
import json
import time
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


from config import format_idr
from data_provider import get_current_price, get_clean_symbol, normalize_ticker

ALERTS_FILE = Path(__file__).resolve().parent / "alerts.json"

def _load_alerts() -> List[Dict[str, Any]]:
    if not ALERTS_FILE.exists():
        return []
    try:
        with open(ALERTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _save_alerts(alerts: List[Dict[str, Any]]):
    try:
        with open(ALERTS_FILE, "w", encoding="utf-8") as f:
            json.dump(alerts, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Gagal menyimpan alerts.json: {e}")

def add_price_alert(symbol: str, target_price: float, chat_id: str) -> Dict[str, Any]:
    """
    Menambahkan pengingat harga baru.
    """
    clean_sym = get_clean_symbol(symbol)
    ticker = normalize_ticker(symbol)
    current_price = get_current_price(ticker)
    
    if current_price is None or current_price <= 0:
        return {"success": False, "message": f"Saham `{clean_sym}` tidak valid atau data harga tidak tersedia."}
        
    condition = "GTE" if target_price >= current_price else "LTE"
    cond_text = "naik menyentuh atau melampaui" if condition == "GTE" else "turun menyentuh atau di bawah"
    
    alerts = _load_alerts()
    new_id = (max([a.get("id", 0) for a in alerts], default=0) + 1)
    
    alert_item = {
        "id": new_id,
        "symbol": clean_sym,
        "ticker": ticker,
        "target_price": round(target_price),
        "condition": condition,
        "created_price": round(current_price),
        "chat_id": str(chat_id),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "triggered": False
    }
    
    alerts.append(alert_item)
    _save_alerts(alerts)
    
    return {
        "success": True,
        "alert": alert_item,
        "message": f"✅ Alarm #{new_id} dipasang untuk `{clean_sym}`!\nBot akan memberi tahu jika harga {cond_text} `{format_idr(target_price)}` (Harga saat ini: `{format_idr(current_price)}`)."
    }

def get_user_alerts(chat_id: str) -> List[Dict[str, Any]]:
    """Mengambil daftar alarm aktif milik user"""
    alerts = _load_alerts()
    return [a for a in alerts if a.get("chat_id") == str(chat_id) and not a.get("triggered", False)]

def delete_price_alert(alert_id: int, chat_id: str) -> Dict[str, Any]:
    """Menghapus alarm berdasarkan ID"""
    alerts = _load_alerts()
    new_alerts = []
    found = False
    
    for a in alerts:
        if a.get("id") == alert_id and a.get("chat_id") == str(chat_id):
            found = True
        else:
            new_alerts.append(a)
            
    if found:
        _save_alerts(new_alerts)
        return {"success": True, "message": f"✅ Alarm #{alert_id} berhasil dihapus."}
    return {"success": False, "message": f"⚠️ Alarm #{alert_id} tidak ditemukan."}

def check_all_alerts(on_trigger_callback: Optional[Callable[[Dict[str, Any], float], None]] = None) -> List[Dict[str, Any]]:
    """
    Memeriksa seluruh alarm aktif terhadap harga pasar terkini.
    """
    alerts = _load_alerts()
    active_alerts = [a for a in alerts if not a.get("triggered", False)]
    if not active_alerts:
        return []
        
    triggered_list = []
    has_update = False
    
    for alert in active_alerts:
        curr_price = get_current_price(alert["ticker"])
        if curr_price is None or curr_price <= 0:
            continue
            
        target = alert["target_price"]
        cond = alert["condition"]
        
        is_hit = False
        if cond == "GTE" and curr_price >= target:
            is_hit = True
        elif cond == "LTE" and curr_price <= target:
            is_hit = True
            
        if is_hit:
            alert["triggered"] = True
            alert["triggered_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            alert["triggered_price"] = curr_price
            has_update = True
            triggered_list.append((alert, curr_price))
            
            if on_trigger_callback:
                try:
                    on_trigger_callback(alert, curr_price)
                except Exception as e:
                    print(f"Error callback alert: {e}")
                    
    if has_update:
        _save_alerts(alerts)
        
    return [t[0] for t in triggered_list]
