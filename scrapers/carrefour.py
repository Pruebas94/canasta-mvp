import requests
from bs4 import BeautifulSoup
import json
import time

BASE_URL = "https://www.carrefour.es"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept": "application/json, text/plain, */*",
}

CATEGORIES = [
    "/supermercado/frutas-y-verduras/c/10",
    "/supermercado/lacteos-y-huevos/c/11",
    "/supermercado/carnes/c/12",
    "/supermercado/pescados/c/13",
    "/supermercado/bebidas/c/14",
]

def scrape_category(category_url):
    products = []
    url = f"{BASE_URL}{category_url}?pageSize=48"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("[class*='product-card']")
        for card in cards:
            name_el = card.select_one("[class*='product-card__title']")
            price_el = card.select_one("[class*='product-card__price']")
            if name_el and price_el:
                price_text = price_el.get_text(strip=True).replace("€", "").replace(",", ".").strip()
                try:
                    price = float(price_text.split()[0])
                except:
                    price = 0.0
                products.append({
                    "supermarket": "Carrefour",
                    "name": name_el.get_text(strip=True),
                    "price": price,
                    "category": category_url.split("/")[2] if len(category_url.split("/")) > 2 else "",
                })
    except Exception as e:
        print(f"  Error scraping {category_url}: {e}")
    return products

def scrape():
    print("Scraping Carrefour...")
    all_products = []
    for cat in CATEGORIES:
        products = scrape_category(cat)
        all_products.extend(products)
        print(f"  {cat.split('/')[2]}: {len(products)} productos")
        time.sleep(1)
    print(f"Total Carrefour: {len(all_products)} productos")
    return all_products

if __name__ == "__main__":
    products = scrape()
    with open("data/carrefour.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
