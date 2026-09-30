from playwright.sync_api import sync_playwright
import re, sys, time, os
from datetime import datetime, timedelta

# ============================================================
# CONFIGURACIÓN PRINCIPAL
# ============================================================

DIAS_ATRAS = 20                # Rango de búsqueda en días
EXCLUIR_MACUL = True           # Cambiar a False cuando ya hayas hecho el relevamiento de Macul

# ============================================================
# COMUNAS DISPONIBLES
# ============================================================

COMUNAS = {
    "macul":         "region-metropolitana-macul",
    "san_miguel":    "region-metropolitana-san-miguel",
    "independencia": "region-metropolitana-independencia",
    "recoleta":      "region-metropolitana-recoleta",
    "las_condes":    "region-metropolitana-las-condes",
}

# ============================================================
# PERFILES
# ============================================================

PERFILES = {
    "todas":                   ["macul", "san_miguel", "independencia", "recoleta", "las_condes"],
    "macul_sanmiguel":         ["macul", "san_miguel"],
    "independencia_recoleta":  ["independencia", "recoleta"],
    "las_condes":              ["las_condes"],
}

QUERY = "q=time.30&sort=f_added&dir=desc"

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
]

PALABRAS_DUENO = [
    r'trato directo', r'sin comisi[óo]n', r'sin corretaje',
    r'dueñ[oó] arrienda', r'duen[oó] arrienda',
    r'arrienda propietario', r'propietario directo',
    r'arriendo directo', r'sin intermediarios', r'sin intermediario',
    r'particular arrienda', r'arrienda particular',
    r'dueñ[oó] directo', r'propietario arrienda',
    r'\bdueñ[oó]\b', r'\bpropietario\b', r'\bpropietaria\b',
    r'\bparticular\b',
]

# ============================================================
# UTILIDADES
# ============================================================

def obtener_enlaces_pagina(page):
    return list(set(page.locator(
        "a[href*='/bienes-raices-alquiler-apartamentos/']"
    ).evaluate_all("""
        elements => elements
            .map(a => a.href)
            .filter(href => /\\/\\d+$/.test(href))
    """)))

def puntuar_texto(texto):
    t = texto.lower()
    return (
        sum(1 for p in PALABRAS_CORREDORA if re.search(p, t, re.IGNORECASE)),
        sum(1 for p in PALABRAS_DUENO     if re.search(p, t, re.IGNORECASE)),
    )

def detectar_tipo_usuario(texto):
    t = texto.lower()
    if re.search(r'\bprofesional\b', t): return 'profesional'
    if re.search(r'\bagente\b', t):       return 'agente'
    if re.search(r'\bparticular\b', t):   return 'particular'
    return None

def url_pagina(region, pagina):
    base = "https://www.yapo.cl/bienes-raices-alquiler-apartamentos"
    if pagina == 1:
        return f"{base}/{region}?{QUERY}"
    return f"{base}.{pagina}/{region}?{QUERY}"

def navegar(page, url, intentos=3, espera=3):
    for i in range(intentos):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return True
        except Exception as e:
            if i < intentos - 1 and ("ERR_NAME" in str(e) or "ERR_CONNECTION" in str(e)):
                time.sleep(espera); continue
            raise

def parsear_fecha(texto):
    """Detecta 'hace X', 'ayer', 'hoy' o fecha absoluta. Retorna datetime o None."""
    texto = texto.strip().lower()
    ahora = datetime.now()
    m = re.search(r'hace\s+(\d+)\s+(minutos?|horas?|d[íi]as?|dias?)', texto)
    if m:
        n, u = int(m.group(1)), m.group(2)
        if u.startswith('minuto'): return ahora - timedelta(minutes=n)
        if u.startswith('hora'):   return ahora - timedelta(hours=n)
        if u.startswith('día') or u.startswith('dia'): return ahora - timedelta(days=n)
        return None
    if 'ayer' in texto: return ahora - timedelta(days=1)
    if 'hoy' in texto:  return ahora
    m = re.search(r'(\d{1,2})[-\/.](\d{1,2})[-\/.](\d{4})', texto)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None

