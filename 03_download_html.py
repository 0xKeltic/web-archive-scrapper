import json
import time
from bs4 import BeautifulSoup
from loguru import logger
import config

def download_articles():
    manifest_path = config.MANIFESTS_DIR / 'articles_manifest.json'
    if not manifest_path.exists():
        logger.error('No se encontro articles_manifest.json. Ejecuta primero 01_discover_sitemap.py')
        return

    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    articles = manifest.get('articles', [])
    actualidad = manifest.get('actualidad', [])
    
    total = len(articles) + len(actualidad)
    logger.info(f'Iniciando descarga de {total} paginas HTML...')

    success = 0
    skipped = 0
    failed = 0
    
    galleries_found = set()

    for idx, art in enumerate(articles, 1):
        slug = art.get('slug')
        url = art.get('url')
        name = art.get('name', slug)
        target_file = config.RAW_HTML_DIR / 'asesino' / f'{slug}.html'

        if target_file.exists() and target_file.stat().st_size > 1000:
            skipped += 1
            try:
                with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
                    soup = BeautifulSoup(f.read(), 'html.parser')
                    for a in soup.find_all('a', href=lambda h: h and '/material/' in h):
                        galleries_found.add(a['href'])
            except Exception:
                pass
            continue

        wayback_url = config.get_wayback_raw_url(url)
        logger.info(f'[{idx}/{total}] Descargando articulo: {name} ({slug})...')
        
        html = config.fetch_with_retry(wayback_url)
        if html and len(html) > 500:
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(html)
            success += 1
            
            # Scan for /material/ photo galleries
            soup = BeautifulSoup(html, 'html.parser')
            for a in soup.find_all('a', href=lambda h: h and '/material/' in h):
                galleries_found.add(a['href'])
        else:
            failed += 1
            logger.warning(f'Fallo al descargar {slug}')

        time.sleep(0.35)

    # Download discovered galleries
    logger.info(f'Descargando {len(galleries_found)} galerias de fotos encontradas...')
    for gal_url in galleries_found:
        gal_url_clean = gal_url.split('?')[0].rstrip('/') + '/'
        slug = [p for p in gal_url_clean.split('/') if p][-1]
        target_file = config.RAW_HTML_DIR / 'material' / f'{slug}.html'
        
        if target_file.exists() and target_file.stat().st_size > 1000:
            continue
            
        wayback_url = config.get_wayback_raw_url(gal_url_clean)
        html = config.fetch_with_retry(wayback_url)
        if html and len(html) > 500:
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(html)
        time.sleep(0.35)

    # Download actualidad
    for idx, act in enumerate(actualidad, 1):
        slug = act.get('slug')
        url = act.get('url')
        target_file = config.RAW_HTML_DIR / 'actualidad' / f'{slug}.html'
        
        if target_file.exists() and target_file.stat().st_size > 1000:
            continue
            
        wayback_url = config.get_wayback_raw_url(url)
        logger.info(f'[Actualidad {idx}/{len(actualidad)}] Descargando: {slug}...')
        html = config.fetch_with_retry(wayback_url)
        if html and len(html) > 500:
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(html)
        time.sleep(0.35)

    logger.success(f'Descargas completadas: {success} nuevas, {skipped} ya existian, {failed} fallidas.')

if __name__ == '__main__':
    download_articles()
