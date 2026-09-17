# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from loguru import logger
import trafilatura
from markdownify import markdownify as md
import config

def rewrite_images_to_local_assets(markdown_text: str, domain: str) -> str:
    """Converts image links in markdown pointing to the original domain into /assets/<path>."""
    def replacer(match):
        alt = match.group(1)
        src = match.group(2).strip()
        clean = src.split('?')[0]
        
        # Check if it belongs to domain or starts with /
        if domain in clean or clean.startswith('/'):
            parsed = urlparse(clean)
            rel = parsed.path.lstrip('/')
            return f'![{alt}](/assets/{rel})'
        return match.group(0)

    pattern = r'!\[([^\]]*)\]\(([^\)]+)\)'
    return re.sub(pattern, replacer, markdown_text)

def extract_article_universal(html: str, file_path: Path) -> dict:
    """Extracts article content and metadata from any HTML using trafilatura with BeautifulSoup fallback."""
    # 1. Trafilatura heuristic extraction
    extracted = trafilatura.bare_extraction(
        html,
        url=f'https://{config.CURRENT_DOMAIN}/{file_path.stem}',
        include_images=True,
        include_links=True,
        include_formatting=True
    )

    soup = BeautifulSoup(html, 'html.parser')
    
    title = ''
    date = ''
    author = ''
    image = ''
    body_md = ''

    if extracted:
        title = extracted.title or ''
        date = extracted.date or ''
        author = extracted.author or ''
        image = extracted.image or ''
        body_md = extracted.text or ''

    # Fallback to BeautifulSoup title
    if not title:
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)
        elif soup.find('title'):
            title = soup.find('title').get_text(strip=True)
        else:
            title = file_path.stem.replace('-', ' ').title()

    # Fallback body conversion using markdownify if trafilatura returned little or nothing
    if not body_md or len(body_md) < 100:
        main_container = soup.find('article') or soup.find('main') or soup.find(id=re.compile(r'content|main|article', re.I)) or soup.find(class_=re.compile(r'content|main|article|post', re.I))
        target_elem = main_container if main_container else soup.body
        if target_elem:
            # Clean scripts and styles
            for tag in target_elem.find_all(['script', 'style', 'noscript', 'iframe', 'form', 'nav']):
                tag.decompose()
            body_md = md(str(target_elem), heading_style='ATX', strip=['script', 'style'])

    # Find featured image fallback
    if not image:
        first_img = soup.find('img')
        if first_img:
            src = first_img.get('src') or first_img.get('data-src')
            if src and not src.startswith('data:'):
                image = config.clean_target_url(src)

    # Clean and rewrite image paths to local assets
    body_md = rewrite_images_to_local_assets(body_md, config.CURRENT_DOMAIN)
    if image:
        rel_img = urlparse(config.clean_target_url(image)).path.lstrip('/')
        local_featured = f'/assets/{rel_img}'
    else:
        local_featured = ''

    slug = file_path.stem
    clean_title = title.replace('"', '\\"')

    return {
        'title': clean_title,
        'slug': slug,
        'date': date,
        'author': author,
        'featured_image': local_featured,
        'content': body_md.strip(),
        'excerpt': body_md[:250].replace('\n', ' ').strip() + '...' if len(body_md) > 250 else body_md.strip()
    }

def export_all():
    raw_dir = config.RAW_HTML_DIR
    if not raw_dir.exists():
        logger.error(f'Directorio de HTMLs no existe: {raw_dir}. Ejecuta primero el paso 3.')
        return

    all_htmls = list(raw_dir.rglob('*.html'))
    total = len(all_htmls)
    logger.info(f'Iniciando extraccion heuristica y exportacion a Markdown de {total} paginas...')

    database = []

    for idx, html_path in enumerate(all_htmls, 1):
        try:
            with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_text = f.read()

            rel_to_raw = html_path.relative_to(raw_dir)
            parsed = extract_article_universal(html_text, html_path)
            
            # Destination markdown path preserving directory hierarchy
            dest_md = config.CONTENT_DIR / rel_to_raw.with_suffix('.md')
            dest_md.parent.mkdir(parents=True, exist_ok=True)

            frontmatter = (
                '---\n'
                f'title: "{parsed["title"]}"\n'
                f'slug: "{parsed["slug"]}"\n'
                f'date: "{parsed["date"]}"\n'
                f'author: "{parsed["author"]}"\n'
                f'featured_image: "{parsed["featured_image"]}"\n'
                f'url: "https://{config.CURRENT_DOMAIN}/{parsed["slug"]}"\n'
                '---\n\n'
            )

            with open(dest_md, 'w', encoding='utf-8') as f:
                f.write(frontmatter + parsed['content'])

            database.append({
                'title': parsed['title'],
                'slug': parsed['slug'],
                'date': parsed['date'],
                'author': parsed['author'],
                'featured_image': parsed['featured_image'],
                'relative_path': str(rel_to_raw.with_suffix('.md')).replace('\\', '/'),
                'excerpt': parsed['excerpt']
            })
        except Exception as e:
            logger.debug(f'Error procesando {html_path}: {e}')

    # Global structured database
    db_file = config.CONTENT_DIR / 'database.json'
    with open(db_file, 'w', encoding='utf-8') as f:
        json.dump(database, f, ensure_ascii=False, indent=2)

    logger.success(f'Exportacion completa: {len(database)} documentos convertidos a Markdown en {config.CONTENT_DIR}')
    logger.info(f'Catalogo global unificado: {db_file}')

def main():
    export_all()

if __name__ == '__main__':
    main()
