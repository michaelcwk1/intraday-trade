"""
Bot Telegram Interaktif Super Lengkap Saham Indonesia (IDX / BEI)
Fitur-Fitur Lengkap:
- /start & /help: Menampilkan menu & tombol navigasi interaktif
- /scan: Memindai saham IDX dengan lonjakan volume & momentum
- /plan <KODE>: Trading Plan lengkap (Area Beli, Stop Loss, Target TP1/TP2, Risk:Reward)
- /chart <KODE>: 📊 Mengirim gambar grafik candlestick dengan MA, TP, SL langsung ke chat Telegram!
- /alert <KODE> <HARGA>: 🚨 Memasang alarm pengingat harga otomatis
- /alerts & /delalert <ID>: Melihat dan menghapus alarm harga aktif
- /flow <KODE> atau /bandar <KODE>: 🌐 Analisis arus dana asing / Bandarmology & Money Flow (CMF & OBV)
- /watch <KODE> & /unwatch <KODE>: ⭐ Mengelola daftar saham pantauan favorit pribadi
- /watchlist atau /mywatch: Memindai khusus saham-saham pilihan pribadi Anda
- /calc <KODE> <RISIKO_RP>: 🧮 Kalkulator Money Management & ukuran lot ideal sesuai toleransi risiko
- /buy <KODE> <LOT> [TP%] [SL%]: Membeli saham simulasi (Paper Trading)
- /sell <KODE> [LOT]: Menjual saham simulasi
- /portfolio: Menampilkan ringkasan saldo & posisi saham virtual
- Background Scheduler:
  1. Memantau alarm harga setiap 30 detik (notifikasi instan saat harga menyentuh target)
  2. Otomatis kirim update ke Telegram setiap jam bursa dibuka (09:05 WIB & 13:35/14:05 WIB) & tutup (16:05 WIB)!
"""
import os
import sys
import time
import threading
from datetime import datetime, timezone, timedelta
import requests
from typing import Dict, Any, Optional, List

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import config
from config import format_idr, format_price, get_asset_type, get_display_name, DEFAULT_TP2_PCT, DEFAULT_SL_PCT
from data_provider import get_current_price, get_clean_symbol, get_ticker_summary
from screener import run_screener
from strategy import get_trading_plan
from paper_trader import (
    load_portfolio, buy_stock, sell_stock, update_and_check_portfolio,
    display_portfolio_summary
)
from telegram_notifier import get_credentials, send_telegram_message, send_telegram_photo
from chart_generator import generate_candlestick_chart
from alert_manager import add_price_alert, get_user_alerts, delete_price_alert, check_all_alerts
from bandarmology import analyze_bandarmology
from watchlist_manager import add_to_watchlist, remove_from_watchlist, get_user_watchlist
from news_provider import get_stock_news, get_market_news, format_news_markdown
from top_movers import format_top_movers_summary, format_top_gainers_only, format_top_losers_only
from special_screeners import format_ara_message, format_bsjp_message
from crypto_forex import format_crypto_message, format_forex_message
from technical_analysis import format_ta_message
from swing_screener import format_bow_message
from fundamental_provider import format_fundamental_message, format_calendar_message
from ai_analyzer import get_ai_market_insight
from bandar_screener import format_bandar_screener_message
from sector_heatmap import format_sector_heatmap_message
from breakout_scanner import format_breakout_message, check_new_breakout_alerts

# Timezone WIB (UTC + 7)
WIB = timezone(timedelta(hours=7))

def get_now_wib() -> datetime:
    return datetime.now(WIB)

def send_reply(chat_id: str, text: str, reply_markup: Optional[Dict[str, Any]] = None):
    token, _ = get_credentials()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"Error send_reply: {e}")

def handle_start(chat_id: str, first_name: str):
    welcome_msg = f"""
👋 *Halo {first_name}!* 
Selamat datang di *Bot Trading Saham Indonesia (IDX), Crypto & Forex Super Lengkap* 🤖📈

Bot ini dilengkapi analisis kuantitatif, grafis visual, AI market insight, berita terkini, pasar Crypto, Forex/Emas, konsensus teknikal, alarm harga, dan deteksi arus dana bandar (Bandarmology).

📋 *Menu Perintah Lengkap:*
  • `/ai <KODE>` - 🤖 Analisis Cerdas AI (Teknikal + Smart Money + Berita)
  • `/akumulasi` - 🌐 Screener Akumulasi Smart Money & Bandar Hunter
  • `/sektor` atau `/heatmap` - 🗺️ Radar Rotasi Sektor & Heatmap IDX (8 Sektor)
  • `/breakout` - 🚨 Sinyal Breakout Lonjakan Volume & Resistensi (Auto-Alert)
  • `/ta <KODE>` - 🧭 Meteran Konsensus Teknikal (TradingView Style)
  • `/bow` - 🎣 Screener Buy on Weakness & Rebound Support
  • `/fund <KODE>` - 🏢 Profil Fundamental, PER, PBV & Dividend Yield
  • `/kalender` - 📅 Jadwal Cum-Date Dividen & Laporan Keuangan IDX
  • `/scan` - 🔍 Pindai saham IDX dengan lonjakan volume & momentum
  • `/ara` - 🎯 Screener ARA Hunter (Terkunci ARA & Potensi Menuju ARA)
  • `/bsjp` - 🌅 Screener BSJP (Beli Sore Jual Pagi - Candle & Akumulasi)
  • `/crypto` - 🪙 Pasar Crypto Teratas (BTC, ETH, SOL, BNB, XRP, DOGE)
  • `/forex` - 🌍 Pasar Forex & Logam Mulia (Gold/XAU, Silver, Oil, EUR/USD)
  • `/plan <KODE>` - 🎯 Trading Plan lengkap (Area Beli, Stop Loss & TP)
  • `/chart <KODE>` - 📊 Kirim grafik Candlestick + MA + TP/SL (contoh: `/chart BTC` atau `/chart XAU`)
  • `/price <KODE>` - 💵 Cek harga instan saham, crypto, atau emas
  • `/news [KODE]` - 📰 Berita terkini emiten / crypto / emas (contoh: `/news BBCA` atau `/news BTC`)
  • `/topmovers` - 🔥 Ringkasan Top Gainers, Losers & Turnover Tertinggi
  • `/topgain` - 🚀 Daftar saham kenaikan persentase tertinggi hari ini
  • `/toploss` - 🔻 Daftar saham penurunan terdalam hari ini
  • `/alert <KODE> <HARGA>` - 🚨 Pasang alarm pengingat harga (contoh: `/alert BBCA 6000`)
  • `/alerts` - 📋 Lihat daftar alarm harga aktif
  • `/flow <KODE>` - 🌐 Cek arus dana asing & Bandarmology (contoh: `/flow BBRI`)
  • `/calc <KODE> <RISIKO>` - 🧮 Kalkulator Lot Ideal (contoh: `/calc BBCA 500000`)
  • `/watch <KODE>` - ⭐ Tambah saham ke pantauan favorit Anda
  • `/watchlist` - 🌟 Pantau khusus saham-saham favorit Anda
  • `/buy <KODE> <LOT> [TP%] [SL%]` - 🛒 Beli saham di akun simulasi
  • `/sell <KODE> [LOT]` - 💰 Jual saham di akun simulasi
  • `/portfolio` - 💼 Cek saldo & posisi saham virtual
  • `/update` - 🔔 Paksa kirim update pasar bursa saat ini
  • `/help` - ℹ️ Tampilkan panduan ini kembali

⏰ *Update Otomatis Jam Bursa:* 09:05 WIB | 13:35 WIB | 16:05 WIB

_Klik tombol cepat di bawah untuk mencoba fitur favorit:_
"""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🌐 Screener Bandar", "callback_data": "btn_akumulasi"},
                {"text": "🗺️ Rotasi Sektor", "callback_data": "btn_sektor"},
                {"text": "🚨 Breakout Volume", "callback_data": "btn_breakout"}
            ],
            [
                {"text": "🤖 AI Insight BBCA", "callback_data": "btn_ai_BBCA"},
                {"text": "🧭 Meteran TA BBCA", "callback_data": "btn_ta_BBCA"}
            ],
            [
                {"text": "🎣 Radar BoW / Swing", "callback_data": "btn_bow"},
                {"text": "📅 Kalender Dividen", "callback_data": "btn_kalender"}
            ],
            [
                {"text": "🔍 Scan Saham & SL/TP", "callback_data": "btn_scan"},
                {"text": "💼 Portofolio", "callback_data": "btn_portfolio"}
            ],
            [
                {"text": "🪙 Pasar Crypto (BTC)", "callback_data": "btn_crypto"},
                {"text": "🌍 Forex & Gold (XAU)", "callback_data": "btn_forex"}
            ],
            [
                {"text": "🎯 Screener ARA Hunter", "callback_data": "btn_ara"},
                {"text": "🌅 Screener BSJP", "callback_data": "btn_bsjp"}
            ],
            [
                {"text": "🚀 Top Gainers", "callback_data": "btn_topgain"},
                {"text": "🔥 Top Movers", "callback_data": "btn_topmovers"},
                {"text": "📰 Berita IHSG", "callback_data": "btn_news_market"}
            ],
            [
                {"text": "📊 Chart BBCA", "callback_data": "btn_chart_BBCA"},
                {"text": "🎯 Plan BTC", "callback_data": "btn_plan_BTC"},
                {"text": "⭐ Watchlist", "callback_data": "btn_watchlist"}
            ]
        ]
    }
    send_reply(chat_id, welcome_msg.strip(), reply_markup=keyboard)

