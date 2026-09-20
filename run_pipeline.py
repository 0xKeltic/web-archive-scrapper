# -*- coding: utf-8 -*-
import sys
import argparse
import importlib
from pathlib import Path
from loguru import logger
import config

def list_existing_projects():
    """Lists all archived projects found in the data/ directory."""
    data_dir = config.DATA_DIR
    if not data_dir.exists():
        logger.info("No prior projects found in the data/ directory.")
        return []
    
    projects = [d for d in data_dir.iterdir() if d.is_dir()]
    if not projects:
        logger.info("No prior projects found in the data/ directory.")
        return []

    logger.info("Available preserved projects in data/:")
    for idx, p in enumerate(projects, 1):
        pages_count = len(list((p / 'raw_html').rglob('*.html'))) if (p / 'raw_html').exists() else 0
        assets_count = len(list((p / 'assets').rglob('*.*'))) if (p / 'assets').exists() else 0
        md_count = len(list((p / 'content').rglob('*.md'))) if (p / 'content').exists() else 0
        logger.info(f"  [{idx}] {p.name} | HTMLs: {pages_count} | Assets: {assets_count} | Markdown: {md_count}")
    return projects

def show_project_status():
    """Displays stats of the currently active project."""
    mode_str = "Live Web" if config.IS_LIVE_MODE else f"Historical Archive (Wayback: {config.CURRENT_TIMESTAMP})"
    logger.info(f"=== PROJECT STATUS: {config.CURRENT_DOMAIN} ===")
    logger.info(f"  Mode:              {mode_str}")
    logger.info(f"  Target URL:        {config.CURRENT_URL}")
    logger.info(f"  Directory:         {config.PROJECT_DATA_DIR}")
    if not config.IS_LIVE_MODE:
        logger.info(f"  Wayback Prefix:    {config.WAYBACK_RAW_PREFIX}")
    
    pages = len(list(config.RAW_HTML_DIR.rglob('*.html'))) if config.RAW_HTML_DIR.exists() else 0
    assets = len(list(config.ASSETS_DIR.rglob('*.*'))) if config.ASSETS_DIR.exists() else 0
    mds = len(list(config.CONTENT_DIR.rglob('*.md'))) if config.CONTENT_DIR.exists() else 0
    
    logger.info(f"  HTML Pages:        {pages}")
    logger.info(f"  Asset Files:       {assets}")
    logger.info(f"  Markdown Docs:     {mds}")
    logger.info("============================================")

