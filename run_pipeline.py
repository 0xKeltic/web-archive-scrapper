import sys
import argparse
from loguru import logger

def main():
    parser = argparse.ArgumentParser(description='Criminalia.es Web Archive Scraper Pipeline')
    parser.add_argument('--step', type=int, choices=[1, 2, 3, 4, 5], help='Ejecutar un paso especifico (1: Mapeo, 2: Assets, 3: HTMLs, 4: Descarga Assets, 5: Parseo)')
    parser.add_argument('--all', action='store_true', help='Ejecutar todos los pasos secuencialmente')
    
    args = parser.parse_args()
    
    if args.step == 1 or args.all:
        logger.info('>>> PASO 1: Descubriendo mapa del sitio e indices...')
        import importlib
        step1 = importlib.import_module('01_discover_sitemap')
        step1.main()
        
    if args.step == 2 or args.all:
        logger.info('>>> PASO 2: Descubriendo assets (CSS, JS, Fuentes, Imagenes)...')
        import importlib
        step2 = importlib.import_module('02_discover_assets')
        step2.main()
        
    if args.step == 3 or args.all:
        logger.info('>>> PASO 3: Descargando paginas HTML...')
        import importlib
        step3 = importlib.import_module('03_download_html')
        step3.download_articles()
        
    if args.step == 4 or args.all:
        logger.info('>>> PASO 4: Descargando archivos estaticos (CSS, JS, Imagenes)...')
        import importlib
        step4 = importlib.import_module('04_download_assets')
        step4.download_all_assets()
        
    if args.step == 5 or args.all:
        logger.info('>>> PASO 5: Parseando y exportando a Markdown y JSON...')
        import importlib
        step5 = importlib.import_module('05_parse_articles')
        step5.export_all()
        
    if not args.step and not args.all:
        logger.info('Pipeline de Scraping de Criminalia.es')
        logger.info('Uso:')
        logger.info('  python run_pipeline.py --step 1   (Mapear todos los articulos e indices)')
        logger.info('  python run_pipeline.py --step 2   (Descubrir todos los CSS, JS e imagenes)')
        logger.info('  python run_pipeline.py --step 3   (Descargar todos los HTMLs)')
        logger.info('  python run_pipeline.py --step 4   (Descargar CSS, JS y fotos)')
        logger.info('  python run_pipeline.py --step 5   (Convertir a Markdown y JSON)')
        logger.info('  python run_pipeline.py --all      (Ejecutar todo de inicio a fin)')

if __name__ == '__main__':
    main()