def handle_chart_cmd(chat_id: str, symbol: str):
    """
    Menghasilkan dan mengirimkan gambar grafik candlestick langsung ke chat Telegram
    """
    sym = get_clean_symbol(symbol)
    send_reply(chat_id, f"⏳ *Sedang merender chart candlestick untuk {sym}...*")
    
    chart_file = generate_candlestick_chart(sym)
    if not chart_file or not os.path.exists(chart_file):
        send_reply(chat_id, f"❌ Gagal membuat chart untuk `{sym}`. Pastikan simbol/kode benar.")
        return
        
    plan = get_trading_plan(sym)
    actual_ticker = plan.get('ticker', sym)
    asset_type = plan.get('asset_type', get_asset_type(actual_ticker))
    display_name = get_display_name(actual_ticker)
    
    caption = f"""
📊 *GRAFIK CANDLESTICK: {display_name} ({asset_type.upper()})*
━━━━━━━━━━━━━━━━━━━━
💵 *Harga Now:* `{format_price(plan['close'], actual_ticker)}` ({plan['change_pct']:+.2f}%)
🛒 *Area Beli (Entry):* `{format_price(plan['buy_min'], actual_ticker)} - {format_price(plan['buy_max'], actual_ticker)}`
🛑 *Stop Loss (SL):* `{format_price(plan['sl_price'], actual_ticker)}` (-{plan['sl_pct']:.1f}%)
🎯 *Target TP 2:* `{format_price(plan['tp2'], actual_ticker)}` (+5.0%)
⚖️ *Risk/Reward:* `1 : {plan['rrr']}`
━━━━━━━━━━━━━━━━━━━━
"""
    if asset_type == "stock":
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": f"🛒 Beli 1 Lot {sym}", "callback_data": f"btn_buy_{sym}_1"},
                    {"text": f"🛒 Beli 5 Lot {sym}", "callback_data": f"btn_buy_{sym}_5"},
                    {"text": f"🛒 Beli 10 Lot {sym}", "callback_data": f"btn_buy_{sym}_10"}
                ],
                [
                    {"text": f"🤖 AI Insight {sym}", "callback_data": f"btn_ai_{sym}"},
                    {"text": f"🧭 Teknikal {sym}", "callback_data": f"btn_ta_{sym}"},
                    {"text": f"🏢 Fundamental {sym}", "callback_data": f"btn_fund_{sym}"}
                ],
                [
                    {"text": f"🌐 Bandarmology {sym}", "callback_data": f"btn_flow_{sym}"},
                    {"text": f"🎯 Plan Detail", "callback_data": f"btn_plan_{sym}"},
                    {"text": f"📰 Berita {sym}", "callback_data": f"btn_news_{sym}"}
                ]
            ]
        }
    else:
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": f"🤖 AI Insight {display_name}", "callback_data": f"btn_ai_{sym}"},
                    {"text": f"🧭 Teknikal {display_name}", "callback_data": f"btn_ta_{sym}"}
                ],
                [
                    {"text": f"🎯 Plan {display_name}", "callback_data": f"btn_plan_{sym}"},
                    {"text": f"📰 Berita {display_name}", "callback_data": f"btn_news_{sym}"}
                ],
                [
                    {"text": "🪙 Market Crypto", "callback_data": "btn_crypto"},
                    {"text": "🌍 Forex & Gold", "callback_data": "btn_forex"}
                ]
            ]
        }
    
    success = send_telegram_photo(chart_file, caption=caption.strip(), reply_markup=keyboard)
    if not success:
        send_reply(chat_id, "⚠️ Gagal mengirim file gambar ke Telegram. Coba ulangi beberapa saat lagi.")

def handle_plan_cmd(chat_id: str, symbol: str):
    """
    Menampilkan Trading Plan lengkap: Area Beli, Stop Loss (SL), Target Profit (TP), dan Risk:Reward
    """
    sym = get_clean_symbol(symbol)
    send_reply(chat_id, f"⏳ *Menghitung Trading Plan untuk {sym}...*")
    
    plan = get_trading_plan(sym)
    if not plan.get("valid"):
        send_reply(chat_id, f"❌ Gagal memuat data `{sym}`: {plan.get('error', 'Instrumen tidak ditemukan')}")
        return
        
    actual_ticker = plan.get('ticker', sym)
    asset_type = plan.get('asset_type', get_asset_type(actual_ticker))
    display_name = get_display_name(actual_ticker)
    
    signal_badge = "🔥 STRONG BUY" if plan['signal'] == 'STRONG BUY' else ("🟢 BUY" if plan['signal'] == 'BUY' else "⚪ NEUTRAL")
    chg_badge = "🟢" if plan['change_pct'] >= 0 else "🔴"
    
    msg = f"""
🎯 *TRADING PLAN: {display_name} ({asset_type.upper()})*
━━━━━━━━━━━━━━━━━━━━
📊 *Status Pasar:* {signal_badge}
💵 *Harga Terkini:* `{format_price(plan['close'], actual_ticker)}` ({chg_badge} {plan['change_pct']:+.2f}%)
📈 *RVol:* `{plan['rvol']}x` | *RSI:* `{plan['rsi']}`

🛒 *REKOMENDASI BELI (ENTRY ZONE):*
  • *Area Beli*  : `{format_price(plan['buy_min'], actual_ticker)} - {format_price(plan['buy_max'], actual_ticker)}`
  • *Ideal Entry*: `{format_price(plan['buy_entry_ideal'], actual_ticker)}`

🛑 *BATAS RISIKO (STOP LOSS):*
  • *Stop Loss (SL)*: `{format_price(plan['sl_price'], actual_ticker)}` (-{plan['sl_pct']:.1f}%)
  ⚠️ *Wajib Cut Loss jika harga tembus ke bawah `{format_price(plan['sl_price'], actual_ticker)}`*

🎯 *TARGET TAKE PROFIT (TP):*
  • *Target TP 1* : `{format_price(plan['tp1'], actual_ticker)}` (+3.0%)
  • *Target TP 2* : `{format_price(plan['tp2'], actual_ticker)}` (+5.0%)
  • *Target TP 3* : `{format_price(plan['tp3'], actual_ticker)}` (+8.0%)

⚖️ *Risk to Reward Ratio:* `1 : {plan['rrr']}`
🧱 *Support Terdekat:* `{format_price(plan['support'], actual_ticker)}`
🏢 *Resistance:* `{format_price(plan['resistance'], actual_ticker)}`
━━━━━━━━━━━━━━━━━━━━
"""
    if asset_type == "stock":
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": f"🤖 AI Insight {sym}", "callback_data": f"btn_ai_{sym}"},
                    {"text": f"🧭 Teknikal {sym}", "callback_data": f"btn_ta_{sym}"},
                    {"text": f"🏢 Fundamental {sym}", "callback_data": f"btn_fund_{sym}"}
                ],
                [
                    {"text": f"📊 Lihat Chart {sym}", "callback_data": f"btn_chart_{sym}"},
                    {"text": f"🌐 Cek Bandar {sym}", "callback_data": f"btn_flow_{sym}"},
                    {"text": f"📰 Berita {sym}", "callback_data": f"btn_news_{sym}"}
                ],
                [
                    {"text": f"🛒 Beli 1 Lot {sym}", "callback_data": f"btn_buy_{sym}_1"},
                    {"text": f"🛒 Beli 5 Lot {sym}", "callback_data": f"btn_buy_{sym}_5"},
                    {"text": f"🛒 Beli 10 Lot {sym}", "callback_data": f"btn_buy_{sym}_10"}
                ]
            ]
        }
    else:
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": f"🤖 AI Insight {display_name}", "callback_data": f"btn_ai_{sym}"},
                    {"text": f"🧭 Teknikal {display_name}", "callback_data": f"btn_ta_{sym}"}
                ],
                [
                    {"text": f"📊 Lihat Chart {display_name}", "callback_data": f"btn_chart_{sym}"},
                    {"text": f"📰 Berita {display_name}", "callback_data": f"btn_news_{sym}"}
                ],
                [
                    {"text": "🪙 Market Crypto", "callback_data": "btn_crypto"},
                    {"text": "🌍 Forex & Gold", "callback_data": "btn_forex"}
                ]
            ]
        }
    send_reply(chat_id, msg.strip(), reply_markup=keyboard)

