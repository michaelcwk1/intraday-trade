"""
Aplikasi Utama: Bot Trading Saham Indonesia (IDX / BEI)
Mengintegrasikan Screener Momentum & Volume Spike, Backtesting, Paper Trading, dan Notifikasi Telegram.
"""
import sys
import time
import argparse
from typing import Optional

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import (
    DEFAULT_WATCHLIST, INITIAL_BALANCE, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    ENABLE_TELEGRAM, format_idr
)
from screener import run_screener
from backtester import run_backtest_single, print_backtest_report
from paper_trader import (
    display_portfolio_summary, buy_stock, sell_stock,
    update_and_check_portfolio, reset_portfolio
)
from telegram_notifier import test_telegram_connection, send_telegram_message
from news_provider import get_stock_news, get_market_news, format_news_markdown
from top_movers import format_top_movers_summary
from special_screeners import format_ara_message, format_bsjp_message
from crypto_forex import format_crypto_message, format_forex_message
from technical_analysis import format_ta_message
from swing_screener import format_bow_message
from fundamental_provider import format_fundamental_message, format_calendar_message
from ai_analyzer import get_ai_market_insight
from bandar_screener import format_bandar_screener_message
from sector_heatmap import format_sector_heatmap_message
from breakout_scanner import format_breakout_message

BANNER = r"""
╔═══════════════════════════════════════════════════════════════╗
║         🤖 BOT TRADING SAHAM INDONESIA (IDX / BEI)           ║
║       Strategi: Momentum & Volume Spike Accumulation          ║
║      Fitur: Screener + Backtest + Paper Trading + Telegram    ║
╚═══════════════════════════════════════════════════════════════╝
"""

def print_menu():
    print(BANNER)
    print("Silakan pilih menu:")
    print("  [1] 🔍 Jalankan Screener Saham Momentum & Volume Spike (LQ45 / Populer)")
    print("  [2] 📊 Backtest Strategi pada Saham Historis (Uji Win Rate & PnL)")
    print("  [3] 💼 Lihat Portofolio Paper Trading (Virtual Account)")
    print("  [4] 🛒 Beli Saham (Paper Trading Order)")
    print("  [5] 💰 Jual Saham (Paper Trading Order)")
    print("  [6] 🔄 Cek & Update TP / SL / Trailing Stop Posisi Terbuka")
    print("  [7] 🤖 Jalankan Auto-Monitoring Loop (Pemantau Otomatis Berkala)")
    print("  [8] 📱 Cek Status & Tes Notifikasi Telegram")
    print("  [9] ⚙️  Reset Saldo Portofolio Paper Trading")
    print("  [10] 🔥 Top Movers IDX (Top Gainers, Losers & Most Active)")
    print("  [11] 📰 Berita Pasar Modal & Saham Terkini (RSS)")
    print("  [12] 🎯 Screener Saham ARA Hunter (Auto Rejection Atas)")
    print("  [13] 🌅 Screener Saham BSJP (Beli Sore Jual Pagi)")
    print("  [14] 🪙 Pasar Crypto Teratas (BTC, ETH, SOL, BNB, XRP, DOGE)")
    print("  [15] 🌍 Pasar Forex & Logam Mulia Dunia (Gold/XAU, Silver, Oil)")
    print("  [16] 🤖 AI Market Insight (Sintesis Teknikal, Bandar & Berita)")
    print("  [17] 🧭 Meteran Konsensus Teknikal TradingView Style")
    print("  [18] 🎣 Screener Buy on Weakness (BoW) & Swing Rebound")
    print("  [19] 🏢 Profil Fundamental, PER, PBV & Dividen")
    print("  [20] 📅 Kalender Aksi Korporasi & Dividen IDX")
    print("  [21] 🌐 Screener Akumulasi Smart Money & Bandar Hunter")
    print("  [22] 🗺️ Radar Rotasi Sektor & Heatmap IDX")
    print("  [23] 🚨 Radar Lonjakan Volume Breakout (Auto Volume Spike)")
    print("  [0] ❌ Keluar")
    print("─" * 63)

def handle_screener():
    print("\n🔍 PILIHAN SCREENER:")
    print("1. Tampilkan hanya saham yang lolos Sinyal BUY (RVol > 1.5x, Momentum > 1.5%)")
    print("2. Tampilkan semua saham yang dipindai (diurutkan volume tertinggi)")
    sub_choice = input("Pilih [1/2] (Default 1): ").strip() or "1"
    show_all = (sub_choice == "2")
    run_screener(show_all=show_all)

