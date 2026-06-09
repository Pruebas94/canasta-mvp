import requests

HEADERS = {"User-Agent": "Foocation/1.0 (educational project)"}

# Cadenas con cobertura regional limitada
COBERTURA_REGIONAL = {
    "Ahorramas": {"provincias": ["Madrid", "Toledo", "Guadalajara"], "ccaa": ["Comunidad de Madrid", "Castilla-La Mancha"]},
    "Eroski": {"provincias": ["Vizcaya", "Guipúzcoa", "Álava", "Navarra", "Cantabria"], "ccaa": ["País Vasco", "Navarra", "Cantabria", "Galicia"]},
}

NACIONAL = ["Mercadona", "DIA", "Carrefour", "Lidl", "Aldi", "Alcampo"]


def reverse_geocode(lat: float, lon: float) -> dict:
    """Obtiene CP, ciudad y provincia desde lat/lon usando Nominatim"""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json", "addressdetails": 1, "accept-language": "es"},
            headers=HEADERS,
            timeout=8,
        )
        data = r.json()
        addr = data.get("address", {})
        return {
            "postcode": addr.get("postcode"),
            "city": addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality"),
            "district": addr.get("city_district") or addr.get("suburb"),
            "state": addr.get("state"),
            "country": addr.get("country"),
        }
    except Exception as e:
        return {"error": str(e)}


def supermercados_disponibles(state: str = None, city: str = None) -> dict:
    """
    Devuelve qué supermercados están disponibles en esa zona.
    """
    state_norm = (state or "").strip()
    available = list(NACIONAL)
    skipped = []

    for chain, scope in COBERTURA_REGIONAL.items():
        en_zona = (state_norm in scope.get("ccaa", []) or
                   state_norm in scope.get("provincias", []))
        if en_zona:
            available.append(chain)
        else:
            skipped.append({"name": chain, "reason": f"No cobertura en {state_norm}"})

    return {"available": available, "skipped": skipped}
