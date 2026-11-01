"""
Modul Generator Grafik Candlestick Saham Indonesia (IDX / BEI)
Menghasilkan gambar chart candlestick profesional dengan MA20, MA50, garis Entry,
Target TP, dan Stop Loss untuk dikirim langsung ke Telegram.
"""
import os
import io
import sys
from pathlib import Path
from typing import Optional, Dict, Any

import matplotlib
matplotlib.use('Agg') # Mode non-GUI backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import format_idr, format_price, get_display_name, get_asset_type
from data_provider import get_stock_data, get_clean_symbol
from strategy import get_trading_plan

CHARTS_DIR = Path(__file__).resolve().parent / "charts"
try:
    CHARTS_DIR.mkdir(exist_ok=True)
except Exception:
    import tempfile
    CHARTS_DIR = Path(tempfile.gettempdir()) / "charts"
    try:
        CHARTS_DIR.mkdir(exist_ok=True)
    except Exception:
        pass

def generate_candlestick_chart(ticker: str, period: str = "3mo") -> Optional[str]:
    """
    Menghasilkan gambar chart candlestick untuk saham, crypto, komoditas, atau forex.
    Returns path file gambar (.png) atau None jika gagal.
    """
    display_title = get_display_name(ticker)
    df = get_stock_data(ticker, period=period, interval="1d")
    
    if df.empty or len(df) < 15:
        return None
        
    plan = get_trading_plan(ticker)
    if not plan.get("valid"):
        return None
        
    actual_ticker = plan.get("ticker", ticker)
    asset_type = plan.get("asset_type", get_asset_type(actual_ticker))
    
    # Ambil 50 candle terakhir agar grafik terlihat jelas dan proporsional
    df_plot = df.tail(50).copy()
    
    # Hitung MA20 dan MA50
    df_plot['MA20'] = df['Close'].rolling(min(20, len(df))).mean().loc[df_plot.index]
    df_plot['MA50'] = df['Close'].rolling(min(50, len(df))).mean().loc[df_plot.index]
    
    # Setting Style Dark Theme Modern
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(10, 6.5), gridspec_kw={'height_ratios': [3.5, 1]},
        dpi=150, facecolor='#121820'
    )
    ax1.set_facecolor('#171e28')
    ax2.set_facecolor('#171e28')
    
    # Siapkan data candlestick
    dates = df_plot.index
    opens = df_plot['Open'].values
    highs = df_plot['High'].values
    lows = df_plot['Low'].values
    closes = df_plot['Close'].values
    volumes = df_plot['Volume'].values
    
    # Warna lilin: Hijau untuk bullish, Merah untuk bearish
    up_color = '#00c853'
    down_color = '#ff3d00'
    colors = [up_color if c >= o else down_color for o, c in zip(opens, closes)]
    
    # Gambar garis sumbu candle (High-Low)
    x_indices = np.arange(len(df_plot))
    ax1.vlines(x_indices, lows, highs, color=colors, linewidth=1.2, alpha=0.9)
    
    # Gambar badan candle (Open-Close)
    bar_width = 0.65
    for i in range(len(df_plot)):
        rect_bottom = min(opens[i], closes[i])
        rect_height = max(abs(closes[i] - opens[i]), 1e-6)
        ax1.bar(
            x_indices[i], rect_height, bottom=rect_bottom,
            width=bar_width, color=colors[i], edgecolor=colors[i], alpha=0.95
        )
        
    # Plot Moving Averages
    ax1.plot(x_indices, df_plot['MA20'].values, color='#00e5ff', label='MA 20 (Trend Cepat)', linewidth=1.5)
    if not df_plot['MA50'].isna().all():
        ax1.plot(x_indices, df_plot['MA50'].values, color='#ffd600', label='MA 50 (Trend Utama)', linewidth=1.5)
        
    # Garis Horizontal Trading Plan (Entry, TP, SL)
    entry_val = plan['close']
    tp_val = plan['tp2']
    sl_val = plan['sl_price']
    
    entry_lbl = format_price(entry_val, actual_ticker)
    tp_lbl = format_price(tp_val, actual_ticker)
    sl_lbl = format_price(sl_val, actual_ticker)
    
    ax1.axhline(entry_val, color='#00e5ff', linestyle='--', linewidth=1.2, alpha=0.7, label=f"Entry: {entry_lbl}")
    ax1.axhline(tp_val, color='#00e676', linestyle='--', linewidth=1.4, alpha=0.9, label=f"Target TP (+5%): {tp_lbl}")
    ax1.axhline(sl_val, color='#ff1744', linestyle='--', linewidth=1.4, alpha=0.9, label=f"Stop Loss (-3%): {sl_lbl}")
    
    # Shading Area Profit & Area Loss
    ax1.axhspan(entry_val, tp_val, color='#00e676', alpha=0.07)
    ax1.axhspan(sl_val, entry_val, color='#ff1744', alpha=0.07)
    
    # Konfigurasi Sumbu Harga (Ax1)
    badge_market = "IDX" if asset_type == "stock" else asset_type.upper()
    ax1.set_title(
        f"{display_title} ({badge_market}) - Candlestick & Trading Plan\nHarga: {entry_lbl} ({plan['change_pct']:+.2f}%) | RVol: {plan['rvol']}x | RSI: {plan['rsi']}",
        fontsize=13, fontweight='bold', color='#ffffff', pad=12
    )

    ax1.grid(True, linestyle=':', alpha=0.25, color='#90a4ae')
    ax1.legend(loc='upper left', fontsize=8.5, framealpha=0.6, facecolor='#121820', edgecolor='#37474f')
    currency_label = "IDR" if asset_type == "stock" else ("JPY" if "JPY" in actual_ticker else "USD")
    ax1.set_ylabel(f'Harga ({currency_label})', color='#cfd8dc', fontsize=9.5)
    ax1.tick_params(colors='#b0bec5', labelsize=8.5)
    
    # Subplot Volume (Ax2)
    vol_scale = 1e6 if asset_type == "stock" else 1.0
    vol_unit = "M" if asset_type == "stock" else ""
    ax2.bar(x_indices, volumes / vol_scale, color=colors, width=bar_width, alpha=0.85)
    ax2.grid(True, linestyle=':', alpha=0.2, color='#90a4ae')
    ax2.set_ylabel(f'Vol {vol_unit}'.strip(), color='#cfd8dc', fontsize=8.5)
    ax2.tick_params(colors='#b0bec5', labelsize=8)
    
    # Label tanggal pada sumbu X
    step = max(len(df_plot) // 7, 1)
    ax2.set_xticks(x_indices[::step])
    ax2.set_xticklabels([d.strftime('%d %b') for d in dates[::step]], rotation=25, color='#b0bec5', fontsize=8)
    ax1.set_xticks([]) # Hilangkan x-ticks di panel atas
    
    plt.tight_layout()
    
    safe_sym = ticker.replace("=", "_").replace("/", "_").replace("-", "_").replace(".", "_")
    chart_path = CHARTS_DIR / f"{safe_sym}_chart.png"
    plt.savefig(chart_path, dpi=150, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
    plt.close(fig)
    
    return str(chart_path)

if __name__ == "__main__":
    test_sym = sys.argv[1] if len(sys.argv) > 1 else "BBCA"
    p = generate_candlestick_chart(test_sym)
    print(f"Chart saved at: {p}")
