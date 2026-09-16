# -*- coding: utf-8 -*-
import os
import re
import time
import gzip
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from loguru import logger

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / 'data'
MANIFESTS_DIR = DATA_DIR / 'manifests'
RAW_HTML_DIR = DATA_DIR / 'raw_html'
ASSETS_DIR = DATA_DIR / 'assets'
CONTENT_DIR = DATA_DIR / 'content'

for d in [DATA_DIR, MANIFESTS_DIR, RAW_HTML_DIR, ASSETS_DIR, CONTENT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

ORIGINAL_BASE_URL = 'https://criminalia.es'
WAYBACK_TIMESTAMP = '20230711124744'
WAYBACK_RAW_PREFIX = f'https://web.archive.org/web/{WAYBACK_TIMESTAMP}id_/'
CDX_API_URL = 'https://web.archive.org/cdx/search/cdx'

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate',
}

SESSION = requests.Session()
SESSION.headers.update(DEFAULT_HEADERS)

def extract_original_url(url: str) -> str:
    m = re.search(r'https?://web\.archive\.org/web/[^/]+/(https?://.*)', url)
    if m:
        return m.group(1)
    return url

def clean_target_url(url: str) -> str:
    cleaned = extract_original_url(url.strip())
    if cleaned.startswith('//'):
        cleaned = 'https:' + cleaned
    elif not cleaned.startswith('http'):
        cleaned = ORIGINAL_BASE_URL + ('/' if not cleaned.startswith('/') else '') + cleaned
    return cleaned

def get_wayback_raw_url(original_url: str) -> str:
    cleaned = clean_target_url(original_url)
    return f'{WAYBACK_RAW_PREFIX}{cleaned}'

def fetch_single_request(url: str, is_binary: bool = False, max_retries: int = 3, backoff: float = 1.5, timeout: int = 20):
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
        except requests.exceptions.RequestException as e:
            time.sleep(backoff * attempt)
    return None

def fetch_from_archive_today(clean_url: str, is_binary: bool = False):
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
    clean_url = clean_target_url(url)
    
    # 1. TIER 1: Wayback Machine en timestamp 2023
    wb_2023 = f'{WAYBACK_RAW_PREFIX}{clean_url}'
    res = fetch_single_request(wb_2023, is_binary=is_binary, max_retries=max_retries, backoff=backoff, timeout=timeout)
    if res is not None:
        return res

    # 2. TIER 2: Wayback Machine Historico Total (2id_ - rastrea 2015 a 2022)
    wb_historical = f'https://web.archive.org/web/2id_/{clean_url}'
    res = fetch_single_request(wb_historical, is_binary=is_binary, max_retries=2, backoff=backoff, timeout=timeout)
    if res is not None:
        logger.debug(f'[Recuperado via Wayback Historico 2id_] {clean_url}')
        return res
        
    # Tier 2b: Alternar protocolo http/https para historicos antiguos
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
