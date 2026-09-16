# ⚖️ Criminalia.es - Web Archive Scraper & Local Preservation Suite

Herramienta integral para rescatar, preservar y estructurar el 100% de la enciclopedia del crimen **Criminalia.es** (creada por Juan Ignacio Blanco) desde **The Internet Archive (Wayback Machine)** y **archive.today (archive.ph)**.

---

## 🌟 Características Principales

* **Mapeo Completo del Sitio (856 contenidos):**
  * Descarga y análisis de los **78 índices alfabéticos** (26 letras x 3 categorías: *Hombres*, *Mujeres*, *Crímenes*) y la sección *Actualidad*.
* **Motor de Rescate en Cascada de 3 Niveles:**
  * **Nivel 1:** Snapshot oficial de Wayback Machine (11 de julio de 2023).
  * **Nivel 2 (Histórico Total):** Si devuelve 404, busca automáticamente en todas las capturas entre **2015 y 2022** con comodín `2id_` y prueba de protocolos `http`/`https`.
  * **Nivel 3 (archive.today):** Si no existe en Wayback Machine, consulta automáticamente la red de `archive.is` / `archive.ph` con cabeceras de navegador reales.
* **Servidor de Previsualización Local (`preview_server.py`):**
  * Replica la **portada real** de Criminalia con sus estilos CSS originales, cabecera, slider fotográfico y abecedarios en `http://localhost:8080`.
  * Permite navegar por cualquier criminal o galería; si un recurso aún no está descargado, el servidor **lo descarga al vuelo en 1 segundo** y lo guarda en disco.
* **Panel de Progreso en Vivo (`/status`):**
  * Dashboard visual en tiempo real en `http://localhost:8080/status` con auto-refresco cada 3 segundos que muestra cuántos artículos, galerías y fotos van de cuántos totales.
* **Conversión Estructurada a Markdown y JSON:**
  * Cada biografía se limpia de código obsoleto y se exporta a formato Markdown (`.md`) con Frontmatter YAML y a un catálogo global `database.json`, listos para alimentar una web moderna en **Next.js** o **Astro**.

---

## 🚀 Instalación Rápida

Requiere **Python 3.10+**:

```bash
# 1. Clonar el repositorio
git clone https://github.com/0xKeltic/web-archive-scrapper.git
cd web-archive-scrapper

# 2. Instalar dependencias
pip install -r requirements.txt
```

---

## 💻 Uso del Pipeline

### Ejecución Completa Automática:
```bash
python run_pipeline.py --all
```

### Ejecución Modular por Pasos:
```bash
# Paso 1: Descubrir sitemap y 78 índices alfabéticos
python run_pipeline.py --step 1

# Paso 2: Inventario de assets (CSS, JS, fuentes e imágenes de plantilla)
python run_pipeline.py --step 2

# Paso 3: Descargar todos los HTMLs (856 artículos + galerías de fotos)
python run_pipeline.py --step 3

# Paso 4: Descarga masiva de fotografías de expedientes y assets multimedia
python run_pipeline.py --step 4

# Paso 5: Parsear y exportar a Markdown (.md) y database.json
python run_pipeline.py --step 5
```

> **Nota:** Todos los módulos verifican si el archivo ya existe en disco antes de pedirlo a internet, por lo que puedes pausar con `Ctrl+C` y reanudar en cualquier momento sin perder progreso ni duplicar descargas.

---

## 🌐 Servidor Local y Dashboard de Estado

Inicia el visualizador local en cualquier momento:

```bash
python preview_server.py
```

* **Web Principal:** [http://localhost:8080](http://localhost:8080) — Navega por la enciclopedia con el diseño y fotos originales.
* **Panel de Progreso en Vivo:** [http://localhost:8080/status](http://localhost:8080/status) — Muestra en tiempo real las estadísticas exactas de descarga con barras de progreso.

---

## 📂 Estructura de Carpetas

```
web-archive-scrapper/
├── config.py                 # Configuración central y motor de rescate en 3 niveles
├── 01_discover_sitemap.py    # Fase 1: Mapeo de índices alfabéticos (A-Z)
├── 02_discover_assets.py     # Fase 2: Mapeo de estilos CSS, JS y fuentes
├── 03_download_html.py       # Fase 3: Descarga de artículos y galerías
├── 04_download_assets.py     # Fase 4: Descarga de miles de fotografías de crímenes
├── 05_parse_articles.py      # Fase 5: Conversión a Markdown y catálogo JSON
├── preview_server.py         # Servidor local con renderizado y descarga al vuelo
├── run_pipeline.py           # Orquestador interactivo / CLI
├── requirements.txt          # Dependencias
├── README.md                 # Documentación en español
├── MANUAL.md                 # Comprehensive English technical manual
└── data/                     # Datos locales (ignorado en Git para ligereza)
    ├── manifests/            # articles_manifest.json, assets_manifest.json
    ├── raw_html/             # index.html, asesino/*.html, material/*.html
    ├── assets/               # wp-content/ (style.css, uploads, gallery)
    └── content/              # articles/*.md, database.json
```

---

## 📖 Documentación Avanzada

Para una guía técnica detallada en inglés sobre la arquitectura, el protocolo de recuperación en cascada y las especificaciones de datos, consulta [MANUAL.md](MANUAL.md).
