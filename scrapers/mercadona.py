import requests
import json
import os
import time

BASE_URL = "https://tienda.mercadona.es/api"
CACHE_FILE = "data/mercadona_cache.json"
CACHE_TTL = 3600  # 1 hora

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
}

_cache = None
_cache_time = 0

def _load_cache():
    global _cache, _cache_time
    # Si ya tenemos en memoria y es reciente, usar eso
    if _cache and (time.time() - _cache_time) < CACHE_TTL:
        return _cache
    # Si hay fichero en disco reciente, leerlo
    if os.path.exists(CACHE_FILE):
        age = time.time() - os.path.getmtime(CACHE_FILE)
        if age < CACHE_TTL:
            with open(CACHE_FILE, encoding="utf-8") as f:
                _cache = json.load(f)
                _cache_time = time.time()
                return _cache
    # Descargar catalogo completo
    return _download_catalog()

def _download_catalog():
    global _cache, _cache_time
    print("Descargando catalogo Mercadona...")
    products = []
    try:
        r = requests.get(f"{BASE_URL}/categories/", headers=HEADERS, timeout=10)
        categories = r.json().get("results", [])
        for cat in categories:
            for subcat in cat.get("categories", []):
                try:
                    r2 = requests.get(f"{BASE_URL}/categories/{subcat['id']}/", headers=HEADERS, timeout=10)
                    data = r2.json()
                    for section in data.get("categories", []):
                        for p in section.get("products", []):
                            price_info = p.get("price_instructions", {})
                            price = price_info.get("unit_price") or price_info.get("bulk_price")
                            if price:
                                products.append({
                                    "supermarket": "Mercadona",
                                    "name": p.get("display_name", ""),
                                    "price": float(price),
                                    "unit": price_info.get("size_format", "ud"),
                                    "category": cat.get("name", ""),
                                })
                except:
                    continue
    except Exception as e:
        print(f"Mercadona download error: {e}")

    os.makedirs("data", exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False)
    _cache = products
    _cache_time = time.time()
    print(f"Catalogo Mercadona: {len(products)} productos")
    return products

def search(query: str) -> list:
    products = _load_cache()
    query_lower = query.lower()
    matches = [p for p in products if query_lower in p["name"].lower()]
    # Ordenar por relevancia (nombre más corto = más exacto)
    matches.sort(key=lambda x: len(x["name"]))
    return matches[:10]
