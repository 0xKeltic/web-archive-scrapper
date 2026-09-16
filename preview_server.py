# -*- coding: utf-8 -*-
import http.server
import socketserver
import os
import re
import mimetypes
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import requests
import config

PORT = 8080

def rewrite_html_for_local(html: str) -> str:
    html = re.sub(r'https?://criminalia\.es/wp-content/', '/assets/wp-content/', html)
    html = re.sub(r'//criminalia\.es/wp-content/', '/assets/wp-content/', html)
    html = re.sub(r'https?://criminalia\.es/wp-includes/', '/assets/wp-includes/', html)
    html = re.sub(r'//criminalia\.es/wp-includes/', '/assets/wp-includes/', html)
    
    html = re.sub(r'https?://criminalia\.es/asesino/', '/asesino/', html)
    html = re.sub(r'https?://criminalia\.es/material/', '/material/', html)
    html = re.sub(r'https?://criminalia\.es/actualidad/', '/actualidad/', html)
    html = re.sub(r'https?://criminalia\.es/resultados-de-la-busqueda/', '/resultados-de-la-busqueda/', html)
    html = re.sub(r'https?://criminalia\.es/?(?=[\"\x27\s])', '/', html)
    
    html = re.sub(r'src=[\"\x27][^\"\x27]*lazy_placeholder\.gif[\"\x27]\s+data-src=([\"\x27][^\"\x27]+[\"\x27])', r'src=\1', html)
    html = re.sub(r'data-lazy-src=([\"\x27][^\"\x27]+[\"\x27])', r'src=\1', html)
    
    return html

