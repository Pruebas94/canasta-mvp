import re

# Patrones para extraer tamaño y calcular precio por unidad
# Importante: orden importa — patrones más específicos primero
UNIT_PATTERNS = [
    (r'(\d+(?:[.,]\d+)?)\s*kg\b', 'weight', 1000),
    (r'(\d+(?:[.,]\d+)?)\s*g\b', 'weight', 1),
    (r'(\d+(?:[.,]\d+)?)\s*ml\b', 'volume', 1),
    (r'(\d+(?:[.,]\d+)?)\s*cl\b', 'volume', 10),
    (r'(\d+(?:[.,]\d+)?)\s*l\b', 'volume', 1000),
    (r'(\d+(?:[.,]\d+)?)\s*litros?\b', 'volume', 1000),
    (r'(\d+(?:[.,]\d+)?)\s*kilos?\b', 'weight', 1000),
    # Unidades discretas
    (r'(\d+)\s*(?:unidades|uds|ud|unit)\b', 'units', 1),
    (r'cart[oó]n\s*(?:de\s*)?(\d+)\b', 'units', 1),
    (r'docena', 'units_fixed_12', 1),
    (r'media\s+docena', 'units_fixed_6', 1),
]

PACK_PATTERN = re.compile(r'(\d+)\s*[xX×]\s*(\d+(?:[.,]\d+)?)\s*(kg|g|ml|cl|l)\b', re.IGNORECASE)

def extraer_tamano(nombre: str):
    """
    Extrae tamaño y devuelve cantidad en unidad BASE (ml para volume, g para weight, u para units).
    Retorna: { 'base': float, 'category': str, 'size_label': str }
    """
    nombre_lower = nombre.lower()

    # 1. Packs: "6x200ml", "3 x 1L"
    m = PACK_PATTERN.search(nombre_lower)
    if m:
        units = int(m.group(1))
        qty = float(m.group(2).replace(',', '.'))
        unit = m.group(3).lower()
        if unit == 'kg':
            base = units * qty * 1000
            return {'base': base, 'category': 'weight', 'size_label': f'{units}×{_clean_num(qty)}kg'}
        if unit == 'g':
            base = units * qty
            return {'base': base, 'category': 'weight', 'size_label': f'{units}×{_clean_num(qty)}g'}
        if unit == 'l':
            base = units * qty * 1000
            return {'base': base, 'category': 'volume', 'size_label': f'{units}×{_clean_num(qty)}L'}
        if unit == 'cl':
            base = units * qty * 10
            return {'base': base, 'category': 'volume', 'size_label': f'{units}×{_clean_num(qty)}cl'}
        if unit == 'ml':
            base = units * qty
            return {'base': base, 'category': 'volume', 'size_label': f'{units}×{_clean_num(qty)}ml'}

    # 2. Casos especiales
    if 'docena' in nombre_lower and 'media' not in nombre_lower:
        return {'base': 12, 'category': 'units', 'size_label': '12 u'}
    if 'media docena' in nombre_lower:
        return {'base': 6, 'category': 'units', 'size_label': '6 u'}

    # 3. Unidades simples
    for pattern, cat, multiplier in UNIT_PATTERNS:
        if cat in ('units_fixed_12', 'units_fixed_6'):
            continue
        m = re.search(pattern, nombre_lower)
        if m:
            qty = float(m.group(1).replace(',', '.'))
            base = qty * multiplier
            if cat == 'weight':
                label = f'{_clean_num(qty)}{"kg" if multiplier == 1000 else "g"}'
            elif cat == 'volume':
                label = f'{_clean_num(qty)}{"L" if multiplier == 1000 else "ml" if multiplier == 1 else "cl"}'
            else:
                label = f'{int(qty)} u'
            return {'base': base, 'category': cat, 'size_label': label}

    return None

def _clean_num(n):
    """Quita .0 innecesarios: 1.0 -> 1, 1.5 -> 1.5"""
    return str(int(n)) if n == int(n) else f"{n:.2f}".rstrip('0').rstrip('.')

def calcular_precio_unitario(price: float, nombre: str):
    """
    Devuelve dict completo: precio unitario + base + categoría.
    Esto permite ordenar y comparar correctamente.
    """
    tamano = extraer_tamano(nombre)
    if not tamano or tamano['base'] == 0:
        return None

    base = tamano['base']
    category = tamano['category']

    if category == 'volume':
        precio_por_l = (price / base) * 1000
        return {
            'size_label': tamano['size_label'],
            'base_value': base,         # ml totales
            'category': 'volume',
            'unit_price': round(precio_por_l, 2),
            'unit_label': '€/L',
        }
    elif category == 'weight':
        precio_por_kg = (price / base) * 1000
        return {
            'size_label': tamano['size_label'],
            'base_value': base,         # g totales
            'category': 'weight',
            'unit_price': round(precio_por_kg, 2),
            'unit_label': '€/kg',
        }
    else:  # units
        precio_por_unidad = price / base
        return {
            'size_label': tamano['size_label'],
            'base_value': base,         # unidades totales
            'category': 'units',
            'unit_price': round(precio_por_unidad, 2),
            'unit_label': '€/u',
        }
