# -*- coding: utf-8 -*-
import http.server
import socketserver
import os
import re
import argparse
import mimetypes
import json
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

def set_active_project_context(domain: str):
    """Dynamically activates project settings (is_live, timestamp, prefix) for the given domain."""
    proj_dir = config.DATA_DIR / domain
    cfg_file = proj_dir / 'project_config.json'
    if cfg_file.exists():
        try:
            with open(cfg_file, 'r', encoding='utf-8') as f:
                c = json.load(f)
                config.CURRENT_URL = c.get('target_url', f'https://{domain}')
                config.CURRENT_DOMAIN = c.get('domain', domain)
                config.IS_LIVE_MODE = c.get('is_live', False)
                config.CURRENT_TIMESTAMP = c.get('timestamp', '')
                if config.IS_LIVE_MODE:
                    config.WAYBACK_RAW_PREFIX = ''
                else:
                    ts = config.CURRENT_TIMESTAMP or '2'
                    config.WAYBACK_RAW_PREFIX = f'https://web.archive.org/web/{ts}id_/'
                return
        except Exception:
            pass

class UniversalPreviewHandler(http.server.BaseHTTPRequestHandler):
    selected_domain = None

    def do_HEAD(self):
        self.do_GET()

    def log_message(self, format, *args):
        logger.debug(f'[{self.command}] {self.path} - {args[1] if len(args) > 1 else ""}')

    @classmethod
    def get_valid_projects(cls):
        """Returns directories in DATA_DIR that contain valid scraped website data, ignoring dummy/empty dirs."""
        valid = []
        if config.DATA_DIR.exists():
            for d in config.DATA_DIR.iterdir():
                if not d.is_dir() or d.name == 'example.com':
                    continue
                raw_html = d / 'raw_html'
                cfg = d / 'project_config.json'
                has_html = raw_html.exists() and any(raw_html.iterdir())
                if has_html or cfg.exists():
                    valid.append(d)
        return sorted(valid, key=lambda x: x.name)

    def get_target_domain(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        site = None

        if 'site' in qs and qs['site'][0]:
            site = qs['site'][0].strip().lower()
        elif 'domain' in qs and qs['domain'][0]:
            site = qs['domain'][0].strip().lower()

        if not site:
            cookie_hdr = self.headers.get('Cookie', '')
            for part in cookie_hdr.split(';'):
                part = part.strip()
                if part.startswith('active_site='):
                    site = part.split('=', 1)[1].strip().lower()
                    break

        if not site and UniversalPreviewHandler.selected_domain:
            site = UniversalPreviewHandler.selected_domain

        if site == 'example.com':
            site = None

        valid_projects = [d.name for d in self.get_valid_projects()]
        if not site or (valid_projects and site not in valid_projects):
            if valid_projects:
                site = valid_projects[0]
            else:
                site = config.CURRENT_DOMAIN

        new_cookie = f'active_site={site}; Path=/; SameSite=Lax'
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
        set_active_project_context(target_domain)

        proj_dir = config.DATA_DIR / target_domain
        raw_html_dir = proj_dir / 'raw_html'
        assets_dir = proj_dir / 'assets'
        content_dir = proj_dir / 'content'

        # 1. MULTI-SITE LIVE STATUS DASHBOARD (/status)
        if url_path in ('/status', '/progreso'):
            projects = self.get_valid_projects()
            cards_html = []

            for p in projects:
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
                    except Exception as e:
                        logger.warning(f'Error reading {cfg_file}: {e}')

                pages_count = len(list((p / 'raw_html').rglob('*.html'))) if (p / 'raw_html').exists() else 0
                assets_count = len(list((p / 'assets').rglob('*.*'))) if (p / 'assets').exists() else 0
                markdowns_count = len(list((p / 'content').rglob('*.md'))) if (p / 'content').exists() else 0

                is_active = (domain_name == target_domain)
                mode_badge = '<span class="badge badge-live">🌐 LIVE</span>' if is_live else f'<span class="badge badge-archive">🏛️ WAYBACK: {ts}</span>'
                active_pill = '<span class="active-tag">Active in Browser</span>' if is_active else ''
                border_style = 'border: 2px solid #0284c7;' if is_active else 'border: 1px solid #334155;'

                cards_html.append(f"""
                <div class="card" style="{border_style}">
                    <div class="card-top">
                        <div>
                            <span class="domain-title">{domain_name}</span>
                            {mode_badge}
                            {active_pill}
                        </div>
                        <a href="/?site={domain_name}" class="btn-explore">Explore Website →</a>
                    </div>
                    <div class="stat-grid">
                        <div class="stat-item">
                            <span class="stat-num">{pages_count}</span>
                            <span class="stat-lbl">📄 HTML Pages</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-num">{assets_count}</span>
                            <span class="stat-lbl">💾 Assets / Media</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-num">{markdowns_count}</span>
                            <span class="stat-lbl">📝 Markdown Docs</span>
                        </div>
                    </div>
                </div>
                """)

            cards_rendered = "\n".join(cards_html) if cards_html else """
                <div class="card" style="text-align: center; padding: 40px;">
                    <p style="color: #94a3b8; font-size: 16px;">No websites saved in data/ yet.</p>
                    <p style="color: #64748b; font-size: 14px;">Run <code>python run_pipeline.py --url &lt;URL&gt; --all</code> to begin.</p>
                </div>
            """

            total_projects = len(projects)
            status_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Multi-Site Preservation Dashboard</title>
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
            <h1>🌐 Multi-Site Monitor <span style="font-size: 14px; color: #94a3b8; font-weight: normal;">({total_projects} projects on disk)</span></h1>
            <span class="refresh-pill" id="countdown-badge">Auto-refresh 2s</span>
        </header>
        {cards_rendered}
    </div>
    <script>
        let remaining = 2;
        const badge = document.getElementById('countdown-badge');
        setInterval(() => {{
            remaining--;
            if (remaining <= 0) {{
                if (badge) badge.innerText = 'Refreshing...';
                location.reload();
            }} else {{
                if (badge) badge.innerText = 'Auto-refresh ' + remaining + 's';
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
            logger.info(f'[{target_domain}] [On-The-Fly Asset] Rescuing resource: {rel_asset}...')
            data = config.fetch_with_retry(original_asset_url, is_binary=True, timeout=8)
            if data:
                local_asset.parent.mkdir(parents=True, exist_ok=True)
                local_asset.write_bytes(data)
                self.send_asset_file(local_asset, cookie=new_cookie)
                return
            else:
                self.send_error(404, f'Asset not found: {rel_asset}')
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
        if target_domain == 'example.com':
            self.send_error(404, 'example.com is a placeholder and cannot be rescued.')
            return

        full_target_url = f'https://{target_domain}{url_path}'
        logger.info(f'[{target_domain}] [On-The-Fly] Rescuing page: {full_target_url}...')
        fetched_content = config.fetch_with_retry(full_target_url, timeout=8)
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
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>404 - Page not archived</title>
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
        <h2>Resource not found</h2>
        <p>The address <code>{url_path}</code> is not saved on disk for <code>{target_domain}</code> and could not be recovered.</p>
        <a href="/" class="btn">← Back to Home</a>
        <a href="/status" class="btn" style="background: #334155; margin-left: 10px;">Multi-Site Monitor</a>
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
        valid = UniversalPreviewHandler.get_valid_projects()
        active_display = valid[0].name if valid else config.CURRENT_DOMAIN
        logger.success(f'Universal multithreaded local server started for {active_display}')
        logger.info(f'-> Preserved website: http://localhost:{port}/')
        logger.info(f'-> Status monitor: http://localhost:{port}/status')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info('Server stopped by user.')

def main():
    parser = argparse.ArgumentParser(description='Universal Web Archive Preview Server')
    parser.add_argument('--domain', type=str, help='Domain to serve (e.g. example.com, example.org)')
    parser.add_argument('--port', type=int, default=8080, help='Local port (default: 8080)')
    args = parser.parse_args()

    if args.domain:
        config.init_project(args.domain)

    run_server(args.port)

if __name__ == '__main__':
    main()
