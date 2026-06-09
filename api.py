from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import asyncio
from concurrent.futures import ThreadPoolExecutor

from scrapers import mercadona, dia, eroski, ahorramas

app = FastAPI(title="Canasta MVP")

@app.on_event("startup")
async def startup_event():
    # Pre-cargar catalogo de Mercadona en background al arrancar el servidor
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, mercadona._load_cache)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

executor = ThreadPoolExecutor(max_workers=4)

class SearchRequest(BaseModel):
    items: list[str]

@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.post("/comparar")
async def comparar(request: SearchRequest):
    loop = asyncio.get_event_loop()
    resultado = {}

    for item in request.items:
        # Buscar en todos los supermercados en paralelo
        futures = [
            loop.run_in_executor(executor, mercadona.search, item),
            loop.run_in_executor(executor, dia.search, item),
            loop.run_in_executor(executor, eroski.search, item),
            loop.run_in_executor(executor, ahorramas.search, item),
        ]
        all_results = await asyncio.gather(*futures)

        # Agrupar por supermercado - tomar el mas barato de cada uno
        por_super = {}
        for products in all_results:
            for p in products:
                s = p["supermarket"]
                if s not in por_super or p["price"] < por_super[s]["price"]:
                    por_super[s] = p

        resultado[item] = {
            "supermercados": por_super,
            "mejor_precio": min(por_super.values(), key=lambda x: x["price"]) if por_super else None,
        }

    # Calcular canasta total por supermercado
    totales = {}
    for item_data in resultado.values():
        for super_name, product in item_data["supermercados"].items():
            totales[super_name] = totales.get(super_name, 0) + product["price"]

    return {
        "items": resultado,
        "totales": totales,
        "mejor_canasta": min(totales, key=totales.get) if totales else None,
    }

@app.get("/health")
def health():
    return {"status": "ok"}