def handle_backtest():
    print("\n📊 BACKTEST STRATEGI:")
    ticker = input("Masukkan kode saham IDX (contoh: BBCA, BBRI, BRIS, MEDC): ").strip().upper()
    if not ticker:
        print("⚠️ Kode saham tidak boleh kosong.")
        return
        
    period_input = input("Pilih periode ['3mo', '6mo', '1y', '2y'] (Default '1y'): ").strip() or "1y"
    print(f"\n⏳ Menjalankan backtest untuk {ticker} periode {period_input}...")
    res = run_backtest_single(ticker, period=period_input)
    print_backtest_report(res)

def handle_buy_order():
    print("\n🛒 ORDER BELI (PAPER TRADING):")
    ticker = input("Kode saham yang ingin dibeli (contoh: BBCA, ASII): ").strip().upper()
    if not ticker:
        print("⚠️ Kode saham tidak boleh kosong.")
        return
        
    try:
        lots_str = input("Jumlah lot (1 lot = 100 lembar): ").strip()
        lots = int(lots_str)
    except ValueError:
        print("⚠️ Jumlah lot harus berupa angka bulat.")
        return
        
    res = buy_stock(ticker, lots=lots)
    if res["success"]:
        print(f"\n✅ {res['message']}")
        print(f"💰 Sisa Saldo Kas: {format_idr(res['remaining_cash'])}")
        print(f"🎯 Target TP (+5%): {format_idr(res['tp_price'])} | 🛑 Stop Loss (-3%): {format_idr(res['sl_price'])}")
    else:
        print(f"\n❌ Gagal: {res['message']}")

def handle_sell_order():
    print("\n💰 ORDER JUAL (PAPER TRADING):")
    ticker = input("Kode saham yang ingin dijual (contoh: BBCA): ").strip().upper()
    if not ticker:
        print("⚠️ Kode saham tidak boleh kosong.")
        return
        
    lots_input = input("Jumlah lot yang dijual (kosongkan jika ingin jual semua): ").strip()
    lots = int(lots_input) if lots_input.isdigit() else None
    
    res = sell_stock(ticker, lots=lots)
    if res["success"]:
        print(f"\n✅ {res['message']}")
        print(f"💰 Sisa Saldo Kas: {format_idr(res['remaining_cash'])}")
    else:
        print(f"\n❌ Gagal: {res['message']}")

def handle_auto_monitor(interval_seconds: int = 60):
    print("\n🤖 AUTO-MONITORING LOOP DIAKTIFKAN")
    print(f"Interval pembaruan: setiap {interval_seconds} detik. Tekan Ctrl+C untuk menghentikan.\n")
    try:
        cycle = 1
        while True:
            print(f"[{time.strftime('%H:%M:%S')}] Siklus #{cycle} - Memeriksa harga pasar & posisi portofolio...")
            res = update_and_check_portfolio()
            if res.get("closed_positions"):
                for cp in res["closed_positions"]:
                    print(f"  🚨 AUTO-TRIGGER: {cp['symbol']} {cp['reason']} di harga {format_idr(cp['price'])} (PnL: {format_idr(cp['pnl'])})")
            else:
                print("  ✓ Tidak ada trigger TP/SL yang tersentuh. Portofolio aman.")
                
            cycle += 1
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\n🛑 Auto-monitoring dihentikan oleh pengguna.")

