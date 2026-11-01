"""
Modul Pengelola Watchlist Pribadi (Custom Watchlist Manager)
Menyimpan dan mengelola daftar saham pantauan khusus pengguna secara persisten.
"""
import json
from pathlib import Path
from typing import List, Dict, Any
from data_provider import get_clean_symbol, normalize_ticker

WATCHLIST_FILE = Path(__file__).resolve().parent / "watchlist.json"

def _load_watchlist_data() -> Dict[str, List[str]]:
    if not WATCHLIST_FILE.exists():
        return {}
    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_watchlist_data(data: Dict[str, List[str]]):
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Gagal menyimpan watchlist.json: {e}")

def add_to_watchlist(symbol: str, chat_id: str) -> Dict[str, Any]:
    """Menambahkan saham ke watchlist user"""
    clean_sym = get_clean_symbol(symbol)
    ticker = normalize_ticker(symbol)
    
    data = _load_watchlist_data()
    user_list = data.setdefault(str(chat_id), [])
    
    if ticker in user_list or clean_sym in [get_clean_symbol(t) for t in user_list]:
        return {"success": False, "message": f"Saham `{clean_sym}` sudah ada di watchlist Anda."}
        
    user_list.append(ticker)
    _save_watchlist_data(data)
    
    return {"success": True, "symbol": clean_sym, "message": f"⭐ Berhasil menambahkan `{clean_sym}` ke daftar pantau pribadi Anda!"}

def remove_from_watchlist(symbol: str, chat_id: str) -> Dict[str, Any]:
    """Menghapus saham dari watchlist user"""
    clean_sym = get_clean_symbol(symbol)
    data = _load_watchlist_data()
    user_list = data.get(str(chat_id), [])
    
    initial_len = len(user_list)
    new_list = [t for t in user_list if get_clean_symbol(t) != clean_sym]
    
    if len(new_list) == initial_len:
        return {"success": False, "message": f"Saham `{clean_sym}` tidak ditemukan di watchlist Anda."}
        
    data[str(chat_id)] = new_list
    _save_watchlist_data(data)
    
    return {"success": True, "symbol": clean_sym, "message": f"🗑️ Berhasil menghapus `{clean_sym}` dari watchlist Anda."}

def get_user_watchlist(chat_id: str) -> List[str]:
    """Mengambil daftar ticker saham milik user"""
    data = _load_watchlist_data()
    return data.get(str(chat_id), ["BBCA.JK", "BBRI.JK", "BMRI.JK", "ASII.JK", "TLKM.JK"])