def handle_price_cmd(chat_id: str, symbol: str):
    """
    Menampilkan ringkasan harga instan untuk saham, crypto, komoditas, atau forex
    """
    sym = get_clean_symbol(symbol)
    summary = get_ticker_summary(sym)
    if not summary.get("valid"):
        send_reply(chat_id, f"❌ Data harga untuk `{sym}` tidak ditemukan.")
        return
        
    chg_sign = "+" if summary["change_pct"] >= 0 else ""
    chg_badge = "🟢" if summary["change_pct"] >= 0 else "🔴"
    disp_name = get_display_name(summary["ticker"])
    
    msg = f"""
💵 *CEK HARGA: {disp_name}*
━━━━━━━━━━━━━━━━━━━━
📌 *Harga Terkini:* `{summary['formatted_price']}` ({chg_badge} `{chg_sign}{summary['change_pct']:.2f}%`)
📊 *Tertinggi (High):* `{format_price(summary['high'], summary['ticker'])}`
📉 *Terendah (Low):* `{format_price(summary['low'], summary['ticker'])}`
🏁 *Open:* `{format_price(summary['open'], summary['ticker'])}` | *Prev Close:* `{format_price(summary['prev_close'], summary['ticker'])}`
━━━━━━━━━━━━━━━━━━━━
_Ketik `/plan {sym}` untuk trading plan atau `/chart {sym}` untuk candlestick chart._
"""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": f"📊 Chart {disp_name}", "callback_data": f"btn_chart_{sym}"},
                {"text": f"🎯 Plan {disp_name}", "callback_data": f"btn_plan_{sym}"}
            ]
        ]
    }
    send_reply(chat_id, msg.strip(), reply_markup=keyboard)

def handle_bandarmology_cmd(chat_id: str, symbol: str):
    """
    Menampilkan analisis arus dana besar / Bandarmology & Money Flow
    """
    sym = get_clean_symbol(symbol)
    send_reply(chat_id, f"⏳ *Menganalisis arus dana & akumulasi bandar {sym}...*")
    
    flow = analyze_bandarmology(sym)
    if not flow.get("valid"):
        send_reply(chat_id, f"❌ Gagal memuat data bandarmology untuk `{sym}`.")
        return
        
    obv_str = "🟢 Uptrend (Akumulasi Berjalan)" if flow['is_obv_uptrend'] else "🔴 Downtrend (Tekanan Jual)"
    cmf_str = f"+{flow['cmf']:.3f}" if flow['cmf'] >= 0 else f"{flow['cmf']:.3f}"
    
    msg = f"""
🌐 *ANALISIS ARUS DANA & BANDARMOLOGY: {flow['symbol']}*
━━━━━━━━━━━━━━━━━━━━
🏆 *Skor Akumulasi:* `{flow['score']}/100`
📊 *Status:* {flow['status']}
💡 *Sentimen:* _{flow['sentiment']}_

📈 *Indikator Aliran Dana:*
  • *Chaikin Money Flow (CMF):* `{cmf_str}`
    _(> +0.05 = Inflow Uang Besar | < -0.05 = Outflow)_
  • *Tren OBV (Volume Akumulasi):* {obv_str}
  • *Relative Volume (RVol):* `{flow['rvol']}x`
  • *Turnover Hari Ini:* `{format_idr(flow['turnover'])}`
  • *Performa 5 Hari:* `{flow['change_5d']:+.2f}%`
━━━━━━━━━━━━━━━━━━━━
"""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": f"📊 Chart {sym}", "callback_data": f"btn_chart_{sym}"},
                {"text": f"🎯 Trading Plan {sym}", "callback_data": f"btn_plan_{sym}"}
            ]
        ]
    }
    send_reply(chat_id, msg.strip(), reply_markup=keyboard)

def handle_alert_cmd(chat_id: str, args: list):
    """
    Format: /alert <KODE> <HARGA>
    Contoh: /alert BBCA 6000
    """
    if len(args) < 2:
        send_reply(chat_id, "⚠️ *Format salah!*\nGunakan: `/alert <KODE> <HARGA_TARGET>`\nContoh: `/alert BBCA 6000` atau `/alert BBRI 3200`")
        return
        
    sym = args[0].upper()
    try:
        price = float(args[1].replace(".", "").replace(",", ""))
    except ValueError:
        send_reply(chat_id, "⚠️ Target harga harus berupa angka. Contoh: `/alert BBCA 6000`")
        return
        
    res = add_price_alert(sym, price, chat_id)
    send_reply(chat_id, res["message"])

def handle_alerts_list_cmd(chat_id: str):
    """Menampilkan daftar alarm harga yang sedang aktif"""
    alerts = get_user_alerts(chat_id)
    if not alerts:
        send_reply(chat_id, "ℹ️ Anda belum memiliki alarm harga yang aktif.\nPasang alarm dengan: `/alert <KODE> <HARGA>` (contoh: `/alert BBCA 6000`).")
        return
        
    msg = "🚨 *DAFTAR ALARM HARGA AKTIF:*\n━━━━━━━━━━━━━━━━━━━━\n"
    for a in alerts:
        cond_badge = "Naik ke ≥" if a["condition"] == "GTE" else "Turun ke ≤"
        msg += f"• *ID #{a['id']}* : `{a['symbol']}` {cond_badge} `{format_idr(a['target_price'])}`\n  _Dibuat di harga: {format_idr(a['created_price'])}_\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n_Untuk menghapus alarm, ketik: `/delalert <ID>` (contoh: `/delalert 1`)_"
    send_reply(chat_id, msg.strip())

def handle_delalert_cmd(chat_id: str, args: list):
    """Format: /delalert <ID>"""
    if not args or not args[0].isdigit():
        send_reply(chat_id, "⚠️ Masukkan ID alarm yang ingin dihapus. Contoh: `/delalert 1`\nKetik `/alerts` untuk melihat daftar ID.")
        return
    alert_id = int(args[0])
    res = delete_price_alert(alert_id, chat_id)
    send_reply(chat_id, res["message"])

def handle_watch_cmd(chat_id: str, symbol: str):
    """Format: /watch <KODE>"""
    if not symbol:
        send_reply(chat_id, "⚠️ Masukkan kode saham. Contoh: `/watch ANTM`")
        return
    res = add_to_watchlist(symbol, chat_id)
    send_reply(chat_id, res["message"])

def handle_unwatch_cmd(chat_id: str, symbol: str):
    """Format: /unwatch <KODE>"""
    if not symbol:
        send_reply(chat_id, "⚠️ Masukkan kode saham. Contoh: `/unwatch ANTM`")
        return
    res = remove_from_watchlist(symbol, chat_id)
    send_reply(chat_id, res["message"])

def handle_watchlist_cmd(chat_id: str):
    """Memindai saham-saham pilihan di watchlist pribadi user"""
    user_list = get_user_watchlist(chat_id)
    if not user_list:
        send_reply(chat_id, "ℹ️ Watchlist pribadi Anda masih kosong.\nTambahkan saham favorit dengan: `/watch <KODE>` (contoh: `/watch BBCA`).")
        return
        
    send_reply(chat_id, f"⭐ *Memindai {len(user_list)} saham favorit di Watchlist Anda...*")
    results = run_screener(watchlist=user_list, send_telegram=False, show_all=True)
    
    reply = f"⭐ *HASIL PANTAUAN WATCHLIST PRIBADI ANDA:*\n━━━━━━━━━━━━━━━━━━━━\n"
    for s in results:
        close = s['close']
        sl = round(close * 0.97)
        tp = round(close * 1.05)
        buy_min = round(close * 0.99)
        buy_max = round(close * 1.005)
        reply += f"""
📌 *{s['symbol']}* ({s['signal']})
💵 Harga Now: `{format_idr(close)}` ({s['change_pct']:+.2f}%) | RVol: `{s['rvol']:.2f}x`
🛒 *Area Beli* : `{format_idr(buy_min)} - {format_idr(buy_max)}`
🛑 *Stop Loss*  : `{format_idr(sl)}` (-3.0%)
🎯 *Target TP*  : `{format_idr(tp)}` (+5.0%)
────────────────────
"""
    reply += "_Ketik `/chart KODE` untuk grafik atau `/plan KODE` untuk detail._"
    send_reply(chat_id, reply.strip())

