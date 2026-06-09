from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
}

def _query_words(query: str) -> list:
    """Genera palabras clave normalizadas para validar matches"""
    q = query.lower().strip()
    # Quitar acentos básicos
    accents = str.maketrans("áéíóúñ", "aeioun")
    q = q.translate(accents)
    words = [w for w in re.split(r"\s+", q) if len(w) >= 3]
    return words

def _name_matches(name: str, query_words: list) -> bool:
    """Verifica que el nombre del producto realmente contiene la búsqueda"""
    if not query_words:
        return True
    n = name.lower()
    accents = str.maketrans("áéíóúñ", "aeioun")
    n = n.translate(accents)
    # Al menos una palabra clave debe estar presente
    return any(w in n for w in query_words)

def search(query: str) -> list:
    results = []
    query_words = _query_words(query)
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
                if not (price_match and name not in seen and len(name) > 4):
                    continue
                # Validar que el producto coincide con la búsqueda
                if not _name_matches(name, query_words):
                    continue
                # DIA: el div .product-special-offer existe siempre, pero solo
                # tiene texto cuando hay oferta REAL.
                offer_el = card.select_one(".product-special-offer")
                promo_text = offer_el.get_text(strip=True)[:60] if offer_el else None
                on_sale = bool(promo_text)  # solo True si hay texto real

                seen.add(name)
                results.append({
                    "supermarket": "DIA",
                    "name": name,
                    "price": float(price_match.group(1).replace(",", ".")),
                    "unit": "ud",
                    "on_sale": on_sale,
                    "promo_text": promo_text,
                })
    except Exception as e:
        print(f"DIA error: {e}")
    return results
