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

import time as _time
import logging as _logging

_logger = _logging.getLogger("foocation")
_logging.basicConfig(level=_logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Estado del cache de Mercadona
_mercadona_status = {
    "loaded": False,
    "loading": False,
    "last_update": None,
    "product_count": 0,
    "error": None,
}

REFRESH_INTERVAL = 12 * 60 * 60  # 12 horas

async def _precargar_mercadona():
    """Precarga el catálogo de Mercadona en background, refrescando cada 12h"""
    loop = asyncio.get_event_loop()
    while True:
        try:
            _mercadona_status["loading"] = True
            _logger.info("🛒 Iniciando precarga Mercadona...")
            t0 = _time.time()
            products = await loop.run_in_executor(None, mercadona._download_catalog)
            dt = round(_time.time() - t0, 1)
            _mercadona_status.update({
                "loaded": True,
                "loading": False,
                "last_update": _time.time(),
                "product_count": len(products) if products else 0,
                "error": None,
            })
            _logger.info(f"✅ Mercadona precargada: {len(products)} productos en {dt}s. Próxima actualización en 12h")
        except Exception as e:
            _mercadona_status.update({"loading": False, "error": str(e)})
            _logger.exception(f"❌ Error precarga Mercadona: {e}")
        # Esperar 12 horas
        await asyncio.sleep(REFRESH_INTERVAL)

@app.on_event("startup")
async def startup_event():
    # Si ya hay cache en disco reciente, usarla mientras refresca en background
    asyncio.create_task(_precargar_mercadona())

@app.get("/admin/status")
def admin_status():
    """Endpoint público para verificar el estado del sistema"""
    return {
        "mercadona": _mercadona_status,
        "next_refresh_in_seconds": (
            int(REFRESH_INTERVAL - (_time.time() - _mercadona_status["last_update"]))
            if _mercadona_status["last_update"] else None
        ),
    }

@app.post("/admin/refresh-mercadona")
async def refresh_mercadona():
    """Forzar refresco manual del catálogo de Mercadona"""
    loop = asyncio.get_event_loop()
    _mercadona_status["loading"] = True
    products = await loop.run_in_executor(None, mercadona._download_catalog)
    _mercadona_status.update({
        "loaded": True,
        "loading": False,
        "last_update": _time.time(),
        "product_count": len(products) if products else 0,
    })
    return {"status": "ok", "products": len(products) if products else 0}

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

import math

def _enriquecer(products):
    """Añade size_label, unit_price, base_value, category a cada producto"""
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
    return enriched

def _mejor_combinacion(products, target, qty_user=1):
    """
    Para cada producto, calcula cuántas unidades comprar para cubrir el target.
    Devuelve la opción más barata (puede ser N unidades del mismo producto).

    Ejemplo target 1L (1000ml), qty_user=2 → necesito 2000ml total
    Para cada producto con tamaño conocido:
      units = ceil(2000 / producto.base_value)
      total_price = units × producto.price
    Elige el de menor total_price.
    """
    if not products:
        return None, None

    enriched = _enriquecer(products)

    if not target:
        # Sin target: ordenar por €/unidad si todos tienen, sino por precio
        with_unit = [p for p in enriched if p.get("unit_price")]
        if with_unit and len(with_unit) == len(enriched):
            return min(with_unit, key=lambda x: x["unit_price"]), None
        return min(enriched, key=lambda x: x["price"]), None

    target_base = target["base_value"]
    target_cat = target["category"]
    target_total = target_base * qty_user  # cantidad total a cubrir

    # Filtrar misma categoría con tamaño detectable
    candidates = [p for p in enriched
                  if p.get("category") == target_cat and p.get("base_value")]

    if not candidates:
        # Sin candidatos de la categoría: fallback al más barato global
        return min(enriched, key=lambda x: x["price"]), "no_match"

    # Para cada producto, calcular la combinación óptima
    options = []
    for p in candidates:
        size = p["base_value"]
        units = max(1, math.ceil(target_total / size))
        total_price = round(units * p["price"], 2)
        total_size = units * size
        coverage = total_size / target_total  # 1.0 = exacto, >1 = sobra

        # Penalizar si sobra demasiado (más de 50%)
        if coverage > 1.5:
            penalty = (coverage - 1) * 0.1  # 10% peor por cada 100% extra
        else:
            penalty = 0

        options.append({
            **p,
            "units_needed": units,
            "combo_price": total_price,
            "combo_size": total_size,
            "coverage": round(coverage, 2),
            "score": total_price * (1 + penalty),
        })

    # Ordenar por score (precio efectivo penalizando sobras)
    options.sort(key=lambda x: x["score"])
    best = options[0]

    # Crear copia con campos del combo
    result = dict(best)
    result["price"] = best["combo_price"]  # precio del combo es el precio que pagas
    result["precio_unitario"] = best["price"]  # precio por una unidad del producto
    result["combo_units"] = best["units_needed"]
    result["combo_size_label"] = f'{best["units_needed"]}× {best.get("size_label", "")}'.strip()

    warning = None
    if best["coverage"] < 0.95:
        warning = "less"
    elif best["coverage"] > 1.3:
        warning = "more"
    elif best["units_needed"] > 1:
        warning = "multiple"

    return result, warning


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
            best, warning = _mejor_combinacion(products, target_size, qty)
            if not best:
                continue
            # Si NO hay target_size, aplicar qty manualmente
            if not target_size:
                best["precio_unitario"] = best["price"]
                best["price"] = round(best["price"] * qty, 2)
            best["cantidad"] = qty
            por_super[super_name] = best
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
