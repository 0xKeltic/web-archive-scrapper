# -*- coding: utf-8 -*-
import json
import re
import time
import xml.etree.ElementTree as ET
from collections import deque
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from loguru import logger
import config

SITEMAP_CANDIDATES = [
    '/sitemap.xml',
    '/sitemap_index.xml',
    '/sitemap-posts.xml',
    '/wp-sitemap.xml',
    '/robots.txt',
]

EXCLUDED_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico',
    '.css', '.js', '.woff', '.woff2', '.ttf', '.eot',
    '.pdf', '.zip', '.rar', '.tar', '.gz', '.mp3', '.mp4', '.avi', '.xml'
}

def is_internal_url(url: str, domain: str) -> bool:
    try:
        parsed = urlparse(url)
        netloc = (parsed.netloc or '').lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        return netloc == domain or netloc == ''
    except Exception:
        return False

def clean_extracted_url(base_url: str, href: str) -> str:
    if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
        return ''
    full_url = urljoin(base_url, href)
    # Strip fragment and normalize
    clean = full_url.split('#')[0].strip()
    return clean

def parse_xml_sitemap(xml_text: str, domain: str) -> set:
    urls = set()
    try:
        root = ET.fromstring(xml_text)
        # Namespaces handling
        for elem in root.iter():
            if elem.tag.endswith('loc') and elem.text:
                loc = elem.text.strip()
                if is_internal_url(loc, domain):
                    urls.add(loc)
    except Exception as e:
        logger.debug(f'Error parsing XML sitemap: {e}')
    return urls

def discover_sitemaps(domain: str) -> set:
    source_label = "live" if config.IS_LIVE_MODE else "in Wayback"
    logger.info(f'Searching for sitemaps and robots.txt {source_label} for {domain}...')
    discovered = set()
    
    for path in SITEMAP_CANDIDATES:
        test_url = f'https://{domain}{path}'
        data = config.fetch_with_retry(test_url)
        if not data:
            continue
            
        if path == '/robots.txt':
            for line in data.splitlines():
                if line.lower().startswith('sitemap:'):
                    sitemap_url = line.split(':', 1)[1].strip()
                    s_data = config.fetch_with_retry(sitemap_url)
                    if s_data:
                        found = parse_xml_sitemap(s_data, domain)
                        discovered.update(found)
                        logger.info(f'Found {len(found)} URLs from robots.txt -> {sitemap_url}')
        elif '<?xml' in data or '<urlset' in data or '<sitemapindex' in data:
            found = parse_xml_sitemap(data, domain)
            discovered.update(found)
            logger.info(f'Found {len(found)} URLs in {path}')
            
    return discovered

def crawl_site_bfs(start_url: str, max_depth: int = 3, max_pages: int = 5000):
    domain = config.CURRENT_DOMAIN
    start_url = config.clean_target_url(start_url)
    
    logger.info(f'Starting BFS crawler for {start_url} (Max depth: {max_depth})...')
    
    # Check sitemaps first
    sitemap_urls = discover_sitemaps(domain)
    
    visited = set()
    queue = deque()
    
    # Add start URL
    queue.append((start_url, 0))
    
    # Also seed with sitemap URLs if any
    for s_url in sitemap_urls:
        if s_url != start_url:
            queue.append((s_url, 1))

    pages_catalog = []

    try:
        while queue and len(visited) < max_pages:
            current_url, depth = queue.popleft()
            clean_url = current_url.split('#')[0].rstrip('/')
            if not clean_url:
                clean_url = current_url

            if clean_url in visited:
                continue

            visited.add(clean_url)
            
            parsed = urlparse(clean_url)
            ext = '.' + parsed.path.rsplit('.', 1)[-1].lower() if '.' in parsed.path else ''
            if ext in EXCLUDED_EXTENSIONS:
                continue

            logger.info(f'[{len(visited)}] [Depth {depth}] Crawling: {clean_url}')
            
            rel_path = config.url_to_relative_path(clean_url)
            target_file = config.RAW_HTML_DIR / rel_path

            html = None
            if target_file.exists() and target_file.stat().st_size > 200:
                try:
                    with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
                        html = f.read()
                    logger.debug(f'[Local Cache] Using local HTML: {rel_path}')
                except Exception:
                    html = None

            if not html:
                html = config.fetch_with_retry(clean_url)
                if not html or len(html) < 200:
                    continue
                try:
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(target_file, 'w', encoding='utf-8', errors='ignore') as f:
                        f.write(html)
                except Exception as e:
                    logger.debug(f'Error saving local HTML for {clean_url}: {e}')
                time.sleep(0.15)

            title = ''
            try:
                soup = BeautifulSoup(html, 'html.parser')
                t_tag = soup.find('title')
                if t_tag:
                    title = t_tag.get_text(strip=True)
                    
                # If within depth limit, extract new links
                if depth < max_depth:
                    for a in soup.find_all('a', href=True):
                        candidate = clean_extracted_url(clean_url, a['href'])
                        if candidate and is_internal_url(candidate, domain):
                            c_clean = candidate.split('#')[0].rstrip('/')
                            if c_clean not in visited:
                                c_ext = '.' + urlparse(c_clean).path.rsplit('.', 1)[-1].lower() if '.' in urlparse(c_clean).path else ''
                                if c_ext not in EXCLUDED_EXTENSIONS:
                                    queue.append((candidate, depth + 1))
            except Exception:
                pass

            pages_catalog.append({
                'url': clean_url,
                'relative_path': rel_path,
                'title': title,
                'depth': depth,
            })
            
            # Periodic auto-checkpoint every 100 pages
            if len(pages_catalog) % 100 == 0:
                manifest_file = config.MANIFESTS_DIR / 'pages_manifest.json'
                manifest_data = {
                    'target_url': config.CURRENT_URL,
                    'domain': config.CURRENT_DOMAIN,
                    'timestamp': config.CURRENT_TIMESTAMP,
                    'is_live': config.IS_LIVE_MODE,
                    'total_pages': len(pages_catalog),
                    'pages': pages_catalog,
                }
                try:
                    manifest_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(manifest_file, 'w', encoding='utf-8') as f:
                        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
            
            time.sleep(0.2)
    except KeyboardInterrupt:
        logger.warning(f'Crawl paused by user ({len(pages_catalog)} pages cataloged). Saving checkpoint...')

    # Export manifest
    manifest_file = config.MANIFESTS_DIR / 'pages_manifest.json'
    manifest_data = {
        'target_url': config.CURRENT_URL,
        'domain': config.CURRENT_DOMAIN,
        'timestamp': config.CURRENT_TIMESTAMP,
        'is_live': config.IS_LIVE_MODE,
        'total_pages': len(pages_catalog),
        'pages': pages_catalog,
    }
    with open(manifest_file, 'w', encoding='utf-8') as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    logger.success(f'Crawl finished: {len(pages_catalog)} pages discovered saved to {manifest_file}')
    return pages_catalog

def main():
    crawl_site_bfs(config.CURRENT_URL, max_depth=3)

if __name__ == '__main__':
    main()