def handle_news_cmd(chat_id: str, symbol_or_query: Optional[str] = None):
    """
    Mengambil dan menampilkan berita terkini saham IDX atau berita pasar modal makro (IHSG).
    Format: /news atau /news <KODE_SAHAM>
    """
    sym = symbol_or_query.strip().upper() if symbol_or_query else ""
    if sym:
        clean_sym = get_clean_symbol(sym)
        send_reply(chat_id, f"⏳ *Mencari berita terkini untuk saham {clean_sym}...*")
        news_items = get_stock_news(clean_sym, limit=5)
        header = f"📰 *BERITA TERKINI EMITEN: {clean_sym} (IDX)*"
        reply_text = format_news_markdown(news_items, header)
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": f"📊 Chart {clean_sym}", "callback_data": f"btn_chart_{clean_sym}"},
                    {"text": f"🎯 Plan {clean_sym}", "callback_data": f"btn_plan_{clean_sym}"},
                    {"text": f"🌐 Bandar {clean_sym}", "callback_data": f"btn_flow_{clean_sym}"}
                ],
                [
                    {"text": "🔥 Top Movers Hari Ini", "callback_data": "btn_topmovers"},
                    {"text": "📰 Berita IHSG & Pasar", "callback_data": "btn_news_market"}
                ]
            ]
        }
    else:
        send_reply(chat_id, "⏳ *Mengambil rangkuman berita pasar modal & IHSG terkini...*")
        news_items = get_market_news(limit=5)
        header = "📰 *BERITA PASAR MODAL & IHSG HARI INI*"
        reply_text = format_news_markdown(news_items, header)
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🚀 Top Gainers", "callback_data": "btn_topgain"},
                    {"text": "🔻 Top Losers", "callback_data": "btn_toploss"},
                    {"text": "🔥 Top Movers", "callback_data": "btn_topmovers"}
                ],
                [
                    {"text": "🔍 Scan Sinyal BUY", "callback_data": "btn_scan"},
                    {"text": "⭐ Watchlist", "callback_data": "btn_watchlist"}
                ]
            ]
        }
    send_reply(chat_id, reply_text, reply_markup=keyboard)

def handle_topmovers_cmd(chat_id: str):
    """
    Menampilkan ringkasan Top Gainers, Top Losers, dan Most Active Turnover
    """
    send_reply(chat_id, "⏳ *Menghitung pergerakan Top Movers saham IDX hari ini...*")
    msg = format_top_movers_summary(limit=5)
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🚀 Top Gainers Lengkap", "callback_data": "btn_topgain"},
                {"text": "🔻 Top Losers Lengkap", "callback_data": "btn_toploss"}
            ],
            [
                {"text": "📰 Berita Pasar", "callback_data": "btn_news_market"},
                {"text": "🔍 Scan Momentum", "callback_data": "btn_scan"}
            ]
        ]
    }
    send_reply(chat_id, msg, reply_markup=keyboard)

def handle_topgain_cmd(chat_id: str):
    """
    Menampilkan daftar Top Gainers saham IDX hari ini
    """
    send_reply(chat_id, "⏳ *Mengambil daftar saham Top Gainers hari ini...*")
    msg = format_top_gainers_only(limit=7)
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔻 Cek Top Losers", "callback_data": "btn_toploss"},
                {"text": "🔥 Ringkasan Movers", "callback_data": "btn_topmovers"}
            ],
            [
                {"text": "🔍 Scan Sinyal BUY", "callback_data": "btn_scan"},
                {"text": "📰 Berita Pasar", "callback_data": "btn_news_market"}
            ]
        ]
    }
    send_reply(chat_id, msg, reply_markup=keyboard)

def handle_toploss_cmd(chat_id: str):
    """
    Menampilkan daftar Top Losers saham IDX hari ini
    """
    send_reply(chat_id, "⏳ *Mengambil daftar saham Top Losers hari ini...*")
    msg = format_top_losers_only(limit=7)
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🚀 Cek Top Gainers", "callback_data": "btn_topgain"},
                {"text": "🔥 Ringkasan Movers", "callback_data": "btn_topmovers"}
            ],
            [
                {"text": "🔍 Scan Sinyal BUY", "callback_data": "btn_scan"},
                {"text": "📰 Berita Pasar", "callback_data": "btn_news_market"}
            ]
        ]
    }
    send_reply(chat_id, msg, reply_markup=keyboard)

def handle_ara_cmd(chat_id: str):
    """
    Screener Saham ARA Hunter (Auto Rejection Atas)
    """
    send_reply(chat_id, "⏳ *Memindai saham IDX untuk radar ARA Hunter...*\n_Menghitung batas harga ARA (+20% s/d +35%), fraksi harga, dan jarak sisa tick..._")
    msg = format_ara_message(limit=7)
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🌅 Cek Screener BSJP", "callback_data": "btn_bsjp"},
                {"text": "🚀 Top Gainers", "callback_data": "btn_topgain"}
            ],
            [
                {"text": "🔍 Scan Momentum Reguler", "callback_data": "btn_scan"},
                {"text": "💼 Portofolio", "callback_data": "btn_portfolio"}
            ]
        ]
    }
    send_reply(chat_id, msg, reply_markup=keyboard)

def handle_bsjp_cmd(chat_id: str):
    """
    Screener Saham BSJP (Beli Sore Jual Pagi)
    """
    send_reply(chat_id, "⏳ *Menjalankan Screener BSJP (Beli Sore Jual Pagi)...*\n_Menganalisis kekuatan candle penutupan, volume akumulasi, dan target jual pagi..._")
    msg = format_bsjp_message(limit=6)
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🎯 Cek ARA Hunter", "callback_data": "btn_ara"},
                {"text": "🔥 Top Movers", "callback_data": "btn_topmovers"}
            ],
            [
                {"text": "🔍 Scan Sinyal BUY", "callback_data": "btn_scan"},
                {"text": "💼 Portofolio", "callback_data": "btn_portfolio"}
            ]
        ]
    }
    send_reply(chat_id, msg, reply_markup=keyboard)

def handle_crypto_cmd(chat_id: str):
    """
    Menampilkan ringkasan pasar Crypto teratas (BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX)
    """
    send_reply(chat_id, "⏳ *Memuat ringkasan harga pasar Cryptocurrency terkini...*")
    msg = format_crypto_message()
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📊 Chart BTC", "callback_data": "btn_chart_BTC"},
                {"text": "🎯 Plan BTC", "callback_data": "btn_plan_BTC"},
                {"text": "📰 Berita BTC", "callback_data": "btn_news_BTC"}
            ],
            [
                {"text": "📊 Chart ETH", "callback_data": "btn_chart_ETH"},
                {"text": "🎯 Plan ETH", "callback_data": "btn_plan_ETH"},
                {"text": "📊 Chart SOL", "callback_data": "btn_chart_SOL"}
            ],
            [
                {"text": "🌍 Forex & Gold", "callback_data": "btn_forex"},
                {"text": "🔄 Refresh Crypto", "callback_data": "btn_crypto"}
            ]
        ]
    }
    send_reply(chat_id, msg, reply_markup=keyboard)

def handle_forex_cmd(chat_id: str):
    """
    Menampilkan ringkasan pasar Forex & Komoditas dunia (Gold/XAU, Silver, Oil, EURUSD, GBPUSD, USDJPY)
    """
    send_reply(chat_id, "⏳ *Memuat ringkasan pasar Forex & Komoditas dunia...*")
    msg = format_forex_message()
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📊 Chart Gold (XAU)", "callback_data": "btn_chart_XAU"},
                {"text": "🎯 Plan Gold", "callback_data": "btn_plan_XAU"},
                {"text": "📰 Berita Gold", "callback_data": "btn_news_XAU"}
            ],
            [
                {"text": "📊 Chart Silver", "callback_data": "btn_chart_XAG"},
                {"text": "📊 Chart Oil", "callback_data": "btn_chart_OIL"},
                {"text": "📊 Chart EURUSD", "callback_data": "btn_chart_EURUSD"}
            ],
            [
                {"text": "🪙 Market Crypto", "callback_data": "btn_crypto"},
                {"text": "🔄 Refresh Forex", "callback_data": "btn_forex"}
            ]
        ]
    }
    send_reply(chat_id, msg, reply_markup=keyboard)

def handle_ai_cmd(chat_id: str, symbol: str):
    """
    Menampilkan AI Market Insight (Sintesis Teknikal, Smart Money, dan Sentimen Berita)
    """
    sym = get_clean_symbol(symbol)
    send_reply(chat_id, f"🧠 *AI sedang menganalisis sentimen teknikal, arus bandar, dan berita {sym}...*")
    msg = get_ai_market_insight(sym)
    keyboard = {
        "inline_keyboard": [
            [
                {"text": f"🎯 Plan {sym}", "callback_data": f"btn_plan_{sym}"},
                {"text": f"🧭 Teknikal {sym}", "callback_data": f"btn_ta_{sym}"},
                {"text": f"📊 Chart {sym}", "callback_data": f"btn_chart_{sym}"}
            ],
            [
                {"text": f"🏢 Fundamental {sym}", "callback_data": f"btn_fund_{sym}"},
                {"text": f"📰 Berita {sym}", "callback_data": f"btn_news_{sym}"}
            ]
        ]
    }
    send_reply(chat_id, msg, reply_markup=keyboard)

