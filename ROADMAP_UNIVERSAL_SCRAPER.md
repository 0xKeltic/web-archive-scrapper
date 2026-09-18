# 🚀 Universalization Plan: From Site-Specific Scraper to Universal Web Archiving Suite

This document details the architecture, file-by-file technical design, and migration plan executed to transform the original **Criminalia.es** scraper into a **100% universal digital preservation suite** capable of rescuing, locally reconstructing, and structuring **any fallen or live website** from Web Archive (Wayback Machine), Archive.today, or active live servers.

---

## 🎯 Universalization Objectives

Transform the suite into a multi-purpose CLI runnable with:

```bash
python run_pipeline.py --url https://any-website.com [options]
```

Where the tool autonomously:
1. Detects whether sitemaps exist (`sitemap.xml`, `robots.txt`).
2. If no sitemap exists, executes a **recursive graph crawler (Breadth-First Search)** starting from the root `/` to discover 100% of internal pages.
3. Stores data in isolated domain workspaces under `data/<domain>/...` (allowing concurrent preservation without collisions).
4. Downloads and reconstructs all CSS stylesheets, fonts, scripts, and multimedia images.
5. Employs an intelligent heuristic content extraction engine (**Readability / Trafilatura**) to convert any article to Markdown without requiring hand-coded CSS selectors.
6. Allows high-fidelity local browser preview at `http://localhost:8080/` replicating the original look-and-feel.

---

## 🏗️ Architecture Comparison: Original State vs. Universal Architecture

| Component | Initial State (Criminalia-specific) | Universal State (Any Target Domain) |
| :--- | :--- | :--- |
| **Parameters** | Hardcoded domain and date in `config.py` | CLI Arguments (`--url`, `--date`, `--depth`, `--live`) or auto-detected |
| **Storage** | Fixed folders `data/raw_html/`, `data/assets/` | Isolated workspaces: `data/<domain>/raw_html/`, `data/<domain>/assets/` |
| **Discovery** | 78 specific alphabetic index queries (`?l=a&g=hombre`) | **Recursive Graph Crawler (BFS)** + Automated `sitemap.xml` / `robots.txt` parser |
| **Routing** | Hardcoded rules (`/asesino/`, `/material/`, etc.) | Domain-agnostic URL router reproducing original hierarchical directory structures |
| **Markdown Parsing** | Specific CSS selectors (`.entry-content`, custom meta) | **Automated Heuristic Extraction (Readability / Trafilatura)** |
| **Local Server** | Static string replacement of `criminalia.es` | Dynamic proxy replacing `target_domain` with relative local paths & live status dashboard |

---

## 📋 File-by-File Technical Specifications

### 1. `config.py` (Dynamic Configuration & Fallback Engine)
* **Design & Implementation:**
  * Removed hardcoded target URLs.
  * Added `init_project(target_url, custom_timestamp=None, depth=3, is_live=False)`:
    * Extracts sanitized domain (e.g. `example.com`, `criminalia.es`) to define `DOMAIN_SLUG`.
    * Dynamically creates workspace directories:
      * `DATA_DIR / DOMAIN_SLUG / manifests`
      * `DATA_DIR / DOMAIN_SLUG / raw_html`
      * `DATA_DIR / DOMAIN_SLUG / assets`
      * `DATA_DIR / DOMAIN_SLUG / content`
  * Automated snapshot timestamp detection:
    * If no fixed date is provided, queries Wayback Machine's CDX Server API with reverse sort to lock onto the latest snapshot before site demise.
  * Preserves the **3-Tier Cascading Fallback Engine** (`fetch_with_retry`) supporting both historical archive and live web modes.

---

### 2. `01_crawler.py` (Universal Recursive BFS Graph Crawler)
* **Design & Implementation:**
  * Replaced manual catalog querying with a two-phase discovery engine:
    1. **Phase A (Sitemaps & Robots):** Inspects candidate endpoints:
       * `/robots.txt`
       * `/sitemap.xml`
       * `/sitemap_index.xml`
       * Extracts all internal URLs in bulk when available.
    2. **Phase B (Recursive BFS Graph Crawler):**
       * Seeds crawler from root `/` and any discovered sitemap links.
       * Queue of pending URLs (`queue = deque()`) and set of visited URLs (`visited = set()`).
       * For each retrieved HTML page:
         * Extracts internal `<a href="...">` links.
         * Normalizes URLs, stripping external domains, `#` fragments, session queries, and binary files.
         * Enqueues unvisited internal links up to `--depth`.
  * Generates `data/<domain>/manifests/pages_manifest.json`.

