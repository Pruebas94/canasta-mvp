import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
}

def search(query: str) -> list:
    results = []
    try:
        url = f"https://www.ahorramas.com/search?q={query}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        seen = set()
        for card in soup.select("[class*=product]"):
            name_el = card.select_one("h2, h3")
            price_el = card.select_one("[class*=price], [class*=precio]")
            if name_el and price_el:
                name = name_el.get_text(strip=True)
                if query.lower() not in name.lower():
                    continue
                price_match = re.search(r"(\d+[.,]\d{2})", price_el.get_text())
                if price_match and name not in seen and len(name) > 4:
                    card_text = card.get_text().lower()
                    has_strike = bool(card.select_one("del, s, [class*=strike], [class*=old-price]"))
                    has_promo_word = any(w in card_text for w in ["oferta", "ahorra", "3x2", "2x1", "%dto"])
                    on_sale = has_strike or has_promo_word

                    seen.add(name)
                    results.append({
                        "supermarket": "Ahorramas",
                        "name": name,
                        "price": float(price_match.group(1).replace(",", ".")),
                        "unit": "ud",
                        "on_sale": on_sale,
                    })
    except Exception as e:
        print(f"Ahorramas error: {e}")
    return results
