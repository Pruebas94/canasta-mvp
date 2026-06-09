import re

# Patrones para extraer tamaño y calcular precio por unidad
UNIT_PATTERNS = [
    (r'(\d+(?:[.,]\d+)?)\s*kg', 'kg', 1000),      # 1kg = 1000g
    (r'(\d+(?:[.,]\d+)?)\s*g\b', 'g', 1),          # gramos
    (r'(\d+(?:[.,]\d+)?)\s*l\b', 'L', 1000),       # litros
    (r'(\d+(?:[.,]\d+)?)\s*ml\b', 'ml', 1),        # mililitros
    (r'(\d+(?:[.,]\d+)?)\s*cl\b', 'cl', 10),       # centilitros -> ml
    (r'(\d+(?:[.,]\d+)?)\s*litros?', 'L', 1000),
    (r'(\d+(?:[.,]\d+)?)\s*kilos?', 'kg', 1000),
]

# Patrones para packs: "6x200ml", "pack 4x1L"
PACK_PATTERNS = [
    r'(\d+)\s*[xX×]\s*(\d+(?:[.,]\d+)?)\s*(kg|g|l|ml|cl|litros?)',
]

def extraer_tamano(nombre: str):
    """
    Extrae tamaño y calcula precio por unidad.
    Retorna: { 'size_ml': float, 'size_label': str }
    Ej: "Leche entera 1L" → { 'size_ml': 1000, 'size_label': '1L' }
    """
    nombre_lower = nombre.lower()

    # Primero buscar packs: "6x200ml"
    for pattern in PACK_PATTERNS:
        m = re.search(pattern, nombre_lower)
        if m:
            units = int(m.group(1))
            qty = float(m.group(2).replace(',', '.'))
            unit = m.group(3).lower()
            if 'kg' in unit or 'kilo' in unit:
                total_ml = units * qty * 1000
                label = f"{units}x{qty}kg"
            elif unit in ('l', 'litro', 'litros'):
                total_ml = units * qty * 1000
                label = f"{units}x{qty}L"
            elif unit == 'cl':
                total_ml = units * qty * 10
                label = f"{units}x{qty}cl"
            else:
                total_ml = units * qty
                label = f"{units}x{qty}ml"
            return {'size_ml': total_ml, 'size_label': label}

    # Luego buscar unidades simples
    for pattern, unit_label, multiplier in UNIT_PATTERNS:
        m = re.search(pattern, nombre_lower)
        if m:
            qty = float(m.group(1).replace(',', '.'))
            size_ml = qty * multiplier
            label = f"{qty}{unit_label}".replace('.0', '')
            return {'size_ml': size_ml, 'size_label': label}

    return None

def calcular_precio_unitario(price: float, nombre: str):
    """
    Calcula precio por litro/kg dado el precio total y el nombre.
    Retorna dict con info de precio unitario o None si no se puede calcular.
    """
    tamano = extraer_tamano(nombre)
    if not tamano or tamano['size_ml'] == 0:
        return None

    size_ml = tamano['size_ml']

    # Calcular por litro (si es líquido) o por kg (si es sólido)
    if size_ml >= 100:  # probablemente ml/L
        precio_por_l = (price / size_ml) * 1000
        return {
            'size_label': tamano['size_label'],
            'unit_price': round(precio_por_l, 2),
            'unit_label': '€/L'
        }
    else:  # gramos -> kg
        precio_por_kg = (price / size_ml) * 1000
        return {
            'size_label': tamano['size_label'],
            'unit_price': round(precio_por_kg, 2),
            'unit_label': '€/kg'
        }
