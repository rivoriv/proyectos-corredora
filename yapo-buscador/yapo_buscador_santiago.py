from playwright.sync_api import sync_playwright
import re
import time
import os
from datetime import datetime

# ============================================================
# CONFIGURACIÓN
# ============================================================

COMUNAS = [
    {
        "nombre": "santiago",
        "base": "https://www.yapo.cl/bienes-raices-alquiler-apartamentos",
        "region": "region-metropolitana-santiago",
        "query": "q=time.7&sort=f_added&dir=desc"
    }
]

# Carpeta donde se guardan los candidatos
CARPETA_SALIDA = "CANDIDATOS_SANTIAGO"

# ============================================================
# PALABRAS CLAVE
# ============================================================

PALABRAS_CORREDORA = [
    r'\binmobiliaria\b', r'\binmobiliario\b', r'\bcorretaje\b',
    r'\bcorredora\b', r'\bcorredor\b', r'\bbroker\b',
    r'\breal estate\b', r'\bagente inmobiliario\b',
    r'\basesor inmobiliario\b', r'\bgestion inmobiliaria\b',
    r'comisi[óo]n de corretaje', r'honorarios de corretaje',
    r'\bprofesional inmobiliario\b', r'\bejecutivo de ventas\b',
    r'\bempresa\b', r'\bconstructora\b',
]

PALABRAS_DUENO = [
    r'trato directo', r'sin comisi[óo]n', r'sin corretaje',
    r'dueñ[oó] arrienda', r'duen[oó] arrienda',
    r'arrienda propietario', r'propietario directo',
    r'arriendo directo', r'sin intermediarios', r'sin intermediario',
    r'particular arrienda', r'arrienda particular',
    r'dueñ[oó] directo', r'propietario arrienda',
    r'su dueñ[oa]', r'por su dueñ[oa]',
    r'arriendo sin comisi[óo]n',
    r'\bdueñ[oó]\b', r'\bdueña\b', r'\bpropietario\b', r'\bpropietaria\b',
    r'\bparticular\b', r'\bpersona natural\b',
]

# ============================================================
# DETECCIÓN DE TIPO DE ANUNCIANTE
# ============================================================

def detectar_tipo_usuario(texto):
    texto_lower = texto.lower()
    for linea in texto_lower.split('\n'):
        linea = linea.strip()
        if not linea or len(linea) > 60:
            continue
        if re.fullmatch(r'profesional', linea):
            return 'profesional'
        if re.fullmatch(r'agente', linea):
            return 'agente'
        if re.fullmatch(r'particular', linea):
            return 'particular'
        if re.match(r'^profesional\b', linea) and 'inmobiliaria' not in linea and 'servicio' not in linea:
            return 'profesional'
        if re.match(r'^agente\b', linea) and 'inmobiliario' not in linea and 'vendedor' not in linea:
            return 'agente'
        if re.match(r'^particular\b', linea):
            return 'particular'

    patron_contexto = r'(publicado por|anunciante|vendedor|tipo de usuario)[:\s]+([^\n]{0,150})'
    coincidencias = re.findall(patron_contexto, texto_lower)
    for _, contexto in coincidencias:
        if re.search(r'\bprofesional\b', contexto):
            return 'profesional'
        if re.search(r'\bagente\b', contexto):
            return 'agente'
        if re.search(r'\bparticular\b', contexto):
            return 'particular'
    return None

def puntuar_texto(texto):
    texto = texto.lower()
    score_corredora = 0
    score_dueno = 0
    for patron in PALABRAS_CORREDORA:
        if re.search(patron, texto, re.IGNORECASE):
            score_corredora += 1
    for patron in PALABRAS_DUENO:
        if re.search(patron, texto, re.IGNORECASE):
            score_dueno += 1
    return score_corredora, score_dueno

def clasificar_anuncio(texto):
    tipo = detectar_tipo_usuario(texto)
    score_corredora, score_dueno = puntuar_texto(texto)

    if tipo in ('profesional', 'agente'):
        return ('descartado', f"tipo={tipo}")
    if tipo == 'particular':
        if score_corredora > 0:
            return ('descartado', f"particular con evidencia corredora ({score_corredora})")
        return ('candidato', "tipo=particular")
    if score_corredora > 0 and score_corredora >= score_dueno:
        return ('descartado', f"corredora={score_corredora}, dueño={score_dueno}")
    if score_dueno > 0 and score_dueno > score_corredora:
        return ('candidato', f"dueño={score_dueno}, corredora={score_corredora}")
    return ('descartado', f"poco claro (corredora={score_corredora}, dueño={score_dueno})")

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def obtener_enlaces_pagina(page):
    enlaces = page.locator("a[href*='/bienes-raices-alquiler-apartamentos/']").evaluate_all("""
        elements => elements
            .map(a => a.href)
            .filter(href => /\\/\\d+$/.test(href))
    """)
    return list(set(enlaces))

