from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import asyncio
from concurrent.futures import ThreadPoolExecutor
from tinydb import TinyDB, Query
import uuid
import os

from scrapers import mercadona, dia, eroski, ahorramas
from scrapers.distancias import buscar_supermercados_cercanos
from scrapers.traducciones import traducir
from scrapers.precio_unitario import calcular_precio_unitario

app = FastAPI(title="Canasta MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

executor = ThreadPoolExecutor(max_workers=4)

# Base de datos de listas
os.makedirs("data", exist_ok=True)
db = TinyDB("data/listas.json")
listas = db.table("listas")
Lista = Query()

# ── MODELOS ──────────────────────────────────────────────

class SearchRequest(BaseModel):
    items: list[str]
    cantidades: dict = {}
    sizes: dict = {}

class CrearListaRequest(BaseModel):
    nombre: str
    creador: str = "Anónimo"

class ActualizarListaRequest(BaseModel):
    items: list[str]
    editor: str = "Anónimo"

# ── STARTUP ──────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, mercadona._load_cache)

# ── RUTAS PRINCIPALES ────────────────────────────────────

@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/supermercados-cercanos")
async def supermercados_cercanos(lat: float, lon: float):
    loop = asyncio.get_event_loop()
    resultados = await loop.run_in_executor(
        executor, buscar_supermercados_cercanos, lat, lon
    )
    return {"supermercados": resultados}

# ── LISTAS COLABORATIVAS ─────────────────────────────────

@app.post("/listas")
def crear_lista(req: CrearListaRequest):
    lista_id = str(uuid.uuid4())[:8]
    lista = {
        "id": lista_id,
        "nombre": req.nombre,
        "creador": req.creador,
        "items": [],
        "historial": [f"{req.creador} creó la lista"],
    }
    listas.insert(lista)
    return lista

@app.get("/listas/{lista_id}")
def obtener_lista(lista_id: str):
    resultado = listas.search(Lista.id == lista_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return resultado[0]

@app.put("/listas/{lista_id}")
def actualizar_lista(lista_id: str, req: ActualizarListaRequest):
    resultado = listas.search(Lista.id == lista_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    lista = resultado[0]
    historial = lista.get("historial", [])
    historial.append(f"{req.editor} actualizó la lista")
    listas.update(
        {"items": req.items, "historial": historial[-10:]},
        Lista.id == lista_id
    )
    return {**lista, "items": req.items, "historial": historial[-10:]}

# ── COMPARADOR ───────────────────────────────────────────

@app.post("/comparar")
def _parse_target_size(size_str):
    """Parsea '600ml', '1L', '12u' a base value + category"""
    if not size_str:
        return None
    info = calcular_precio_unitario(1.0, f"x {size_str}")  # truco: usar parser de productos
    return info

def _seleccionar_mejor(products, target):
    """
    Selecciona el mejor producto considerando tamaño objetivo.
    Si hay target, prioriza match exacto > misma categoría ordenada por €/unit.
    """
    if not products:
        return None, None
    enriched = []
    for p in products:
        unit_info = calcular_precio_unitario(p["price"], p["name"])
        item = dict(p)
        if unit_info:
            item.update({
                "size_label": unit_info["size_label"],
                "unit_price": unit_info["unit_price"],
                "unit_label": unit_info["unit_label"],
                "base_value": unit_info["base_value"],
                "category": unit_info["category"],
            })
        enriched.append(item)

    if target:
        target_base = target["base_value"]
        target_cat = target["category"]
        # Primero: match exacto (±10%) en misma categoría
        same_cat = [p for p in enriched if p.get("category") == target_cat]
        exact = [p for p in same_cat
                 if p.get("base_value") and 0.9 <= p["base_value"] / target_base <= 1.1]
        if exact:
            best = min(exact, key=lambda x: x.get("unit_price") or x["price"])
            return best, "exact"
        # Segundo: misma categoría, ordenado por €/unidad
        if same_cat:
            valid = [p for p in same_cat if p.get("unit_price")]
            if valid:
                best = min(valid, key=lambda x: x["unit_price"])
                warning = None
                if best.get("base_value"):
                    ratio = best["base_value"] / target_base
                    if ratio < 0.5:
                        warning = "smaller"
                    elif ratio > 2:
                        warning = "larger"
                return best, warning or "approx"

    # Sin target: ordenar por €/unidad si todos tienen, sino por precio absoluto
    with_unit = [p for p in enriched if p.get("unit_price")]
    if with_unit and len(with_unit) == len(enriched):
        best = min(with_unit, key=lambda x: x["unit_price"])
        return best, None
    best = min(enriched, key=lambda x: x["price"])
    return best, None


async def comparar(request: SearchRequest):
    loop = asyncio.get_event_loop()
    resultado = {}

    for item in request.items:
        item_es = traducir(item)
        target_size = _parse_target_size(request.sizes.get(item))

        futures = [
            loop.run_in_executor(executor, mercadona.search, item_es),
            loop.run_in_executor(executor, dia.search, item_es),
            loop.run_in_executor(executor, eroski.search, item_es),
            loop.run_in_executor(executor, ahorramas.search, item_es),
        ]
        all_results = await asyncio.gather(*futures)

        qty = request.cantidades.get(item, 1)
        por_super = {}
        warnings = {}

        for products in all_results:
            if not products:
                continue
            super_name = products[0]["supermarket"]
            best, warning = _seleccionar_mejor(products, target_size)
            if not best:
                continue
            p_copy = dict(best)
            p_copy["precio_unitario"] = best["price"]
            p_copy["cantidad"] = qty
            p_copy["price"] = round(best["price"] * qty, 2)
            por_super[super_name] = p_copy
            if warning:
                warnings[super_name] = warning

        # Mejor: ordenar por €/unidad si todos tienen, sino por precio total
        mejor = None
        if por_super:
            with_unit = [p for p in por_super.values() if p.get("unit_price")]
            if with_unit and len(with_unit) == len(por_super):
                mejor = min(with_unit, key=lambda x: x["unit_price"])
            else:
                mejor = min(por_super.values(), key=lambda x: x["price"])

        resultado[item] = {
            "supermercados": por_super,
            "cantidad": qty,
            "size_filter": request.sizes.get(item),
            "target_category": target_size["category"] if target_size else None,
            "warnings": warnings,
            "mejor_precio": mejor,
        }

    totales = {}
    for item_data in resultado.values():
        for super_name, product in item_data["supermercados"].items():
            totales[super_name] = totales.get(super_name, 0) + product["price"]

    return {
        "items": resultado,
        "totales": totales,
        "mejor_canasta": min(totales, key=totales.get) if totales else None,
    }
