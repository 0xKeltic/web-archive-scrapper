# -*- coding: utf-8 -*-
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse, urljoin
from loguru import logger
import config

def get_relative_asset_path(url: str) -> str:
    clean = config.clean_target_url(url)
    parsed = urlparse(clean)
    path = parsed.path.lstrip('/')
    if not path:
        return ''
    return path

def download_asset(url: str, is_binary: bool = True):
    rel_path = get_relative_asset_path(url)
    if not rel_path:
        return None
        
    target_file = config.ASSETS_DIR / rel_path
    if target_file.exists() and target_file.stat().st_size > 0:
        return target_file
        
    target_file.parent.mkdir(parents=True, exist_ok=True)
    
    data = config.fetch_with_retry(url, is_binary=is_binary)
    if data:
        with open(target_file, 'wb') as f:
            f.write(data)
        return target_file
    return None

def download_all_assets():
    manifest_file = config.MANIFESTS_DIR / 'assets_manifest.json'
    missing_file = config.MANIFESTS_DIR / 'missing_assets.json'
    
    if not manifest_file.exists():
        logger.error(f'No se encontro {manifest_file}. Ejecuta primero el paso 2 (02_discover_assets.py)')
        return

    missing_assets = set()
    if missing_file.exists():
        try:
            with open(missing_file, 'r', encoding='utf-8') as f:
                missing_assets = set(json.load(f))
        except Exception:
            pass

    manifest_assets = set()
    with open(manifest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        for group, urls in data.get('assets', {}).items():
            manifest_assets.update(urls)

    all_target_urls = sorted(list(manifest_assets))
    total = len(all_target_urls)
    logger.info(f'Iniciando descarga de {total} assets (CSS, JS, Fuentes, Imagenes) para {config.CURRENT_DOMAIN}...')
    logger.info(f'Memoria de cache: {len(missing_assets)} recursos marcados previamente como no archivados (404).')
    
    css_extra_assets = set()
    success = 0
    skipped = 0
    failed = 0
    
    for idx, url in enumerate(all_target_urls, 1):
        rel_path = get_relative_asset_path(url)
        if not rel_path:
            continue
            
        target_file = config.ASSETS_DIR / rel_path
        
        if target_file.exists() and target_file.stat().st_size > 0:
            skipped += 1
            continue
            
        if rel_path in missing_assets:
            skipped += 1
            continue
            
        logger.info(f'[{idx}/{total}] Descargando asset: {rel_path}...')
        res = download_asset(url, is_binary=True)
        if res:
            success += 1
            # Discover nested assets in CSS (fonts, background images)
            if url.endswith('.css'):
                try:
                    with open(res, 'r', encoding='utf-8', errors='ignore') as f:
                        css_text = f.read()
                        found = re.findall(r'url\([\"\x27]?([^\"\'\)]+)[\"\x27]?\)', css_text)
                        for item in found:
                            if not item.startswith('data:'):
                                full_asset = urljoin(url, item)
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
        time.sleep(0.2)
        
    if css_extra_assets:
        logger.info(f'Descargando {len(css_extra_assets)} sub-recursos descubiertos en archivos CSS...')
        for ext_url in css_extra_assets:
            download_asset(ext_url, is_binary=True)
            time.sleep(0.2)
            
    try:
        with open(missing_file, 'w', encoding='utf-8') as f:
            json.dump(sorted(list(missing_assets)), f, indent=2, ensure_ascii=False)
    except Exception:
        pass
        
    logger.success(f'Descarga de assets finalizada: {success} nuevos, {skipped} ya existian, {failed} fallidos.')

def main():
    download_all_assets()

if __name__ == '__main__':
    main()
