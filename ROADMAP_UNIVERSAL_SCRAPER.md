# 🚀 Plan de Universalización: De Scraper Específico a Suite Universal de Archivo Web

Este documento detalla la arquitectura, los cambios técnicos archivo por archivo y el plan de migración para transformar el scraper actual de **Criminalia.es** en una herramienta **100% universal** capaz de rescatar, reconstruir localmente y estructurar **cualquier sitio web caído** a partir de Web Archive (Wayback Machine) y Archive.today.

---

## 🎯 Objetivo de la Generalización

Convertir la suite en un CLI multipropósito ejecutable con:

```bash
python run_pipeline.py --url https://cualquier-web.com [opciones]
```

Donde la herramienta:
1. Detecte automáticamente si existe sitemap (`sitemap.xml`, `robots.txt`).
2. Si no hay sitemap, realice un **rastreo recursivo por grafos (BFS Crawler)** empezando en la portada `/` hasta descubrir el 100% de las páginas internas.
3. Almacene los datos de forma aislada en `data/<dominio>/...` (permitiendo archivar múltiples webs sin colisiones).
4. Descargue y reconstruya todos los estilos CSS, fuentes, scripts e imágenes.
5. Emplee un motor de extracción inteligente de contenido (estilo **Readability / Trafilatura**) para convertir cualquier artículo a Markdown sin necesidad de configurar selectores CSS a mano.
6. Permita previsualizar la web archivada en `http://localhost:8080` de forma idéntica a la original.

---

## 🏗️ Comparativa de Arquitectura: Estado Actual vs. Universal

| Componente | Estado Actual (Criminalia) | Estado Universal (Cualquier Web) |
| :--- | :--- | :--- |
| **Parámetros** | Dominio y fecha fijos en `config.py` | Argumentos CLI (`--url`, `--date`, `--depth`, `--workers`) o `.env` |
| **Almacenamiento** | Carpeta fija `data/raw_html/`, `data/assets/` | Espacios aislados: `data/<dominio>/raw_html/`, `data/<dominio>/assets/` |
| **Descubrimiento** | 78 índices alfabéticos propios de Juan Ignacio Blanco (`?l=a&g=hombre`) | **Crawler Recursivo por Grafos (BFS/DFS)** + Parser automático de `sitemap.xml` |
| **Rutas y Menús** | Reglas manuales (`/asesino/`, `/material/`, etc.) | Enrutador agnóstico de URLs que reproduce la estructura de rutas original |
| **Parseo Markdown** | Selectores CSS específicos (`.entry-content`, metadatos) | **Extracción heurística automática (Readability / Trafilatura)** + opción de selectores custom |
| **Servidor Local** | Reemplazo estático de strings `criminalia.es` | Proxy dinámico que sustituye `target_domain` por rutas relativas locales |

---

## 📋 Lista de Cambios Archivo por Archivo

### 1. `config.py` (Gestión Dinámica de Configuración)
* **Cambios a realizar:**
  * Eliminar `ORIGINAL_BASE_URL = 'https://criminalia.es'` hardcodeado.
  * Añadir función `init_project(target_url, custom_timestamp=None)`:
    * Extrae el dominio limpio (ej. `criminalia.es`, `otra-web.org`) para nombrarlo `DOMAIN_SLUG`.
    * Define dinámicamente las carpetas:
      * `DATA_DIR / DOMAIN_SLUG / manifests`
      * `DATA_DIR / DOMAIN_SLUG / raw_html`
      * `DATA_DIR / DOMAIN_SLUG / assets`
      * `DATA_DIR / DOMAIN_SLUG / content`
  * Detección automática del mejor snapshot:
    * Si el usuario no pasa una fecha fija, consultar la API CDX de Wayback Machine (`/cdx/search/cdx?url=dominio&output=json&limit=1`) para fijar la última instantánea válida antes de la caída.
  * Mantener 100% intacto el **Motor en Cascada de 3 Niveles** (`fetch_with_retry`), ya que es agnóstico y universal.

---

### 2. `01_discover_sitemap.py` → `01_crawler.py` (Crawler Recursivo Universal)
* **Cambios a realizar:**
  * Sustituir el bucle alfabético de 78 consultas por un motor de rastreo en dos fases:
    1. **Fase A (Sitemaps y Robots):** Comprobar si Wayback Machine tiene copias de:
       * `/robots.txt`
       * `/sitemap.xml`
       * `/sitemap_index.xml`
       * Si existen, extraer todas las URLs de golpe (ahorra horas de rastreo).
    2. **Fase B (Crawler Recursivo BFS por Grafos):**
       * Si no hay sitemap (o para complementar), arrancar en la portada `/`.
       * Cola de URLs pendientes (`queue = deque(['/'])`) y conjunto de visitadas (`visited = set()`).
       * Por cada página descargada:
         * Extraer todos los `<a href="...">`.
         * Normalizar URLs descartando enlaces externos, anclas `#`, parámetros de sesión y archivos binarios.
         * Encolar nuevas URLs internas no visitadas hasta una profundidad configurable (`--depth`).
  * Generar `data/<dominio>/manifests/pages_manifest.json`.