def handle_ta_cmd(chat_id: str, symbol: str):
    """
    Menampilkan Konsensus Meteran Teknikal (TradingView style)
    """
    sym = get_clean_symbol(symbol)
    send_reply(chat_id, f"⏳ *Menghitung meteran konsensus teknikal untuk {sym}...*")
    msg = format_ta_message(sym)
    keyboard = {
        "inline_keyboard": [
            [
                {"text": f"🤖 AI Insight {sym}", "callback_data": f"btn_ai_{sym}"},
                {"text": f"🎯 Plan {sym}", "callback_data": f"btn_plan_{sym}"},
                {"text": f"📊 Chart {sym}", "callback_data": f"btn_chart_{sym}"}
            ],
            [
                {"text": f"🏢 Fundamental {sym}", "callback_data": f"btn_fund_{sym}"},
                {"text": f"🌐 Bandarmology {sym}", "callback_data": f"btn_flow_{sym}"}
            ]
        ]
    }
    send_reply(chat_id, msg, reply_markup=keyboard)

def handle_bow_cmd(chat_id: str):
    """
    Screener Buy on Weakness (BoW) & Swing Rebound
    """
    send_reply(chat_id, "⏳ *Memindai saham Buy on Weakness (BoW) & Swing Rebound...*\n_Mencari saham diskon/oversold di area support kuat dengan potensi pembalikan arah..._")
    msg = format_bow_message(limit=6)
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔍 Scan Sinyal BUY", "callback_data": "btn_scan"},
                {"text": "🌅 Screener BSJP", "callback_data": "btn_bsjp"}
            ],
            [
                {"text": "🎯 Screener ARA", "callback_data": "btn_ara"},
                {"text": "📅 Kalender Dividen", "callback_data": "btn_kalender"}
            ]
        ]
    }
    send_reply(chat_id, msg, reply_markup=keyboard)

def handle_fund_cmd(chat_id: str, symbol: str):
    """
    Menampilkan profil fundamental dan valuasi emiten
    """
    sym = get_clean_symbol(symbol)
    send_reply(chat_id, f"⏳ *Memuat rasio fundamental & valuasi {sym}...*")
    msg = format_fundamental_message(sym)
    keyboard = {
        "inline_keyboard": [
            [
                {"text": f"🤖 AI Insight {sym}", "callback_data": f"btn_ai_{sym}"},
                {"text": f"🧭 Teknikal {sym}", "callback_data": f"btn_ta_{sym}"},
                {"text": f"🎯 Plan {sym}", "callback_data": f"btn_plan_{sym}"}
            ],
            [
                {"text": "📅 Kalender Dividen", "callback_data": "btn_kalender"},
                {"text": f"📰 Berita {sym}", "callback_data": f"btn_news_{sym}"}
            ]
        ]
    }
    send_reply(chat_id, msg, reply_markup=keyboard)

def handle_kalender_cmd(chat_id: str):
    """
    Menampilkan kalender aksi korporasi & jadwal dividen IDX
    """
    send_reply(chat_id, "⏳ *Mengambil kalender aksi korporasi & jadwal dividen IDX...*")
    msg = format_calendar_message()
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🎣 Screener BoW", "callback_data": "btn_bow"},
                {"text": "🔥 Top Movers", "callback_data": "btn_topmovers"}
            ],
            [
                {"text": "🏢 Fundamental BBCA", "callback_data": "btn_fund_BBCA"},
                {"text": "🏢 Fundamental BBRI", "callback_data": "btn_fund_BBRI"}
            ]
        ]
    }
    send_reply(chat_id, msg, reply_markup=keyboard)

def handle_akumulasi_cmd(chat_id: str):
    """
    Screener Akumulasi Smart Money & Bandar Hunter seluruh saham IDX
    """
    send_reply(chat_id, "⏳ *Memindai seluruh saham IDX untuk Akumulasi Smart Money & Bandar Hunter...*\n_Menganalisis Big Inflow Score, Chaikin Money Flow (CMF), dan tren OBV..._")
    msg, markup = format_bandar_screener_message()
    send_reply(chat_id, msg, reply_markup=markup)

def handle_sektor_cmd(chat_id: str):
    """
    Radar Rotasi Sektor & Heatmap IDX
    """
    send_reply(chat_id, "⏳ *Menghitung radar rotasi sektor & performa 8 sektor utama IDX...*")
    msg, markup = format_sector_heatmap_message()
    send_reply(chat_id, msg, reply_markup=markup)

def handle_breakout_cmd(chat_id: str):
    """
    Radar Lonjakan Volume Breakout & Volume Spike Hunter
    """
    send_reply(chat_id, "⏳ *Memindai saham dengan lonjakan volume mendadak (RVol ≥ 2.0x) & kenaikan harga...*")
    msg, markup = format_breakout_message()
    send_reply(chat_id, msg, reply_markup=markup)

