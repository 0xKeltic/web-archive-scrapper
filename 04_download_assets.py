import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from loguru import logger
import config

def get_relative_asset_path(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.lstrip('/')
    return path

def download_asset(url: str, is_binary: bool = True):
    rel_path = get_relative_asset_path(url)
    if not rel_path:
        return None
        
    target_file = config.ASSETS_DIR / rel_path
    if target_file.exists() and target_file.stat().st_size > 0:
        return target_file
        
    target_file.parent.mkdir(parents=True, exist_ok=True)
    
    wayback_url = config.get_wayback_raw_url(url)
    data = config.fetch_with_retry(wayback_url, is_binary=is_binary)
    if data:
        with open(target_file, 'wb') as f:
            f.write(data)
        return target_file
    return None

def scan_html_files_for_images():
    logger.info('Escaneando todos los HTMLs descargados para extraer fotografias e imagenes de uploads...')
    images = set()
    for folder in [config.RAW_HTML_DIR / 'asesino', config.RAW_HTML_DIR / 'material', config.RAW_HTML_DIR / 'actualidad']:
        if not folder.exists():
            continue
        for html_file in folder.glob('*.html'):
            try:
                with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                    soup = BeautifulSoup(f.read(), 'html.parser')
                    for img in soup.find_all('img'):
                        for attr in ('src', 'data-src', 'data-lazy-src'):
                            src = img.get(attr)
                            if src and 'lazy_placeholder' not in src and 'criminalia.es' in src:
                                clean = src.split('?')[0].strip()
                                if clean.startswith('//'):
                                    clean = 'https:' + clean
                                images.add(clean)
            except Exception:
                pass
    logger.info(f'Fotografias encontradas en HTMLs locales: {len(images)}')
    return images

def download_all_assets():
    manifest_file = config.MANIFESTS_DIR / 'assets_manifest.json'
    missing_file = config.MANIFESTS_DIR / 'missing_assets.json'
    
    missing_assets = set()
    if missing_file.exists():
        try:
            with open(missing_file, 'r', encoding='utf-8') as f:
                missing_assets = set(json.load(f))
        except Exception:
            pass

    manifest_assets = set()
    if manifest_file.exists():
        with open(manifest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for group, urls in data.get('assets', {}).items():
                manifest_assets.update(urls)

    # Combine with all images discovered in HTMLs
    html_images = scan_html_files_for_images()
    all_target_urls = sorted(manifest_assets.union(html_images))
    
    total = len(all_target_urls)
    logger.info(f'Iniciando descarga de {total} assets (CSS, JS, Fuentes, Fotografias)...')
    logger.info(f'Memoria de cache: {len(missing_assets)} recursos marcados previamente como no archivados (404).')
    
    css_extra_assets = set()
    success = 0
    skipped = 0
    failed = 0
    
    for idx, url in enumerate(all_target_urls, 1):
        rel_path = get_relative_asset_path(url)
        target_file = config.ASSETS_DIR / rel_path
        
        if target_file.exists() and target_file.stat().st_size > 0:
            skipped += 1
            continue
            
        if rel_path in missing_assets:
            skipped += 1
            continue
            
        logger.info(f'[{idx}/{total}] Descargando: {rel_path}...')
        res = download_asset(url, is_binary=True)
        if res:
            success += 1
            if url.endswith('.css'):
                try:
                    with open(res, 'r', encoding='utf-8', errors='ignore') as f:
                        css_text = f.read()
                        found = re.findall(r'url\([\"\x27]?([^\"\'\)]+)[\"\x27]?\)', css_text)
                        for item in found:
                            if not item.startswith('data:'):
                                base_css_dir = url.rsplit('/', 1)[0]
                                if item.startswith('/'):
                                    full_asset = f'https://criminalia.es{item}'
                                elif item.startswith('http'):
                                    full_asset = item
                                else:
                                    full_asset = f'{base_css_dir}/{item}'
                                css_extra_assets.add(full_asset)
                except Exception:
                    pass
        else:
            failed += 1
            missing_assets.add(rel_path)
            if failed % 25 == 0:
                try:
                    with open(missing_file, 'w', encoding='utf-8') as f:
                        json.dump(sorted(list(missing_assets)), f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
        time.sleep(0.25)
        
    if css_extra_assets:
        logger.info(f'Descargando {len(css_extra_assets)} assets extra referenciados en CSS...')
        for ext_url in css_extra_assets:
            download_asset(ext_url, is_binary=True)
            time.sleep(0.25)
            
    try:
        with open(missing_file, 'w', encoding='utf-8') as f:
            json.dump(sorted(list(missing_assets)), f, indent=2, ensure_ascii=False)
    except Exception:
        pass
        
    logger.success(f'Descarga de assets finalizada: {success} nuevos, {skipped} ya existian, {failed} fallidos.')

if __name__ == '__main__':
    download_all_assets()
