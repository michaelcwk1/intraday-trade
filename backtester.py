"""
Modul Backtesting Strategi Saham Indonesia (IDX / BEI)
Menguji performa strategi Momentum & Volume Spike pada data historis dengan simulasi lot dan fee bursa yang realistis.
"""
import sys
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from tabulate import tabulate

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import (
    LOT_SIZE, BUY_FEE_PCT, SELL_FEE_PCT, INITIAL_BALANCE,
    DEFAULT_TP2_PCT, DEFAULT_SL_PCT, TRAILING_STOP_PCT,
    format_idr
)
from data_provider import get_stock_data, get_clean_symbol, normalize_ticker
from strategy import calculate_indicators

def run_backtest_single(
    ticker: str,
    period: str = "1y",
    initial_cash: float = 50_000_000,
    allocation_pct: float = 0.50, # 50% modal per trade
    tp_pct: float = DEFAULT_TP2_PCT, # +5%
    sl_pct: float = DEFAULT_SL_PCT,  # -3%
    trailing_pct: float = TRAILING_STOP_PCT, # 2%
    max_holding_days: int = 15
) -> Dict[str, Any]:
    """
    Menjalankan backtest pada satu saham IDX.
    """
    symbol = get_clean_symbol(ticker)
    df = get_stock_data(ticker, period=period, interval="1d")
    
    if df.empty or len(df) < 30:
        return {"symbol": symbol, "valid": False, "error": "Data historis tidak mencukupi"}
        
    df = calculate_indicators(df)
    
    cash = initial_cash
    equity_curve = [initial_cash]
    trades: List[Dict[str, Any]] = []
    
    in_position = False
    entry_price = 0.0
    entry_date = None
    lots = 0
    highest_price_since_entry = 0.0
    holding_days = 0
    
    # Looping bar per bar untuk simulasi realistis tanpa lookahead bias
    for i in range(25, len(df)):
        row = df.iloc[i]
        date = df.index[i]
        close = float(row['Close'])
        high = float(row['High'])
        low = float(row['Low'])
        
        if in_position:
            holding_days += 1
            highest_price_since_entry = max(highest_price_since_entry, high)
            
            # Hitung target harga
            target_tp = entry_price * (1 + tp_pct / 100)
            target_sl = entry_price * (1 - sl_pct / 100)
            target_trailing = highest_price_since_entry * (1 - trailing_pct / 100)
            
            exit_reason = None
            exit_price = close
            
            # Cek Stop Loss
            if low <= target_sl:
                exit_reason = "STOP LOSS"
                exit_price = min(close, target_sl)
            # Cek Take Profit
            elif high >= target_tp:
                exit_reason = "TAKE PROFIT"
                exit_price = max(close, target_tp)
            # Cek Trailing Stop (hanya aktif jika sudah pernah floating profit > 2%)
            elif highest_price_since_entry >= entry_price * 1.02 and low <= target_trailing:
                exit_reason = "TRAILING STOP"
                exit_price = target_trailing
            # Cek batas waktu holding (time-based exit)
            elif holding_days >= max_holding_days:
                exit_reason = "TIME EXPIRED"
                exit_price = close
                
            if exit_reason:
                # Eksekusi Jual
                gross_proceeds = lots * LOT_SIZE * exit_price
                sell_fee = gross_proceeds * SELL_FEE_PCT
                net_proceeds = gross_proceeds - sell_fee
                cash += net_proceeds
                
                initial_cost = trades[-1]['total_cost']
                net_pnl = net_proceeds - initial_cost
                pnl_pct = (net_pnl / initial_cost) * 100
                
                trades[-1].update({
                    "exit_date": str(date.date()),
                    "exit_price": round(exit_price),
                    "holding_days": holding_days,
                    "exit_reason": exit_reason,
                    "net_pnl": round(net_pnl),
                    "pnl_pct": round(pnl_pct, 2),
                    "status": "CLOSED"
                })
                
                in_position = False
                lots = 0
                holding_days = 0
                
        else:
            # Evaluasi Sinyal Beli (Momentum & Volume Spike)
            rvol = float(row['RVol'])
            change_pct = float(row['Change_Pct'])
            turnover = float(row['Turnover'])
            rsi = float(row['RSI'])
            ma20 = float(row['MA20'])
            
            from config import RVOL_THRESHOLD, MIN_PRICE_CHANGE_PCT, MIN_TURNOVER_IDR
            is_volume_spike = rvol >= RVOL_THRESHOLD
            is_price_momentum = change_pct >= MIN_PRICE_CHANGE_PCT
            is_liquid = turnover >= MIN_TURNOVER_IDR
            is_above_ma20 = close > ma20
            is_rsi_safe = rsi < 80.0
            
            if is_volume_spike and is_price_momentum and is_liquid and is_above_ma20 and is_rsi_safe:
                # Alokasikan modal
                capital_to_use = cash * allocation_pct
                lot_cost = close * LOT_SIZE
                possible_lots = int(capital_to_use // (lot_cost * (1 + BUY_FEE_PCT)))
                
                if possible_lots > 0:
                    gross_cost = possible_lots * LOT_SIZE * close
                    buy_fee = gross_cost * BUY_FEE_PCT
                    total_buy_cost = gross_cost + buy_fee
                    
                    if cash >= total_buy_cost:
                        cash -= total_buy_cost
                        in_position = True
                        entry_price = close
                        entry_date = date
                        lots = possible_lots
                        highest_price_since_entry = high
                        holding_days = 0
                        
                        trades.append({
                            "symbol": symbol,
                            "entry_date": str(date.date()),
                            "entry_price": round(entry_price),
                            "lots": lots,
                            "shares": lots * LOT_SIZE,
                            "total_cost": round(total_buy_cost),
                            "status": "OPEN"
                        })
                        
        current_equity = cash + (lots * LOT_SIZE * close if in_position else 0)
        equity_curve.append(current_equity)

    # Jika posisi masih terbuka di akhir periode
    if in_position and trades:
        last_close = float(df['Close'].iloc[-1])
        gross_val = lots * LOT_SIZE * last_close
        sell_fee = gross_val * SELL_FEE_PCT
        net_val = gross_val - sell_fee
        initial_cost = trades[-1]['total_cost']
        net_pnl = net_val - initial_cost
        pnl_pct = (net_pnl / initial_cost) * 100
        
        trades[-1].update({
            "exit_date": str(df.index[-1].date()),
            "exit_price": round(last_close),
            "holding_days": holding_days,
            "exit_reason": "OPEN AT END",
            "net_pnl": round(net_pnl),
            "pnl_pct": round(pnl_pct, 2),
            "status": "CLOSED"
        })
        cash += net_val

    # Analisis Statistik Performa
    closed_trades = [t for t in trades if "net_pnl" in t]
    total_trades = len(closed_trades)
    winning_trades = [t for t in closed_trades if t['net_pnl'] > 0]
    losing_trades = [t for t in closed_trades if t['net_pnl'] <= 0]
    
    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0.0
    total_net_pnl = sum(t['net_pnl'] for t in closed_trades)
    total_return_pct = ((cash - initial_cash) / initial_cash) * 100
    
    gross_profits = sum(t['net_pnl'] for t in winning_trades)
    gross_losses = abs(sum(t['net_pnl'] for t in losing_trades))
    profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else (99.0 if gross_profits > 0 else 0.0)
    
    # Max Drawdown
    equity_arr = np.array(equity_curve)
    peak_arr = np.maximum.accumulate(equity_arr)
    drawdowns = (equity_arr - peak_arr) / peak_arr * 100
    max_drawdown = abs(drawdowns.min()) if len(drawdowns) > 0 else 0.0
    
    return {
        "symbol": symbol,
        "valid": True,
        "period": period,
        "initial_cash": initial_cash,
        "final_cash": round(cash),
        "total_net_pnl": round(total_net_pnl),
        "total_return_pct": round(total_return_pct, 2),
        "total_trades": total_trades,
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2),
        "max_drawdown": round(max_drawdown, 2),
        "trades": closed_trades
    }

