import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Accept-Language": "es-ES,es;q=0.9",
}

def search(query: str) -> list:
    results = []
    try:
        url = f"https://supermercado.eroski.es/es/search/results/?q={query}&ajax=true"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        seen = set()
        for card in soup.select("div.product-item-lineal"):
            img = card.select_one("img.product-img")
            name = img["alt"] if img and img.get("alt") else None
            if not name or query.lower() not in name.lower():
                continue
            prices = re.findall(r"\b(\d+[.,]\d{2})\b", card.get_text())
            if prices and name not in seen:
                # Detectar promo
                card_text = card.get_text().lower()
                has_strike = bool(card.select_one("del, s, [class*=strike], [class*=old-price], [class*=before-price]"))
                has_promo_word = any(w in card_text for w in ["oferta", "ahorra", "3x2", "2x1", "descuento", "%dto"])
                on_sale = has_strike or has_promo_word

                seen.add(name)
                results.append({
                    "supermarket": "Eroski",
                    "name": name,
                    "price": float(prices[0].replace(",", ".")),
                    "unit": "ud",
                    "on_sale": on_sale,
                })
    except Exception as e:
        print(f"Eroski error: {e}")
    return results
