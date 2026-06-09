import json
import os
from difflib import SequenceMatcher

DATA_DIR = "data"

def load_all_products():
    products = []
    for filename in ["mercadona.json", "carrefour.json", "dia.json"]:
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                products.extend(json.load(f))
    return products

def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_product(name, products, threshold=0.5):
    matches = []
    for p in products:
        score = similarity(name, p["name"])
        if score >= threshold:
            matches.append({**p, "_score": score})
    return sorted(matches, key=lambda x: x["_score"], reverse=True)

def best_canasta(lista_compra, products):
    resultado = {}
    total_por_super = {"Mercadona": 0, "Carrefour": 0, "DIA": 0}

    print("\n====== COMPARADOR DE CANASTA ======\n")

    for item in lista_compra:
        matches = find_product(item, products)
        if not matches:
            print(f"❌ '{item}' — no encontrado en ningún supermercado")
            continue

        por_super = {}
        for p in matches:
            s = p["supermarket"]
            if s not in por_super:
                por_super[s] = p

        print(f"🛒 {item}")
        for s, p in sorted(por_super.items(), key=lambda x: x[1]["price"]):
            tag = " ✅ MÁS BARATO" if p["price"] == min(x["price"] for x in por_super.values()) else ""
            print(f"   {s:12} → {p['price']:.2f}€  ({p['name']}){tag}")
        print()

        resultado[item] = por_super
        for s, p in por_super.items():
            total_por_super[s] += p["price"]

    print("====== CANASTA TOTAL ======")
    for s, total in sorted(total_por_super.items(), key=lambda x: x[1]):
        if total > 0:
            tag = " ✅ GANAS AQUÍ" if total == min(v for v in total_por_super.values() if v > 0) else ""
            print(f"  {s:12} → {total:.2f}€{tag}")

    return resultado

if __name__ == "__main__":
    products = load_all_products()

    if not products:
        print("⚠️  No hay datos. Ejecuta primero los scrapers:")
        print("   py scrapers/mercadona.py")
        print("   py scrapers/carrefour.py")
        print("   py scrapers/dia.py")
    else:
        lista = [
            "leche entera",
            "aceite de oliva",
            "pan de molde",
            "huevos",
            "yogur natural",
            "agua mineral",
        ]
        best_canasta(lista, products)
