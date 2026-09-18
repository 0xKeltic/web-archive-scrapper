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
    selected_domain = None

    def do_HEAD(self):
        self.do_GET()

    def log_message(self, format, *args):
        logger.debug(f'[{self.command}] {self.path} - {args[1] if len(args) > 1 else ""}')

    def get_target_domain(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        site = None
        new_cookie = None

        if 'site' in qs and qs['site'][0]:
            site = qs['site'][0].strip().lower()
            new_cookie = f'active_site={site}; Path=/; SameSite=Lax'
        elif 'domain' in qs and qs['domain'][0]:
            site = qs['domain'][0].strip().lower()
            new_cookie = f'active_site={site}; Path=/; SameSite=Lax'

        if not site:
            cookie_hdr = self.headers.get('Cookie', '')
            for part in cookie_hdr.split(';'):
                part = part.strip()
                if part.startswith('active_site='):
                    site = part.split('=', 1)[1].strip().lower()
                    break

        if not site and UniversalPreviewHandler.selected_domain:
            site = UniversalPreviewHandler.selected_domain

        projects = [d.name for d in config.DATA_DIR.iterdir() if d.is_dir()] if config.DATA_DIR.exists() else []
        if not site or (projects and site not in projects):
            if projects:
                site = projects[0]
            else:
                site = config.CURRENT_DOMAIN

        UniversalPreviewHandler.selected_domain = site
        return site, new_cookie

    def send_asset_file(self, file_path: Path, cookie: str = None):
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
            if cookie:
                self.send_header('Set-Cookie', cookie)
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(500, f'Error reading asset: {e}')

    def do_GET(self):
        parsed = urlparse(self.path)
        url_path = unquote(parsed.path)
        target_domain, new_cookie = self.get_target_domain()

        proj_dir = config.DATA_DIR / target_domain
        raw_html_dir = proj_dir / 'raw_html'
        assets_dir = proj_dir / 'assets'
        content_dir = proj_dir / 'content'

        # 1. MULTI-SITE LIVE STATUS DASHBOARD (/status)
        if url_path in ('/status', '/progreso'):
            projects = [d for d in config.DATA_DIR.iterdir() if d.is_dir()] if config.DATA_DIR.exists() else []
            cards_html = []

            for p in sorted(projects, key=lambda x: x.name):
                domain_name = p.name
                cfg_file = p / 'project_config.json'
                is_live = False
                ts = ""
                if cfg_file.exists():
                    try:
                        with open(cfg_file, 'r', encoding='utf-8') as f:
                            c = json.load(f)
                            is_live = c.get('is_live', False)
                            ts = c.get('timestamp', '')
                    except Exception:
                        pass

                pages_count = len(list((p / 'raw_html').rglob('*.html'))) if (p / 'raw_html').exists() else 0
                assets_count = len(list((p / 'assets').rglob('*.*'))) if (p / 'assets').exists() else 0
                markdowns_count = len(list((p / 'content').rglob('*.md'))) if (p / 'content').exists() else 0

                is_active = (domain_name == target_domain)
                mode_badge = '<span class="badge badge-live">🌐 EN VIVO</span>' if is_live else f'<span class="badge badge-archive">🏛️ WAYBACK: {ts}</span>'
                active_pill = '<span class="active-tag">Activo en Navegador</span>' if is_active else ''
                border_style = 'border: 2px solid #0284c7;' if is_active else 'border: 1px solid #334155;'

                cards_html.append(f"""
                <div class="card" style="{border_style}">
                    <div class="card-top">
                        <div>
                            <span class="domain-title">{domain_name}</span>
                            {mode_badge}
                            {active_pill}
                        </div>
                        <a href="/?site={domain_name}" class="btn-explore">Explorar Web →</a>
                    </div>
                    <div class="stat-grid">
                        <div class="stat-item">
                            <span class="stat-num">{pages_count}</span>
                            <span class="stat-lbl">📄 Páginas HTML</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-num">{assets_count}</span>
                            <span class="stat-lbl">💾 Assets / Multimedia</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-num">{markdowns_count}</span>
                            <span class="stat-lbl">📝 Documentos Markdown</span>
                        </div>
                    </div>
                </div>
                """)

            cards_rendered = "\n".join(cards_html) if cards_html else """
                <div class="card" style="text-align: center; padding: 40px;">
                    <p style="color: #94a3b8; font-size: 16px;">No hay sitios descargados en data/ todavía.</p>
                    <p style="color: #64748b; font-size: 14px;">Ejecuta <code>python run_pipeline.py --url &lt;URL&gt; --all</code> para comenzar.</p>
                </div>
            """

            total_projects = len(projects)
            status_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Monitor de Preservación Multi-Sitio</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 30px 20px; margin: 0; }}
        .container {{ max-width: 860px; margin: 0 auto; }}
        header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 25px; border-bottom: 1px solid #334155; padding-bottom: 15px; }}
        h1 {{ color: #38bdf8; font-size: 24px; margin: 0; display: flex; align-items: center; gap: 10px; }}
        .refresh-pill {{ font-size: 13px; background: #22c55e; color: #000; padding: 4px 12px; border-radius: 20px; font-weight: bold; min-width: 140px; text-align: center; }}
        .card {{ background: #1e293b; padding: 24px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.25); }}
        .card-top {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }}
        .domain-title {{ font-size: 20px; font-weight: bold; color: #f8fafc; margin-right: 10px; }}
        .badge {{ font-size: 12px; padding: 3px 8px; border-radius: 4px; font-weight: 600; text-transform: uppercase; margin-right: 6px; }}
        .badge-live {{ background: #0284c7; color: #ffffff; }}
        .badge-archive {{ background: #d97706; color: #ffffff; }}
        .active-tag {{ font-size: 11px; background: #10b981; color: #000; padding: 2px 6px; border-radius: 4px; font-weight: bold; }}
        .btn-explore {{ background: #0284c7; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 14px; }}
        .btn-explore:hover {{ background: #0369a1; }}
        .stat-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; background: #0f172a; padding: 14px; border-radius: 8px; border: 1px solid #334155; }}
        .stat-item {{ text-align: center; }}
        .stat-num {{ display: block; font-size: 22px; font-weight: bold; color: #38bdf8; }}
        .stat-lbl {{ font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🌐 Monitor Multi-Sitio <span style="font-size: 14px; color: #94a3b8; font-weight: normal;">({total_projects} proyectos en disco)</span></h1>
            <span class="refresh-pill" id="countdown-badge">Auto-refresco 2s</span>
        </header>
        {cards_rendered}
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
            if new_cookie:
                self.send_header('Set-Cookie', new_cookie)
            self.end_headers()
            self.wfile.write(status_html.encode('utf-8'))
            return

        # 2. SERVE AND AUTO-RESCUE STATIC ASSETS
        ext = Path(url_path).suffix.lower()
        is_asset = (
            url_path.startswith('/assets/') or
            ext in ('.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.woff', '.woff2', '.ttf', '.eot', '.otf', '.mp3', '.mp4', '.pdf', '.map') or
            any(url_path.startswith(p) for p in ('/wp-content/', '/wp-includes/', '/static/', '/media/', '/images/', '/img/', '/css/', '/js/', '/fonts/'))
        )

        if is_asset:
            rel_asset = url_path[len('/assets/'):] if url_path.startswith('/assets/') else url_path.lstrip('/')
            local_asset = assets_dir / rel_asset
            if local_asset.exists() and local_asset.is_file() and local_asset.stat().st_size > 0:
                self.send_asset_file(local_asset, cookie=new_cookie)
                return

            # Dynamic on-the-fly rescue
            original_asset_url = f'https://{target_domain}/{rel_asset}'
            logger.info(f'[{target_domain}] [On-The-Fly Asset] Descargando recurso: {rel_asset}...')
            data = config.fetch_with_retry(original_asset_url, is_binary=True)
            if data:
                local_asset.parent.mkdir(parents=True, exist_ok=True)
                local_asset.write_bytes(data)
                self.send_asset_file(local_asset, cookie=new_cookie)
                return
            else:
                self.send_error(404, f'Asset no encontrado: {rel_asset}')
                return

        # 3. SERVE HTML PAGES
        clean_rel = config.url_to_relative_path(url_path)
        candidates = [
            raw_html_dir / clean_rel,
            raw_html_dir / (url_path.lstrip('/') + '.html'),
            raw_html_dir / url_path.lstrip('/') / 'index.html',
            raw_html_dir / 'index.html' if url_path in ('/', '') else None
        ]

        for cand in candidates:
            if cand and cand.exists() and cand.is_file():
                try:
                    raw_html = cand.read_text(encoding='utf-8', errors='ignore')
                    processed_html = rewrite_html_universal(raw_html, target_domain)
                    data = processed_html.encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(data)))
                    if new_cookie:
                        self.send_header('Set-Cookie', new_cookie)
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except Exception as e:
                    self.send_error(500, f'Error serving HTML: {e}')
                    return

        # 4. DYNAMIC CATCH-ALL ON-THE-FLY RESCUE
        full_target_url = f'https://{target_domain}{url_path}'
        logger.info(f'[{target_domain}] [On-The-Fly] Rescatando pagina: {full_target_url}...')
        fetched_content = config.fetch_with_retry(full_target_url)
        if fetched_content and len(fetched_content) > 100:
            target_html_file = raw_html_dir / clean_rel
            target_html_file.parent.mkdir(parents=True, exist_ok=True)
            target_html_file.write_text(fetched_content, encoding='utf-8', errors='ignore')
            
            processed = rewrite_html_universal(fetched_content, target_domain)
            data = processed.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            if new_cookie:
                self.send_header('Set-Cookie', new_cookie)
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
        <p>La direccion <code>{url_path}</code> no esta en disco para <code>{target_domain}</code> ni pudo recuperarse.</p>
        <a href="/" class="btn">← Volver al inicio</a>
        <a href="/status" class="btn" style="background: #334155; margin-left: 10px;">Monitor Multi-Sitio</a>
    </div>
</body>
</html>"""
        self.send_response(404)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(not_found_html.encode('utf-8'))))
        if new_cookie:
            self.send_header('Set-Cookie', new_cookie)
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