def main():
    parser = argparse.ArgumentParser(
        description='Universal Web Archive & Live Scraper Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage Examples:
  # Archive a historical website from Wayback Machine / archive.today:
  python run_pipeline.py --url https://example.com --all

  # Scrape an active, live website directly (Live Web Mode):
  python run_pipeline.py --url https://example.com --live --all

  # Archive with explicit historical snapshot timestamp from Wayback:
  python run_pipeline.py --url https://example.com --date 20200512 --all

  # Run individual modular steps:
  python run_pipeline.py --url https://example.com --step 1   # BFS Graph Crawler
  python run_pipeline.py --url https://example.com --step 2   # Asset Inventory (CSS/JS/Img)
  python run_pipeline.py --url https://example.com --step 3   # Bulk HTML Download
  python run_pipeline.py --url https://example.com --step 4   # Bulk Asset Download
  python run_pipeline.py --url https://example.com --step 5   # Conversion to Markdown & DB

  # Preview the preserved site in local browser:
  python run_pipeline.py --url https://example.com --serve
  python run_pipeline.py --serve --port 8080

  # List saved projects:
  python run_pipeline.py --list
        """
    )
    
    parser.add_argument('--url', type=str, help='Target website URL to scrape or archive (e.g. https://example.com)')
    parser.add_argument('--live', action='store_true', help='Live web mode: scrape directly from active server instead of Wayback / archive.today')
    parser.add_argument('--date', '--timestamp', dest='date', type=str, help='Wayback snapshot timestamp (e.g. 20230711 or 20230711124744). If omitted, CDX detects the latest snapshot.')
    parser.add_argument('--depth', type=int, default=3, help='Maximum recursive BFS crawling depth (default: 3)')
    parser.add_argument('--max-pages', type=int, default=5000, help='Maximum number of pages to crawl (default: 5000)')
    parser.add_argument('--step', type=int, choices=[1, 2, 3, 4, 5], help='Execute a specific step (1: Crawler, 2: Assets, 3: HTMLs, 4: Download Assets, 5: Markdown)')
    parser.add_argument('--from-step', type=int, choices=[1, 2, 3, 4, 5], help='Start execution from this step onwards (e.g. --from-step 4 executes steps 4 and 5)')
    parser.add_argument('--threads', type=int, default=None, help='Concurrency worker threads for downloads (default: 8 in live mode, 3 in archive mode)')
    parser.add_argument('--all', action='store_true', help='Execute steps 1 through 5 sequentially')
    parser.add_argument('--serve', action='store_true', help='Start local preview server proxy')
    parser.add_argument('--port', type=int, default=8080, help='Port for the preview server (default: 8080)')
    parser.add_argument('--list', action='store_true', help='List saved projects in data/')
    parser.add_argument('--status', action='store_true', help='Display summary status of active project')

    args = parser.parse_args()

    if args.list:
        list_existing_projects()
        return

    # Initialize or load project
    if args.url:
        config.init_project(args.url, custom_timestamp=args.date, depth=args.depth, is_live=args.live)
    else:
        active = config.load_active_project()
        if active and args.live:
            config.init_project(active['target_url'], custom_timestamp=args.date, depth=args.depth, is_live=True)
        if not active and not args.serve:
            logger.warning("No --url was provided and no active project was found.")
            list_existing_projects()
            logger.info("Run: python run_pipeline.py --url https://example.com --all")
            return

    if args.status:
        show_project_status()
        if not (args.step or args.all or args.from_step or args.serve):
            return

    # Step Execution
    run_step1 = args.step == 1 or args.all or (args.from_step and args.from_step <= 1)
    run_step2 = args.step == 2 or args.all or (args.from_step and args.from_step <= 2)
    run_step3 = args.step == 3 or args.all or (args.from_step and args.from_step <= 3)
    run_step4 = args.step == 4 or args.all or (args.from_step and args.from_step <= 4)
    run_step5 = args.step == 5 or args.all or (args.from_step and args.from_step <= 5)

    if run_step1:
        logger.info(f">>> STEP 1: BFS crawl & URL discovery for {config.CURRENT_DOMAIN}...")
        step1 = importlib.import_module('01_crawler')
        step1.crawl_site_bfs(config.CURRENT_URL, max_depth=args.depth, max_pages=args.max_pages)

    if run_step2:
        logger.info(f">>> STEP 2: Discovering static assets (CSS, JS, Fonts, Images)...")
        step2 = importlib.import_module('02_discover_assets')
        step2.main()

    if run_step3:
        logger.info(f">>> STEP 3: Downloading HTML pages to {config.RAW_HTML_DIR}...")
        step3 = importlib.import_module('03_download_html')
        step3.download_all_pages()

    if run_step4:
        logger.info(f">>> STEP 4: Downloading static files to {config.ASSETS_DIR}...")
        step4 = importlib.import_module('04_download_assets')
        step4.download_all_assets(max_workers=args.threads)

    if run_step5:
        logger.info(f">>> STEP 5: Parsing heuristic content to Markdown & JSON in {config.CONTENT_DIR}...")
        step5 = importlib.import_module('05_parse_articles')
        step5.export_all()

    if args.serve:
        logger.info(f">>> Starting preview server at http://localhost:{args.port}/...")
        preview = importlib.import_module('preview_server')
        preview.run_server(port=args.port)

    if not args.step and not args.all and not args.from_step and not args.serve and not args.status:
        show_project_status()
        logger.info("To run the complete pipeline use: python run_pipeline.py --all")

if __name__ == '__main__':
    main()