def handle_telegram_menu():
    import config
    from pathlib import Path
    
    while True:
        is_active = bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)
        print("\n" + "═"*50)
        print("📱 PENGATURAN & KONEKSI TELEGRAM BOT")
        print("═"*50)
        if is_active:
            masked_token = f"{config.TELEGRAM_BOT_TOKEN[:6]}...{config.TELEGRAM_BOT_TOKEN[-4:]}" if len(config.TELEGRAM_BOT_TOKEN) > 10 else "***"
            print("✓ Status   : 🟢 AKTIF")
            print(f"✓ Bot Token: {masked_token}")
            print(f"✓ Chat ID  : {config.TELEGRAM_CHAT_ID}")
        else:
            print("✓ Status   : 🔴 BELUM TERHUBUNG (NON-AKTIF)")
        print("─"*50)
        print("  [1] 🔑 Masukkan / Ubah Bot Token & Chat ID")
        print("  [2] 🧪 Kirim Pesan Tes ke Telegram")
        print("  [3] 🤖 Jalankan Bot Interaktif (Balas Chat /start, /scan, /portfolio, /buy)")
        print("  [4] 📖 Panduan Lengkap Cara Buat Bot Telegram")
        print("  [0] ⬅️  Kembali ke Menu Utama")
        print("─"*50)
        
        sub = input("Pilih menu Telegram [0-4]: ").strip()
        
        if sub == "1":
            print("\n🔑 PENGATURAN KREDENSIAL TELEGRAM:")
            token_in = input("Masukkan TELEGRAM_BOT_TOKEN (dari @BotFather): ").strip()
            chat_id_in = input("Masukkan TELEGRAM_CHAT_ID (dari @userinfobot): ").strip()
            
            if token_in and chat_id_in:
                # Simpan ke file .env
                env_file = Path(__file__).resolve().parent / ".env"
                env_content = f"TELEGRAM_BOT_TOKEN={token_in}\nTELEGRAM_CHAT_ID={chat_id_in}\n"
                with open(env_file, "w", encoding="utf-8") as f:
                    f.write(env_content)
                
                # Perbarui runtime config
                config.TELEGRAM_BOT_TOKEN = token_in
                config.TELEGRAM_CHAT_ID = chat_id_in
                config.ENABLE_TELEGRAM = True
                
                print("\n✅ Kredensial berhasil disimpan ke file .env!")
                
                # Tawarkan tes kirim pesan
                test_now = input("Kirim pesan tes sekarang untuk memastikan bot terhubung? (y/n): ").strip().lower()
                if test_now == 'y':
                    print("Mengirim pesan tes...")
                    res = test_telegram_connection()
                    if res["success"]:
                        print(f"🎉 SUKSES: {res['message']}")
                    else:
                        print(f"❌ PERINGATAN: {res['message']}")
            else:
                print("⚠️ Token atau Chat ID tidak boleh kosong.")
                
        elif sub == "2":
            if not is_active:
                print("⚠️ Bot belum dikonfigurasi. Silakan pilih menu [1] terlebih dahulu.")
            else:
                print("Mengirim pesan tes...")
                res = test_telegram_connection()
                if res["success"]:
                    print(f"🎉 SUKSES: {res['message']}")
                else:
                    print(f"❌ PERINGATAN: {res['message']}")
                    
        elif sub == "3":
            if not is_active:
                print("⚠️ Bot belum dikonfigurasi. Silakan masukkan token di menu [1] terlebih dahulu.")
            else:
                from bot_telegram import start_interactive_listener
                start_interactive_listener()
                
        elif sub == "4":
            print("\n📖 PANDUAN CARA MENGHUBUNGKAN BOT TELEGRAM:")
            print("1. Buka aplikasi Telegram dan cari bot: @BotFather (yang memiliki centang biru resmi).")
            print("2. Kirim pesan: /newbot")
            print("3. Ikuti instruksi BotFather:")
            print("   • Masukkan nama bot (contoh: Bot Saham IDX)")
            print("   • Masukkan username unik yang berakhiran 'bot' (contoh: saham_idx_alert_bot)")
            print("4. BotFather akan memberikan BOT TOKEN (contoh: 123456789:ABCdef-xyz123). Salin token ini.")
            print("5. Buka bot Anda tersebut di Telegram dan klik tombol 'START' (Wajib dilakukan agar bot boleh mengirim pesan ke Anda).")
            print("6. Untuk mengetahui CHAT ID Anda, cari bot: @userinfobot di Telegram, lalu klik 'START'.")
            print("   • Lihat baris 'Id:' (contoh: 987654321). Salin angka ID tersebut.")
            print("7. Kembali ke aplikasi ini, pilih menu [1], lalu tempel Token dan Chat ID Anda.")
            
        elif sub == "0":
            break
        else:
            print("⚠️ Pilihan tidak valid.")
        
        input("\n[Tekan Enter untuk melanjutkan]")



