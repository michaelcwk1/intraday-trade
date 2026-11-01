"""
Modul AI Market Insight & Sintesis Sentimen Pasar (Powered by Gemini AI & Quantitative Engine)
Menggabungkan data Teknikal, Bandarmology, Fundamental, dan Berita Terkini
menjadi ringkasan insight trading 3-poin yang padat, tajam, dan langsung actionable.
"""
import sys
import os
import requests
from typing import Dict, Any, Optional

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import config
from config import format_price, get_display_name, get_asset_type
from data_provider import get_clean_symbol, normalize_ticker
from strategy import get_trading_plan
from technical_analysis import calculate_technical_consensus
from bandarmology import analyze_bandarmology
from fundamental_provider import get_fundamental_summary
from news_provider import get_stock_news

def _call_gemini_api(prompt: str, api_key: str) -> Optional[str]:
    """Memanggil endpoint Gemini REST API untuk menghasilkan teks ringkasan analisis"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 600
        }
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return text.strip()
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
    return None

def _synthesize_rule_based(ctx: Dict[str, Any]) -> str:
    """Algoritma kuantitatif fallback yang mensintesis data menjadi 3 poin insight tajam"""
    sym = ctx["symbol"]
    signal = ctx.get("signal", "NEUTRAL")
    consensus = ctx.get("consensus", "NEUTRAL")
    bandar_score = ctx.get("bandar_score", 50)
    bandar_status = ctx.get("bandar_status", "Netral")
    rsi = ctx.get("rsi", 50)
    chg = ctx.get("change_pct", 0)
    val_status = ctx.get("val_status", "Wajar")
    sl_price = ctx.get("sl_price_str", "-")
    tp_price = ctx.get("tp_price_str", "-")
    buy_zone = ctx.get("buy_zone_str", "-")
    
    # 1. Diagnosis Pasar
    if bandar_score >= 65 and ("BUY" in consensus or "BUY" in signal):
        diag = f"Saham {sym} sedang dalam fase **Akumulasi Kuat** dengan konfirmasi tren teknikal bullish. Sinyal beli terkonfirmasi oleh aliran smart money dan RSI di level {rsi} yang masih sehat."
    elif bandar_score <= 35 or "SELL" in consensus:
        diag = f"Saham {sym} mengalami **Tekanan Distribusi / Jual** dengan konsensus teknikal menunjukkan {consensus}. Pelaku pasar cenderung melepas aset jangka pendek (RSI {rsi})."
    elif rsi <= 35:
        diag = f"Saham {sym} telah memasuki area **Oversold (Jenuh Jual)** dengan valuasi {val_status}. Terindikasi potensi pantulan harga (technical rebound) di area support."
    else:
        diag = f"Kondisi {sym} saat ini berada dalam fase **Konsolidasi / Sideways** (RSI {rsi}). Arus transaksi masih netral dan menunggu pemicu katalis arah baru."
        
    # 2. Rekomendasi Taktis
    if "BUY" in consensus and bandar_score >= 50:
        recom = f"Disarankan **Akumulasi Beli Bertahap** di area entry `{buy_zone}`. Amankan cuan awal di target TP `{tp_price}` (+5%), disiplin cut loss jika jebol ke bawah `{sl_price}`."
    elif rsi <= 35:
        recom = f"Strategi **Buy on Weakness (BoW)** di dekat support `{sl_price}`. Tunggu candle hijau konfirmasi sebelum masuk, pasang target swing di `{tp_price}`."
    elif "SELL" in consensus or bandar_score < 40:
        recom = f"Disarankan **Wait and See** atau *Sell on Strength*. Hindari menangkap pisau jatuh sampai tekanan jual reda dan terbentuk lantai support baru."
    else:
        recom = f"Strategi **Trading Kilat / Fast Trade** dengan batas risiko ketat. Entry ideal di `{buy_zone}`, kunci profit jika menyentuh `{tp_price}`."
        
    # 3. Catatan Risiko
    if chg > 5.0:
        risk = "Risiko aksi ambil untung (profit taking) cepat karena kenaikan harga harian sudah cukup tinggi."
    elif sl_price != "-":
        risk = f"Wajib disiplin Cut Loss jika harga tembus ke bawah level proteksi `{sl_price}` untuk membatasi penurunan lebih lanjut."
    else:
        risk = "Waspadai volatilitas pasar global dan sentimen berita makro yang dapat memicu pembalikan arah tiba-tiba."
        
    return f"""🎯 *1. DIAGNOSIS & SENTIMEN PASAR:*
{diag}

💡 *2. REKOMENDASI TAKTIS:*
{recom}

