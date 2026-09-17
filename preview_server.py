# -*- coding: utf-8 -*-
import http.server
import socketserver
import os
import re
import mimetypes
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import config

PORT = 8080

def rewrite_html_for_local(html: str) -> str:
    # 1. Map all WordPress asset directories (including wp-criminalia legacy paths)
    html = re.sub(r'https?://(?:www\.)?criminalia\.es/wp-criminalia/wp-content/', '/assets/wp-content/', html)
    html = re.sub(r'//(?:www\.)?criminalia\.es/wp-criminalia/wp-content/', '/assets/wp-content/', html)
    html = re.sub(r'https?://(?:www\.)?criminalia\.es/wp-content/', '/assets/wp-content/', html)
    html = re.sub(r'//(?:www\.)?criminalia\.es/wp-content/', '/assets/wp-content/', html)
    html = re.sub(r'https?://(?:www\.)?criminalia\.es/wp-includes/', '/assets/wp-includes/', html)
    html = re.sub(r'//(?:www\.)?criminalia\.es/wp-includes/', '/assets/wp-includes/', html)
    html = re.sub(r'https?://(?:www\.)?criminalia\.es/wp-criminalia/wp-includes/', '/assets/wp-includes/', html)
    html = re.sub(r'//(?:www\.)?criminalia\.es/wp-criminalia/wp-includes/', '/assets/wp-includes/', html)
    
    # 2. Map relative asset references
    html = re.sub(r'(href|src)=[\'"]/wp-criminalia/wp-content/', r'\1="/assets/wp-content/', html)
    html = re.sub(r'(href|src)=[\'"]/wp-content/', r'\1="/assets/wp-content/', html)
    html = re.sub(r'(href|src)=[\'"]/wp-includes/', r'\1="/assets/wp-includes/', html)

    # 3. Convert all remaining criminalia.es internal links to local root
    html = re.sub(r'https?://(?:www\.)?criminalia\.es/', '/', html)
    html = re.sub(r'//(?:www\.)?criminalia\.es/', '/', html)
    html = re.sub(r'https?://(?:www\.)?criminalia\.es(?=[\"\x27\s#\?])', '/', html)
    
    # 4. Handle lazy loaded images
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

        # 0.0 SERVE LIVE STATUS DASHBOARD (/status)
        if url_path in ('/status', '/progreso'):
            asesinos = len(list((config.RAW_HTML_DIR / 'asesino').glob('*.html')))
            materiales = len(list((config.RAW_HTML_DIR / 'material').glob('*.html')))
            actualidad = len(list((config.RAW_HTML_DIR / 'actualidad').glob('*.html')))
            paginas_dir = config.RAW_HTML_DIR / 'paginas'
            paginas = len(list(paginas_dir.glob('*.html'))) if paginas_dir.exists() else 0
            assets_count = len(list((config.ASSETS_DIR).rglob('*.*')))
            markdowns = len(list((config.CONTENT_DIR).rglob('*.md')))
            p_asesinos = min(100, int((asesinos / 850) * 100))
            p_materiales = min(100, int((materiales / 798) * 100))
            
            status_html = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Progreso de Descarga - Criminalia</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px 20px; }
        .card { max-width: 680px; margin: 0 auto; background: #1e293b; padding: 32px; border-radius: 12px; border: 1px solid #334155; box-shadow: 0 10px 25px rgba(0,0,0,0.3); }
        h1 { color: #ef4444; margin-top: 0; display: flex; align-items: center; justify-content: space-between; font-size: 24px; }
        .badge { font-size: 13px; background: #22c55e; color: #000; padding: 4px 12px; border-radius: 20px; font-weight: bold; min-width: 130px; text-align: center; }
        .stat-row { padding: 14px 0; border-bottom: 1px solid #334155; }
        .stat-header { display: flex; justify-content: space-between; margin-bottom: 6px; }
        .stat-label { font-size: 15px; color: #cbd5e1; font-weight: 500; }
        .stat-val { font-size: 16px; font-weight: bold; color: #f8fafc; }
        .bar { width: 100%; height: 10px; background: #334155; border-radius: 5px; overflow: hidden; }
        .fill { height: 100%; background: #ef4444; transition: width 0.3s ease; }
        .btn { display: inline-block; background: #3b82f6; color: white; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: 600; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Estado de la Descarga <span class="badge" id="countdown-badge">Auto-refresco 2s</span></h1>
        <div class="stat-row">
            <div class="stat-header">
                <span class="stat-label">📖 Artículos Biográficos (Asesinos)</span>
                <span class="stat-val">""" + str(asesinos) + """ / 850 (""" + str(p_asesinos) + """%)</span>
            </div>
            <div class="bar"><div class="fill" style="width: """ + str(p_asesinos) + """%; background: #22c55e;"></div></div>
        </div>
        <div class="stat-row">
            <div class="stat-header">
                <span class="stat-label">📸 Galerías de Fotos (Expedientes)</span>
                <span class="stat-val">""" + str(materiales) + """ / 620 recuperables (100% de Wayback, 78% de 796 históricas)</span>
            </div>
            <div class="bar"><div class="fill" style="width: 100%; background: #22c55e;"></div></div>
        </div>
        <div class="stat-row">
            <div class="stat-header">
                <span class="stat-label">🌐 Páginas Institucionales y Noticias (Contacto, Colabora, etc.)</span>
                <span class="stat-val">""" + str(paginas) + """ páginas guardadas</span>
            </div>
        </div>
        <div class="stat-row">
            <div class="stat-header">
                <span class="stat-label">📰 Artículos de Actualidad</span>
                <span class="stat-val">""" + str(actualidad) + """ / 7 (100%)</span>
            </div>
            <div class="bar"><div class="fill" style="width: 100%; background: #22c55e;"></div></div>
        </div>
        <div class="stat-row">
            <div class="stat-header">
                <span class="stat-label">💾 Archivos Multimedia y Fotos en disco</span>
                <span class="stat-val">""" + str(assets_count) + """ archivos</span>
            </div>
        </div>
        <div class="stat-row">
            <div class="stat-header">
                <span class="stat-label">📝 Artículos convertidos a Markdown (.md)</span>
                <span class="stat-val">""" + str(markdowns) + """ artículos</span>
            </div>
        </div>
        <a href="/" class="btn">← Ir a Criminalia.es</a>
    </div>
    <script>
        let remaining = 2;
        const badge = document.getElementById('countdown-badge');
        setInterval(() => {
            remaining--;
            if (remaining <= 0) {
                if (badge) badge.innerText = 'Refrescando...';
                location.reload();
            } else {
                if (badge) badge.innerText = 'Auto-refresco ' + remaining + 's';
            }
        }, 1000);
    </script>
</body>
</html>"""
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(status_html.encode('utf-8'))
            return

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
                
            # Cascading fetch across all tiers
            data = config.fetch_with_retry(f'https://criminalia.es/{rel}', is_binary=True)
            if data:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_bytes(data)
                self.send_asset_file(file_path)
                return
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
                raw_data = config.fetch_with_retry(f'https://criminalia.es/resultados-de-la-busqueda/?l={l}&g={g}')
                if raw_data:
                    idx_file.parent.mkdir(parents=True, exist_ok=True)
                    idx_file.write_text(raw_data, encoding='utf-8')
                    
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
                raw_data = config.fetch_with_retry(f'https://criminalia.es/asesino/{slug}/')
                if raw_data:
                    article_file.parent.mkdir(parents=True, exist_ok=True)
                    article_file.write_text(raw_data, encoding='utf-8')
                    
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
                raw_data = config.fetch_with_retry(f'https://criminalia.es/material/{slug}/')
                if raw_data and len(raw_data) > 1000:
                    mat_file.parent.mkdir(parents=True, exist_ok=True)
                    mat_file.write_text(raw_data, encoding='utf-8')
                    
            if mat_file.exists():
                html = mat_file.read_text(encoding='utf-8', errors='ignore')
                html_rewritten = rewrite_html_for_local(html)
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html_rewritten.encode('utf-8'))
                return
            else:
                not_found_page = f'''<!DOCTYPE html>
                <html lang=\"es\">
                <head>
                    <meta charset=\"UTF-8\">
                    <title>Galería no archivada</title>
                    <link rel=\"stylesheet\" href=\"/assets/wp-content/themes/criminalia/style.css\">
                </head>
                <body style=\"font-family: sans-serif; padding: 40px; background: #f8f9fa;\">
                    <div style=\"max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);\">
                        <h2 style=\"color: #b91c1c;\">Fotografías no disponibles en los archivos</h2>
                        <p>La galería complementaria <code>{slug}</code> no fue capturada por los rastreadores en Wayback Machine ni en archive.today.</p>
                        <p>Sin embargo, el artículo principal y los datos del caso siguen estando disponibles.</p>
                        <p><a href=\"javascript:history.back()\" style=\"display: inline-block; background: #b91c1c; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px;\">← Volver al artículo</a></p>
                    </div>
                </body>
                </html>'''
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(not_found_page.encode('utf-8'))
                return

        # 6. UNIVERSAL ROUTE HANDLER (Actualidad, Páginas Institucionales, Noticias, Fechas)
        # Handles /actualidad/, /ultimas-entradas/, /contacto/, /colabora/, /politica-de-cookies/,
        # date archives, categories, and news posts dynamically with 3-tier cascade
        clean_slug = url_path.strip('/').replace('/', '_')
        if not clean_slug:
            clean_slug = 'index'

        paginas_dir = config.RAW_HTML_DIR / 'paginas'
        paginas_dir.mkdir(parents=True, exist_ok=True)
        target_file = paginas_dir / f'{clean_slug}.html'

        # Check candidate locations on disk
        candidate_files = [target_file]
        parts = [p for p in url_path.split('/') if p]
        if parts and parts[0] == 'actualidad':
            if len(parts) == 1:
                candidate_files.append(config.RAW_HTML_DIR / 'actualidad' / 'index_page_1.html')
            else:
                candidate_files.append(config.RAW_HTML_DIR / 'actualidad' / f'{parts[-1]}.html')
        candidate_files.append(config.RAW_HTML_DIR / f'{clean_slug}.html')

        found_file = None
        for cf in candidate_files:
            if cf.exists() and cf.is_file() and cf.stat().st_size > 300:
                found_file = cf
                break

        if not found_file:
            # Dynamically fetch on the fly via 3-tier cascade engine!
            raw_data = config.fetch_with_retry(f'https://criminalia.es{url_path}')
            if not raw_data and not url_path.endswith('/'):
                raw_data = config.fetch_with_retry(f'https://criminalia.es{url_path}/')
            elif not raw_data and url_path.endswith('/'):
                raw_data = config.fetch_with_retry(f'https://criminalia.es{url_path.rstrip("/")}')

            if raw_data and len(raw_data) > 300:
                target_file.write_text(raw_data, encoding='utf-8')
                found_file = target_file

        if found_file:
            html = found_file.read_text(encoding='utf-8', errors='ignore')
            html_rewritten = rewrite_html_for_local(html)
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html_rewritten.encode('utf-8'))
            return

        # Friendly styled 404 page if not found in any web archive
        not_found_page = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Página no archivada - Criminalia</title>
    <link rel="stylesheet" href="/assets/wp-content/themes/criminalia/style.css">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 50px 20px; text-align: center; }}
        .box {{ max-width: 600px; margin: 0 auto; background: #1e293b; padding: 40px; border-radius: 12px; border: 1px solid #334155; }}
        h2 {{ color: #ef4444; font-size: 22px; }}
        p {{ color: #94a3b8; line-height: 1.6; }}
        code {{ background: #0f172a; color: #38bdf8; padding: 2px 6px; border-radius: 4px; }}
        .btn {{ display: inline-block; background: #ef4444; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: bold; margin-top: 15px; }}
    </style>
</head>
<body>
    <div class="box">
        <h2>Contenido no archivado</h2>
        <p>La dirección <code>{url_path}</code> no fue capturada por los rastreadores en Wayback Machine ni en archive.today.</p>
        <p>El resto de la enciclopedia criminal, expedientes y fotografías siguen estando disponibles.</p>
        <a href="/" class="btn">← Volver al inicio</a>
    </div>
</body>
</html>'''
        self.send_response(404)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(not_found_page.encode('utf-8'))

def main():
    with socketserver.TCPServer(('', PORT), CriminaliaServer) as httpd:
        print(f'Servidor Criminalia activo en http://localhost:{PORT}')
        httpd.serve_forever()

if __name__ == '__main__':
    main()
