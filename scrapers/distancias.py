import requests
import math

HEADERS = {'User-Agent': 'canasta-mvp/1.0 (educational project)'}

SUPERMERCADOS = ['Mercadona', 'Eroski', 'Ahorramas', 'DIA', 'Carrefour', 'Lidl', 'Aldi', 'Alcampo']

# Datos estimados de delivery por plataforma
DELIVERY_INFO = {
    "Glovo": {"emoji": "🟡", "tiempo_min": 25, "tiempo_max": 40, "tarifa_base": 1.99, "tarifa_km": 0.5},
    "Uber Eats": {"emoji": "⬛", "tiempo_min": 30, "tiempo_max": 50, "tarifa_base": 2.49, "tarifa_km": 0.6},
    "Propio": {"emoji": "🏪", "tiempo_min": 60, "tiempo_max": 120, "tarifa_base": 0, "tarifa_km": 0, "min_gratis": 50},
}

def calcular_distancia(lat1, lon1, lat2, lon2):
    """Distancia en metros entre dos coordenadas (Haversine)"""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return round(6371000 * 2 * math.asin(math.sqrt(a)))

def buscar_supermercados_cercanos(lat: float, lon: float, radio_km: float = 3.0) -> list:
    """Busca supermercados de nuestras cadenas cercanos a la ubicación dada"""
    resultados = []
    seen = set()

    for nombre in SUPERMERCADOS:
        try:
            r = requests.get('https://nominatim.openstreetmap.org/search', params={
                'q': nombre,
                'format': 'json',
                'limit': 3,
                'countrycodes': 'es',
                'viewbox': f'{lon - radio_km/80},{lat + radio_km/80},{lon + radio_km/80},{lat - radio_km/80}',
                'bounded': 1,
            }, headers=HEADERS, timeout=8)

            for item in r.json():
                nlat = float(item['lat'])
                nlon = float(item['lon'])
                dist = calcular_distancia(lat, lon, nlat, nlon)

                if dist > radio_km * 1000:
                    continue

                key = f"{nombre}-{round(nlat,4)}-{round(nlon,4)}"
                if key in seen:
                    continue
                seen.add(key)

                # Estimar tiempo a pie y en coche
                tiempo_andando = round(dist / 80)  # ~80m/min andando
                tiempo_coche = round(dist / 400) + 5  # ~400m/min + aparcar

                # Calcular opciones de delivery
                delivery = []
                dist_km = dist / 1000
                for plat, info in DELIVERY_INFO.items():
                    if plat == "Propio":
                        tarifa = 0
                        nota = f"Gratis desde {info['min_gratis']}€"
                    else:
                        tarifa = round(info['tarifa_base'] + info['tarifa_km'] * dist_km, 2)
                        nota = ""
                    delivery.append({
                        "plataforma": plat,
                        "emoji": info['emoji'],
                        "tiempo_estimado": f"{info['tiempo_min']}-{info['tiempo_max']} min",
                        "tarifa": tarifa,
                        "nota": nota,
                    })

                resultados.append({
                    "nombre": nombre,
                    "direccion": item.get('display_name', '').split(',')[0:3],
                    "distancia_m": dist,
                    "distancia_texto": f"{dist}m" if dist < 1000 else f"{dist/1000:.1f}km",
                    "tiempo_andando": f"~{tiempo_andando} min andando",
                    "tiempo_coche": f"~{tiempo_coche} min en coche",
                    "lat": nlat,
                    "lon": nlon,
                    "delivery": delivery,
                })
        except Exception as e:
            print(f"Error buscando {nombre}: {e}")
            continue

    resultados.sort(key=lambda x: x['distancia_m'])
    return resultados[:10]
