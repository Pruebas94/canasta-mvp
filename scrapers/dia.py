from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
}

def search(query: str) -> list:
    results = []
    session = cffi_requests.Session(impersonate="chrome")
    try:
        url = f"https://www.dia.es/search?q={query}"
        r = session.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        seen = set()
        for card in soup.select("[class*=product]"):
            name_el = card.select_one("h2, h3, [class*=name], [class*=title]")
            price_el = card.select_one("[class*=price], [class*=precio]")
            if name_el and price_el:
                name = name_el.get_text(strip=True)
                price_match = re.search(r"(\d+[.,]\d{2})", price_el.get_text())
                if price_match and name not in seen and len(name) > 4:
                    seen.add(name)
                    results.append({
                        "supermarket": "DIA",
                        "name": name,
                        "price": float(price_match.group(1).replace(",", ".")),
                        "unit": "ud",
                    })
    except Exception as e:
        print(f"DIA error: {e}")
    return results
