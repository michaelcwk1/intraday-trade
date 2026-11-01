"""
Modul Pengambil Berita Saham & Pasar Modal Indonesia (IDX / BEI)
Menggunakan RSS feed Google News Keuangan Indonesia terpercaya (real-time & terkurasi).
"""
import sys
import html
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import email.utils
from datetime import timezone, timedelta
from typing import List, Dict, Any, Optional

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

WIB = timezone(timedelta(hours=7))

def _parse_pubdate(pub_date_str: str) -> str:
    """Format string pubDate RSS menjadi format WIB yang mudah dibaca"""
    if not pub_date_str:
        return ""
    try:
        dt = email.utils.parsedate_to_datetime(pub_date_str)
        wib_dt = dt.astimezone(WIB)
        return wib_dt.strftime("%d/%m/%Y %H:%M WIB")
    except Exception:
        return pub_date_str

def get_stock_news(ticker_or_code: str, limit: int = 5) -> List[Dict[str, str]]:
    """
    Mengambil berita terbaru untuk saham, crypto, forex, atau komoditas.
    """
    import config
    raw = ticker_or_code.strip().upper()
    atype = config.get_asset_type(raw)
    
    if atype == "crypto":
        query = f"crypto {config.get_display_name(raw)}"
    elif atype == "commodity":
        t_alias = config.SYMBOL_ALIASES.get(raw, raw)
        if "GC=F" in t_alias or "GOLD" in raw or "EMAS" in raw:
            query = "harga emas dunia XAU"
        elif "SI=F" in t_alias or "SILVER" in raw or "PERAK" in raw:
            query = "harga perak dunia XAG"
        elif "CL=F" in t_alias or "OIL" in raw or "MINYAK" in raw:
            query = "harga minyak mentah dunia crude oil"
        else:
            query = f"komoditas {config.get_display_name(raw)}"
    elif atype == "forex":
        query = f"kurs {config.get_display_name(raw)} forex"
    else:
        clean_sym = raw.replace(".JK", "")
        query = f"saham {clean_sym} IDX"
        
    return fetch_news_rss(query, limit=limit)

def get_market_news(limit: int = 5) -> List[Dict[str, str]]:
    """
    Mengambil berita pasar modal makro terkini (IHSG, bursa efek, sentimen ekonomi).
    """
    query = "IHSG bursa efek indonesia saham"
    return fetch_news_rss(query, limit=limit)

def fetch_news_rss(query: str, limit: int = 5) -> List[Dict[str, str]]:
    """
    Mengambil dan mem-parsing RSS Google News Indonesia berdasarkan query.
    """
    encoded_q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_q}&hl=id&gl=ID&ceid=ID:id"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
            root = ET.fromstring(content)
            
            results = []
            for item in root.findall(".//item"):
                raw_title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                source_elem = item.find("source")
                source_name = source_elem.text if source_elem is not None and source_elem.text else ""
                
                # Unescape HTML entities
                title = html.unescape(raw_title).strip()
                if source_name:
                    source_name = html.unescape(source_name).strip()
                elif " - " in title:
                    parts = title.rsplit(" - ", 1)
                    title = parts[0].strip()
                    source_name = parts[1].strip()
                
                # Buang akhiran sumber di judul jika ada duplikasi
                if source_name and title.endswith(f" - {source_name}"):
                    title = title[:-len(f" - {source_name}")].strip()
                
                formatted_date = _parse_pubdate(pub_date)
                
                results.append({
                    "title": title,
                    "source": source_name or "Media Finansial",
                    "date": formatted_date,
                    "link": link
                })
                
                if len(results) >= limit:
                    break
                    
            return results
    except Exception as e:
        print(f"Error fetching news for '{query}': {e}")
        return []

def format_news_markdown(news_list: List[Dict[str, str]], header_title: str) -> str:
    """
    Memformat daftar berita menjadi format pesan Telegram Markdown yang menarik.
    """
    if not news_list:
        return f"{header_title}\n\n⚠️ _Belum ada berita terbaru ditemukan saat ini._"
        
    lines = [f"{header_title}", "━━━━━━━━━━━━━━━━━━━━"]
    for i, item in enumerate(news_list, 1):
        title = item["title"]
        source = item["source"]
        date = item["date"]
        link = item["link"]
        
        lines.append(f"*{i}. {title}*")
        lines.append(f"📰 _{source}_ | 🕒 `{date}`")
        if link:
            lines.append(f"🔗 [Baca Selengkapnya]({link})")
        lines.append("") # baris kosong pemisah
        
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 _Gunakan informasi berita sebagai konfirmasi aksi harga (price action)._")
    return "\n".join(lines).strip()
