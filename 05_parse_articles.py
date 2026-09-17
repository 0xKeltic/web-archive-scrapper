import json
import re
from pathlib import Path
from bs4 import BeautifulSoup
from loguru import logger
import config

def clean_html_to_markdown(element) -> str:
    if not element:
        return ''
    
    for tag in element.find_all(['script', 'style', 'iframe', 'noscript', 'form', 'button']):
        tag.decompose()
        
    for h in element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        level = int(h.name[1])
        text = h.get_text(strip=True)
        h_prefix = '#' * level
        h.replace_with('\n\n' + h_prefix + ' ' + text + '\n\n')
        
    for b in element.find_all(['strong', 'b']):
        text = b.get_text()
        if text.strip():
            b.replace_with('**' + text.strip() + '**')
            
    for i in element.find_all(['em', 'i']):
        text = i.get_text()
        if text.strip():
            i.replace_with('*' + text.strip() + '*')
            
    for bq in element.find_all('blockquote'):
        text = bq.get_text(strip=True)
        bq.replace_with('\n\n> ' + text + '\n\n')
        
    for li in element.find_all('li'):
        text = li.get_text(strip=True)
        li.replace_with('\n- ' + text)
        
    for img in element.find_all('img'):
        src = img.get('data-src') or img.get('src') or ''
        alt = img.get('alt') or 'Fotografia'
        if src:
            src_clean = src.split('?')[0]
            if 'criminalia.es/' in src_clean:
                rel = src_clean.split('criminalia.es/')[-1]
                local_path = '/assets/' + rel
            else:
                local_path = src_clean
            img.replace_with('\n\n![' + alt + '](' + local_path + ')\n\n')
            
    for p in element.find_all('p'):
        text = p.get_text().strip()
        if text:
            p.replace_with('\n\n' + text + '\n\n')
            
    text = element.get_text()
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def parse_article(html_path: Path, meta_info: dict) -> dict:
    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    
    h1 = soup.find('h1')
    title = ''
    if h1:
        title = h1.get_text(separator=' ', strip=True)
    if not title:
        title = meta_info.get('name') or html_path.stem.replace('-', ' ').title()
        
    featured_img = ''
    img_container = soup.find(class_=lambda x: x and ('image' in x or 'thumb' in x or 'featured' in x))
    if img_container:
        img_tag = img_container.find('img')
        if img_tag:
            raw_src = img_tag.get('data-src') or img_tag.get('src') or ''
            if 'lazy_placeholder' not in raw_src and raw_src:
                clean_src = raw_src.split('?')[0]
                if 'criminalia.es/' in clean_src:
                    featured_img = '/assets/' + clean_src.split('criminalia.es/')[-1]
                else:
                    featured_img = clean_src

    gallery_slugs = []
    meta_links = soup.find_all(class_=lambda x: x and 'meta' in x)
    for m in meta_links:
        for a in m.find_all('a', href=lambda h: h and '/material/' in h):
            gal_href = a['href'].split('?')[0].rstrip('/') + '/'
            gal_slug = [p for p in gal_href.split('/') if p][-1]
            if gal_slug not in gallery_slugs:
                gallery_slugs.append(gal_slug)

    content_container = soup.find(class_=lambda x: x and ('the-content' in x or 'entry-content' in x or 'post-content' in x))
    markdown_body = clean_html_to_markdown(content_container) if content_container else ''

    slug = html_path.stem
    category = meta_info.get('category', 'crimen')

    return {
        'title': title,
        'slug': slug,
        'category': category,
        'featured_image': featured_img,
        'galleries': gallery_slugs,
        'url': meta_info.get('url', 'https://criminalia.es/asesino/' + slug + '/'),
        'content': markdown_body
    }