def extraer_fecha(page):
    selectores = [
        "span:has-text('Publicado')", "span:has-text('hace')",
        "div:has-text('Publicado')", "div:has-text('hace')",
        "span.publication-date", "span.date", "time"
    ]
    for sel in selectores:
        try:
            for el in page.locator(sel).all():
                t = el.inner_text()
                if re.search(r'hace|ayer|hoy|\d{1,2}[-\/.]\d{1,2}[-\/.]\d{4}', t, re.IGNORECASE):
                    f = parsear_fecha(t)
                    if f: return f
        except:
            continue
    try:
        body = page.locator("body").inner_text()
        for pat in [r'hace\s+\d+\s+(?:minutos?|horas?|d[íi]as?|dias?)', r'\bayer\b', r'\bhoy\b',
                    r'\d{1,2}[-\/.]\d{1,2}[-\/.]\d{4}']:
            m = re.search(pat, body, re.IGNORECASE)
            if m:
                f = parsear_fecha(m.group(0))
                if f: return f
    except:
        pass
    return None

# ============================================================
# PROCESAR UNA COMUNA (DOS FASES)
# ============================================================

def procesar_comuna(nombre, region, ts, script_dir):
    print(f"\n{'='*60}")
    print(f"COMUNA: {nombre.upper()}")
    print(f"{'='*60}")

    candidatos = []
    total_descartados = 0
    error_critico = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # ============================================================
        # FASE 1: RECOLECTAR TODAS LAS URLs
        # ============================================================
        print(f"\n📋 FASE 1: Recolectando URLs (páginas con 20 enlaces hasta <20)...")
        print("-" * 60)

        enlaces_totales = []
        pagina = 1
        MAX_PAGINAS = 100

        while pagina <= MAX_PAGINAS:
            url = url_pagina(region, pagina)
            try:
                navegar(page, url)
                page.wait_for_timeout(2000)

                body = page.locator("body").inner_text()
                if "No se encontraron resultados" in body or "no hay publicaciones" in body.lower():
                    print(f"  Página {pagina}: sin resultados. Fin de recolección.")
                    break

                enlaces = obtener_enlaces_pagina(page)
                cantidad = len(enlaces)
                print(f"  Página {pagina}: {cantidad} enlaces")

                if cantidad == 0:
                    print(f"  Página {pagina}: sin enlaces. Fin de recolección.")
                    break

                nuevos = 0
                for e in enlaces:
                    if e not in enlaces_totales:
                        enlaces_totales.append(e)
                        nuevos += 1

                print(f"    → +{nuevos} nuevos (acumulado: {len(enlaces_totales)})")

                if cantidad < 20:
                    print(f"  ⏹️ Página con {cantidad} enlaces (<20). Última página.")
                    break

                if nuevos == 0:
                    print(f"  ⏹️ Sin nuevos. Deteniendo.")
                    break

                pagina += 1

            except Exception as e:
                print(f"  ❌ Error en página {pagina}: {e}")
                error_critico = True
                break

        print(f"\n✅ Total URLs recolectadas en {nombre.upper()}: {len(enlaces_totales)}")

        if not enlaces_totales:
            print("⚠️ No hay URLs para analizar.")
            browser.close()
            return len(candidatos), total_descartados, error_critico

        # ============================================================
        # FASE 2: ANALIZAR CADA URL
        # ============================================================
        print(f"\n🔍 FASE 2: Analizando {len(enlaces_totales)} avisos...")
        print("-" * 60)

        total = len(enlaces_totales)
        for idx, u in enumerate(enlaces_totales, 1):
            print(f"\n[{idx}/{total}] {u}")
            try:
                navegar(page, u, intentos=2, espera=2)
                page.wait_for_selector("body", timeout=5000)

                # Detectar fecha (solo informativa)
                fecha = extraer_fecha(page)
                if fecha:
                    print(f"  📅 Fecha: {fecha:%Y-%m-%d}")
                else:
                    print(f"  ⚠️ Sin fecha detectada.")

                texto = page.locator("body").inner_text()
                tipo = detectar_tipo_usuario(texto)

                if tipo in ('profesional', 'agente'):
                    total_descartados += 1
                    print(f"  ❌ DESCARTADO (tipo={tipo})")
                    continue
                if tipo == 'particular':
                    candidatos.append(f"{u} | tipo=particular")
                    print(f"  ✅ CANDIDATO (particular)")
                    continue

                sc, sd = puntuar_texto(texto)
                if sd >= sc:
                    candidatos.append(f"{u} | corredora={sc}, dueno={sd}")
                    if sc == 0 and sd == 0:
                        print(f"  ⚠️ CANDIDATO (0,0)")
                    else:
                        print(f"  ✅ CANDIDATO (c={sc}, d={sd})")
                else:
                    total_descartados += 1
                    print(f"  ❌ DESCARTADO (c={sc}, d={sd})")

            except Exception as e:
                print(f"  ERROR: {e}")
                continue

        browser.close()

    # Guardar candidatos
    if candidatos:
        f = os.path.join(script_dir, f"candidatos_{nombre}_{ts}.txt")
        open(f, "w", encoding="utf-8").write("\n".join(candidatos))
        print(f"\n✅ GUARDADO: {os.path.basename(f)} ({len(candidatos)})")
    else:
        print(f"\n📭 Sin candidatos en {nombre.upper()}")

    print(f"\n--- {nombre.upper()} | Candidatos: {len(candidatos)} | Descartados: {total_descartados} ---")
    return len(candidatos), total_descartados, error_critico

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    perfil = sys.argv[1] if len(sys.argv) > 1 else "todas"

    if perfil not in PERFILES:
        print(f"❌ Perfil '{perfil}' no existe.")
        print(f"   Opciones: {list(PERFILES.keys())}")
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(script_dir, "ejecucion.log")

    def log(msg):
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} - {msg}\n")
        print(msg)

    now = datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S")

    comunas_a_procesar = PERFILES[perfil]

    # Excluir Macul si corresponde
    if EXCLUIR_MACUL and "macul" in comunas_a_procesar:
        comunas_a_procesar = [c for c in comunas_a_procesar if c != "macul"]
        log(f"⏭️ Macul EXCLUIDO (variable EXCLUIR_MACUL=True)")

    log("=" * 60)
    log(f"PERFIL: {perfil.upper()}")
    log(f"Comunas: {', '.join(comunas_a_procesar)}")
    log(f"Rango de búsqueda: últimos {DIAS_ATRAS} días")
    log(f"Inicio: {now:%Y-%m-%d %H:%M:%S}")
    log("=" * 60)

    resumen = {}
    hubo_error = False

    for nombre in comunas_a_procesar:
        region = COMUNAS[nombre]
        try:
            nc, nd, err = procesar_comuna(nombre, region, ts, script_dir)
            resumen[nombre] = {"c": nc, "d": nd}
            if err:
                hubo_error = True
        except Exception as e:
            log(f"[{nombre}] ERROR CRÍTICO: {e}")
            resumen[nombre] = {"c": 0, "d": 0}
            hubo_error = True

    log("\n" + "=" * 60)
    log(f"RESUMEN PERFIL: {perfil.upper()}")
    log("=" * 60)
    tc, td = 0, 0
    for n, r in resumen.items():
        log(f"  {n.upper():15s} | Candidatos: {r['c']:3d} | Descartados: {r['d']:3d}")
        tc += r["c"]; td += r["d"]
    log("-" * 60)
    log(f"  TOTAL           | Candidatos: {tc:3d} | Descartados: {td:3d}")
    log("=" * 60)

    if hubo_error:
        log("⚠️ Hubo errores en algunas comunas. Revisa el log.")