def interactive_loop():
    while True:
        print_menu()
        choice = input("Masukkan pilihan [0-9]: ").strip()
        
        if choice == "1":
            handle_screener()
        elif choice == "2":
            handle_backtest()
        elif choice == "3":
            display_portfolio_summary()
        elif choice == "4":
            handle_buy_order()
        elif choice == "5":
            handle_sell_order()
        elif choice == "6":
            print("\n🔄 Memeriksa kondisi pasar terkini untuk seluruh posisi...")
            res = update_and_check_portfolio()
            if res.get("closed_positions"):
                print(f"🚨 {len(res['closed_positions'])} posisi otomatis ditutup sesuai TP/SL/Trailing Stop!")
            else:
                print("✓ Pemeriksaan selesai. Tidak ada posisi yang memicu batas keluar saat ini.")
            display_portfolio_summary()
        elif choice == "7":
            handle_auto_monitor(interval_seconds=60)
        elif choice == "8":
            handle_telegram_menu()
        elif choice == "9":
            confirm = input(f"Yakin ingin mereset portofolio kembali ke modal awal {format_idr(INITIAL_BALANCE)}? (y/n): ").strip().lower()
            if confirm == 'y':
                reset_portfolio()
        elif choice == "10":
            print("\n⏳ Mengambil data Top Movers IDX hari ini...")
            print(format_top_movers_summary(limit=5))
        elif choice == "11":
            target = input("Masukkan kode saham untuk berita spesifik (atau kosongkan untuk berita pasar IHSG): ").strip().upper()
            if target:
                print(f"\n⏳ Mengambil berita terkini saham {target}...")
                news_list = get_stock_news(target, limit=5)
                print(format_news_markdown(news_list, f"📰 BERITA SAHAM {target}"))
            else:
                print("\n⏳ Mengambil berita pasar modal IHSG terkini...")
                news_list = get_market_news(limit=5)
                print(format_news_markdown(news_list, "📰 BERITA PASAR MODAL & IHSG"))
        elif choice == "12":
            print("\n⏳ Menjalankan Screener ARA Hunter...")
            print(format_ara_message(limit=8))
        elif choice == "13":
            print("\n⏳ Menjalankan Screener BSJP (Beli Sore Jual Pagi)...")
            print(format_bsjp_message(limit=8))
        elif choice == "14":
            print("\n⏳ Mengambil data pasar Cryptocurrency teratas...")
            print(format_crypto_message())
        elif choice == "15":
            print("\n⏳ Mengambil data pasar Forex & Komoditas dunia...")
            print(format_forex_message())
        elif choice == "16":
            target = input("Masukkan kode saham / crypto / emas (contoh: BBCA, BTC, XAU): ").strip().upper() or "BBCA"
            print(f"\n⏳ Menganalisis AI Market Insight untuk {target}...")
            print(get_ai_market_insight(target))
        elif choice == "17":
            target = input("Masukkan kode saham / aset (contoh: BBCA, BTC): ").strip().upper() or "BBCA"
            print(f"\n⏳ Menghitung konsensus teknikal untuk {target}...")
            print(format_ta_message(target))
        elif choice == "18":
            print("\n⏳ Menjalankan Screener Buy on Weakness (BoW)...")
            print(format_bow_message())
        elif choice == "19":
            target = input("Masukkan kode saham (contoh: BBCA, BBRI): ").strip().upper() or "BBCA"
            print(f"\n⏳ Mengambil profil fundamental {target}...")
            print(format_fundamental_message(target))
        elif choice == "20":
            print("\n⏳ Mengambil kalender aksi korporasi & dividen...")
            print(format_calendar_message())
        elif choice == "21":
            print("\n⏳ Menjalankan Screener Akumulasi Smart Money...")
            msg, _ = format_bandar_screener_message()
            print(msg)
        elif choice == "22":
            print("\n⏳ Menghitung Radar Rotasi Sektor & Heatmap IDX...")
            msg, _ = format_sector_heatmap_message()
            print(msg)
        elif choice == "23":
            print("\n⏳ Memindai Sinyal Lonjakan Volume Breakout...")
            msg, _ = format_breakout_message()
            print(msg)
        elif choice == "0":
            print("\n👋 Terima kasih telah menggunakan Bot Trading Saham Indonesia. Salam Cuan!\n")
            break
        else:
            print("⚠️ Pilihan tidak valid, silakan ulangi.")
            
        input("\n[Tekan Enter untuk kembali ke Menu Utama]")

