# -*- coding: utf-8 -*-
import json
import re
import time
from pathlib import Path
from loguru import logger
import config

def discover_all_standalone_urls():
    """
    Escanea todos los archivos HTML descargados y la portada para encontrar
    TODAS las paginas institucionales, secciones de actualidad por pais,
    articulos de sucesos y noticias independientes.
    """
    urls = set()
    
    seed_pages = [
        '/ultimas-entradas/',
        '/contacto/',
        '/colabora/',
        '/politica-de-cookies/',
        '/actualidad/',
        '/actualidad/espana/',
        '/actualidad/mexico/',
        '/actualidad/argentina/',
        '/actualidad/chile/',
        '/actualidad/colombia/',
        '/actualidad/estados-unidos/',
        '/actualidad/peru/',
        '/actualidad/venezuela/',
        '/actualidad/dinamarca/',
        '/actualidad/australia/',
        '/actualidad/brasil/',
        '/actualidad/francia/',
        '/actualidad/sudafrica/',
    ]
    for p in seed_pages:
        urls.add(p)

    logger.info('Escaneando archivos HTML para descubrir paginas independientes...')
    for html_file in config.RAW_HTML_DIR.glob('**/*.html'):
        try:
            content = html_file.read_text(encoding='utf-8', errors='ignore')
            matches = re.findall(r'href=[\'"]([^\'"]+)[\'"]', content)
            for m in matches:
                if 'criminalia.es' in m or (m.startswith('/') and not m.startswith('//')):
                    clean = re.sub(r'^https?://(?:www\.)?criminalia\.es', '', m).split('?')[0].split('#')[0]
                    if clean and not any(clean.startswith(x) for x in [
                        '/asesino/', '/material/', '/resultados-de-la-busqueda',
                        '/wp-content', '/wp-includes', '/assets', '/wp-criminalia',
                        '/wp-json', '/xmlrpc.php', '/feed', '/comments'
                    ]):
                        if not any(clean.endswith(ext) for ext in ['.css', '.js', '.jpg', '.png', '.gif', '.ico', '.xml', '.rss']):
                            clean = '/' + clean.strip('/') + '/'
                            if clean != '//' and not clean.startswith('/http'):
                                urls.add(clean)
        except Exception:
            pass

    sorted_urls = sorted(urls)
    logger.info(f'Total de URLs independientes descubiertas: {len(sorted_urls)}')
    
    manifest = {
        'total': len(sorted_urls),
        'urls': [{'path': u, 'slug': u.strip('/').replace('/', '_')} for u in sorted_urls]
    }
    manifest_file = config.MANIFESTS_DIR / 'standalone_manifest.json'
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.success(f'Manifiesto guardado en {manifest_file}')
    return manifest['urls']

def download_standalone_pages():
    urls = discover_all_standalone_urls()
    out_dir = config.RAW_HTML_DIR / 'paginas'
    out_dir.mkdir(parents=True, exist_ok=True)
    
    total = len(urls)
    logger.info(f'Iniciando descarga de {total} paginas independientes...')
    
    success = 0
    skipped = 0
    failed = 0
    
    for idx, item in enumerate(urls, 1):
        path = item['path']
        slug = item['slug']
        target_file = out_dir / f'{slug}.html'
        
        if target_file.exists() and target_file.stat().st_size > 500:
            skipped += 1
            continue
            
        logger.info(f'[{idx}/{total}] Descargando: {path} -> {slug}.html...')
        url = f'https://criminalia.es{path}'
        data = config.fetch_with_retry(url)
        if data and len(data) > 300:
            target_file.write_text(data, encoding='utf-8')
            success += 1
        else:
            failed += 1
            logger.warning(f'No se pudo descargar {path}')
            
        time.sleep(0.3)
        
    logger.success(f'Descarga finalizada: {success} nuevas, {skipped} ya existian, {failed} no encontradas.')

if __name__ == '__main__':
    download_standalone_pages()