def generar_url_paginacion(base, region, query, numero_pagina):
    if numero_pagina == 1:
        return f"{base}/{region}?{query}"
    else:
        return f"{base}.{numero_pagina}/{region}?{query}"

def navegar_con_reintentos(page, url, intentos=3, espera=3):
    for intento in range(intentos):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return True
        except Exception as e:
            if "ERR_NAME_NOT_RESOLVED" in str(e) or "ERR_CONNECTION" in str(e):
                print(f"  Error de red (intento {intento+1}/{intentos}): {e}")
                if intento < intentos - 1:
                    time.sleep(espera)
                    continue
                else:
                    raise e
            else:
                raise e
    return False

# ============================================================
# PROCESAR COMUNA
# ============================================================

def procesar_comuna(comuna):
    nombre = comuna["nombre"]
    base = comuna["base"]
    region = comuna["region"]
    query = comuna["query"]

    print(f"\n{'='*60}")
    print(f"PROCESANDO COMUNA: {nombre.upper()}")
    print(f"{'='*60}")

    enlaces_totales = set()
    candidatos = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        pagina_actual = 1
        MAX_PAGINAS = 50

        while pagina_actual <= MAX_PAGINAS:
            url_pagina = generar_url_paginacion(base, region, query, pagina_actual)
            print(f"\n--- Página {pagina_actual} ---")

            try:
                navegar_con_reintentos(page, url_pagina, intentos=3, espera=3)
                page.wait_for_timeout(2000)

                enlaces = obtener_enlaces_pagina(page)
                cantidad = len(enlaces)
                print(f"  Enlaces encontrados: {cantidad}")

                if cantidad == 0:
                    print("  No hay enlaces. Deteniendo.")
                    break

                # Detención: menos de 20 enlaces = última página
                if cantidad < 20:
                    print("  Página con menos de 20 enlaces. Es la última. Deteniendo.")
                    for e in enlaces:
                        enlaces_totales.add(e)
                    break

                # Detección de página duplicada
                enlaces_set = set(enlaces)
                nuevos = enlaces_set - enlaces_totales
                if not nuevos:
                    print("  Página duplicada. Deteniendo.")
                    break

                for e in enlaces:
                    enlaces_totales.add(e)

                pagina_actual += 1

            except Exception as e:
                print(f"  Error: {e}. Deteniendo.")
                break

        print(f"\nTotal de enlaces únicos: {len(enlaces_totales)}")

        if not enlaces_totales:
            browser.close()
            return []

        print("\nAnalizando anuncios...")
        total = len(enlaces_totales)
        for i, url in enumerate(enlaces_totales, 1):
            print(f"[{i}/{total}] {url}")
            try:
                navegar_con_reintentos(page, url, intentos=3, espera=3)
                page.wait_for_selector("body", timeout=5000)
                texto = page.locator("body").inner_text()

                categoria, detalle = clasificar_anuncio(texto)

                if categoria == 'candidato':
                    candidatos.append(url)
                    print(f"  ✅ CANDIDATO ({detalle})")
                else:
                    print(f"  ❌ descartado ({detalle})")

            except Exception as e:
                print(f"  ERROR: {e}. Saltando.")
                continue

        browser.close()

    return candidatos

# ============================================================
# EJECUCIÓN PRINCIPAL
# ============================================================

if __name__ == "__main__":
    inicio = datetime.now()
    print("\n" + "="*60)
    print(f"🚀 BÚSQUEDA SANTIAGO - ÚLTIMOS 7 DÍAS: {inicio.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # Crear carpeta de salida si no existe
    os.makedirs(CARPETA_SALIDA, exist_ok=True)

    todos_candidatos = []

    for comuna in COMUNAS:
        candidatos = procesar_comuna(comuna)

        print(f"\n--- RESULTADOS PARA {comuna['nombre'].upper()} ---")
        print(f"Candidatos: {len(candidatos)}")

        todos_candidatos.append(f"\n### {comuna['nombre'].upper()} ({len(candidatos)}) ###")
        todos_candidatos.extend(candidatos)

    # Guardar todo en un archivo con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo_salida = os.path.join(CARPETA_SALIDA, f"candidatos_{timestamp}.txt")

    with open(archivo_salida, "w", encoding="utf-8") as f:
        f.write("\n".join(todos_candidatos))

    fin = datetime.now()
    duracion = (fin - inicio).total_seconds()

    print("\n" + "="*60)
    print("✅ PROCESO COMPLETADO")
    print("="*60)
    print(f"⏱️ Duración: {round(duracion, 2)} segundos")
    print(f"📁 Archivo: {archivo_salida}")
    print(f"📊 Total candidatos: {len([c for c in todos_candidatos if c.startswith('http')])}")