---

### 3. `02_discover_assets.py` (Inventario Dinámico de Recursos)
* **Cambios a realizar:**
  * Ya no buscar únicamente en plantillas fijas.
  * Analizar la totalidad de los HTMLs descubiertos en la Fase 1:
    * `<link rel="stylesheet">` $ightarrow$ Hojas de estilo CSS.
    * `<script src="...">` $ightarrow$ Scripts JS.
    * `<link rel="icon">`, `<link rel="apple-touch-icon">` $ightarrow$ Favicons.
    * `<img src="...">`, `data-src`, `srcset` $ightarrow$ Imágenes.
    * Reglas CSS `@font-face` y `background: url(...)` $ightarrow$ Tipografías y fondos.
  * Generar `data/<dominio>/manifests/assets_manifest.json`.

---

### 4. `03_download_html.py` (Descargador Masivo Agrupado)
* **Cambios a realizar:**
  * Unificar `03_download_html.py` y `03b_download_standalone.py` en un único gestor de descarga masiva.
  * Leer `pages_manifest.json`.
  * Guardar cada página recreando su jerarquía original o con un nombre unívoco seguro:
    * `dominio.com/noticias/caso-1/` $ightarrow$ `raw_html/noticias/caso-1.html`.
  * Sistema de reanudación automática (idempotente: si el archivo existe y pesa > 0, se salta).

---

### 5. `04_download_assets.py` (Descarga de Multimedia y Estilos)
* **Cambios a realizar:**
  * Este módulo ya es un 90% genérico.
  * Único cambio: recrear la estructura de carpetas de origen bajo `data/<dominio>/assets/`.
    * Ejemplo: `https://otra-web.com/static/css/theme.css` $ightarrow$ `data/<dominio>/assets/static/css/theme.css`.
  * Soporte de reintento automático con cabeceras `Referer` auténticas para evitar defensas hotlink.

---

### 6. `05_parse_articles.py` (Conversor Inteligente a Markdown)
* **Cambios a realizar:**
  * En Criminalia se usaban selectores hardcodeados (`div.entry-content`). En una web genérica (por ejemplo hecha en Drupal, Joomla, Wix, Medium o código a medida), esos selectores fallarían.
  * **Solución Universal:** Integrar la librería **`readability-lxml`** o **`trafilatura`**:
    * Analiza la densidad de texto del DOM y extrae automáticamente el titular, cuerpo principal, fecha y autor sin necesidad de saber qué CMS utilizaba la web.
    * Convierte el árbol limpio a Markdown con `markdownify`.
    * Añade Frontmatter YAML estandarizado (`title`, `date`, `url`, `author`, `slug`).
  * Añadir opción de "selectores manuales" en un archivo JSON para cuando el usuario quiera afinar una web concreta.

---

### 7. `preview_server.py` (Servidor Local Universal)
* **Cambios a realizar:**
  * Parámetro para indicar qué web archivada se desea servir: `python preview_server.py --site otra-web.org`.
  * El enrutador universal sustituye `target_domain` por la raíz local `/`:
    * Si pide un asset (`.css`, `.js`, `.png`, `.jpg`, `.woff2`, etc.) $ightarrow$ sirve desde `assets/` o lo baja al vuelo.
    * Si pide una página HTML $ightarrow$ sirve desde `raw_html/` o la baja al vuelo.
  * El panel `/status` lee automáticamente las estadísticas del dominio seleccionado.

---

### 8. `run_pipeline.py` (Orquestador CLI Moderno con `argparse`)
* **Nueva Interfaz de Usuario:**

```bash
# Archivar cualquier sitio web por completo:
python run_pipeline.py --url https://ejemplo-crimen.org --all

# Archivar con fecha histórica concreta:
python run_pipeline.py --url https://ejemplo-crimen.org --date 20190501 --all

# Ejecutar paso específico:
python run_pipeline.py --url https://ejemplo-crimen.org --step 1  # Solo rastreo

# Lanzar servidor de previsualización local:
python run_pipeline.py --url https://ejemplo-crimen.org --serve
```

---

## 🛠️ Dependencias Nuevas a Añadir a `requirements.txt`

Para soportar extracción agnóstica de contenidos y crawler eficiente:

```txt
requests>=2.31.0
beautifulsoup4>=4.12.0
loguru>=0.7.0
readability-lxml>=0.8.1
trafilatura>=1.6.0
markdownify>=0.11.6
tqdm>=4.66.0
python-dateutil>=2.8.2
```

---

## 📌 Conclusión y Hoja de Ruta

La ventaja estratégica es que **el trabajo más complejo ya está resuelto y probado en producción**:
1. Resolver los falsos 404 de Wayback Machine con el comodín `2id_` entre 2015 y 2022.
2. La integración y fallback automático a `archive.today` / `archive.is`.
3. La reescritura de URLs y el servidor local al vuelo.

Para dar el siguiente paso y universalizar el proyecto, simplemente se reemplaza el buscador de Criminalia por el rastreador BFS estándar y se parametrizan los directorios por dominio.
