# Criminalia.es - Web Archive Scraper

Herramienta completa para rescatar y preservar la enciclopedia del crimen **Criminalia.es** (creada por Juan Ignacio Blanco) desde The Internet Archive (Wayback Machine).

## ¿Que hace este proyecto?
1. **Mapeo completo (Fase 1):** Rastrea las 78 paginas del indice alfabetico (A-Z) para las categorias *Hombres*, *Mujeres* y *Crimenes*, mas la seccion de actualidad.
2. **Descubrimiento de Assets (Fase 2):** Identifica todos los archivos CSS, JavaScript, fuentes tipograficas y fotografias del archivo wp-content/.
3. **Descarga de HTMLs (Fase 3):** Descarga cada articulo en modo RAW (id_) de Wayback Machine con tolerancia a fallos, reanudacion automatica y pausas para evitar bloqueos.
4. **Descarga de Assets (Fase 4):** Guarda todas las imagenes, estilos y scripts preservando la estructura original de carpetas.
5. **Parseo a Markdown y JSON (Fase 5):** Limpia el contenido HTML y genera archivos Markdown (.md) con Frontmatter YAML y un archivo database.json, listos para alimentar una web moderna en Next.js o Astro.

## Instalacion y Requisitos
Requiere Python 3.10+:
\\\ash
pip install -r requirements.txt
\\\

## Uso

### Ejecutar paso a paso:
\\\ash
# 1. Descubrir todos los enlaces y generar el catalogo de articulos
python run_pipeline.py --step 1

# 2. Descubrir todos los archivos CSS, JS e imagenes
python run_pipeline.py --step 2

# 3. Descargar todos los HTMLs de los articulos
python run_pipeline.py --step 3

# 4. Descargar todos los assets (estilos, scripts, fotos)
python run_pipeline.py --step 4

# 5. Convertir articulos a Markdown (.md) y generar database.json
python run_pipeline.py --step 5
\\\

### Ejecutar todo el proceso:
\\\ash
python run_pipeline.py --all
\\\

## Estructura de Salida
- \data/manifests/\: Catalogos JSON de articulos y assets descubiertos.
- \data/raw_html/\: Copia exacta de los HTMLs descargados de Wayback Machine.
- \data/assets/\: Archivos CSS, JS e imagenes originales organizados.
- \data/content/\: Articulos procesados en Markdown y base de datos JSON lista para la nueva web.
