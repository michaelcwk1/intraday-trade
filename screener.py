"""
Modul Screener Saham Indonesia (IDX / BEI)
Memindai puluhan hingga ratusan saham likuid secara paralel untuk mendeteksi momentum dan lonjakan volume.
"""
import json
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any, Optional
from tabulate import tabulate

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


from config import DEFAULT_WATCHLIST, format_idr
from data_provider import get_stock_data, get_clean_symbol, normalize_ticker
from strategy import analyze_ticker_momentum
from telegram_notifier import notify_buy_signal

SCAN_RESULTS_FILE = Path(__file__).resolve().parent / "scan_results.json"

def scan_single_ticker(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Memindai satu emiten saham IDX dan mengevaluasi indikator momentum.
    """
    symbol = get_clean_symbol(ticker)
    try:
        df = get_stock_data(ticker, period="3mo", interval="1d")
        if df.empty or len(df) < 20:
            return None
            
        analysis = analyze_ticker_momentum(df)
        analysis['symbol'] = symbol
        analysis['ticker'] = normalize_ticker(ticker)
        return analysis
    except Exception as e:
        return None

def run_screener(
    watchlist: Optional[List[str]] = None,
    max_workers: int = 6,
    send_telegram: bool = True,
    show_all: bool = False
) -> List[Dict[str, Any]]:
    """
    Menjalankan pemindaian saham secara multi-threaded.
    
    Args:
        watchlist: Daftar ticker (default menggunakan DEFAULT_WATCHLIST dari config)
        max_workers: Jumlah thread paralel
        send_telegram: Kirim notifikasi jika sinyal BUY ditemukan
        show_all: Jika True, tampilkan seluruh saham yang discan, bukan hanya yang bersinyal
    """
    if watchlist is None:
        watchlist = DEFAULT_WATCHLIST

    print(f"\n🔍 [SCREENER] Memulai pemindaian {len(watchlist)} saham IDX...")
    start_time = time.time()
    
    results: List[Dict[str, Any]] = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {executor.submit(scan_single_ticker, ticker): ticker for ticker in watchlist}
        
        for future in as_completed(future_to_ticker):
            res = future.result()
            if res:
                results.append(res)

    elapsed = time.time() - start_time
    print(f"⏱️ Selesai dalam {elapsed:.2f} detik. Total saham diproses: {len(results)}\n")

    # Urutkan berdasarkan RVol tertinggi (lonjakan volume terbesar)
    results.sort(key=lambda x: (x.get('has_signal', False), x.get('rvol', 0)), reverse=True)

    # Simpan hasil scan ke file JSON
    try:
        with open(SCAN_RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": time.time(),
                "total_scanned": len(results),
                "data": results
            }, f, indent=2)
    except Exception as e:
        print(f"⚠️ Gagal menyimpan scan_results.json: {e}")

    # Pisahkan yang memiliki sinyal beli vs netral
    buy_signals = [r for r in results if r.get('has_signal', False)]
    
    # Tampilkan Tabel Hasil
    display_list = results if show_all else (buy_signals if buy_signals else results[:15])
    
    table_data = []
    for item in display_list:
        turnover_str = f"Rp {item['turnover'] / 1e9:.2f} M" if item['turnover'] < 1e12 else f"Rp {item['turnover'] / 1e12:.2f} T"
        status_badge = "🔥 STRONG BUY" if item['signal'] == 'STRONG BUY' else ("🟢 BUY" if item['signal'] == 'BUY' else "⚪ NEUTRAL")
        
        table_data.append([
            item['symbol'],
            format_idr(item['close']),
            f"{item['change_pct']:+.2f}%",
            f"{item['rvol']:.2f}x",
            turnover_str,
            f"{item['rsi']:.1f}",
            status_badge,
            item['rrr'] if item.get('has_signal') else "-"
        ])

    headers = ["Saham", "Harga", "Chg %", "RVol", "Turnover", "RSI", "Sinyal", "R:R"]
    print(tabulate(table_data, headers=headers, tablefmt="rounded_grid"))
    
    if buy_signals:
        print(f"\n🎉 Ditemukan {len(buy_signals)} saham dengan sinyal MOMENTUM BUY!")
        for sig in buy_signals:
            print(f"  • {sig['symbol']} (Harga: {format_idr(sig['close'])}, RVol: {sig['rvol']}x, TP1: {format_idr(sig['tp1'])}, SL: {format_idr(sig['sl'])})")
            if send_telegram:
                notify_buy_signal(sig, sig['symbol'])
    else:
        print("\nℹ️ Tidak ada saham yang memenuhi seluruh kriteria volume spike & momentum ekstrem saat ini.")
        print("💡 Menampilkan saham dengan aktivitas volume & likuiditas tertinggi di atas.")

    return results

if __name__ == "__main__":
    run_screener(show_all=False)