def handle_calc_cmd(chat_id: str, args: list):
    """
    Kalkulator Money Management:
    Format: /calc <KODE> <RISIKO_RUPIAH>
    Contoh: /calc BBCA 500000 (Siap rugi maksimal Rp 500.000 jika kena SL)
    """
    if len(args) < 2:
        send_reply(chat_id, "⚠️ *Format salah!*\nGunakan: `/calc <KODE> <MAX_RISIKO_RP>`\nContoh: `/calc BBCA 500000`\n_(Artinya Anda siap rugi maksimal Rp 500.000 jika terkena Stop Loss)_")
        return
        
    sym = args[0].upper()
    try:
        max_risk_rp = float(args[1].replace(".", "").replace(",", ""))
    except ValueError:
        send_reply(chat_id, "⚠️ Nominal risiko harus berupa angka. Contoh: `/calc BBCA 500000`")
        return
        
    plan = get_trading_plan(sym)
    if not plan.get("valid"):
        send_reply(chat_id, f"❌ Gagal memuat data `{sym}`.")
        return
        
    entry = plan["close"]
    sl = plan["sl_price"]
    tp2 = plan["tp2"]
    
    # Jarak risiko per lembar & per lot
    risk_per_share = max(entry - sl, 1)
    risk_per_lot = risk_per_share * 100 # 1 lot = 100 lembar
    
    # Hitung rekomendasi lot maksimal
    recommended_lots = max(int(max_risk_rp // risk_per_lot), 1)
    shares = recommended_lots * 100
    total_modal = shares * entry
    
    potential_loss = shares * risk_per_share
    potential_profit = shares * (tp2 - entry)
    
    msg = f"""
🧮 *KALKULATOR MONEY MANAGEMENT: {sym}*
━━━━━━━━━━━━━━━━━━━━
🎯 *Toleransi Risiko Anda:* `{format_idr(max_risk_rp)}`

📊 *Parameter Trading Plan:*
  • *Harga Beli (Entry):* `{format_idr(entry)}`
  • *Stop Loss (SL):* `{format_idr(sl)}` (-{plan['sl_pct']:.1f}%)
  • *Target TP 2:* `{format_idr(tp2)}` (+5.0%)
  • *Jarak Risiko per Lot:* `{format_idr(risk_per_lot)}` / lot

💡 *REKOMENDASI UKURAN POSISI (LOT SIZING):*
  📦 *Maksimal Beli:* `{recommended_lots} Lot` ({shares:,} lembar)
  💸 *Total Modal Masuk:* `{format_idr(total_modal)}`
  
  🛑 *Maksimal Kerugian (Jika kena SL):* `{format_idr(potential_loss)}`
  🟢 *Potensi Keuntungan (Jika kena TP2):* `+{format_idr(potential_profit)}`
  ⚖️ *Risk to Reward:* `1 : {plan['rrr']}`
━━━━━━━━━━━━━━━━━━━━
_Klik tombol di bawah untuk langsung membeli sesuai ukuran ideal di atas:_
"""
    keyboard = {
        "inline_keyboard": [
            [
                {"text": f"🛒 Beli {recommended_lots} Lot {sym}", "callback_data": f"btn_buy_{sym}_{recommended_lots}"},
                {"text": f"📊 Lihat Chart {sym}", "callback_data": f"btn_chart_{sym}"}
            ]
        ]
    }
    send_reply(chat_id, msg.strip(), reply_markup=keyboard)

def handle_scan_cmd(chat_id: str, header_prefix: str = ""):
    """
    Memindai saham IDX dan menampilkan hasil lengkap dengan Area Beli dan Stop Loss.
    """
    if not header_prefix:
        send_reply(chat_id, "⏳ *Sedang memindai saham-saham likuid IDX...*\n_Menghitung Area Beli, Target TP, dan Stop Loss..._")
        
    results = run_screener(send_telegram=False, show_all=False)
    buy_signals = [r for r in results if r.get('has_signal', False)]
    
    title = f"{header_prefix}\n" if header_prefix else ""
    
    if buy_signals:
        reply = f"{title}🎉 *HASIL SCREENER: DITEMUKAN SINYAL MOMENTUM BUY!* 🚀\n━━━━━━━━━━━━━━━━━━━━\n"
        for sig in buy_signals[:5]:
            buy_min = round(sig['close'] * 0.99)
            buy_max = round(sig['close'] * 1.005)
            reply += f"""
📌 *{sig['symbol']}* ({sig['signal']})
💵 Harga: `{format_idr(sig['close'])}` ({sig['change_pct']:+.2f}%) | RVol: `{sig['rvol']}x`
🛒 *Area Beli (Entry)*: `{format_idr(buy_min)} - {format_idr(buy_max)}`
🛑 *Stop Loss (SL)*   : `{format_idr(sig['sl'])}` (-3.0%)
🎯 *Target TP 1*       : `{format_idr(sig['tp1'])}` (+3.0%)
🎯 *Target TP 2*       : `{format_idr(sig['tp2'])}` (+5.0%)
⚖️ *Risk/Reward*      : `1 : {sig['rrr']}`
━━━━━━━━━━━━━━━━━━━━
"""
        reply += "💡 _Ketik `/chart KODE` untuk grafik atau `/buy KODE LOT` untuk membeli._"
    else:
        top_stocks = sorted(results, key=lambda x: x.get('rvol', 0), reverse=True)[:4]
        reply = f"{title}ℹ️ *PEMANTAUAN SAHAM LIKUID IDX TERAKTIF*\n_Belum ada breakout momentum agresif saat ini. Berikut panduan Buy & SL saham bervolume tinggi:_ \n━━━━━━━━━━━━━━━━━━━━\n"
        for s in top_stocks:
            close = s['close']
            sl = round(close * 0.97)
            tp = round(close * 1.05)
            buy_min = round(close * 0.99)
            buy_max = round(close * 1.005)
            reply += f"""
📌 *{s['symbol']}* (RVol: `{s['rvol']:.2f}x` | RSI: `{s['rsi']}`)
💵 Harga Now: `{format_idr(close)}` ({s['change_pct']:+.2f}%)
🛒 *Area Beli* : `{format_idr(buy_min)} - {format_idr(buy_max)}`
🛑 *Stop Loss*  : `{format_idr(sl)}` (-3.0%)
🎯 *Target TP*  : `{format_idr(tp)}` (+5.0%)
────────────────────
"""
        reply += "💡 _Ketik `/chart KODE` untuk grafik atau `/plan KODE` untuk detail._"
        
    send_reply(chat_id, reply.strip())

def handle_price_cmd(chat_id: str, symbol: str):
    handle_plan_cmd(chat_id, symbol)

def handle_portfolio_cmd(chat_id: str):
    portfolio = load_portfolio()
    cash = portfolio.get("cash_balance", 0.0)
    initial = portfolio.get("initial_balance", 50_000_000)
    positions = portfolio.get("positions", {})
    
    total_market_val = 0.0
    pos_lines = []
    
    for sym, pos in positions.items():
        curr_price = get_current_price(pos["ticker"]) or pos["avg_price"]
        shares = pos["shares"]
        val = shares * curr_price * 0.9975 # net sell
        unrealized = val - pos["total_cost"]
        pnl_pct = (unrealized / pos["total_cost"]) * 100 if pos["total_cost"] else 0
        total_market_val += val
        
        pnl_badge = "🟢" if unrealized >= 0 else "🔴"
        tp_price = pos.get('tp_price', round(pos['avg_price'] * 1.05))
        sl_price = pos.get('sl_price', round(pos['avg_price'] * 0.97))
        
        pos_lines.append(
            f"{pnl_badge} *{sym}*: {pos['lots']} Lot @ `{format_idr(pos['avg_price'])}`\n"
            f"   Now: `{format_idr(curr_price)}` | PnL: `{format_idr(unrealized)}` ({pnl_pct:+.2f}%)\n"
            f"   🎯 TP: `{format_idr(tp_price)}` | 🛑 SL: `{format_idr(sl_price)}`"
        )
        
    total_assets = cash + total_market_val
    overall_pnl = total_assets - initial
    overall_pct = (overall_pnl / initial) * 100
    
    msg = f"""
💼 *PORTOFOLIO PAPER TRADING IDX*
━━━━━━━━━━━━━━━━━━━━
💰 *Kas Tunai:* `{format_idr(cash)}`
📈 *Nilai Saham:* `{format_idr(total_market_val)}`
🏆 *Total Aset:* `{format_idr(total_assets)}`
📊 *Total Return:* `{format_idr(overall_pnl)}` ({overall_pct:+.2f}%)
━━━━━━━━━━━━━━━━━━━━
*Posisi Terbuka:*
"""
    if pos_lines:
        msg += "\n\n".join(pos_lines)
    else:
        msg += "_(Tidak ada posisi saham aktif. 100% Kas Tunai)_"
        
    send_reply(chat_id, msg.strip())

def handle_buy_cmd(chat_id: str, args: list):
    """
    Format: /buy <KODE> <LOT> [TP%] [SL%]
    Contoh: /buy BBCA 5
    Contoh: /buy BBCA 5 7 3
    """
    if len(args) < 2:
        send_reply(chat_id, "⚠️ *Format salah!*\nGunakan: `/buy <KODE> <LOT> [TP%] [SL%]`\n\n*Contoh:* \n• `/buy BBCA 5` (Default TP +5%, SL -3%)\n• `/buy BBCA 5 7 4` (Kustom TP +7%, SL -4%)")
        return
        
    sym = args[0].upper()
    try:
        lots = int(args[1])
    except ValueError:
        send_reply(chat_id, "⚠️ Jumlah lot harus berupa angka bulat.")
        return
        
    tp_pct = float(args[2]) if len(args) > 2 and args[2].replace('.', '', 1).isdigit() else DEFAULT_TP2_PCT
    sl_pct = float(args[3]) if len(args) > 3 and args[3].replace('.', '', 1).isdigit() else DEFAULT_SL_PCT
        
    res = buy_stock(sym, lots=lots, tp_pct=tp_pct, sl_pct=sl_pct)
    if res["success"]:
        send_reply(
            chat_id,
            f"✅ *ORDER BELI BERHASIL DIEKSEKUSI!*\n━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Saham:* `{res['symbol']}`\n"
            f"📦 *Jumlah:* `{res['lots']} Lot` ({res['shares']} lembar)\n"
            f"💵 *Harga Beli (Entry):* `{format_idr(res['price'])}`\n"
            f"💸 *Total Modal:* `{format_idr(res['total_cost'])}`\n\n"
            f"🛑 *Stop Loss (SL) Aktif:* `{format_idr(res['sl_price'])}` (-{sl_pct:.1f}%)\n"
            f"🎯 *Take Profit (TP) Aktif:* `{format_idr(res['tp_price'])}` (+{tp_pct:.1f}%)\n"
            f"🛡️ *Trailing Stop:* Aktif di 2.0%\n"
            f"💰 *Sisa Saldo Kas:* `{format_idr(res['remaining_cash'])}`\n━━━━━━━━━━━━━━━━━━━━"
        )
    else:
        send_reply(chat_id, f"❌ Gagal: {res['message']}")

def handle_sell_cmd(chat_id: str, args: list):
    if len(args) < 1:
        send_reply(chat_id, "⚠️ Format salah. Gunakan: `/sell <KODE_SAHAM> [JUMLAH_LOT]`\nContoh: `/sell BBCA` (jual semua) atau `/sell BBCA 2`")
        return
    sym = args[0].upper()
    lots = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    
    res = sell_stock(sym, lots=lots)
    if res["success"]:
        pnl_badge = "🟢 PROFIT" if res.get('net_pnl', 0) >= 0 else "🔴 LOSS"
        send_reply(
            chat_id,
            f"✅ *ORDER JUAL BERHASIL DIEKSEKUSI! ({pnl_badge})*\n━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Saham:* `{res['symbol']}` ({res['lots']} Lot)\n"
            f"💵 *Harga Jual:* `{format_idr(res['sell_price'])}`\n"
            f"💸 *Total Diterima:* `{format_idr(res['net_revenue'])}`\n"
            f"📊 *Realized PnL:* `{format_idr(res['net_pnl'])}` ({res['pnl_pct']:+.2f}%)\n"
            f"💰 *Sisa Saldo Kas:* `{format_idr(res['remaining_cash'])}`\n━━━━━━━━━━━━━━━━━━━━"
        )
    else:
        send_reply(chat_id, f"❌ Gagal: {res['message']}")

def process_callback_query(query: Dict[str, Any]):
    chat_id = str(query.get("message", {}).get("chat", {}).get("id"))
    data = query.get("data", "")
    
    token, _ = get_credentials()
    try:
        requests.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery", json={"callback_query_id": query.get("id")}, timeout=5)
    except Exception:
        pass
        
    if data == "btn_scan":
        handle_scan_cmd(chat_id)
    elif data == "btn_portfolio":
        handle_portfolio_cmd(chat_id)
    elif data == "btn_watchlist":
        handle_watchlist_cmd(chat_id)
    elif data.startswith("btn_plan_"):
        sym = data.replace("btn_plan_", "")
        handle_plan_cmd(chat_id, sym)
    elif data.startswith("btn_chart_"):
        sym = data.replace("btn_chart_", "")
        handle_chart_cmd(chat_id, sym)
    elif data.startswith("btn_flow_"):
        sym = data.replace("btn_flow_", "")
        handle_bandarmology_cmd(chat_id, sym)
    elif data.startswith("btn_buy_"):
        # Format: btn_buy_BBCA_5
        parts = data.split("_")
        if len(parts) >= 4:
            sym = parts[2]
            lots = int(parts[3])
            handle_buy_cmd(chat_id, [sym, str(lots)])
    elif data == "btn_topmovers":
        handle_topmovers_cmd(chat_id)
    elif data == "btn_topgain":
        handle_topgain_cmd(chat_id)
    elif data == "btn_toploss":
        handle_toploss_cmd(chat_id)
    elif data == "btn_ara":
        handle_ara_cmd(chat_id)
    elif data == "btn_bsjp":
        handle_bsjp_cmd(chat_id)
    elif data == "btn_news_market":
        handle_news_cmd(chat_id, None)
    elif data == "btn_crypto":
        handle_crypto_cmd(chat_id)
    elif data == "btn_forex":
        handle_forex_cmd(chat_id)
    elif data == "btn_bow":
        handle_bow_cmd(chat_id)
    elif data == "btn_kalender":
        handle_kalender_cmd(chat_id)
    elif data == "btn_akumulasi":
        handle_akumulasi_cmd(chat_id)
    elif data == "btn_sektor":
        handle_sektor_cmd(chat_id)
    elif data == "btn_breakout":
        handle_breakout_cmd(chat_id)
    elif data.startswith("btn_ai_"):
        sym = data.replace("btn_ai_", "")
        handle_ai_cmd(chat_id, sym)
    elif data.startswith("btn_ta_"):
        sym = data.replace("btn_ta_", "")
        handle_ta_cmd(chat_id, sym)
    elif data.startswith("btn_fund_"):
        sym = data.replace("btn_fund_", "")
        handle_fund_cmd(chat_id, sym)
    elif data.startswith("btn_news_"):
        sym = data.replace("btn_news_", "")
        handle_news_cmd(chat_id, sym)
    elif data == "btn_update_now":
        handle_scan_cmd(chat_id, header_prefix="🔔 *UPDATE PASAR SAHAM IDX SAAT INI*")

# ==============================================================================
# BACKGROUND SCHEDULER: MONITOR HARGA, ALARM, DAN JAM BURSA
# ==============================================================================
def on_alert_triggered(alert: Dict[str, Any], current_price: float):
    cond_str = "telah naik melampaui" if alert["condition"] == "GTE" else "telah turun menyentuh"
    msg = f"""
🚨 *[PRICE ALERT TERPICU!]* ⏰
━━━━━━━━━━━━━━━━━━━━
📌 *Saham:* `{alert['symbol']}`
💵 *Target Harga:* `{format_idr(alert['target_price'])}`
⚡ *Kondisi:* {cond_str} level target!
📈 *Harga Terkini:* `{format_idr(current_price)}`
━━━━━━━━━━━━━━━━━━━━
_Ketik `/plan {alert['symbol']}` untuk melihat aksi trading plan atau `/buy {alert['symbol']} <LOT>`._
"""
    send_reply(alert["chat_id"], msg.strip())

def background_monitoring_loop():
    """
    Loop pemantau latar belakang:
    1. Memeriksa Price Alert setiap 30 detik
    2. Mengirim update otomatis setiap jam buka/tutup bursa IDX
    """
    token, chat_id = get_credentials()
    if not token or not chat_id:
        return
        
    print("⏰ [SCHEDULER] Background monitoring loop aktif (Alarm harga & Jam bursa)...")
    last_triggered_key = ""
    
    while True:
        try:
            # 1. Cek Alarm Harga
            check_all_alerts(on_alert_triggered)
            
            # 2. Cek Jadwal Jam Bursa (WIB)
            now = get_now_wib()
            weekday = now.weekday()
            hour = now.hour
            minute = now.minute
            
            if weekday < 5:
                # Sesi 1 Buka: 09:05 WIB
                if hour == 9 and 5 <= minute <= 10:
                    slot_key = f"{now.date()}_sesi1_open"
                    if last_triggered_key != slot_key:
                        last_triggered_key = slot_key
                        header = f"🔔 *[UPDATE BURSA IDX: SESI 1 RESMI DIBUKA - {now.strftime('%H:%M')} WIB]* 🚀\n_Pasar saham baru saja dimulai. Berikut pantauan saham momentum, Area Beli, dan batas Stop Loss:_"
                        handle_scan_cmd(chat_id, header_prefix=header)

                # Sesi 2 Buka: 13:35 WIB (Senin-Kamis) atau 14:05 WIB (Jumat)
                is_sesi2_open = (weekday < 4 and hour == 13 and 35 <= minute <= 40) or (weekday == 4 and hour == 14 and 5 <= minute <= 10)
                if is_sesi2_open:
                    slot_key = f"{now.date()}_sesi2_open"
                    if last_triggered_key != slot_key:
                        last_triggered_key = slot_key
                        header = f"🔔 *[UPDATE BURSA IDX: SESI 2 RESMI DIBUKA - {now.strftime('%H:%M')} WIB]* 📈\n_Perdagangan sesi siang dimulai. Berikut saham dengan akumulasi volume terbesar:_"
                        handle_scan_cmd(chat_id, header_prefix=header)

                # Penutupan Pasar: 16:05 WIB
                if hour == 16 and 5 <= minute <= 10:
                    slot_key = f"{now.date()}_market_close"
                    if last_triggered_key != slot_key:
                        last_triggered_key = slot_key
                        header = f"🔔 *[EOD: PENUTUPAN BURSA EFEK INDONESIA - {now.strftime('%H:%M')} WIB]* 🏁\n_Ringkasan penutupan pasar hari ini & saham terbaik untuk watchlist besok:_"
                        handle_scan_cmd(chat_id, header_prefix=header)

                # Auto Volume Breakout Alert selama jam perdagangan aktif (09:00 - 16:00 WIB)
                if (9 <= hour < 12) or (13 <= hour < 16):
                    try:
                        today_str = str(now.date())
                        new_breakouts = check_new_breakout_alerts(today_str)
                        for s in new_breakouts:
                            turn = s['turnover']
                            turn_str = f"Rp {turn / 1_000_000_000:.1f} M" if turn >= 1_000_000_000 else format_idr(turn)
                            spike_msg = (
                                f"🚨 *[REAL-TIME BREAKOUT ALERT!]* ⚡\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"📌 *Saham:* `{s['symbol']}`\n"
                                f"💵 *Harga Terkini:* `{format_idr(s['close'])}` (+{s['change_pct']}%)\n"
                                f"🔥 *Lonjakan Volume:* `{s['rvol']:.1f}x Lipat Normal`!\n"
                                f"💰 *Nilai Transaksi:* `{turn_str}`\n"
                                f"🎯 *Resistensi 20H:* `{format_idr(s['high_20d'])}`\n"
                                f"━━━━━━━━━━━━━━━━━━━━\n"
                                f"_Sinyal otomatis terdeteksi saat bursa berjalan. Ketik `/plan {s['symbol']}` atau `/chart {s['symbol']}`._"
                            )
                            send_reply(chat_id, spike_msg.strip())
                    except Exception as eb:
                        pass
                        
            time.sleep(30)
        except Exception as e:
            print(f"⚠️ Error scheduler loop: {e}")
            time.sleep(30)

def register_bot_commands(token: str):
    """
    Mendaftarkan tombol menu slash command ke Telegram API agar muncul di tombol Menu bot Telegram user
    """
    commands = [
        {"command": "start", "description": "Buka menu navigasi & tombol klik interaktif"},
        {"command": "ai", "description": "Analisis cerdas AI (Teknikal + Bandar + Berita)"},
        {"command": "ta", "description": "Konsensus teknikal meter TradingView style"},
        {"command": "bow", "description": "Screener Buy on Weakness & Rebound Support"},
        {"command": "fund", "description": "Rasio fundamental, PER, PBV, dan Dividen"},
        {"command": "kalender", "description": "Jadwal dividen Cum-Date dan agenda emiten"},
        {"command": "akumulasi", "description": "Screener akumulasi Smart Money & bandar hunter"},
        {"command": "sektor", "description": "Radar rotasi sektor & heatmap performa 8 sektor IDX"},
        {"command": "breakout", "description": "Radar lonjakan volume & breakout resistance"},
        {"command": "scan", "description": "Scan saham momentum & volume spike"},
        {"command": "ara", "description": "Screener ARA Hunter & Potensi ARA"},
        {"command": "bsjp", "description": "Screener Beli Sore Jual Pagi (BSJP)"},
        {"command": "topmovers", "description": "Ringkasan Top Gainers, Losers & Turnover"},
        {"command": "topgain", "description": "Daftar saham kenaikan tertinggi hari ini"},
        {"command": "toploss", "description": "Daftar saham penurunan terdalam hari ini"},
        {"command": "crypto", "description": "Pasar Crypto teratas (BTC, ETH, SOL, BNB)"},
        {"command": "forex", "description": "Pasar Forex & Logam Mulia (Gold/XAU, Oil)"},
        {"command": "news", "description": "Berita finansial & pasar modal terkini"},
        {"command": "chart", "description": "Grafik candlestick teknikal (contoh: /chart BBCA)"},
        {"command": "plan", "description": "Trading plan lengkap (Area Beli, TP, SL)"},
        {"command": "flow", "description": "Analisis bandarmology & CMF (contoh: /flow BBRI)"},
        {"command": "calc", "description": "Kalkulator lot sizing risiko rupiah"},
        {"command": "portfolio", "description": "Portofolio & saldo paper trading"},
        {"command": "watchlist", "description": "Pantau saham-saham favorit pribadi"},
        {"command": "alerts", "description": "Lihat daftar price alert aktif"},
        {"command": "help", "description": "Panduan lengkap semua fitur"}
    ]
    try:
        requests.post(f"https://api.telegram.org/bot{token}/setMyCommands", json={"commands": commands}, timeout=10)
    except Exception:
        pass

def start_interactive_listener():
    """
    Menjalankan background long-polling untuk merespons perintah Telegram secara realtime.
    """
    token, chat_id = get_credentials()
    if not token or not chat_id:
        print("❌ Token Telegram atau Chat ID belum dikonfigurasi.")
        return

    # Daftarkan daftar slash commands resmi ke Telegram agar muncul di Menu bot
    register_bot_commands(token)

    # Mulai thread scheduler & alarm di background
    sched_thread = threading.Thread(target=background_monitoring_loop, daemon=True)
    sched_thread.start()

    print(f"🤖 Bot Telegram @bilnabil_bot sedang aktif mendengarkan perintah...")
    print("⏰ Fitur Lengkap: Chart, Price Alert, Bandarmology, Watchlist, & Money Management aktif!")
    print("Tekan Ctrl+C untuk menghentikan.\n")
    
    offset = None
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates?timeout=20"
            if offset:
                url += f"&offset={offset}"
                
            resp = requests.get(url, timeout=30)
            if resp.status_code != 200:
                time.sleep(3)
                continue
                
            updates = resp.json().get("result", [])
            for u in updates:
                offset = u.get("update_id", 0) + 1
                
                if "callback_query" in u:
                    process_callback_query(u["callback_query"])
                    continue
                    
                msg = u.get("message", {})
                sender_chat_id = str(msg.get("chat", {}).get("id"))
                text = msg.get("text", "").strip()
                first_name = msg.get("from", {}).get("first_name", "Trader")
                
                if not text:
                    continue
                    
                parts = text.split()
                cmd = parts[0].lower()
                cmd_args = parts[1:]
                
                if cmd in ["/start", "/help", "start", "help", "menu"]:
                    handle_start(sender_chat_id, first_name)
                elif cmd.startswith("/ai"):
                    sym = cmd_args[0] if cmd_args else "BBCA"
                    handle_ai_cmd(sender_chat_id, sym)
                elif cmd.startswith("/ta") or cmd in ["/analisis", "analisis", "ta"]:
                    sym = cmd_args[0] if cmd_args else "BBCA"
                    handle_ta_cmd(sender_chat_id, sym)
                elif cmd in ["/bow", "bow", "/swing", "swing"]:
                    handle_bow_cmd(sender_chat_id)
                elif cmd.startswith("/fund") or cmd.startswith("/fundamental"):
                    sym = cmd_args[0] if cmd_args else "BBCA"
                    handle_fund_cmd(sender_chat_id, sym)
                elif cmd in ["/kalender", "kalender", "/calendar", "calendar", "/dividen", "dividen"]:
                    handle_kalender_cmd(sender_chat_id)
                elif cmd in ["/scan", "scan"]:
                    handle_scan_cmd(sender_chat_id)
                elif cmd.startswith("/chart"):
                    sym = cmd_args[0] if cmd_args else "BBCA"
                    handle_chart_cmd(sender_chat_id, sym)
                elif cmd.startswith("/plan"):
                    sym = cmd_args[0] if cmd_args else "BBCA"
                    handle_plan_cmd(sender_chat_id, sym)
                elif cmd.startswith("/price"):
                    sym = cmd_args[0] if cmd_args else "BBCA"
                    handle_price_cmd(sender_chat_id, sym)
                elif cmd in ["/akumulasi", "akumulasi", "/bandarhunter", "bandarhunter"]:
                    handle_akumulasi_cmd(sender_chat_id)
                elif cmd in ["/sektor", "sektor", "/heatmap", "heatmap", "/sector", "sector"]:
                    handle_sektor_cmd(sender_chat_id)
                elif cmd in ["/breakout", "breakout", "/spike", "spike"]:
                    handle_breakout_cmd(sender_chat_id)
                elif cmd.startswith("/flow") or cmd.startswith("/bandar"):
                    if cmd_args:
                        handle_bandarmology_cmd(sender_chat_id, cmd_args[0])
                    elif cmd.startswith("/bandar"):
                        # /bandar tanpa argumen = screener akumulasi bandar
                        handle_akumulasi_cmd(sender_chat_id)
                    else:
                        handle_bandarmology_cmd(sender_chat_id, "BBCA")
                elif cmd.startswith("/calc"):
                    handle_calc_cmd(sender_chat_id, cmd_args)
                elif cmd.startswith("/alert") and not cmd.startswith("/alerts"):
                    handle_alert_cmd(sender_chat_id, cmd_args)
                elif cmd in ["/alerts", "alerts"]:
                    handle_alerts_list_cmd(sender_chat_id)
                elif cmd.startswith("/delalert"):
                    handle_delalert_cmd(sender_chat_id, cmd_args)
                elif cmd.startswith("/watch") and not cmd.startswith("/watchlist"):
                    sym = cmd_args[0] if cmd_args else ""
                    handle_watch_cmd(sender_chat_id, sym)
                elif cmd.startswith("/unwatch"):
                    sym = cmd_args[0] if cmd_args else ""
                    handle_unwatch_cmd(sender_chat_id, sym)
                elif cmd in ["/watchlist", "/mywatch", "watchlist", "mywatch"]:
                    handle_watchlist_cmd(sender_chat_id)
                elif cmd in ["/update", "update"]:
                    handle_scan_cmd(sender_chat_id, header_prefix="🔔 *UPDATE MANUAL PASAR SAHAM IDX*")
                elif cmd in ["/portfolio", "portfolio"]:
                    handle_portfolio_cmd(sender_chat_id)
                elif cmd.startswith("/news"):
                    sym = cmd_args[0] if cmd_args else ""
                    handle_news_cmd(sender_chat_id, sym)
                elif cmd in ["/topmovers", "topmovers", "/movers", "movers"]:
                    handle_topmovers_cmd(sender_chat_id)
                elif cmd in ["/topgain", "/topgainers", "topgain", "gainers"]:
                    handle_topgain_cmd(sender_chat_id)
                elif cmd in ["/toploss", "/toplosers", "toploss", "losers"]:
                    handle_toploss_cmd(sender_chat_id)
                elif cmd in ["/ara", "ara", "/arahunter", "arahunter"]:
                    handle_ara_cmd(sender_chat_id)
                elif cmd in ["/bsjp", "bsjp"]:
                    handle_bsjp_cmd(sender_chat_id)
                elif cmd in ["/crypto", "crypto", "/btc", "btc"]:
                    handle_crypto_cmd(sender_chat_id)
                elif cmd in ["/forex", "forex", "/commodity", "commodity", "/emas", "emas", "/gold", "gold", "/xau", "xau"]:
                    handle_forex_cmd(sender_chat_id)
                elif cmd.startswith("/buy"):
                    handle_buy_cmd(sender_chat_id, cmd_args)
                elif cmd.startswith("/sell"):
                    handle_sell_cmd(sender_chat_id, cmd_args)
                else:
                    send_reply(sender_chat_id, f"Perintah `{text}` tidak dikenali. Ketik `/help` untuk melihat panduan menu.")
                    
        except KeyboardInterrupt:
            print("\n🛑 Bot listener dihentikan.")
            break
        except Exception as e:
            print(f"⚠️ Error loop: {e}")
            time.sleep(3)

if __name__ == "__main__":
    start_interactive_listener()
