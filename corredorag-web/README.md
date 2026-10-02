# Corredora G — Sitio Web

Sitio web oficial de **Corredora G** ([corredorag.cl](https://corredorag.cl)), corredora de propiedades especializada en arriendo en la Región Metropolitana de Santiago, Chile.

## Stack

- **Python 3** + **Flask** — servidor web
- **HTML5 + CSS3** — frontend estático
- **Phusion Passenger** (`passenger_wsgi.py`) — deployment en hosting compartido
- **Google Maps Embed** — ubicación

## Estructura

    corredorag-web/
    ├── app.py                 # Servidor Flask
    ├── passenger_wsgi.py      # Entry point para deployment
    ├── requirements.txt       # Dependencias Python
    ├── templates/
    │   └── index.html         # Landing page
    └── static/
        ├── css/style.css
        └── img/
            ├── portada.png
            └── logo.png

## Instalación local

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt

## Ejecución local

    python app.py

Abrir en el navegador: [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Contacto

- **Email:** [info@corredorag.cl](mailto:info@corredorag.cl)
- **Teléfono:** +56 9 6551 3814
- **Dirección:** Antonio Bellet 193, Of. 1210, Providencia, Santiago
