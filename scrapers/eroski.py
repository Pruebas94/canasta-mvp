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
                # Eroski: solo es OFERTA real cuando hay "Antes" + "Ahora" o %
                offer_el = card.select_one(".offer-description")
                on_sale = False
                promo_text = None
                previous_price = None
                if offer_el:
                    offer_txt = offer_el.get_text(strip=True)
                    txt_low = offer_txt.lower()
                    has_antes = "antes" in txt_low
                    has_percent = "%" in offer_txt
                    has_2da = "2ª" in offer_txt or "2a" in offer_txt
                    # Sólo SALE si hay "antes" o porcentaje o "2ª unidad"
                    if has_antes or has_percent or has_2da:
                        on_sale = True
                        promo_text = offer_txt[:60]
                        # Intentar extraer precio anterior
                        if has_antes:
                            antes_match = re.search(r"(\d+[.,]\d{2})\s*€?\s*antes", txt_low)
                            if not antes_match:
                                # patrón "Ahora X€" precedido de otro precio
                                all_prices_txt = re.findall(r"(\d+[.,]\d{2})", offer_txt)
                                if len(all_prices_txt) >= 2:
                                    try:
                                        previous_price = float(all_prices_txt[0].replace(",", "."))
                                    except ValueError:
                                        pass

                current_price = float(prices[0].replace(",", "."))
                if previous_price and previous_price <= current_price:
                    previous_price = None  # validación

                seen.add(name)
                results.append({
                    "supermarket": "Eroski",
                    "name": name,
                    "price": current_price,
                    "unit": "ud",
                    "on_sale": on_sale,
                    "previous_price": previous_price,
                    "promo_text": promo_text,
                })
    except Exception as e:
        print(f"Eroski error: {e}")
    return results
