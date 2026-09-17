# -*- coding: utf-8 -*-
import http.server
import socketserver
import os
import re
import argparse
import mimetypes
from urllib.parse import urlparse, parse_qs, unquote
from pathlib import Path
from loguru import logger
import config

PORT = 8080

def rewrite_html_universal(html: str, domain: str) -> str:
    """Dynamically converts all links and asset references pointing to the target domain to local paths."""
    # 1. Strip protocol and domain to relative root
    pattern_domain = rf'https?://(?:www\.)?{re.escape(domain)}/'
    html = re.sub(pattern_domain, '/', html, flags=re.IGNORECASE)
    
    pattern_protocol_relative = rf'//(?:www\.)?{re.escape(domain)}/'
    html = re.sub(pattern_protocol_relative, '/', html, flags=re.IGNORECASE)
    
    # 2. Bare domain references
    pattern_bare = rf'https?://(?:www\.)?{re.escape(domain)}(?=[\"\x27\s#\?])'
    html = re.sub(pattern_bare, '/', html, flags=re.IGNORECASE)

    # 3. Robust fix for lazy-loaded images (a3-lazy-load, WP-Rocket, etc.)
    html = re.sub(r'data-src=[\"\x27]([^\"]+)[\"\x27]', r'src="\1" data-src="\1"', html)
    html = re.sub(r'data-lazy-src=[\"\x27]([^\"]+)[\"\x27]', r'src="\1"', html)
    
    return html

