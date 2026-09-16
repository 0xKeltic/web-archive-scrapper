import json
import string
import time
from bs4 import BeautifulSoup
from loguru import logger
import config

def discover_from_search_indexes():
    categories = ['hombre', 'mujer', 'crimen']
    letters = list(string.ascii_lowercase)
    articles_map = {}
    
    logger.info(f'Iniciando descubrimiento de indices: {len(letters)} letras x {len(categories)} categorias = {len(letters)*len(categories)} paginas...')
    
    total_queries = len(letters) * len(categories)
    count = 0
    
    for g in categories:
        for l in letters:
            count += 1
            index_url = f'https://criminalia.es/resultados-de-la-busqueda/?l={l}&g={g}'
            cached_file = config.RAW_HTML_DIR / 'indices' / f'{l}_{g}.html'
            
            html = None
            if cached_file.exists():
                with open(cached_file, 'r', encoding='utf-8', errors='ignore') as f:
                    html = f.read()
            else:
                wayback_url = config.get_wayback_raw_url(index_url)
                logger.info(f'[{count}/{total_queries}] Descargando indice: l={l}, g={g}...')
                html = config.fetch_with_retry(wayback_url)
                if html:
                    with open(cached_file, 'w', encoding='utf-8') as f:
                        f.write(html)
                time.sleep(0.4)
            
            if not html:
                continue
                
            soup = BeautifulSoup(html, 'html.parser')
            links = soup.find_all('a', href=lambda h: h and '/asesino/' in h)
            found_in_page = 0
            for a in links:
                href = a.get('href', '').strip()
                if not href.startswith('http'):
                    href = f'https://criminalia.es{href}'
                # normalize url
                href = href.split('?')[0].rstrip('/') + '/'
                
                parts = [p for p in href.split('/') if p]
                if len(parts) >= 2 and parts[-2] == 'asesino':
                    slug = parts[-1]
                else:
                    slug = parts[-1]
                
                name = a.get_text(separator=' ', strip=True)
                if not name or name.lower() in ('leer ms', 'leer mas', 'ver ms', 'ver mas'):
                    continue
                
                if href not in articles_map:
                    articles_map[href] = {
                        'url': href,
                        'slug': slug,
                        'name': name,
                        'category': g,
                        'letter': l
                    }
                    found_in_page += 1
                    
            if found_in_page > 0:
                logger.debug(f'  -> {found_in_page} articulos encontrados en l={l}, g={g}')
                
    logger.success(f'Total articulos unicos encontrados en indices: {len(articles_map)}')
    return articles_map

def discover_actualidad_and_extras(articles_map):
    actualidad_map = {}
    logger.info('Descubriendo articulos de la seccion /actualidad/...')
    
    # Check page 1 to 5 of actualidad
    for page in range(1, 10):
        url = 'https://criminalia.es/actualidad/' if page == 1 else f'https://criminalia.es/actualidad/page/{page}/'
        cached_file = config.RAW_HTML_DIR / 'actualidad' / f'index_page_{page}.html'
        
        html = None
        if cached_file.exists():
            with open(cached_file, 'r', encoding='utf-8', errors='ignore') as f:
                html = f.read()
        else:
            wayback_url = config.get_wayback_raw_url(url)
            html = config.fetch_with_retry(wayback_url)
            if html:
                with open(cached_file, 'w', encoding='utf-8') as f:
                    f.write(html)
            time.sleep(0.5)
            
        if not html:
            break
            
        soup = BeautifulSoup(html, 'html.parser')
        articles = soup.find_all('article')
        if not articles:
            # Fallback: look for entry-title links
            articles = soup.find_all(class_=lambda x: x and 'entry-title' in x)
            
        if not articles:
            logger.info(f'No mas articulos en actualidad (pagina {page}).')
            break
            
        found_in_page = 0
        for art in articles:
            link = art.find('a', href=True)
            if link:
                href = link['href'].split('?')[0].rstrip('/') + '/'
                title = link.get_text(strip=True)
                slug = [p for p in href.split('/') if p][-1]
                if href not in actualidad_map and href not in articles_map:
                    actualidad_map[href] = {
                        'url': href,
                        'slug': slug,
                        'title': title,
                        'category': 'actualidad'
                    }
                    found_in_page += 1
        logger.info(f'Actualidad pagina {page}: {found_in_page} entradas.')
        if found_in_page == 0:
            break
            
    logger.success(f'Total entradas de actualidad encontradas: {len(actualidad_map)}')
    return actualidad_map

def main():
    articles = discover_from_search_indexes()
    actualidad = discover_actualidad_and_extras(articles)
    
    manifest = {
        'total_articles': len(articles),
        'total_actualidad': len(actualidad),
        'by_category': {
            'hombre': len([a for a in articles.values() if a['category'] == 'hombre']),
            'mujer': len([a for a in articles.values() if a['category'] == 'mujer']),
            'crimen': len([a for a in articles.values() if a['category'] == 'crimen']),
            'actualidad': len(actualidad)
        },
        'articles': list(articles.values()),
        'actualidad': list(actualidad.values())
    }
    
    out_file = config.MANIFESTS_DIR / 'articles_manifest.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        
    logger.success(f'=== MANIFIESTO GENERADO EXITOSAMENTE ===')
    logger.info(f'Archivo guardado en: {out_file}')
    logger.info(f'Hombres: {manifest["by_category"]["hombre"]}')
    logger.info(f'Mujeres: {manifest["by_category"]["mujer"]}')
    logger.info(f'Crimenes: {manifest["by_category"]["crimen"]}')
    logger.info(f'Actualidad: {manifest["by_category"]["actualidad"]}')
    logger.info(f'Total contenidos: {manifest["total_articles"] + manifest["total_actualidad"]}')

if __name__ == '__main__':
    main()