⚠️ *3. CATATAN RISIKO UTAMA:*
{risk}"""

def get_ai_market_insight(ticker: str) -> str:
    """
    Menghasilkan ringkasan insight pasar AI untuk emiten atau instrumen tertentu.
    """
    sym = get_clean_symbol(ticker)
    actual = normalize_ticker(ticker)
    atype = get_asset_type(actual)
    disp = get_display_name(actual)
    
    # Kumpulkan data dari modul-modul sistem
    plan = get_trading_plan(actual)
    ta = calculate_technical_consensus(actual)
    flow = analyze_bandarmology(actual) if atype == "stock" else {"score": 50, "status": "Global Asset Flow", "cmf": 0.0}
    fund = get_fundamental_summary(actual) if atype == "stock" else {"pe": None, "pbv": None, "roe_pct": None, "valuation_status": "Umum"}
    news = get_stock_news(actual, limit=3)
    
    curr_price = plan.get("close", 0)
    chg_pct = plan.get("change_pct", 0)
    buy_zone_str = f"{format_price(plan.get('buy_min', 0), actual)} - {format_price(plan.get('buy_max', 0), actual)}"
    sl_str = format_price(plan.get("sl_price", 0), actual)
    tp_str = format_price(plan.get("tp2", 0), actual)
    
    news_titles = "; ".join([n["title"] for n in news]) if news else "Tidak ada berita sensitif terbaru"
    
    ctx = {
        "symbol": sym,
        "display_name": disp,
        "price_str": format_price(curr_price, actual),
        "change_pct": chg_pct,
        "signal": plan.get("signal", "NEUTRAL"),
        "consensus": ta.get("consensus", "NEUTRAL"),
        "buy_count": ta.get("buy_count", 0),
        "sell_count": ta.get("sell_count", 0),
        "rsi": ta.get("rsi", 50),
        "bandar_score": flow.get("score", 50),
        "bandar_status": flow.get("status", "Netral"),
        "cmf": flow.get("cmf", 0.0),
        "pe": fund.get("pe"),
        "pbv": fund.get("pbv"),
        "roe": fund.get("roe_pct"),
        "val_status": fund.get("valuation_status", "Wajar"),
        "buy_zone_str": buy_zone_str,
        "sl_price_str": sl_str,
        "tp_price_str": tp_str,
        "news_titles": news_titles
    }
    
    # 1. Cek apakah ada GEMINI_API_KEY
    api_key = config.GEMINI_API_KEY
    ai_source_badge = "🧠 *Gemini 2.5 Flash AI Engine*" if api_key else "⚡ *Quantitative Hybrid Engine*"
    
    ai_text = None
    if api_key:
        prompt = f"""Kamu adalah analis pasar modal senior berlisensi. Buat ringkasan trading insight profesional untuk:
- Instrumen: {disp}
- Harga: {ctx['price_str']} ({chg_pct:+.2f}%)
- Trading Plan: Area Beli {buy_zone_str}, Target TP {tp_str}, Cut Loss {sl_str}
- Konsensus Teknikal: {ctx['consensus']} (RSI: {ctx['rsi']}, Buy: {ctx['buy_count']}, Sell: {ctx['sell_count']})
- Arus Bandar / Smart Money: Skor {ctx['bandar_score']}/100 ({ctx['bandar_status']})
- Valuasi Fundamental: PER {ctx['pe']}x, PBV {ctx['pbv']}x, Status: {ctx['val_status']}
- Berita Terkini: {news_titles}

Buat analisis tajam dalam Bahasa Indonesia persis dengan format:
🎯 *1. DIAGNOSIS & SENTIMEN PASAR:*
(Penjelasan kondisi pasar & sentimen saat ini)

💡 *2. REKOMENDASI TAKTIS:*
(Aksi yang tepat: Entry/Wait/TP beserta level harganya)

⚠️ *3. CATATAN RISIKO UTAMA:*
(Risiko penting yang harus diwaspadai)

Langsung tulis 3 poin di atas secara padat dan actionable."""
        ai_text = _call_gemini_api(prompt, api_key)
        
    if not ai_text:
        ai_text = _synthesize_rule_based(ctx)
        
    chg_sign = "+" if chg_pct >= 0 else ""
    chg_badge = "🟢" if chg_pct >= 0 else "🔴"
    
    msg = f"""
🤖 *AI MARKET INSIGHT: {disp}*
━━━━━━━━━━━━━━━━━━━━
📊 *Powered by:* {ai_source_badge}
💵 *Harga Terkini:* `{format_price(curr_price, actual)}` ({chg_badge} `{chg_sign}{chg_pct:.2f}%`)
🏆 *Arus Smart Money:* `{ctx['bandar_score']}/100` ({ctx['bandar_status']})
🧭 *Konsensus Teknikal:* `{ctx['consensus']}` (RSI: `{ctx['rsi']}`)

{ai_text}
━━━━━━━━━━━━━━━━━━━━
_Ketik `/ta {sym}` untuk detail indikator atau `/plan {sym}` untuk trading plan lengkap._
"""
    return msg.strip()

if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "BBCA"
    print(get_ai_market_insight(t))
