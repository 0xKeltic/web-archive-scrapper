# -*- coding: utf-8 -*-
import json
import time
from pathlib import Path
from loguru import logger
import config

def download_all_pages():
    manifest_file = config.MANIFESTS_DIR / 'pages_manifest.json'
    if not manifest_file.exists():
        logger.error(f'No se encontro {manifest_file}. Ejecuta primero el paso 1 (01_crawler.py)')
        return

    with open(manifest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    pages = data.get('pages', [])
    total = len(pages)
    logger.info(f'Iniciando descarga de {total} paginas HTML para {config.CURRENT_DOMAIN}...')

    missing_file = config.MANIFESTS_DIR / 'missing_pages.json'
    missing_pages = set()
    if missing_file.exists():
        try:
            with open(missing_file, 'r', encoding='utf-8') as f:
                missing_pages = set(json.load(f))
        except Exception:
            pass

    success = 0
    skipped = 0
    failed = 0

    for idx, item in enumerate(pages, 1):
        url = item.get('url')
        rel_path = item.get('relative_path') or config.url_to_relative_path(url)
        target_file = config.RAW_HTML_DIR / rel_path

        if target_file.exists() and target_file.stat().st_size > 200:
            skipped += 1
            continue

        if url in missing_pages:
            skipped += 1
            continue

        logger.info(f'[{idx}/{total}] Descargando pagina: {rel_path}...')
        html = config.fetch_with_retry(url)
        
        if html and len(html) > 200:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            with open(target_file, 'w', encoding='utf-8', errors='ignore') as f:
                f.write(html)
            success += 1
        else:
            failed += 1
            missing_pages.add(url)
            if failed % 20 == 0:
                try:
                    with open(missing_file, 'w', encoding='utf-8') as f:
                        json.dump(sorted(list(missing_pages)), f, indent=2, ensure_ascii=False)
                except Exception:
                    pass

        time.sleep(0.2)

    try:
        with open(missing_file, 'w', encoding='utf-8') as f:
            json.dump(sorted(list(missing_pages)), f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    logger.success(f'Descarga de paginas finalizada: {success} nuevas, {skipped} ya existian, {failed} fallidas.')

def main():
    download_all_pages()

if __name__ == '__main__':
    main()