class CriminaliaServer(http.server.BaseHTTPRequestHandler):
    def send_asset_file(self, file_path: Path):
        content_type, _ = mimetypes.guess_type(str(file_path))
        if not content_type:
            if file_path.suffix == '.css':
                content_type = 'text/css'
            elif file_path.suffix == '.js':
                content_type = 'application/javascript'
            elif file_path.suffix == '.ico':
                content_type = 'image/x-icon'
            else:
                content_type = 'application/octet-stream'
                
        try:
            data = file_path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(500, f'Error reading file: {e}')

    def do_GET(self):
        parsed = urlparse(self.path)
        url_path = parsed.path
        query_params = parse_qs(parsed.query)

        # 0. SERVE FAVICON (/favicon.ico)
        if url_path == '/favicon.ico':
            fav_path = config.ASSETS_DIR / 'wp-content/themes/criminalia/favicon.ico'
            if fav_path.exists():
                self.send_asset_file(fav_path)
                return

        # 1. SERVE STATIC ASSETS (/assets/wp-content/...)
        if url_path.startswith('/assets/'):
            rel = url_path[len('/assets/'):].lstrip('/')
            file_path = config.ASSETS_DIR / rel
            
            if file_path.exists() and file_path.is_file() and file_path.stat().st_size > 0:
                self.send_asset_file(file_path)
                return
                
            # Flexible on-the-fly fetch using 2id_ (closest capture in Wayback Machine)
            wb_url = f'https://web.archive.org/web/2id_/https://criminalia.es/{rel}'
            try:
                resp = requests.get(wb_url, timeout=8, headers=config.DEFAULT_HEADERS)
                if resp.status_code == 200 and len(resp.content) > 0:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_bytes(resp.content)
                    self.send_asset_file(file_path)
                    return
            except Exception:
                pass
            self.send_error(404, f'Asset not found: {rel}')
            return

        # 2. SERVE HOMEPAGE (/)
        if url_path in ('/', '/index.html'):
            home_file = config.RAW_HTML_DIR / 'index.html'
            if home_file.exists():
                html = home_file.read_text(encoding='utf-8', errors='ignore')
                html_rewritten = rewrite_html_for_local(html)
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html_rewritten.encode('utf-8'))
                return

        # 3. SERVE SEARCH INDEXES (/resultados-de-la-busqueda/)
        if url_path.startswith('/resultados-de-la-busqueda'):
            l = query_params.get('l', ['a'])[0].lower()
            g = query_params.get('g', ['hombre'])[0].lower()
            idx_file = config.RAW_HTML_DIR / 'indices' / f'{l}_{g}.html'
            
            if not idx_file.exists():
                wb_url = f'https://web.archive.org/web/2id_/https://criminalia.es/resultados-de-la-busqueda/?l={l}&g={g}'
                try:
                    resp = requests.get(wb_url, timeout=10, headers=config.DEFAULT_HEADERS)
                    if resp.status_code == 200:
                        idx_file.parent.mkdir(parents=True, exist_ok=True)
                        idx_file.write_text(resp.text, encoding='utf-8')
                except Exception:
                    pass
                    
            if idx_file.exists():
                html = idx_file.read_text(encoding='utf-8', errors='ignore')
                html_rewritten = rewrite_html_for_local(html)
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html_rewritten.encode('utf-8'))
                return

        # 4. SERVE ARTICLE (/asesino/<slug>/ or /asesino/<slug>)
        if url_path.startswith('/asesino/'):
            slug = url_path[len('/asesino/'):].strip('/')
            article_file = config.RAW_HTML_DIR / 'asesino' / f'{slug}.html'
            
            if not article_file.exists():
                wb_url = f'https://web.archive.org/web/2id_/https://criminalia.es/asesino/{slug}/'
                try:
                    resp = requests.get(wb_url, timeout=12, headers=config.DEFAULT_HEADERS)
                    if resp.status_code == 200:
                        article_file.parent.mkdir(parents=True, exist_ok=True)
                        article_file.write_text(resp.text, encoding='utf-8')
                except Exception:
                    pass
                    
            if article_file.exists():
                html = article_file.read_text(encoding='utf-8', errors='ignore')
                html_rewritten = rewrite_html_for_local(html)
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html_rewritten.encode('utf-8'))
                return

        # 5. SERVE PHOTO GALLERIES (/material/<slug>/)
        if url_path.startswith('/material/'):
            slug = url_path[len('/material/'):].strip('/')
            mat_file = config.RAW_HTML_DIR / 'material' / f'{slug}.html'
            
            if not mat_file.exists():
                wb_url = f'https://web.archive.org/web/2id_/https://criminalia.es/material/{slug}/'
                try:
                    resp = requests.get(wb_url, timeout=12, headers=config.DEFAULT_HEADERS)
                    if resp.status_code == 200 and len(resp.text) > 1000:
                        mat_file.parent.mkdir(parents=True, exist_ok=True)
                        mat_file.write_text(resp.text, encoding='utf-8')
                except Exception:
                    pass
                    
            if mat_file.exists():
                html = mat_file.read_text(encoding='utf-8', errors='ignore')
                html_rewritten = rewrite_html_for_local(html)
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html_rewritten.encode('utf-8'))
                return
            else:
                # Friendly fallback message
                not_found_page = f'''<!DOCTYPE html>
                <html lang=\"es\">
                <head>
                    <meta charset=\"UTF-8\">
                    <title>Galería no archivada</title>
                    <link rel=\"stylesheet\" href=\"/assets/wp-content/themes/criminalia/style.css\">
                </head>
                <body style=\"font-family: sans-serif; padding: 40px; background: #f8f9fa;\">
                    <div style=\"max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);\">
                        <h2 style=\"color: #b91c1c;\">Fotografías no disponibles en Web Archive</h2>
                        <p>La galería complementaria <code>{slug}</code> no fue capturada por los rastreadores de Internet Archive en el momento de indexar la web.</p>
                        <p>Sin embargo, el artículo principal y las fotos del expediente siguen estando disponibles.</p>
                        <p><a href=\"javascript:history.back()\" style=\"display: inline-block; background: #b91c1c; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px;\">← Volver al artículo</a></p>
                    </div>
                </body>
                </html>'''
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(not_found_page.encode('utf-8'))
                return

        # 6. SERVE ACTUALIDAD
        if url_path.startswith('/actualidad'):
            parts = [p for p in url_path.split('/') if p]
            if len(parts) == 1:
                act_file = config.RAW_HTML_DIR / 'actualidad' / 'index_page_1.html'
            else:
                act_file = config.RAW_HTML_DIR / 'actualidad' / f'{parts[1]}.html'
                
            if not act_file.exists():
                wb_url = f'https://web.archive.org/web/2id_/https://criminalia.es{url_path}'
                try:
                    resp = requests.get(wb_url, timeout=10, headers=config.DEFAULT_HEADERS)
                    if resp.status_code == 200:
                        act_file.parent.mkdir(parents=True, exist_ok=True)
                        act_file.write_text(resp.text, encoding='utf-8')
                except Exception:
                    pass
                    
            if act_file.exists():
                html = act_file.read_text(encoding='utf-8', errors='ignore')
                html_rewritten = rewrite_html_for_local(html)
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html_rewritten.encode('utf-8'))
                return

        self.send_error(404, f'Ruta no encontrada: {url_path}')

def main():
    with socketserver.TCPServer(('', PORT), CriminaliaServer) as httpd:
        print(f'Servidor Criminalia activo en http://localhost:{PORT}')
        httpd.serve_forever()

if __name__ == '__main__':
    main()