def main():
    parser = argparse.ArgumentParser(description="Bot Trading Saham Indonesia (IDX / BEI)")
    parser.add_argument("--scan", action="store_true", help="Jalankan screener langsung")
    parser.add_argument("--ara", action="store_true", help="Jalankan Screener ARA Hunter (Auto Rejection Atas)")
    parser.add_argument("--bsjp", action="store_true", help="Jalankan Screener BSJP (Beli Sore Jual Pagi)")
    parser.add_argument("--crypto", action="store_true", help="Tampilkan harga pasar cryptocurrency teratas")
    parser.add_argument("--forex", action="store_true", help="Tampilkan harga pasar forex dan komoditas dunia (Gold/Oil)")
    parser.add_argument("--ai", type=str, help="Analisis AI Market Insight (contoh: --ai BBCA)")
    parser.add_argument("--ta", type=str, help="Konsensus teknikal meter (contoh: --ta BBCA)")
    parser.add_argument("--bow", action="store_true", help="Jalankan Screener Buy on Weakness")
    parser.add_argument("--fund", type=str, help="Profil fundamental dan dividen (contoh: --fund BBCA)")
    parser.add_argument("--kalender", action="store_true", help="Tampilkan kalender dividen dan agenda emiten")
    parser.add_argument("--topmovers", action="store_true", help="Tampilkan Top Gainers, Losers, dan Most Active")
    parser.add_argument("--akumulasi", action="store_true", help="Jalankan Screener Akumulasi Smart Money / Bandar Hunter")
    parser.add_argument("--sektor", action="store_true", help="Tampilkan Radar Rotasi Sektor & Heatmap IDX")
    parser.add_argument("--breakout", action="store_true", help="Tampilkan Radar Lonjakan Volume Breakout")
    parser.add_argument("--web", action="store_true", help="Jalankan Web Dashboard Trading Terminal (FastAPI)")
    parser.add_argument("--news", type=str, nargs="?", const="", help="Tampilkan berita saham atau IHSG (contoh: --news BBCA atau --news)")
    parser.add_argument("--backtest", type=str, help="Jalankan backtest untuk simbol tertentu (contoh: --backtest BBCA)")
    parser.add_argument("--portfolio", action="store_true", help="Tampilkan ringkasan portofolio paper trading")
    parser.add_argument("--monitor", action="store_true", help="Jalankan auto-monitoring loop")
    parser.add_argument("--interval", type=int, default=60, help="Interval loop auto-monitoring dalam detik")
    
    args = parser.parse_args()
    
    if args.scan:
        run_screener(show_all=False)
    elif args.ara:
        print(format_ara_message(limit=8))
    elif args.bsjp:
        print(format_bsjp_message(limit=8))
    elif args.crypto:
        print(format_crypto_message())
    elif args.forex:
        print(format_forex_message())
    elif args.ai:
        print(get_ai_market_insight(args.ai))
    elif args.ta:
        print(format_ta_message(args.ta))
    elif args.bow:
        print(format_bow_message())
    elif args.fund:
        print(format_fundamental_message(args.fund))
    elif args.kalender:
        print(format_calendar_message())
    elif args.akumulasi:
        msg, _ = format_bandar_screener_message()
        print(msg)
    elif args.sektor:
        msg, _ = format_sector_heatmap_message()
        print(msg)
    elif args.breakout:
        msg, _ = format_breakout_message()
        print(msg)
    elif args.web:
        import uvicorn
        print('\n🚀 Memulai Web Dashboard IDX Smart Trading Terminal...')
        print('🌐 Buka browser di: http://localhost:8000\n')
        uvicorn.run('web_app.main:app', host='0.0.0.0', port=8000, reload=True)
    elif args.topmovers:
        print(format_top_movers_summary(limit=5))
    elif args.news is not None:
        if args.news:
            news_list = get_stock_news(args.news, limit=5)
            print(format_news_markdown(news_list, f"📰 BERITA SAHAM {args.news.upper()}"))
        else:
            news_list = get_market_news(limit=5)
            print(format_news_markdown(news_list, "📰 BERITA PASAR MODAL & IHSG"))
    elif args.backtest:
        res = run_backtest_single(args.backtest)
        print_backtest_report(res)
    elif args.portfolio:
        display_portfolio_summary()
    elif args.monitor:
        handle_auto_monitor(args.interval)
    else:
        interactive_loop()

if __name__ == "__main__":
    main()
