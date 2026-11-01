"""
Modern Web Trading Dashboard Backend (FastAPI)
Mengintegrasikan seluruh engine kuantitatif, screener bandarmology,
radar volume breakout, rotasi sektor, swing BoW, crypto/forex, paper trading,
dan alert management.
"""
import sys
import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
import pandas as pd
from pydantic import BaseModel

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

# Pastikan root workspace masuk ke sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from config import format_idr, format_price, get_display_name, get_asset_type, INITIAL_BALANCE
from data_provider import get_stock_data, get_current_price, get_clean_symbol, normalize_ticker
from bandar_screener import run_bandar_screener
from breakout_scanner import get_breakout_stocks
from sector_heatmap import get_sector_performance
from swing_screener import run_bow_screener
from crypto_forex import get_crypto_overview, get_forex_overview
from paper_trader import (
    load_portfolio, save_portfolio, buy_stock, sell_stock,
    reset_portfolio, update_and_check_portfolio, SELL_FEE_PCT
)
from alert_manager import _load_alerts, add_price_alert, delete_price_alert
from ai_analyzer import get_ai_market_insight
from strategy import get_trading_plan
from technical_analysis import calculate_technical_consensus
from recommender import get_picks, run_scheduled_snapshots
from forex_signals import get_forex_signals, set_xau_offset
from track_record import get_track_record
from user_settings import load_settings, save_settings
from market_session import get_market_status

app = FastAPI(title="IDX Smart Trading Terminal", version="2.0")

# CORS middleware untuk mendukung akses localhost, 127.0.0.1, maupun origin file://
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

try:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

try:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

if STATIC_DIR.exists():
    try:
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    except Exception:
        pass

# Cari template directory yang valid baik di environment lokal maupun Vercel serverless
possible_template_dirs = [
    TEMPLATES_DIR,
    BASE_DIR / "web_app" / "templates",
    Path("/var/task/web_app/templates"),
]
valid_template_dir = next((d for d in possible_template_dirs if d.exists()), TEMPLATES_DIR)
templates = Jinja2Templates(directory=str(valid_template_dir))

class PaperOrderRequest(BaseModel):
    symbol: str
    lots: int
    price: Optional[float] = None
    reason: Optional[str] = "Manual Web Order"

class AlertRequest(BaseModel):
    symbol: str
    target_price: float
    chat_id: Optional[str] = "web_user"

class SettingsRequest(BaseModel):
    daily_capital: Optional[float] = None
    weekly_capital: Optional[float] = None
    daily_positions: Optional[int] = None
    weekly_positions: Optional[int] = None
    stock_risk_pct: Optional[float] = None
    fx_balance_idr: Optional[float] = None
    fx_risk_pct: Optional[float] = None
    xau_contract_size: Optional[float] = None
    fx_contract_size: Optional[float] = None

class OffsetRequest(BaseModel):
    exness_price: float

# ----------------- SCHEDULER SNAPSHOT REKOMENDASI -----------------
# Membuat daftar harian (tiap hari bursa) & mingguan (Jumat) pukul 16:30 WIB selama server menyala.
def _snapshot_scheduler():
    while True:
        try:
            run_scheduled_snapshots()
        except Exception as e:
            print(f"Scheduler rekomendasi error: {e}")
        time.sleep(60)

@app.on_event("startup")
def start_scheduler():
    if not os.getenv("VERCEL"):
        import threading
        threading.Thread(target=_snapshot_scheduler, daemon=True).start()

# ----------------- ROUTE HALAMAN UTAMA -----------------
# Gunakan def (BUKAN async def) agar FastAPI menjalankan I/O di thread pool terpisah tanpa memblokir event loop!
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        # Fallback langsung baca file jika Jinja2 template loader berbeda di runtime Vercel
        html_paths = [
            Path(__file__).resolve().parent / "templates" / "index.html",
            BASE_DIR / "web_app" / "templates" / "index.html",
            Path("/var/task/web_app/templates/index.html")
        ]
        for p in html_paths:
            if p.exists():
                return HTMLResponse(content=p.read_text(encoding="utf-8"))
        return HTMLResponse(content=f"<h1>Error loading template: {e}</h1>", status_code=500)

