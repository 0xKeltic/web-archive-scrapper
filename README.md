# 🌐 Universal Web Archive Scraper & Rebuilder Suite

Herramienta universal de preservación digital capaz de rescatar, reconstruir localmente y convertir a Markdown estructurado **cualquier sitio web caído** a partir de **The Internet Archive (Wayback Machine)** y la red **archive.today (archive.ph)**.

Originalmente desarrollada y probada en producción con el rescate del 100% de la enciclopedia criminal [Criminalia.es](https://github.com/0xKeltic/criminalia), esta suite ha sido completamente universalizada para operar de manera autónoma y agnóstica con cualquier dominio.

---

## 🌟 Características Principales

* **Universal y Agnóstica de Plataforma:**
  * Funciona con cualquier gestor de contenidos (WordPress, Drupal, Joomla, Ghost, sitios estáticos o hechos a medida).
  * Soporta múltiples webs archivadas simultáneamente en espacios aislados (`data/<dominio>/...`).
* **Doble Modo de Operación (Archivo Histórico vs Web en Vivo):**
  * **Modo Histórico (Por defecto):** Recupera snapshots del pasado en Wayback Machine y Archive.today mediante cascada inteligente.
  * **Modo Web en Vivo (`--live`):** Descarga, replica y convierte webs vivas en tiempo real directamente desde su servidor activo, sin depender de archivos temporales.
* **Descubrimiento Inteligente de URLs:**
  * **Detección de Sitemaps:** Localiza e ingiere automáticamente `/sitemap.xml`, `/sitemap_index.xml` y directivas en `/robots.txt` archivados.
  * **Crawler Recursivo por Grafos (BFS):** Rastrea enlaces internos nivel a nivel hasta la profundidad configurada (`--depth`).
* **Motor de Rescate en Cascada de 3 Niveles:**
  * **Nivel 1:** Snapshot oficial en timestamp seleccionado (o detectado automáticamente mediante la API CDX de Wayback).
  * **Nivel 2 (Histórico Total):** Si devuelve 404, busca automáticamente en todo el historial con comodín `2id_` y prueba alternando protocolos `http`/`https`.
  * **Nivel 3 (archive.today):** Si no existe en Wayback, consulta automáticamente la red `archive.is` / `archive.ph` con cabeceras de navegador reales.
* **Extracción Heurística Inteligente a Markdown (Trafilatura + Markdownify):**
  * Sin necesidad de configurar selectores CSS a mano: detecta automáticamente el titular, autor, fecha, imagen destacada y cuerpo del artículo eliminando anuncios y menús.
  * Reescritura automática de rutas de imágenes a `/assets/...`.
  * Genera Frontmatter YAML estandarizado y un catálogo unificado `database.json`.
* **Servidor Local Universal y On-The-Fly Rescue (`preview_server.py`):**
  * Visualiza cualquier web archivada en `http://localhost:8080/` con sus estilos CSS, tipografías e imágenes.
  * Rescate al vuelo: si visitas una página o asset no descargado previamente, el servidor lo descarga e inyecta en 1 segundo.
  * Panel de estado en tiempo real en `/status` con auto-refresco interactivo.

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

## 💻 Uso de la CLI (`run_pipeline.py`)

### 1. Archivar o Scrappear un Sitio Web Completo:
```bash
# Modo Archivo Histórico (por defecto):
# Detecta automáticamente el snapshot más reciente en Wayback y archive.today:
python run_pipeline.py --url https://ejemplo.com --all

# Modo Web en Vivo (--live):
# Descarga directamente desde la web viva y activa (sin pasar por Wayback Machine):
python run_pipeline.py --url https://ejemplo.com --live --all

# Archivar con fecha histórica concreta de Wayback (ej: 12 de mayo de 2020):
python run_pipeline.py --url https://ejemplo.com --date 20200512 --all

# Ajustar profundidad de rastreo BFS (por defecto 3) y límite de páginas:
python run_pipeline.py --url https://ejemplo.com --depth 4 --max-pages 10000 --all
```

### 2. Ejecución Modular por Pasos:
```bash
# Paso 1: Crawler BFS y descubrimiento de URLs internas
python run_pipeline.py --url https://ejemplo.com --step 1

# Paso 2: Inventario de assets (CSS, JS, tipografías e imágenes)
python run_pipeline.py --url https://ejemplo.com --step 2

# Paso 3: Descarga masiva de páginas HTML
python run_pipeline.py --url https://ejemplo.com --step 3

# Paso 4: Descarga de assets estáticos y recursos multimedia
python run_pipeline.py --url https://ejemplo.com --step 4

# Paso 5: Conversión heurística a Markdown (.md) y database.json
python run_pipeline.py --url https://ejemplo.com --step 5
```

> **Nota:** Todos los módulos son estrictamente idempotentes. Si un archivo ya existe en disco con tamaño > 0, se omite automáticamente. Puedes pausar con `Ctrl+C` y reanudar en cualquier momento.

### 3. Gestión y Visualización de Proyectos:
```bash
# Listar todos los sitios archivados en tu máquina:
python run_pipeline.py --list

# Ver estadísticas detalladas del proyecto activo:
python run_pipeline.py --status

# Lanzar servidor de previsualización local:
python run_pipeline.py --url https://ejemplo.com --serve
# O usando el puerto por defecto (8080):
python preview_server.py --domain ejemplo.com
```

* **Navegar por la Web:** [http://localhost:8080](http://localhost:8080)
* **Monitor en Vivo:** [http://localhost:8080/status](http://localhost:8080/status)

---

## 📂 Estructura de Carpetas

```
web-archive-scrapper/
├── config.py                 # Configuración dinámica y motor de rescate en cascada (3 niveles)
├── 01_crawler.py             # Paso 1: Crawler BFS recursivo y detector de sitemaps/robots
├── 02_discover_assets.py     # Paso 2: Auditoría de CSS, JS, fuentes e imágenes
├── 03_download_html.py       # Paso 3: Descargador masivo de HTMLs con mapeo de rutas
├── 04_download_assets.py     # Paso 4: Descargador de multimedia y análisis recursivo de CSS
├── 05_parse_articles.py      # Paso 5: Extractor heurístico (Trafilatura) a Markdown y JSON
├── preview_server.py         # Servidor local proxy con rescate al vuelo y panel /status
├── run_pipeline.py           # CLI y orquestador universal multiproyecto
├── requirements.txt          # Dependencias Python
├── README.md                 # Documentación general en español
├── MANUAL.md                 # Technical Architecture & Developer Manual (English)
├── ROADMAP_UNIVERSAL_SCRAPER.md # Especificación del diseño de universalización
└── data/                     # Almacenamiento local aislado (ignorado en Git)
    └── <dominio_slug>/       # Directorio dedicado para cada web archivada
        ├── manifests/        # pages_manifest.json, assets_manifest.json, missing_*.json
        ├── raw_html/         # Réplica exacta del árbol de directorios HTML
        ├── assets/           # CSS, JS, imágenes, fuentes locales
        └── content/          # Artículos en .md con Frontmatter YAML y database.json
```

---

## 📄 Formato de Salida en Markdown

Cada documento extraído en `data/<dominio>/content/<ruta>.md` incluye Frontmatter YAML compatible con Next.js, Nuxt, Astro y Hugo:

```yaml
---
title: "Título del Artículo Extraído"
slug: "nombre-del-slug"
date: "2021-04-15"
author: "Redacción"
featured_image: "/assets/uploads/imagen-destacada.jpg"
url: "https://ejemplo.com/noticias/nombre-del-slug"
---

# Título del Artículo Extraído

Cuerpo del artículo extraído en Markdown limpio con imágenes reescritas...
```

Además, `data/<dominio>/content/database.json` proporciona el índice unificado de todas las entradas procesadas para búsqueda instantánea o importación a base de datos relacional.

---

## 🏆 Caso de Estudio: Criminalia.es

Esta suite rescató con éxito el 100% de los contenidos de **Criminalia.es**:
- **850 biografías criminales completas**
- **620 galerías de fotos de expedientes** (100% de las capturas históricas existentes)
- **227 páginas institucionales y feeds de noticias**
- **3.726 assets multimedia**
- El dataset completo preservado se encuentra publicado en el repositorio [0xKeltic/criminalia](https://github.com/0xKeltic/criminalia).

---

## 📖 Documentación Adicional

* Consulta [MANUAL.md](MANUAL.md) para detalles en profundidad sobre el protocolo HTTP, heurísticas del crawler y configuración avanzada.