def export_all():
    manifest_path = config.MANIFESTS_DIR / 'articles_manifest.json'
    articles_meta = {}
    if manifest_path.exists():
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for a in data.get('articles', []):
                articles_meta[a['slug']] = a

    articles_out = config.CONTENT_DIR / 'articles'
    pages_out = config.CONTENT_DIR / 'pages'
    actualidad_out = config.CONTENT_DIR / 'actualidad'
    for d in (articles_out, pages_out, actualidad_out):
        d.mkdir(parents=True, exist_ok=True)

    database = []

    # 1. Artículos Biográficos (Asesinos)
    articles_dir = config.RAW_HTML_DIR / 'asesino'
    all_htmls = list(articles_dir.glob('*.html')) if articles_dir.exists() else []
    logger.info(f'Iniciando parseo de {len(all_htmls)} articulos biograficos a Markdown...')

    for html_path in all_htmls:
        slug = html_path.stem
        meta = articles_meta.get(slug, {'slug': slug, 'category': 'crimen'})
        parsed = parse_article(html_path, meta)
        database.append({
            'type': 'asesino',
            'title': parsed['title'],
            'slug': parsed['slug'],
            'category': parsed['category'],
            'featured_image': parsed['featured_image'],
            'galleries': parsed['galleries'],
            'url': parsed['url'],
            'excerpt': parsed['content'][:250].replace('\n', ' ') + '...' if len(parsed['content']) > 250 else parsed['content']
        })
        md_file = articles_out / f'{slug}.md'
        clean_title = parsed['title'].replace('\"', '\\\"')
        p_slug = parsed['slug']
        p_cat = parsed['category']
        p_img = parsed['featured_image']
        p_url = parsed['url']
        galleries_json = json.dumps(parsed['galleries'])
        frontmatter = (
            '---\n'
            f'title: "{clean_title}"\n'
            f'type: "asesino"\n'
            f'slug: "{p_slug}"\n'
            f'category: "{p_cat}"\n'
            f'featured_image: "{p_img}"\n'
            f'galleries: {galleries_json}\n'
            f'url: "{p_url}"\n'
            '---\n\n'
        )
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(frontmatter + parsed['content'])

    # 2. Artículos de Actualidad
    actualidad_dir = config.RAW_HTML_DIR / 'actualidad'
    all_act = list(actualidad_dir.glob('*.html')) if actualidad_dir.exists() else []
    logger.info(f'Iniciando parseo de {len(all_act)} secciones de actualidad...')
    for html_path in all_act:
        slug = html_path.stem
        parsed = parse_article(html_path, {'slug': slug, 'category': 'actualidad'})
        database.append({
            'type': 'actualidad',
            'title': parsed['title'],
            'slug': parsed['slug'],
            'category': 'actualidad',
            'featured_image': parsed['featured_image'],
            'galleries': parsed['galleries'],
            'url': f'https://criminalia.es/actualidad/{slug}/',
            'excerpt': parsed['content'][:250].replace('\n', ' ') + '...' if len(parsed['content']) > 250 else parsed['content']
        })
        md_file = actualidad_out / f'{slug}.md'
        clean_title = parsed['title'].replace('"', '\\"')
        p_img = parsed['featured_image']
        frontmatter = (
            '---\n'
            f'title: "{clean_title}"\n'
            'type: "actualidad"\n'
            f'slug: "{slug}"\n'
            'category: "actualidad"\n'
            f'featured_image: "{p_img}"\n'
            f'url: "https://criminalia.es/actualidad/{slug}/"\n'
            '---\n\n'
        )
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(frontmatter + parsed['content'])

    # 3. Páginas Institucionales y Noticias (paginas)
    paginas_dir = config.RAW_HTML_DIR / 'paginas'
    all_pages = list(paginas_dir.glob('*.html')) if paginas_dir.exists() else []
    logger.info(f'Iniciando parseo de {len(all_pages)} paginas institucionales y noticias...')
    for html_path in all_pages:
        slug = html_path.stem
        parsed = parse_article(html_path, {'slug': slug, 'category': 'pagina'})
        database.append({
            'type': 'pagina',
            'title': parsed['title'],
            'slug': parsed['slug'],
            'category': 'pagina',
            'featured_image': parsed['featured_image'],
            'galleries': parsed['galleries'],
            'url': f'https://criminalia.es/{slug}/',
            'excerpt': parsed['content'][:250].replace('\n', ' ') + '...' if len(parsed['content']) > 250 else parsed['content']
        })
        md_file = pages_out / f'{slug}.md'
        clean_title = parsed['title'].replace('"', '\\"')
        p_img = parsed['featured_image']
        frontmatter = (
            '---\n'
            f'title: "{clean_title}"\n'
            'type: "pagina"\n'
            f'slug: "{slug}"\n'
            'category: "pagina"\n'
            f'featured_image: "{p_img}"\n'
            f'url: "https://criminalia.es/{slug}/"\n'
            '---\n\n'
        )
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(frontmatter + parsed['content'])

    db_file = config.CONTENT_DIR / 'database.json'
    with open(db_file, 'w', encoding='utf-8') as f:
        json.dump(database, f, ensure_ascii=False, indent=2)

    logger.success(f'Exportacion completa: {len(database)} documentos procesados ({len(all_htmls)} asesinos, {len(all_act)} actualidad, {len(all_pages)} paginas/noticias).')
    logger.info(f'Directorio de contenido: {config.CONTENT_DIR}')
    logger.info(f'Base de datos global: {db_file}')

if __name__ == '__main__':
    export_all()

