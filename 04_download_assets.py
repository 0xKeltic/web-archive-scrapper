# -*- coding: utf-8 -*-
import json
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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

def download_all_assets(max_workers: int = None):
    manifest_file = config.MANIFESTS_DIR / 'assets_manifest.json'
    missing_file = config.MANIFESTS_DIR / 'missing_assets.json'
    
    if not manifest_file.exists():
        logger.error(f'Manifest not found: {manifest_file}. Please run step 2 first (02_discover_assets.py)')
        return

    if max_workers is None:
        max_workers = 8 if config.IS_LIVE_MODE else 3

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
    logger.info(f'Starting concurrent download of {total} assets (Threads: {max_workers}) for {config.CURRENT_DOMAIN}...')
    logger.info(f'Cache memory: {len(missing_assets)} resources previously recorded as missing (404).')
    
    # Fast pre-filter against local disk cache
    urls_to_download = []
    skipped = 0
    for url in all_target_urls:
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
            
        urls_to_download.append((url, rel_path))

    remaining = len(urls_to_download)
    logger.info(f'Disk check: {skipped} assets already cached locally. {remaining} assets queued to download.')
    
    if remaining == 0:
        logger.success('All assets already downloaded.')
        return

    lock = threading.Lock()
    counter = 0
    success = 0
    failed = 0
    css_extra_assets = set()
    last_log_time = time.time()

    def process_asset(item):
        nonlocal counter, success, failed, last_log_time
        url, rel_path = item
        res = download_asset(url, is_binary=True)
        
        with lock:
            counter += 1
            idx = counter
            if res:
                success += 1
            else:
                failed += 1
                missing_assets.add(rel_path)
            
            now = time.time()
            if idx % 25 == 0 or idx == remaining or (now - last_log_time >= 2.5):
                last_log_time = now
                current_total = skipped + idx
                pct = (current_total / total) * 100
                logger.info(f'[{current_total}/{total}] ({pct:.1f}%) Downloading assets... ({success} new, {skipped} cached, {failed} err)')

            if failed > 0 and failed % 50 == 0:
                try:
                    with open(missing_file, 'w', encoding='utf-8') as f:
                        json.dump(sorted(list(missing_assets)), f, indent=2, ensure_ascii=False)
                except Exception:
                    pass

        if res and url.endswith('.css'):
            try:
                with open(res, 'r', encoding='utf-8', errors='ignore') as f:
                    css_text = f.read()
                    found = re.findall(r'url\([\"\x27]?([^\"\'\)]+)[\"\x27]?\)', css_text)
                    for match in found:
                        if not match.startswith('data:'):
                            full_asset = urljoin(url, match)
                            with lock:
                                css_extra_assets.add(full_asset)
            except Exception:
                pass
        return res

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_asset, item) for item in urls_to_download]
        for fut in as_completed(futures):
            fut.result()
        
    if css_extra_assets:
        logger.info(f'Downloading {len(css_extra_assets)} nested sub-resources discovered in CSS files...')
        css_items = [(u, get_relative_asset_path(u)) for u in css_extra_assets if get_relative_asset_path(u)]
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            css_futures = [executor.submit(process_asset, item) for item in css_items]
            for fut in as_completed(css_futures):
                fut.result()
            
    try:
        with open(missing_file, 'w', encoding='utf-8') as f:
            json.dump(sorted(list(missing_assets)), f, indent=2, ensure_ascii=False)
    except Exception:
        pass
        
    logger.success(f'Asset download finished: {success} newly downloaded, {skipped} already existed, {failed} failed.')

def main():
    download_all_assets()

if __name__ == '__main__':
    main()
