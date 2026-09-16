import os
import time
import gzip
import requests
from pathlib import Path
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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
}

SESSION = requests.Session()
SESSION.headers.update(DEFAULT_HEADERS)

def get_wayback_raw_url(original_url: str) -> str:
    original_clean = original_url.strip()
    if original_clean.startswith('//'):
        original_clean = 'https:' + original_clean
    elif not original_clean.startswith('http'):
        original_clean = ORIGINAL_BASE_URL + ('/' if not original_clean.startswith('/') else '') + original_clean
    return f'{WAYBACK_RAW_PREFIX}{original_clean}'

def fetch_with_retry(url: str, is_binary: bool = False, max_retries: int = 4, backoff: float = 2.0, timeout: int = 25):
    for attempt in range(1, max_retries + 1):
        try:
            resp = SESSION.get(url, timeout=timeout)
            if resp.status_code == 200:
                if is_binary:
                    return resp.content
                return resp.text
            elif resp.status_code in (429, 503, 502, 504):
                sleep_time = backoff * attempt
                logger.warning(f'[{resp.status_code}] Rate limited/busy on {url}. Esperando {sleep_time:.1f}s (intento {attempt}/{max_retries})...')
                time.sleep(sleep_time)
            elif resp.status_code == 404:
                logger.info(f'[404] No encontrado en Wayback: {url}')
                return None
            else:
                logger.warning(f'[{resp.status_code}] Respuesta inesperada en {url}')
                return None
        except requests.exceptions.RequestException as e:
            sleep_time = backoff * attempt
            logger.warning(f'Error de red ({e}) en {url}. Reintentando en {sleep_time:.1f}s (intento {attempt}/{max_retries})...')
            time.sleep(sleep_time)
    logger.error(f'Fallo definitivo tras {max_retries} intentos en {url}')
    return None