# ----------------- API OVERVIEW & KPI (Cepat & Non-Blocking) -----------------
@app.get("/api/overview")
def get_overview():
    try:
        portfolio = load_portfolio()
        cash = portfolio.get("cash_balance", INITIAL_BALANCE)
        positions = portfolio.get("positions", {})
        
        total_market_val = 0.0
        for sym, pos in positions.items():
            curr_price = pos.get("avg_price", 0)
            val = pos.get("shares", 0) * curr_price
            val_net = val * (1 - SELL_FEE_PCT)
            total_market_val += val_net
            
        equity = cash + total_market_val
        initial = portfolio.get("initial_balance", INITIAL_BALANCE)
        pnl = equity - initial
        pnl_pct = (pnl / initial * 100) if initial > 0 else 0.0

        # Ambil dari cache yang sudah ada agar tidak memblokir koneksi
        from bandar_screener import _BANDAR_CACHE
        from breakout_scanner import _BREAKOUT_CACHE
        from sector_heatmap import _SECTOR_CACHE
        
        bandar_top = _BANDAR_CACHE.get("results", [])[:3]
        breakout_top = _BREAKOUT_CACHE.get("results", [])[:3]
        sector_leader = _SECTOR_CACHE.get("data", {}).get("leader_sector")
        crypto_data = get_crypto_overview(force_refresh=False)
        
        return {
            "equity": equity,
            "cash": cash,
            "market_value": total_market_val,
            "pnl": pnl,
            "pnl_pct": round(pnl_pct, 2),
            "open_positions_count": len(positions),
            "bandar_top": bandar_top,
            "breakout_top": breakout_top,
            "crypto_top": crypto_data[:4] if crypto_data else [],
            "leader_sector": sector_leader
        }
    except Exception as e:
        return {"error": str(e)}

# ----------------- API REKOMENDASI HARIAN -----------------
@app.get("/api/market-status")
def api_market_status():
    return get_market_status()

@app.get("/api/picks")
def api_picks(kind: str = "harian", force_refresh: bool = False):
    return JSONResponse(content=get_picks(kind=kind, force_refresh=force_refresh))

@app.get("/api/forex/signals")
def api_forex_signals(force_refresh: bool = False):
    return JSONResponse(content=get_forex_signals(force_refresh=force_refresh))

@app.post("/api/forex/offset")
def api_forex_offset(req: OffsetRequest):
    return set_xau_offset(req.exness_price)

@app.get("/api/track-record")
def api_track_record(force_refresh: bool = False):
    return JSONResponse(content=get_track_record(force_refresh=force_refresh))

@app.get("/api/settings")
def api_get_settings():
    return load_settings()

@app.post("/api/settings")
def api_save_settings(req: SettingsRequest):
    from forex_signals import _CACHE as fx_cache
    fx_cache["data"] = None
    return save_settings(req.model_dump(exclude_none=True))

# ----------------- API SCREENER BANDAR -----------------
@app.get("/api/bandar")
def api_bandar(limit: int = 20, force_refresh: bool = False):
    data = run_bandar_screener(limit=limit, force_refresh=force_refresh)
    return JSONResponse(content=data)

# ----------------- API BREAKOUT RADAR -----------------
@app.get("/api/breakout")
def api_breakout(force_refresh: bool = False):
    stocks = get_breakout_stocks(force_refresh=force_refresh)
    return JSONResponse(content={"breakouts": stocks, "count": len(stocks)})

# ----------------- API SWING / BOW SCREENER -----------------
@app.get("/api/swing")
def api_swing(limit: int = 15, force_refresh: bool = False):
    data = run_bow_screener(limit=limit, force_refresh=force_refresh)
    return JSONResponse(content={"swings": data, "count": len(data)})