class UniversalPreviewHandler(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.do_GET()

    def log_message(self, format, *args):
        # Concise logging
        logger.debug(f'[{self.command}] {self.path} - {args[1] if len(args) > 1 else ""}')

    def send_asset_file(self, file_path: Path):
        content_type, _ = mimetypes.guess_type(str(file_path))
        if not content_type:
            if file_path.suffix == '.css':
                content_type = 'text/css'
            elif file_path.suffix == '.js':
                content_type = 'application/javascript'
            elif file_path.suffix == '.ico':
                content_type = 'image/x-icon'
            elif file_path.suffix in ('.woff', '.woff2'):
                content_type = 'font/woff2'
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
            self.send_error(500, f'Error reading asset: {e}')

    def do_GET(self):
        parsed = urlparse(self.path)
        url_path = unquote(parsed.path)

        # 1. LIVE STATUS DASHBOARD (/status)
        if url_path in ('/status', '/progreso'):
            pages_count = len(list(config.RAW_HTML_DIR.rglob('*.html'))) if config.RAW_HTML_DIR.exists() else 0
            assets_count = len(list(config.ASSETS_DIR.rglob('*.*'))) if config.ASSETS_DIR.exists() else 0
            markdowns_count = len(list(config.CONTENT_DIR.rglob('*.md'))) if config.CONTENT_DIR.exists() else 0

            status_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Monitor de Preservacion - {config.CURRENT_DOMAIN}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px 20px; }}
        .card {{ max-width: 680px; margin: 0 auto; background: #1e293b; padding: 32px; border-radius: 12px; border: 1px solid #334155; box-shadow: 0 10px 25px rgba(0,0,0,0.3); }}
        h1 {{ color: #38bdf8; margin-top: 0; display: flex; align-items: center; justify-content: space-between; font-size: 22px; }}
        .badge {{ font-size: 13px; background: #22c55e; color: #000; padding: 4px 12px; border-radius: 20px; font-weight: bold; min-width: 130px; text-align: center; }}
        .domain-tag {{ font-size: 13px; color: #94a3b8; background: #0f172a; padding: 2px 8px; border-radius: 4px; font-family: monospace; }}
        .stat-row {{ padding: 14px 0; border-bottom: 1px solid #334155; }}
        .stat-header {{ display: flex; justify-content: space-between; margin-bottom: 6px; }}
        .stat-label {{ font-size: 15px; color: #cbd5e1; font-weight: 500; }}
        .stat-val {{ font-size: 16px; font-weight: bold; color: #f8fafc; }}
        .btn {{ display: inline-block; background: #0284c7; color: white; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: 600; margin-top: 20px; }}
        .btn:hover {{ background: #0369a1; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>
            <span>Estado de Archivo: <span class="domain-tag">{config.CURRENT_DOMAIN}</span></span>
            <span class="badge" id="countdown-badge">Auto-refresco 2s</span>
        </h1>
        <div class="stat-row">
            <div class="stat-header">
                <span class="stat-label">📄 Paginas HTML archivadas</span>
                <span class="stat-val">{pages_count} paginas</span>
            </div>
        </div>
        <div class="stat-row">
            <div class="stat-header">
                <span class="stat-label">💾 Archivos Multimedia y Estilos (Assets)</span>
                <span class="stat-val">{assets_count} archivos</span>
            </div>
        </div>
        <div class="stat-row">
            <div class="stat-header">
                <span class="stat-label">📝 Documentos Markdown estructurados (.md)</span>
                <span class="stat-val">{markdowns_count} documentos</span>
            </div>
        </div>
        <a href="/" class="btn">← Explorar Web Archivada ({config.CURRENT_DOMAIN})</a>
    </div>
    <script>
        let remaining = 2;
        const badge = document.getElementById('countdown-badge');
        setInterval(() => {{
            remaining--;
            if (remaining <= 0) {{
                if (badge) badge.innerText = 'Refrescando...';
                location.reload();
            }} else {{
                if (badge) badge.innerText = 'Auto-refresco ' + remaining + 's';
            }}
        }}, 1000);
    </script>
</body>
</html>"""
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(status_html.encode('utf-8'))))
            self.end_headers()
            self.wfile.write(status_html.encode('utf-8'))
            return

        # 2. SERVE AND AUTO-RESCUE STATIC ASSETS (Images, CSS, JS, Fonts, Media)
        ext = Path(url_path).suffix.lower()
        is_asset = (
            url_path.startswith('/assets/') or
            ext in ('.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.woff', '.woff2', '.ttf', '.eot', '.otf', '.mp3', '.mp4', '.pdf', '.map') or
            any(url_path.startswith(p) for p in ('/wp-content/', '/wp-includes/', '/static/', '/media/', '/images/', '/img/', '/css/', '/js/', '/fonts/'))
        )

        if is_asset:
            rel_asset = url_path[len('/assets/'):] if url_path.startswith('/assets/') else url_path.lstrip('/')
            local_asset = config.ASSETS_DIR / rel_asset
            if local_asset.exists() and local_asset.is_file() and local_asset.stat().st_size > 0:
                self.send_asset_file(local_asset)
                return

            # Dynamic on-the-fly rescue for missing assets
            original_asset_url = f'https://{config.CURRENT_DOMAIN}/{rel_asset}'
            logger.info(f'[On-The-Fly Asset] Descargando imagen o recurso en vivo: {rel_asset}...')
            data = config.fetch_with_retry(original_asset_url, is_binary=True)
            if data:
                local_asset.parent.mkdir(parents=True, exist_ok=True)
                local_asset.write_bytes(data)
                self.send_asset_file(local_asset)
                return
            else:
                self.send_error(404, f'Asset no encontrado en archivos: {rel_asset}')
                return

        # 3. SERVE HTML PAGES
        # Map URL to HTML file
        clean_rel = config.url_to_relative_path(url_path)
        candidates = [
            config.RAW_HTML_DIR / clean_rel,
            config.RAW_HTML_DIR / (url_path.lstrip('/') + '.html'),
            config.RAW_HTML_DIR / url_path.lstrip('/') / 'index.html',
            config.RAW_HTML_DIR / 'index.html' if url_path in ('/', '') else None
        ]

        for cand in candidates:
            if cand and cand.exists() and cand.is_file():
                try:
                    raw_html = cand.read_text(encoding='utf-8', errors='ignore')
                    processed_html = rewrite_html_universal(raw_html, config.CURRENT_DOMAIN)
                    data = processed_html.encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except Exception as e:
                    self.send_error(500, f'Error serving HTML: {e}')
                    return

        # 4. DYNAMIC CATCH-ALL ON-THE-FLY RESCUE
        full_target_url = f'https://{config.CURRENT_DOMAIN}{url_path}'
        logger.info(f'[On-The-Fly] Rescatando pagina en vivo desde Wayback: {full_target_url}...')
        fetched_content = config.fetch_with_retry(full_target_url)
        if fetched_content and len(fetched_content) > 100:
            target_html_file = config.RAW_HTML_DIR / clean_rel
            target_html_file.parent.mkdir(parents=True, exist_ok=True)
            target_html_file.write_text(fetched_content, encoding='utf-8', errors='ignore')
            
            processed = rewrite_html_universal(fetched_content, config.CURRENT_DOMAIN)
            data = processed.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        # 5. 404 NOT FOUND PAGE
        not_found_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>404 - Pagina no archivada</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 50px 20px; text-align: center; }}
        .box {{ max-width: 600px; margin: 0 auto; background: #1e293b; padding: 40px; border-radius: 12px; border: 1px solid #334155; }}
        h2 {{ color: #ef4444; }}
        code {{ background: #0f172a; color: #38bdf8; padding: 2px 6px; border-radius: 4px; }}
        .btn {{ display: inline-block; background: #0284c7; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: bold; margin-top: 15px; }}
    </style>
</head>
<body>
    <div class="box">
        <h2>Recurso no encontrado</h2>
        <p>La direccion <code>{url_path}</code> no esta en disco ni pudo recuperarse en los archivos web.</p>
        <a href="/" class="btn">← Volver al inicio</a>
        <a href="/status" class="btn" style="background: #334155; margin-left: 10px;">Ver estado</a>
    </div>
</body>
</html>"""
        self.send_response(404)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(not_found_html.encode('utf-8'))))
        self.end_headers()
        self.wfile.write(not_found_html.encode('utf-8'))

def run_server(port: int = 8080):
    handler = UniversalPreviewHandler
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    with http.server.ThreadingHTTPServer(("", port), handler) as httpd:
        logger.success(f'Servidor local universal multihilo iniciado para {config.CURRENT_DOMAIN}')
        logger.info(f'-> Web archivada: http://localhost:{port}/')
        logger.info(f'-> Monitor de estado: http://localhost:{port}/status')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info('Servidor detenido por el usuario.')

def main():
    parser = argparse.ArgumentParser(description='Universal Web Archive Preview Server')
    parser.add_argument('--domain', type=str, help='Dominio a servir (ej: criminalia.es, otra-web.org)')
    parser.add_argument('--port', type=int, default=8080, help='Puerto local (por defecto: 8080)')
    args = parser.parse_args()

    if args.domain:
        config.init_project(args.domain)

    run_server(args.port)

if __name__ == '__main__':
    main()
