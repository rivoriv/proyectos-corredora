# Yapo Buscador — Propietarios Directos

Algoritmos de búsqueda y filtrado de propiedades publicadas por **dueños directos** en [Yapo.cl](https://www.yapo.cl). Descarta automáticamente avisos de corredoras e inmobiliarias, incluyendo las que se disfrazan de particulares.

## Comunas cubiertas (8)

| Script | Comunas | Ventana de búsqueda |
|--------|---------|---------------------|
| `yapo_buscador_santiago.py` | Santiago | Últimos 7 días |
| `yapo_buscador_providencia_nunoa.py` | Providencia, Ñuñoa | Últimos 7 días |
| `Yapo_buscador.py` | Macul, San Miguel, Independencia, Recoleta, Las Condes | Últimos 30 días |

## Stack

- **Python 3**
- **Playwright** (Chromium headless)
- **Expresiones regulares** para clasificación de texto

## Instalación

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    python -m playwright install chromium

## Uso

Cada script se ejecuta de forma independiente:

    python yapo_buscador_santiago.py
    python yapo_buscador_providencia_nunoa.py
    python Yapo_buscador.py

Los resultados se guardan en carpetas `CANDIDATOS_*/` con timestamp en el nombre del archivo.

## Lógica de clasificación

1. **Detección de tipo de anunciante** — el script busca en el HTML del aviso las etiquetas `profesional`, `agente` o `particular`.

2. **Puntuación por palabras clave:**
   - **Corredora:** `inmobiliaria`, `corretaje`, `comisión`, `gestión inmobiliaria`, `empresa`, `constructora`, `asesor inmobiliario`, `agente inmobiliario`, etc.
   - **Dueño:** `trato directo`, `sin comisión`, `sin corretaje`, `particular`, `dueño`, `propietario`, `sin intermediarios`, etc.

3. **Reglas de decisión:**
   - Si el tipo detectado es `profesional` o `agente` → **descartado**.
   - Si el tipo es `particular` sin evidencia de corredora → **candidato**.
   - Si `score_dueño > score_corredora` → **candidato**.
   - En cualquier otro caso → **descartado**.

## Estructura

    yapo-buscador/
    ├── Yapo_buscador.py                      # Macul, San Miguel, Independencia, Recoleta, Las Condes
    ├── yapo_buscador_providencia_nunoa.py    # Providencia, Ñuñoa
    ├── yapo_buscador_santiago.py             # Santiago
    ├── requirements.txt
    └── README.md