def print_backtest_report(res: Dict[str, Any]):
    """
    Menampilkan laporan hasil backtest dalam bentuk tabel yang informatif.
    """
    if not res.get("valid"):
        print(f"❌ Backtest gagal: {res.get('error', 'Error tidak diketahui')}")
        return

    print("\n" + "═"*60)
    print(f"📊 LAPORAN HASIL BACKTEST STRATEGI: {res['symbol']} (IDX)")
    print("═"*60)
    
    metrics = [
        ["Modal Awal", format_idr(res['initial_cash'])],
        ["Nilai Akhir Modal", format_idr(res['final_cash'])],
        ["Total Net Profit (PnL)", f"{format_idr(res['total_net_pnl'])} ({res['total_return_pct']:+.2f}%)"],
        ["Total Transaksi (Trades)", res['total_trades']],
        ["Transaksi Menang (Win)", f"{res['winning_trades']} trades"],
        ["Transaksi Kalah (Loss)", f"{res['losing_trades']} trades"],
        ["Win Rate", f"{res['win_rate']:.2f}%"],
        ["Profit Factor", f"{res['profit_factor']:.2f}"],
        ["Maksimum Drawdown (Risk)", f"-{res['max_drawdown']:.2f}%"]
    ]
    
    print(tabulate(metrics, headers=["Metrik Evaluasi", "Hasil"], tablefmt="rounded_grid"))
    
    trades = res.get('trades', [])
    if trades:
        print("\n📜 RIWAYAT TRANSAKSI HISTORIS:")
        trade_rows = []
        for t in trades:
            pnl_badge = f"+{t['pnl_pct']:.2f}%" if t['pnl_pct'] >= 0 else f"{t['pnl_pct']:.2f}%"
            trade_rows.append([
                t['entry_date'],
                t['exit_date'],
                f"{t['lots']} Lot",
                format_idr(t['entry_price']),
                format_idr(t['exit_price']),
                format_idr(t['net_pnl']),
                pnl_badge,
                t['exit_reason']
            ])
            
        t_headers = ["Tgl Masuk", "Tgl Keluar", "Lot", "Beli", "Jual", "Net PnL", "% PnL", "Alasan Exit"]
        print(tabulate(trade_rows, headers=t_headers, tablefmt="simple"))
    else:
        print("\nℹ️ Tidak ada sinyal yang terpicu selama periode ini.")
    print("═"*60 + "\n")

if __name__ == "__main__":
    ticker_test = "BBCA" if len(sys.argv) < 2 else sys.argv[1]
    res = run_backtest_single(ticker_test, period="1y")
    print_backtest_report(res)