---

### 3. `02_discover_assets.py` (Dynamic Asset Inventory)
* **Design & Implementation:**
  * Queries Wayback CDX API for archived static assets under the domain (in archive mode).
  * Scans all discovered local HTML pages:
    * `<link rel="stylesheet">` $\rightarrow$ CSS stylesheets.
    * `<script src="...">` $\rightarrow$ JS scripts.
    * `<link rel="icon">`, `<link rel="apple-touch-icon">` $\rightarrow$ Favicons.
    * `<img src="...">`, `data-src`, `data-lazy-src` $\rightarrow$ Images.
    * CSS rules `@font-face` and `background: url(...)` $\rightarrow$ Fonts and background images.
  * Generates `data/<domain>/manifests/assets_manifest.json`.

---

### 4. `03_download_html.py` (Bulk HTML Downloader)
* **Design & Implementation:**
  * Reads `pages_manifest.json`.
  * Downloads each page recreating original URL directory structure on disk:
    * `example.com/news/case-1/` $\rightarrow$ `raw_html/news/case-1.html`.
  * Idempotent resume capability: automatically skips existing files.

---

### 5. `04_download_assets.py` (Multimedia & Stylesheet Downloader)
* **Design & Implementation:**
  * Recreates origin directory hierarchy under `data/<domain>/assets/`.
    * Example: `https://example.com/static/css/theme.css` $\rightarrow$ `data/<domain>/assets/static/css/theme.css`.
  * Recursive extraction of sub-resources (fonts and images declared in CSS files).
  * Automatic retry support with authentic `Referer` headers.

---

### 6. `05_parse_articles.py` (Intelligent Markdown Conversion)
* **Design & Implementation:**
  * Criminalia previously used site-specific CSS selectors (`div.entry-content`). On general websites (WordPress, Drupal, Joomla, Wix, Ghost, or custom PHP), hardcoded selectors break.
  * **Universal Solution:** Integrated heuristic libraries **`trafilatura`** and **`markdownify`**:
    * Analyzes DOM text density and semantic markup to automatically extract the title, main article body, date, author, and featured image.
    * Converts clean DOM trees to Markdown with rewritten local asset links.
    * Generates standardized YAML Frontmatter (`title`, `date`, `url`, `author`, `slug`, `featured_image`).
    * Produces a unified `database.json` index.

---

### 7. `preview_server.py` (Universal Local Preview Server)
* **Design & Implementation:**
  * Multi-site dynamic context switching via cookie or query string (`/?site=domain.com`).
  * Universal URL router that maps requests to local relative paths:
    * Static assets (`.css`, `.js`, `.png`, `.jpg`, `.woff2`, etc.) $\rightarrow$ served from `assets/` or rescued on-the-fly.
    * HTML pages $\rightarrow$ served from `raw_html/` or rescued on-the-fly.
  * Real-time preservation dashboard at `/status` displaying live page counts, asset counts, and auto-refresh.

---

### 8. `run_pipeline.py` (Modern CLI Orchestrator with `argparse`)
* **CLI User Interface:**

```bash
# Archive any website completely:
python run_pipeline.py --url https://example.org --all

# Scrape an active live website directly:
python run_pipeline.py --url https://example.org --live --all

# Archive with explicit historical snapshot timestamp:
python run_pipeline.py --url https://example.org --date 20190501 --all

# Execute a specific modular step:
python run_pipeline.py --url https://example.org --step 1  # Crawler only

# Launch local preview server:
python run_pipeline.py --url https://example.org --serve
```

---

## 🛠️ Required Dependencies in `requirements.txt`

```txt
requests>=2.31.0
beautifulsoup4>=4.12.0
loguru>=0.7.0
readability-lxml>=0.8.1
trafilatura>=1.6.0
markdownify>=0.11.6
tqdm>=4.66.0
python-dateutil>=2.8.2
```

---

## 📌 Summary & Engineering Achievements

1. Mitigated historical Wayback Machine 404 gaps using wildcard `2id_` across multi-year captures.
2. Built automated secondary fallback to the `archive.today` / `archive.ph` preservation network.
3. Implemented high-fidelity local browser preview server with dynamic URL rewriting and real-time on-the-fly rescue.
4. Seamlessly unified historical archive mode and active live web mode (`--live`) within a modular, idempotent pipeline architecture.

