# -*- coding: utf-8 -*-
import sys
import argparse
import importlib
from pathlib import Path
from loguru import logger
import config

def list_existing_projects():
    """Lists all archived projects found in the data/ directory."""
    data_dir = config.DATA_DIR
    if not data_dir.exists():
        logger.info("No hay proyectos previos en el directorio data/.")
        return []
    
    projects = [d for d in data_dir.iterdir() if d.is_dir()]
    if not projects:
        logger.info("No hay proyectos previos en el directorio data/.")
        return []

    logger.info("Proyectos archivados disponibles en data/:")
    for idx, p in enumerate(projects, 1):
        pages_count = len(list((p / 'raw_html').rglob('*.html'))) if (p / 'raw_html').exists() else 0
        assets_count = len(list((p / 'assets').rglob('*.*'))) if (p / 'assets').exists() else 0
        md_count = len(list((p / 'content').rglob('*.md'))) if (p / 'content').exists() else 0
        logger.info(f"  [{idx}] {p.name} | HTMLs: {pages_count} | Assets: {assets_count} | Markdown: {md_count}")
    return projects

def show_project_status():
    """Displays stats of the currently active project."""
    mode_str = "Web en Vivo (Live Web)" if config.IS_LIVE_MODE else f"Archivo Historico (Wayback: {config.CURRENT_TIMESTAMP})"
    logger.info(f"=== ESTADO DEL PROYECTO: {config.CURRENT_DOMAIN} ===")
    logger.info(f"  Modo:             {mode_str}")
    logger.info(f"  URL Objetivo:     {config.CURRENT_URL}")
    logger.info(f"  Directorio:       {config.PROJECT_DATA_DIR}")
    if not config.IS_LIVE_MODE:
        logger.info(f"  Wayback Prefix:   {config.WAYBACK_RAW_PREFIX}")
    
    pages = len(list(config.RAW_HTML_DIR.rglob('*.html'))) if config.RAW_HTML_DIR.exists() else 0
    assets = len(list(config.ASSETS_DIR.rglob('*.*'))) if config.ASSETS_DIR.exists() else 0
    mds = len(list(config.CONTENT_DIR.rglob('*.md'))) if config.CONTENT_DIR.exists() else 0
    
    logger.info(f"  Paginas HTML:     {pages}")
    logger.info(f"  Archivos Assets:  {assets}")
    logger.info(f"  Archivos Markdown:{mds}")
    logger.info("============================================")

def main():
    parser = argparse.ArgumentParser(
        description='Universal Web Archive & Live Scraper Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  # Archivar un sitio historico desde Wayback/Archive.ph:
  python run_pipeline.py --url https://ejemplo.com --all

  # Descargar un sitio web en vivo directamente (Live Web):
  python run_pipeline.py --url https://ejemplo.com --live --all

  # Archivar con fecha historica especifica de Wayback:
  python run_pipeline.py --url https://ejemplo.com --date 20200512 --all

  # Ejecutar pasos individuales:
  python run_pipeline.py --url https://ejemplo.com --step 1   # Rastreo BFS y descubrimiento
  python run_pipeline.py --url https://ejemplo.com --step 2   # Inventario de CSS/JS/Fotos
  python run_pipeline.py --url https://ejemplo.com --step 3   # Descarga masiva de HTMLs
  python run_pipeline.py --url https://ejemplo.com --step 4   # Descarga masiva de Assets
  python run_pipeline.py --url https://ejemplo.com --step 5   # Conversion a Markdown y DB

  # Previsualizar la web archivada en el navegador local:
  python run_pipeline.py --url https://ejemplo.com --serve
  python run_pipeline.py --serve --port 8080

  # Listar proyectos guardados:
  python run_pipeline.py --list
        """
    )
    
    parser.add_argument('--url', type=str, help='URL del sitio web a scrappear o archivar (ej: https://ejemplo.com)')
    parser.add_argument('--live', action='store_true', help='Modo web en vivo: descarga directamente del servidor activo en lugar de Wayback / Archive.ph')
    parser.add_argument('--date', '--timestamp', dest='date', type=str, help='Timestamp snapshot de Wayback (ej: 20230711 o 20230711124744). Si se omite, CDX detecta el mas reciente.')
    parser.add_argument('--depth', type=int, default=3, help='Profundidad maxima de rastreo recursivo BFS (por defecto: 3)')
    parser.add_argument('--max-pages', type=int, default=5000, help='Limite maximo de paginas a rastrear (por defecto: 5000)')
    parser.add_argument('--step', type=int, choices=[1, 2, 3, 4, 5], help='Ejecutar un paso especifico (1: Crawler, 2: Assets, 3: HTMLs, 4: Descarga Assets, 5: Markdown)')
    parser.add_argument('--all', action='store_true', help='Ejecutar pasos 1 al 5 secuencialmente')
    parser.add_argument('--serve', action='store_true', help='Iniciar servidor local de previsualizacion proxy')
    parser.add_argument('--port', type=int, default=8080, help='Puerto para el servidor de previsualizacion (por defecto: 8080)')
    parser.add_argument('--list', action='store_true', help='Listar proyectos guardados en data/')
    parser.add_argument('--status', action='store_true', help='Mostrar resumen del proyecto activo')

    args = parser.parse_args()

    if args.list:
        list_existing_projects()
        return

    # Initialize or load project
    if args.url:
        config.init_project(args.url, custom_timestamp=args.date, depth=args.depth, is_live=args.live)
    else:
        active = config.load_active_project()
        if active and args.live:
            config.init_project(active['target_url'], custom_timestamp=args.date, depth=args.depth, is_live=True)
        if not active and not args.serve:
            logger.warning("No se proporciono --url y no hay ningun proyecto activo guardado.")
            list_existing_projects()
            logger.info("Usa: python run_pipeline.py --url https://ejemplo.com --all")
            return

    if args.status:
        show_project_status()
        if not (args.step or args.all or args.serve):
            return

    # Step Execution
    if args.step == 1 or args.all:
        logger.info(f">>> PASO 1: Rastreo BFS y descubrimiento de URLs para {config.CURRENT_DOMAIN}...")
        step1 = importlib.import_module('01_crawler')
        step1.crawl_site_bfs(config.CURRENT_URL, max_depth=args.depth, max_pages=args.max_pages)

    if args.step == 2 or args.all:
        logger.info(f">>> PASO 2: Descubriendo assets estaticos (CSS, JS, Fuentes, Imagenes)...")
        step2 = importlib.import_module('02_discover_assets')
        step2.main()

    if args.step == 3 or args.all:
        logger.info(f">>> PASO 3: Descargando paginas HTML en {config.RAW_HTML_DIR}...")
        step3 = importlib.import_module('03_download_html')
        step3.download_all_pages()

    if args.step == 4 or args.all:
        logger.info(f">>> PASO 4: Descargando archivos estaticos en {config.ASSETS_DIR}...")
        step4 = importlib.import_module('04_download_assets')
        step4.download_all_assets()

    if args.step == 5 or args.all:
        logger.info(f">>> PASO 5: Parseando contenido heuristico a Markdown y JSON en {config.CONTENT_DIR}...")
        step5 = importlib.import_module('05_parse_articles')
        step5.export_all()

    if args.serve:
        logger.info(f">>> Iniciando servidor de previsualizacion en http://localhost:{args.port}/...")
        preview = importlib.import_module('preview_server')
        preview.run_server(port=args.port)

    if not args.step and not args.all and not args.serve and not args.status:
        show_project_status()
        logger.info("Para ejecutar el pipeline completo usa: python run_pipeline.py --all")

if __name__ == '__main__':
    main()
