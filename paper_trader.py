"""
Modul Paper Trading Saham Indonesia (IDX / BEI)
Simulasi portofolio virtual dengan saldo Rupiah, perhitungan lot resmi IDX (1 lot = 100 lembar),
biaya transaksi bursa, trailing stop otomatis, dan pencatatan riwayat transaksi.
"""
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from tabulate import tabulate

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import (
    LOT_SIZE, BUY_FEE_PCT, SELL_FEE_PCT, INITIAL_BALANCE,
    PORTFOLIO_FILE, DEFAULT_TP2_PCT, DEFAULT_SL_PCT, TRAILING_STOP_PCT,
    format_idr
)
from data_provider import get_current_price, get_clean_symbol, normalize_ticker
from telegram_notifier import notify_order_execution, send_telegram_message

def init_portfolio() -> Dict[str, Any]:
    """Inisialisasi struktur portofolio baru"""
    return {
        "initial_balance": INITIAL_BALANCE,
        "cash_balance": INITIAL_BALANCE,
        "positions": {},
        "trade_history": [],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def load_portfolio() -> Dict[str, Any]:
    """Memuat data portofolio dari file JSON"""
    if not PORTFOLIO_FILE.exists():
        portfolio = init_portfolio()
        save_portfolio(portfolio)
        return portfolio
    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        portfolio = init_portfolio()
        save_portfolio(portfolio)
        return portfolio

def save_portfolio(portfolio: Dict[str, Any]):
    """Menyimpan data portofolio ke file JSON"""
    try:
        with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
            json.dump(portfolio, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Gagal menyimpan portfolio: {e}")

def buy_stock(
    ticker: str,
    lots: int,
    price: Optional[float] = None,
    tp_pct: float = DEFAULT_TP2_PCT,
    sl_pct: float = DEFAULT_SL_PCT,
    trailing_pct: float = TRAILING_STOP_PCT
) -> Dict[str, Any]:
    """
    Membeli saham ke portofolio virtual (Paper Trading).
    
    Args:
        ticker: Kode saham (misal 'BBCA' atau 'BBCA.JK')
        lots: Jumlah lot yang ingin dibeli
        price: Harga beli per lembar (jika None, ambil harga pasar terkini)
        tp_pct: Target Take Profit dalam %
        sl_pct: Target Stop Loss dalam %
    """
    symbol = get_clean_symbol(ticker)
    
    if lots <= 0:
        return {"success": False, "message": "Jumlah lot harus lebih dari 0."}
        
    if price is None:
        price = get_current_price(ticker)
        if price is None or price <= 0:
            return {"success": False, "message": f"Gagal mengambil harga pasar terkini untuk {symbol}."}

    shares = lots * LOT_SIZE
    gross_cost = shares * price
    buy_fee = gross_cost * BUY_FEE_PCT
    total_cost = gross_cost + buy_fee

    portfolio = load_portfolio()
    cash = portfolio.get("cash_balance", 0.0)

    if cash < total_cost:
        return {
            "success": False,
            "message": f"Saldo tidak mencukupi. Butuh {format_idr(total_cost)}, saldo saat ini: {format_idr(cash)}."
        }

    # Potong saldo kas
    portfolio["cash_balance"] -= total_cost
    positions = portfolio.setdefault("positions", {})

    tp_price = round(price * (1 + tp_pct / 100))
    sl_price = round(price * (1 - sl_pct / 100))

    if symbol in positions:
        # Rata-rata harga beli (Average Down/Up)
        curr = positions[symbol]
        total_shares = curr["shares"] + shares
        total_prev_cost = curr["total_cost"]
        new_total_cost = total_prev_cost + total_cost
        avg_price = (curr["avg_price"] * curr["shares"] + price * shares) / total_shares
        
        positions[symbol] = {
            "symbol": symbol,
            "ticker": normalize_ticker(ticker),
            "lots": total_shares // LOT_SIZE,
            "shares": total_shares,
            "avg_price": round(avg_price, 2),
            "total_cost": round(new_total_cost, 2),
            "tp_price": tp_price,
            "sl_price": sl_price,
            "highest_price": max(curr.get("highest_price", price), price),
            "trailing_stop_pct": trailing_pct,
            "last_buy_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    else:
        positions[symbol] = {
            "symbol": symbol,
            "ticker": normalize_ticker(ticker),
            "lots": lots,
            "shares": shares,
            "avg_price": round(price, 2),
            "total_cost": round(total_cost, 2),
            "tp_price": tp_price,
            "sl_price": sl_price,
            "highest_price": price,
            "trailing_stop_pct": trailing_pct,
            "buy_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_buy_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    save_portfolio(portfolio)
    
    # Kirim notifikasi Telegram
    notify_order_execution("BUY", symbol, lots, price, total_cost)

    return {
        "success": True,
        "symbol": symbol,
        "lots": lots,
        "shares": shares,
        "price": price,
        "total_cost": total_cost,
        "remaining_cash": portfolio["cash_balance"],
        "tp_price": tp_price,
        "sl_price": sl_price,
        "message": f"Berhasil membeli {lots} lot {symbol} di harga {format_idr(price)}."
    }

def sell_stock(
    ticker: str,
    lots: Optional[int] = None,
    price: Optional[float] = None,
    reason: str = "MANUAL SELL"
) -> Dict[str, Any]:
    """
    Menjual saham dari portofolio virtual.
    Jika lots is None, jual seluruh posisi saham tersebut.
    """
    symbol = get_clean_symbol(ticker)
    portfolio = load_portfolio()
    positions = portfolio.get("positions", {})

    if symbol not in positions:
        return {"success": False, "message": f"Saham {symbol} tidak ditemukan di dalam portofolio."}

    pos = positions[symbol]
    available_lots = pos["lots"]

    if lots is None or lots >= available_lots:
        lots_to_sell = available_lots
    else:
        lots_to_sell = lots

    if lots_to_sell <= 0:
        return {"success": False, "message": "Jumlah lot jual tidak valid."}

    if price is None:
        price = get_current_price(ticker)
        if price is None or price <= 0:
            return {"success": False, "message": f"Gagal mengambil harga pasar terkini untuk {symbol}."}

    shares_to_sell = lots_to_sell * LOT_SIZE
    gross_revenue = shares_to_sell * price
    sell_fee = gross_revenue * SELL_FEE_PCT
    net_revenue = gross_revenue - sell_fee

    cost_proportion = (shares_to_sell / pos["shares"]) * pos["total_cost"]
    net_pnl = net_revenue - cost_proportion
    pnl_pct = (net_pnl / cost_proportion) * 100

    # Tambah saldo kas
    portfolio["cash_balance"] += net_revenue

    # Catat riwayat
    trade_record = {
        "symbol": symbol,
        "lots": lots_to_sell,
        "shares": shares_to_sell,
        "buy_price": pos["avg_price"],
        "sell_price": price,
        "net_revenue": round(net_revenue, 2),
        "net_pnl": round(net_pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "reason": reason,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    portfolio.setdefault("trade_history", []).append(trade_record)

    # Perbarui posisi
    if lots_to_sell >= available_lots:
        del positions[symbol]
    else:
        remaining_shares = pos["shares"] - shares_to_sell
        positions[symbol]["shares"] = remaining_shares
        positions[symbol]["lots"] = remaining_shares // LOT_SIZE
        positions[symbol]["total_cost"] = round(pos["total_cost"] - cost_proportion, 2)

    save_portfolio(portfolio)

    # Kirim notifikasi Telegram
    notify_order_execution("SELL", symbol, lots_to_sell, price, net_revenue, pnl_pct, net_pnl)

    return {
        "success": True,
        "symbol": symbol,
        "lots": lots_to_sell,
        "sell_price": price,
        "net_revenue": net_revenue,
        "net_pnl": net_pnl,
        "pnl_pct": pnl_pct,
        "remaining_cash": portfolio["cash_balance"],
        "message": f"Berhasil menjual {lots_to_sell} lot {symbol} di {format_idr(price)} (PnL: {format_idr(net_pnl)} / {pnl_pct:+.2f}%)."
    }

def update_and_check_portfolio() -> Dict[str, Any]:
    """
    Memeriksa seluruh posisi terbuka terhadap harga pasar terkini:
    - Memperbarui floating PnL & trailing stop level
    - Menutup posisi otomatis jika menyentuh TP, SL, atau Trailing Stop
    """
    portfolio = load_portfolio()
    positions = portfolio.get("positions", {})
    if not positions:
        return {"status": "EMPTY", "closed_positions": []}

    closed_positions = []
    
    # Loop copy keys agar aman jika ada penghapusan
    for symbol in list(positions.keys()):
        pos = positions[symbol]
        current_price = get_current_price(pos["ticker"])
        if not current_price or current_price <= 0:
            continue

        highest_price = max(pos.get("highest_price", pos["avg_price"]), current_price)
        pos["highest_price"] = highest_price
        
        tp_price = pos.get("tp_price", pos["avg_price"] * 1.05)
        sl_price = pos.get("sl_price", pos["avg_price"] * 0.97)
        trailing_pct = pos.get("trailing_stop_pct", 2.0)
        trailing_trigger = highest_price * (1 - trailing_pct / 100)

        exit_reason = None
        # Cek Stop Loss
        if current_price <= sl_price:
            exit_reason = "STOP LOSS TRIGGERED"
        # Cek Take Profit
        elif current_price >= tp_price:
            exit_reason = "TAKE PROFIT TRIGGERED"
        # Cek Trailing Stop (hanya aktif jika harga sempat naik di atas harga beli)
        elif highest_price >= pos["avg_price"] * 1.02 and current_price <= trailing_trigger:
            exit_reason = "TRAILING STOP TRIGGERED"

        if exit_reason:
            sell_res = sell_stock(pos["ticker"], lots=pos["lots"], price=current_price, reason=exit_reason)
            closed_positions.append({
                "symbol": symbol,
                "reason": exit_reason,
                "price": current_price,
                "pnl": sell_res.get("net_pnl", 0),
                "pnl_pct": sell_res.get("pnl_pct", 0)
            })

    save_portfolio(portfolio)
    return {"status": "UPDATED", "closed_positions": closed_positions}

def display_portfolio_summary():
    """
    Menampilkan tabel ringkasan portofolio virtual terkini.
    """
    portfolio = load_portfolio()
    cash = portfolio.get("cash_balance", 0.0)
    initial_cap = portfolio.get("initial_balance", INITIAL_BALANCE)
    positions = portfolio.get("positions", {})
    
    table_rows = []
    total_market_val = 0.0
    total_unrealized_pnl = 0.0

    for symbol, pos in positions.items():
        curr_price = get_current_price(pos["ticker"]) or pos["avg_price"]
        curr_val = pos["shares"] * curr_price
        sell_fee = curr_val * SELL_FEE_PCT
        net_val = curr_val - sell_fee
        
        unrealized_pnl = net_val - pos["total_cost"]
        pnl_pct = (unrealized_pnl / pos["total_cost"]) * 100 if pos["total_cost"] else 0
        
        total_market_val += net_val
        total_unrealized_pnl += unrealized_pnl
        
        pnl_str = f"{format_idr(unrealized_pnl)} ({pnl_pct:+.2f}%)"
        
        table_rows.append([
            symbol,
            f"{pos['lots']} Lot",
            format_idr(pos['avg_price']),
            format_idr(curr_price),
            format_idr(net_val),
            format_idr(pos['tp_price']),
            format_idr(pos['sl_price']),
            pnl_str
        ])

    total_assets = cash + total_market_val
    overall_pnl = total_assets - initial_cap
    overall_pnl_pct = (overall_pnl / initial_cap) * 100

    print("\n" + "═"*70)
    print("💼 PORTOFOLIO PAPER TRADING SAHAM INDONESIA")
    print("═"*70)
    print(f"💰 Saldo Kas Tunai  : {format_idr(cash)}")
    print(f"📈 Nilai Saham (Eq) : {format_idr(total_market_val)}")
    print(f"🏆 Total Nilai Aset : {format_idr(total_assets)}")
    print(f"📊 Total Return PnL : {format_idr(overall_pnl)} ({overall_pnl_pct:+.2f}%)")
    print("─"*70)

    if table_rows:
        headers = ["Saham", "Lot", "Avg Buy", "Harga Now", "Market Val", "Target TP", "Stop Loss", "Floating PnL"]
        print(tabulate(table_rows, headers=headers, tablefmt="rounded_grid"))
    else:
        print("ℹ️ Tidak ada posisi saham aktif (Portofolio 100% Kas Tunai).")

    # Riwayat Trade Terakhir
    history = portfolio.get("trade_history", [])
    if history:
        print("\n📜 RIWAYAT TRANSAKSI TERAKHIR (5 TERBARU):")
        hist_rows = []
        for h in history[-5:]:
            hist_rows.append([
                h['date'],
                h['symbol'],
                f"{h['lots']} Lot",
                format_idr(h['buy_price']),
                format_idr(h['sell_price']),
                format_idr(h['net_pnl']),
                f"{h['pnl_pct']:+.2f}%",
                h['reason']
            ])
        print(tabulate(hist_rows, headers=["Waktu", "Saham", "Lot", "Beli", "Jual", "Net PnL", "%", "Keterangan"], tablefmt="simple"))
    print("═"*70 + "\n")

def reset_portfolio(initial_balance: float = INITIAL_BALANCE):
    """Mereset saldo dan riwayat portofolio ke kondisi awal"""
    p = {
        "initial_balance": initial_balance,
        "cash_balance": initial_balance,
        "positions": {},
        "trade_history": [],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_portfolio(p)
    print(f"✅ Portofolio berhasil direset dengan modal awal: {format_idr(initial_balance)}")
