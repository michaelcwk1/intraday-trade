"""
Modul Notifikasi Telegram
Mengirimkan alert sinyal saham IDX, eksekusi paper trading, dan status portofolio langsung ke chat/channel Telegram.
"""
import os
import requests
from typing import Optional, Dict, Any
import config
from config import format_idr

def get_credentials():
    token = os.getenv("TELEGRAM_BOT_TOKEN") or getattr(config, "TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or getattr(config, "TELEGRAM_CHAT_ID", "")
    return token, chat_id

def send_telegram_message(message: str, parse_mode: str = "Markdown") -> bool:
    """
    Mengirim pesan teks ke Telegram menggunakan HTTP POST request resmi Bot API.
    """
    token, chat_id = get_credentials()
    if not token or not chat_id:
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }

    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"⚠️ Gagal mengirim pesan ke Telegram: {e}")
        return False

def send_telegram_photo(photo_path: str, caption: str = "", reply_markup: Optional[Dict[str, Any]] = None, parse_mode: str = "Markdown") -> bool:
    """
    Mengirim gambar/foto ke Telegram menggunakan endpoint sendPhoto resmi.
    """
    token, chat_id = get_credentials()
    if not token or not chat_id:
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    data = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": parse_mode
    }
    if reply_markup:
        import json
        data["reply_markup"] = json.dumps(reply_markup)
        
    try:
        with open(photo_path, "rb") as photo_file:
            files = {"photo": photo_file}
            response = requests.post(url, data=data, files=files, timeout=25)
            return response.status_code == 200
    except Exception as e:
        print(f"⚠️ Gagal mengirim foto ke Telegram: {e}")
        return False


def notify_buy_signal(signal_data: Dict[str, Any], symbol: str) -> bool:
    """
    Format dan kirim notifikasi sinyal BUY / Momentum Spike.
    """
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        return False
        
    badge = "🚨 *SINYAL TRADING SAHAM IDX*" if signal_data.get('signal') == 'BUY' else "🔥 *STRONG BREAKOUT DETECTED*"
    reasons_str = "\n".join([f"  • {r}" for r in signal_data.get('reasons', [])])
    
    msg = f"""
{badge}
━━━━━━━━━━━━━━━━━━━━
📌 *Emiten:* `{symbol}`
📈 *Harga Terkini:* `{format_idr(signal_data['close'])}` ({signal_data['change_pct']:+.2f}%)
📊 *RVol:* `{signal_data['rvol']}x`
💰 *Turnover:* `{format_idr(signal_data['turnover'])}`
🎯 *RSI (14):* `{signal_data['rsi']}`

🎯 *Rencana Trading (Trading Plan):*
  • Entry Price : `{format_idr(signal_data['entry_price'])}`
  • Target TP1  : `{format_idr(signal_data['tp1'])}` (+3%)
  • Target TP2  : `{format_idr(signal_data['tp2'])}` (+5%)
  • Target TP3  : `{format_idr(signal_data['tp3'])}` (+8%)
  • Stop Loss   : `{format_idr(signal_data['sl'])}` (-3%)
  • Risk/Reward : `{signal_data['rrr']}:1`

💡 *Faktor Pendorong:*
{reasons_str}
━━━━━━━━━━━━━━━━━━━━
_Disclaimer: Sinyal otomatis dari Bot Trading IDX Momentum. Lakukan riset mandiri (DYOR)._
"""
    return send_telegram_message(msg.strip())

def notify_order_execution(order_type: str, symbol: str, lots: int, price: float, total_cost: float, pnl_pct: Optional[float] = None, pnl_idr: Optional[float] = None) -> bool:
    """
    Format dan kirim notifikasi eksekusi order paper trading (Beli/Jual).
    """
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        return False
        
    if order_type.upper() == "BUY":
        msg = f"""
🛒 *PAPER TRADING: ORDER BELI BERHASIL*
━━━━━━━━━━━━━━━━━━━━
📌 *Saham:* `{symbol}`
📦 *Jumlah:* `{lots} Lot` ({lots * 100} lembar)
💵 *Harga Eksekusi:* `{format_idr(price)}`
💸 *Total Modal:* `{format_idr(total_cost)}` (Termasuk Fee 0.15%)
⏱️ *Status:* Posisi Terbuka (Open)
━━━━━━━━━━━━━━━━━━━━
"""
    else:
        pnl_badge = "🟢 PROFIT" if (pnl_idr and pnl_idr >= 0) else "🔴 LOSS"
        msg = f"""
💰 *PAPER TRADING: ORDER JUAL ({pnl_badge})*
━━━━━━━━━━━━━━━━━━━━
📌 *Saham:* `{symbol}`
📦 *Jumlah:* `{lots} Lot` ({lots * 100} lembar)
💵 *Harga Jual:* `{format_idr(price)}`
💵 *Total Diterima:* `{format_idr(total_cost)}` (Setelah Fee 0.25%)
📊 *Realized PnL:* `{format_idr(pnl_idr or 0)}` ({pnl_pct:+.2f}%)
━━━━━━━━━━━━━━━━━━━━
"""
    return send_telegram_message(msg.strip())

def test_telegram_connection() -> Dict[str, Any]:
    """
    Menguji koneksi dan mengirim pesan tes ke Telegram.
    """
    token, chat_id = get_credentials()
    if not token:
        return {"success": False, "message": "TELEGRAM_BOT_TOKEN belum diisi."}
    if not chat_id:
        return {"success": False, "message": "TELEGRAM_CHAT_ID belum diisi."}
        
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if not data.get("ok"):
            return {
                "success": False,
                "message": f"Token tidak valid menurut Telegram API ({data.get('description')}). Pastikan token lengkap dengan awalan angka ID (contoh: 1234567890:AAF...)."
            }
        bot_username = data.get("result", {}).get("username", "Unknown")
    except Exception as e:
        return {"success": False, "message": f"Gagal menghubungi server Telegram: {e}"}

    test_msg = f"✅ *Halo! Koneksi Bot Trading Saham Indonesia (@{bot_username}) Berhasil Terhubung ke Telegram Anda!* 🚀\n\nNotifikasi sinyal & order trading IDX Anda akan dikirimkan ke sini."
    success = send_telegram_message(test_msg)
    if success:
        return {"success": True, "message": f"Berhasil terhubung ke @{bot_username} dan pesan tes terkirim!"}
    else:
        return {
            "success": False,
            "message": f"Token bot valid (@{bot_username}), tetapi gagal mengirim pesan ke Chat ID {chat_id}. Pastikan Anda sudah membuka bot @{bot_username} di Telegram dan menekan tombol START (/start)."
        }


if __name__ == "__main__":
    print(test_telegram_connection())