# ----------------- API SEKTOR HEATMAP -----------------
@app.get("/api/sektor")
def api_sektor(force_refresh: bool = False):
    data = get_sector_performance(force_refresh=force_refresh)
    return JSONResponse(content=data)

# ----------------- API CRYPTO & FOREX -----------------
@app.get("/api/crypto_forex")
def api_crypto_forex(force_refresh: bool = False):
    crypto = get_crypto_overview(force_refresh=force_refresh)
    forex = get_forex_overview(force_refresh=force_refresh)
    return JSONResponse(content={
        "crypto": crypto,
        "forex": forex
    })

# ----------------- API PAPER TRADING -----------------
@app.get("/api/portfolio")
def api_portfolio():
    update_and_check_portfolio()
    portfolio = load_portfolio()
    cash = portfolio.get("cash_balance", INITIAL_BALANCE)
    initial = portfolio.get("initial_balance", INITIAL_BALANCE)
    positions = portfolio.get("positions", {})
    
    positions_list = []
    total_val = 0.0
    total_unrealized = 0.0

    for sym, pos in positions.items():
        curr_price = get_current_price(pos.get("ticker", sym)) or pos.get("avg_price", 0)
        gross_val = pos.get("shares", 0) * curr_price
        net_val = gross_val * (1 - SELL_FEE_PCT)
        cost = pos.get("total_cost", 0)
        unrealized = net_val - cost
        pnl_pct = (unrealized / cost * 100) if cost > 0 else 0.0
        
        total_val += net_val
        total_unrealized += unrealized

        positions_list.append({
            "symbol": sym,
            "ticker": pos.get("ticker", sym),
            "lots": pos.get("lots", 0),
            "shares": pos.get("shares", 0),
            "avg_price": pos.get("avg_price", 0),
            "current_price": curr_price,
            "market_value": round(net_val, 2),
            "total_cost": cost,
            "unrealized_pnl": round(unrealized, 2),
            "pnl_pct": round(pnl_pct, 2),
            "tp_price": pos.get("tp_price", 0),
            "sl_price": pos.get("sl_price", 0),
            "buy_date": pos.get("buy_date", "-")
        })

    equity = cash + total_val
    overall_pnl = equity - initial
    overall_pnl_pct = (overall_pnl / initial * 100) if initial > 0 else 0.0

    trades = portfolio.get("trade_history", [])
    wins = sum(1 for t in trades if t.get("net_pnl", 0) > 0)
    win_rate = (wins / len(trades) * 100) if trades else 0.0

    return {
        "cash_balance": cash,
        "initial_balance": initial,
        "stock_value": total_val,
        "total_equity": equity,
        "overall_pnl": overall_pnl,
        "overall_pnl_pct": round(overall_pnl_pct, 2),
        "win_rate": round(win_rate, 1),
        "total_trades": len(trades),
        "positions": positions_list,
        "trade_history": trades[-25:]
    }

@app.post("/api/paper/buy")
def api_paper_buy(req: PaperOrderRequest):
    res = buy_stock(ticker=req.symbol, lots=req.lots, price=req.price)
    return JSONResponse(content=res)

@app.post("/api/paper/sell")
def api_paper_sell(req: PaperOrderRequest):
    res = sell_stock(ticker=req.symbol, lots=req.lots, price=req.price, reason=req.reason)
    return JSONResponse(content=res)

@app.post("/api/paper/reset")
def api_paper_reset():
    reset_portfolio(INITIAL_BALANCE)
    return {"success": True, "message": "Portofolio berhasil direset ke saldo awal Rp 100 Juta."}

