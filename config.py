# -*- coding: utf-8 -*-
import os
import re
import time
import json
import requests
from urllib.parse import urlparse, unquote
from pathlib import Path
from bs4 import BeautifulSoup
from loguru import logger

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

CDX_API_URL = 'https://web.archive.org/cdx/search/cdx'

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate',
}

SESSION = requests.Session()
SESSION.headers.update(DEFAULT_HEADERS)

# Active Project State (Dynamic)
CURRENT_URL = 'https://criminalia.es'
CURRENT_DOMAIN = 'criminalia.es'
DOMAIN_SLUG = 'criminalia.es'
CURRENT_TIMESTAMP = '20230711124744'
WAYBACK_RAW_PREFIX = f'https://web.archive.org/web/{CURRENT_TIMESTAMP}id_/'

PROJECT_DATA_DIR = DATA_DIR / DOMAIN_SLUG
MANIFESTS_DIR = PROJECT_DATA_DIR / 'manifests'
RAW_HTML_DIR = PROJECT_DATA_DIR / 'raw_html'
ASSETS_DIR = PROJECT_DATA_DIR / 'assets'
CONTENT_DIR = PROJECT_DATA_DIR / 'content'

def get_latest_cdx_timestamp(domain: str) -> str:
    """Queries Wayback CDX API to discover the latest valid 200 OK snapshot timestamp."""
    try:
        query_url = f'{CDX_API_URL}?url={domain}&filter=statuscode:200&limit=1&fastLatest=true&output=json'
        resp = SESSION.get(query_url, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if len(data) > 1 and len(data[1]) > 1:
                ts = data[1][1]
                logger.info(f'Timestamp detectado automaticamente en Wayback para {domain}: {ts}')
                return ts
    except Exception as e:
        logger.debug(f'No se pudo obtener timestamp de CDX ({e}), usando wildcard "2"')
    return '2'

def init_project(target_url: str, custom_timestamp: str = None, depth: int = 3):
    """Initializes project workspace dynamically for any given target URL."""
    global CURRENT_URL, CURRENT_DOMAIN, DOMAIN_SLUG, CURRENT_TIMESTAMP, WAYBACK_RAW_PREFIX
    global PROJECT_DATA_DIR, MANIFESTS_DIR, RAW_HTML_DIR, ASSETS_DIR, CONTENT_DIR

    target_url = target_url.strip()
    
    # Handle direct Wayback Machine URLs (e.g., https://web.archive.org/web/20230711124744/https://ejemplo.com)
    wb_match = re.search(r'https?://web\.archive\.org/web/(\d+)[a-z_]*/(https?://.+)', target_url)
    if wb_match:
        if not custom_timestamp:
            custom_timestamp = wb_match.group(1)
        target_url = wb_match.group(2)
    else:
        wb_match_simple = re.search(r'https?://web\.archive\.org/web/[^/]+/(https?://.+)', target_url)
        if wb_match_simple:
            target_url = wb_match_simple.group(1)

    # Handle direct archive.today / archive.ph URLs
    archive_match = re.search(r'https?://archive\.(?:is|today|ph|md|li|vn)/(?:[0-9a-zA-Z]+/)?(https?://.+)', target_url)
    if archive_match:
        target_url = archive_match.group(1)

    if not target_url.startswith('http'):
        target_url = 'https://' + target_url

    parsed = urlparse(target_url)
    raw_domain = parsed.netloc or parsed.path.split('/')[0]
    domain = raw_domain.lower()
    if domain.startswith('www.'):
        domain = domain[4:]

    CURRENT_URL = f"{parsed.scheme or 'https'}://{raw_domain}"
    CURRENT_DOMAIN = domain
    DOMAIN_SLUG = re.sub(r'[^a-zA-Z0-9.-]', '_', domain)

    if custom_timestamp:
        CURRENT_TIMESTAMP = str(custom_timestamp).strip()
    else:
        CURRENT_TIMESTAMP = get_latest_cdx_timestamp(domain)

    WAYBACK_RAW_PREFIX = f'https://web.archive.org/web/{CURRENT_TIMESTAMP}id_/'

    PROJECT_DATA_DIR = DATA_DIR / DOMAIN_SLUG
    MANIFESTS_DIR = PROJECT_DATA_DIR / 'manifests'
    RAW_HTML_DIR = PROJECT_DATA_DIR / 'raw_html'
    ASSETS_DIR = PROJECT_DATA_DIR / 'assets'
    CONTENT_DIR = PROJECT_DATA_DIR / 'content'

    for d in [PROJECT_DATA_DIR, MANIFESTS_DIR, RAW_HTML_DIR, ASSETS_DIR, CONTENT_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    config_info = {
        'target_url': CURRENT_URL,
        'domain': CURRENT_DOMAIN,
        'domain_slug': DOMAIN_SLUG,
        'timestamp': CURRENT_TIMESTAMP,
        'depth': depth,
        'last_used': time.time(),
    }
    with open(PROJECT_DATA_DIR / 'project_config.json', 'w', encoding='utf-8') as f:
        json.dump(config_info, f, indent=2)

    with open(DATA_DIR / 'active_project.json', 'w', encoding='utf-8') as f:
        json.dump(config_info, f, indent=2)

    logger.info(f'Proyecto inicializado para: {CURRENT_URL} (Directorio: {PROJECT_DATA_DIR})')
    return config_info

def load_active_project():
    """Loads active project state from disk if available."""
    active_file = DATA_DIR / 'active_project.json'
    if active_file.exists():
        try:
            with open(active_file, 'r', encoding='utf-8') as f:
                info = json.load(f)
                init_project(info['target_url'], info.get('timestamp'), info.get('depth', 3))
                return info
        except Exception:
            pass
    return None

def extract_original_url(url: str) -> str:
    """Strips Wayback Machine wrapper and returns original URL."""
    m = re.search(r'https?://web\.archive\.org/web/[^/]+/(https?://.*)', url)
    if m:
        return m.group(1)
    return url

def clean_target_url(url: str) -> str:
    """Normalizes and ensures full target URL."""
    cleaned = extract_original_url(url.strip())
    if cleaned.startswith('//'):
        cleaned = 'https:' + cleaned
    elif not cleaned.startswith('http'):
        cleaned = CURRENT_URL + ('/' if not cleaned.startswith('/') else '') + cleaned
    return cleaned

def get_wayback_raw_url(original_url: str) -> str:
    """Constructs RAW Wayback snapshot URL."""
    cleaned = clean_target_url(original_url)
    return f'{WAYBACK_RAW_PREFIX}{cleaned}'

def url_to_relative_path(url: str) -> str:
    """Converts a URL path to a safe relative filesystem path."""
    clean = clean_target_url(url)
    parsed = urlparse(clean)
    path = unquote(parsed.path).lstrip('/')
    if not path or path.endswith('/'):
        path = path + 'index.html'
    # Handle query parameters safely if present
    if parsed.query:
        safe_query = re.sub(r'[^a-zA-Z0-9_-]', '_', parsed.query)
        path = f"{path}_{safe_query}"
    return path

def fetch_single_request(url: str, is_binary: bool = False, max_retries: int = 3, backoff: float = 1.5, timeout: int = 20):
    """Executes single HTTP request with retries."""
    for attempt in range(1, max_retries + 1):
        try:
            resp = SESSION.get(url, timeout=timeout)
            if resp.status_code == 200 and len(resp.content) > 0:
                if is_binary:
                    return resp.content
                return resp.text
            elif resp.status_code in (429, 503, 502, 504):
                sleep_time = backoff * attempt
                logger.warning(f'[{resp.status_code}] Servidor ocupado en {url}. Esperando {sleep_time:.1f}s...')
                time.sleep(sleep_time)
            elif resp.status_code == 404:
                return None
            else:
                return None
        except requests.exceptions.RequestException:
            time.sleep(backoff * attempt)
    return None

def fetch_from_archive_today(clean_url: str, is_binary: bool = False):
    """Fallback query to archive.today network."""
    domains = ['archive.is', 'archive.today', 'archive.ph']
    for domain in domains:
        search_url = f'https://{domain}/{clean_url}'
        try:
            resp = SESSION.get(search_url, timeout=6)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if re.search(r'archive\.(is|today|ph)/[a-zA-Z0-9]{4,6}$', href):
                        content = fetch_single_request(href, is_binary=is_binary, timeout=8)
                        if content:
                            return content
        except Exception:
            pass
    return None

def fetch_with_retry(url: str, is_binary: bool = False, max_retries: int = 3, backoff: float = 1.5, timeout: int = 20):
    """
    Motor de Recuperacion en Cascada (3 Niveles Universal):
    1. Tier 1: Snapshot seleccionado en modo RAW (id_)
    2. Tier 2: Busqueda historica total (2id_) alternando esquemas http y https
    3. Tier 3: Fallback a red archive.today / archive.is
    """
    clean_url = clean_target_url(url)
    
    # 1. TIER 1: Wayback Machine en timestamp configurado
    wb_target = f'{WAYBACK_RAW_PREFIX}{clean_url}'
    res = fetch_single_request(wb_target, is_binary=is_binary, max_retries=max_retries, backoff=backoff, timeout=timeout)
    if res is not None:
        return res

    # 2. TIER 2: Wayback Machine Historico Total (2id_)
    wb_historical = f'https://web.archive.org/web/2id_/{clean_url}'
    res = fetch_single_request(wb_historical, is_binary=is_binary, max_retries=2, backoff=backoff, timeout=timeout)
    if res is not None:
        logger.debug(f'[Recuperado via Wayback Historico 2id_] {clean_url}')
        return res
        
    # Tier 2b: Alternar protocolo http/https para capturas historicas
    if clean_url.startswith('https://'):
        alt_scheme = 'http://' + clean_url[8:]
    else:
        alt_scheme = 'https://' + clean_url[7:]
    res = fetch_single_request(f'https://web.archive.org/web/2id_/{alt_scheme}', is_binary=is_binary, max_retries=2, timeout=timeout)
    if res is not None:
        logger.debug(f'[Recuperado via Wayback Historico http-alt] {clean_url}')
        return res

    # 3. TIER 3: archive.today / archive.is / archive.ph
    res = fetch_from_archive_today(clean_url, is_binary=is_binary)
    if res is not None:
        logger.info(f'[Recuperado via archive.is] {clean_url}')
        return res

    logger.info(f'[404 Definitivo] No encontrado en ningun archivo: {clean_url}')
    return None

# Attempt loading active project from disk on startup
load_active_project()
