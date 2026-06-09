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
async def comparar(request: SearchRequest):
    loop = asyncio.get_event_loop()
    resultado = {}

    for item in request.items:
        futures = [
            loop.run_in_executor(executor, mercadona.search, item),
            loop.run_in_executor(executor, dia.search, item),
            loop.run_in_executor(executor, eroski.search, item),
            loop.run_in_executor(executor, ahorramas.search, item),
        ]
        all_results = await asyncio.gather(*futures)

        qty = request.cantidades.get(item, 1)
        por_super = {}
        for products in all_results:
            for p in products:
                s = p["supermarket"]
                if s not in por_super or p["price"] < por_super[s]["price"]:
                    p_copy = dict(p)
                    p_copy["precio_unitario"] = p["price"]
                    p_copy["cantidad"] = qty
                    p_copy["price"] = round(p["price"] * qty, 2)
                    por_super[s] = p_copy

        resultado[item] = {
            "supermercados": por_super,
            "cantidad": qty,
            "mejor_precio": min(por_super.values(), key=lambda x: x["price"]) if por_super else None,
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