# ----------------- API CANDLESTICK CHART DATA -----------------
@app.get("/api/chart/{symbol}")
def api_chart_data(symbol: str, period: str = "6mo", interval: str = "1d"):
    """
    Mengembalikan data OHLCV siap pakai untuk TradingView Lightweight Charts.
    """
    try:
        norm = normalize_ticker(symbol)
        clean = get_clean_symbol(norm)
        disp = get_display_name(norm)
        
        df = get_stock_data(norm, period=period, interval=interval)
        if df.empty or len(df) < 2:
            raise HTTPException(status_code=404, detail=f"Data candlestick tidak ditemukan untuk {symbol}")

        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()

        candles = []
        volumes = []
        ma20_series = []
        ma50_series = []

        is_intraday = interval not in ("1d", "5d", "1wk", "1mo", "3mo")
        for idx, row in df.iterrows():
            # Intraday: UNIX timestamp digeser ke WIB agar sumbu waktu chart tampil jam Indonesia
            time_str = int(idx.timestamp()) + 7 * 3600 if is_intraday else idx.strftime("%Y-%m-%d")
            c_open = round(float(row['Open']), 2)
            c_high = round(float(row['High']), 2)
            c_low = round(float(row['Low']), 2)
            c_close = round(float(row['Close']), 2)
            c_vol = round(float(row['Volume']), 2)
            
            is_up = c_close >= c_open

            candles.append({
                "time": time_str,
                "open": c_open,
                "high": c_high,
                "low": c_low,
                "close": c_close
            })

            volumes.append({
                "time": time_str,
                "value": c_vol,
                "color": "rgba(34, 197, 94, 0.45)" if is_up else "rgba(239, 68, 68, 0.45)"
            })

            if not pd.isna(row['MA20']):
                ma20_series.append({
                    "time": time_str,
                    "value": round(float(row['MA20']), 2)
                })
            if not pd.isna(row['MA50']):
                ma50_series.append({
                    "time": time_str,
                    "value": round(float(row['MA50']), 2)
                })

        curr_price = float(df['Close'].iloc[-1])
        prev_price = float(df['Close'].iloc[-2]) if len(df) >= 2 else curr_price
        change_pt = curr_price - prev_price
        change_pct = (change_pt / prev_price * 100) if prev_price > 0 else 0.0

        return {
            "symbol": clean,
            "ticker": norm,
            "display_name": disp,
            "current_price": curr_price,
            "change_pt": change_pt,
            "change_pct": round(change_pct, 2),
            "candles": candles,
            "volumes": volumes,
            "ma20": ma20_series,
            "ma50": ma50_series
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------- API AI INSIGHT & TRADING PLAN -----------------
@app.get("/api/ai/{symbol}")
def api_ai_insight(symbol: str):
    try:
        norm = normalize_ticker(symbol)
        clean = get_clean_symbol(norm)
        insight_text = get_ai_market_insight(norm)
        plan = get_trading_plan(norm)
        ta = calculate_technical_consensus(norm)
        
        return {
            "symbol": clean,
            "ticker": norm,
            "insight": insight_text,
            "plan": plan,
            "technical": ta
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------- API ALERT MANAGEMENT -----------------
@app.get("/api/alerts")
def api_get_alerts():
    alerts = _load_alerts()
    return JSONResponse(content={"alerts": alerts})

@app.post("/api/alerts")
def api_add_alert(req: AlertRequest):
    res = add_price_alert(symbol=req.symbol, target_price=req.target_price, chat_id=req.chat_id or "web_user")
    return JSONResponse(content=res)

@app.delete("/api/alerts/{alert_id}")
def api_delete_alert(alert_id: int):
    alerts = _load_alerts()
    new_alerts = [a for a in alerts if a.get("id") != alert_id]
    if len(new_alerts) < len(alerts):
        from alert_manager import _save_alerts
        _save_alerts(new_alerts)
        return {"success": True, "message": f"Alert #{alert_id} berhasil dihapus"}
    return {"success": False, "message": "Alert tidak ditemukan"}

# ----------------- API WATCHLIST -----------------
@app.get("/api/watchlist")
def api_watchlist():
    return {
        "idx": [get_clean_symbol(t) for t in config.DEFAULT_WATCHLIST],
        "crypto": [t.replace("-USD", "") for t in config.CRYPTO_WATCHLIST],
        "forex": ["XAU", "XAG", "OIL", "USDIDR", "EURUSD"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app.main:app", host="0.0.0.0", port=8000, reload=True)
