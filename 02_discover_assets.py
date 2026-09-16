import json
import re
import time
import requests
from bs4 import BeautifulSoup
from loguru import logger
import config

def extract_assets_from_html(html_text: str, base_url: str = 'https://criminalia.es'):
    assets = set()
    soup = BeautifulSoup(html_text, 'html.parser')
    
    # CSS
    for link in soup.find_all('link', rel=lambda r: r and ('stylesheet' in r or 'icon' in r)):
        href = link.get('href')
        if href:
            assets.add(href)
            
    # JS
    for script in soup.find_all('script', src=True):
        src = script.get('src')
        if src:
            assets.add(src)
            
    # Images
    for img in soup.find_all('img'):
        for attr in ('src', 'data-src', 'data-lazy-src'):
            val = img.get(attr)
            if val and not val.startswith('data:'):
                assets.add(val)
                
    # Normalize
    cleaned = set()
    for a in assets:
        a = a.split('?')[0].strip()
        if a.startswith('//'):
            a = 'https:' + a
        elif a.startswith('/'):
            a = f'{base_url}{a}'
        if 'criminalia.es' in a:
            cleaned.add(a)
    return cleaned

def query_cdx_for_assets():
    endpoints = [
        'criminalia.es/wp-content/themes/*',
        'criminalia.es/wp-content/plugins/*',
        'criminalia.es/wp-content/uploads/*'
    ]
    cdx_assets = set()
    
    logger.info('Consultando API CDX de Web Archive para capturar todos los archivos estaticos...')
    for path_pattern in endpoints:
        cdx_url = f'https://web.archive.org/cdx/search/cdx?url={path_pattern}&output=json&fl=original,mimetype&filter=statuscode:200&collapse=urlkey&limit=10000'
        logger.info(f'Consultando CDX para: {path_pattern}...')
        try:
            resp = config.SESSION.get(cdx_url, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if len(data) > 1:
                    headers = data[0]
                    rows = data[1:]
                    logger.success(f'  Encontrados {len(rows)} archivos en {path_pattern}')
                    for r in rows:
                        orig = r[0].split('?')[0]
                        cdx_assets.add(orig)
            else:
                logger.warning(f'CDX devolvio status {resp.status_code} para {path_pattern}')
        except Exception as e:
            logger.warning(f'No se pudo consultar CDX para {path_pattern} ({e}). Se continuara con assets del HTML.')
        time.sleep(2)
        
    return cdx_assets

def main():
    discovered_assets = set()
    
    # 1. Scrape assets from homepage
    logger.info('Extrayendo assets de la portada...')
    home_url = config.get_wayback_raw_url('https://criminalia.es/')
    home_html = config.fetch_with_retry(home_url)
    if home_html:
        home_assets = extract_assets_from_html(home_html)
        logger.info(f'Assets encontrados en portada: {len(home_assets)}')
        discovered_assets.update(home_assets)
        
    # 2. Scrape assets from available cached index pages
    for cached_file in (config.RAW_HTML_DIR / 'indices').glob('*.html'):
        try:
            with open(cached_file, 'r', encoding='utf-8', errors='ignore') as f:
                idx_assets = extract_assets_from_html(f.read())
                discovered_assets.update(idx_assets)
        except Exception:
            pass
            
    # 3. Query CDX for all uploads, themes, plugins
    cdx_assets = query_cdx_for_assets()
    discovered_assets.update(cdx_assets)
    
    # Classify assets
    classified = {
        'css': [],
        'js': [],
        'images': [],
        'fonts': [],
        'other': []
    }
    
    for asset in sorted(discovered_assets):
        lower = asset.lower()
        if lower.endswith('.css'):
            classified['css'].append(asset)
        elif lower.endswith('.js'):
            classified['js'].append(asset)
        elif any(lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.ico', '.svg']):
            classified['images'].append(asset)
        elif any(lower.endswith(ext) for ext in ['.woff', '.woff2', '.ttf', '.eot']):
            classified['fonts'].append(asset)
        else:
            classified['other'].append(asset)
            
    manifest = {
        'total_assets': len(discovered_assets),
        'counts': {k: len(v) for k, v in classified.items()},
        'assets': classified
    }
    
    out_file = config.MANIFESTS_DIR / 'assets_manifest.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        
    logger.success('=== MANIFIESTO DE ASSETS GENERADO ===')
    logger.info(f'Total assets: {manifest["total_assets"]}')
    logger.info(f'CSS: {manifest["counts"]["css"]}')
    logger.info(f'JS: {manifest["counts"]["js"]}')
    logger.info(f'Imagenes: {manifest["counts"]["images"]}')
    logger.info(f'Fuentes: {manifest["counts"]["fonts"]}')
    logger.info(f'Otros: {manifest["counts"]["other"]}')
    logger.info(f'Guardado en: {out_file}')

if __name__ == '__main__':
    main()
