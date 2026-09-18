# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from loguru import logger
import config

STATIC_EXTENSIONS = (
    '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico',
    '.woff', '.woff2', '.ttf', '.eot', '.otf', '.mp3', '.mp4', '.pdf'
)

def discover_assets_from_cdx(domain: str) -> dict:
    """Queries Wayback CDX API for all archived static assets under the target domain."""
    logger.info(f'Consultando API CDX de Wayback para catalogar assets estaticos de {domain}...')
    assets = {
        'css': set(),
        'js': set(),
        'images': set(),
        'fonts': set(),
        'other': set()
    }
    
    try:
        # Query CDX for original URLs under the domain
        query_url = f'{config.CDX_API_URL}?url={domain}/*&fl=original,mimetype&collapse=urlkey&output=json'
        resp = config.SESSION.get(query_url, timeout=25)
        if resp.status_code == 200:
            data = resp.json()
            # First row is header
            for row in data[1:]:
                if len(row) < 1:
                    continue
                orig_url = row[0].split('?')[0].strip()
                parsed = urlparse(orig_url)
                ext = '.' + parsed.path.rsplit('.', 1)[-1].lower() if '.' in parsed.path else ''
                
                if ext == '.css':
                    assets['css'].add(orig_url)
                elif ext == '.js':
                    assets['js'].add(orig_url)
                elif ext in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico'):
                    assets['images'].add(orig_url)
                elif ext in ('.woff', '.woff2', '.ttf', '.eot', '.otf'):
                    assets['fonts'].add(orig_url)
                elif ext in STATIC_EXTENSIONS:
                    assets['other'].add(orig_url)
                    
            total_cdx = sum(len(v) for v in assets.values())
            logger.info(f'API CDX devolvio {total_cdx} assets estaticos unicos.')
    except Exception as e:
        logger.warning(f'No se pudo consultar CDX para assets ({e}). Se continuara con el escaneo de HTML.')
        
    return assets

def scan_html_for_assets(domain: str, assets: dict) -> dict:
    """Scans all locally downloaded or cataloged HTMLs for referenced static assets."""
    raw_dir = config.RAW_HTML_DIR
    if not raw_dir.exists():
        return assets
        
    html_files = list(raw_dir.rglob('*.html'))
    if not html_files:
        return assets

    logger.info(f'Escaneando {len(html_files)} archivos HTML locales para extraer recursos...')
    
    for html_file in html_files:
        try:
            rel_to_raw = html_file.relative_to(raw_dir).as_posix()
            base_page_url = f"https://{domain}/{rel_to_raw}"
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
                
                # 1. Stylesheets
                for link in soup.find_all('link', rel=lambda r: r and 'stylesheet' in r):
                    href = link.get('href')
                    if href:
                        clean = urljoin(base_page_url, href)
                        assets['css'].add(clean)
                        
                # 2. Scripts
                for script in soup.find_all('script', src=True):
                    src = script.get('src')
                    if src:
                        clean = urljoin(base_page_url, src)
                        assets['js'].add(clean)
                        
                # 3. Images
                for img in soup.find_all('img'):
                    for attr in ('src', 'data-src', 'data-lazy-src'):
                        src = img.get(attr)
                        if src and not src.startswith('data:'):
                            clean = urljoin(base_page_url, src)
                            assets['images'].add(clean)
                            
                # 4. Favicons
                for icon in soup.find_all('link', rel=lambda r: r and ('icon' in r or 'shortcut' in r)):
                    href = icon.get('href')
                    if href and not href.startswith('data:'):
                        clean = urljoin(base_page_url, href)
                        assets['images'].add(clean)
        except Exception:
            pass
            
    return assets

def main():
    domain = config.CURRENT_DOMAIN
    if config.IS_LIVE_MODE:
        logger.info(f'Modo web en vivo activo: omitiendo API CDX de Wayback. Descubriendo assets desde HTMLs...')
        assets = {
            'css': set(),
            'js': set(),
            'images': set(),
            'fonts': set(),
            'other': set()
        }
    else:
        assets = discover_assets_from_cdx(domain)

    assets = scan_html_for_assets(domain, assets)
    
    manifest_file = config.MANIFESTS_DIR / 'assets_manifest.json'
    export_data = {
        'domain': domain,
        'timestamp': config.CURRENT_TIMESTAMP,
        'is_live': config.IS_LIVE_MODE,
        'total_assets': sum(len(v) for v in assets.values()),
        'assets': {k: sorted(list(v)) for k, v in assets.items()}
    }
    
    with open(manifest_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
        
    logger.success(f'Inventario de assets completado: {export_data["total_assets"]} recursos guardados en {manifest_file}')

if __name__ == '__main__':
    main()
