# Universal Web Archive Preservation Suite - Technical Architecture & Developer Manual

A comprehensive engineering reference for the extraction, multi-tier historical recovery, local replication, and structured export pipeline for fallen or offline websites archived on **The Internet Archive (Wayback Machine)** and secondary preservation networks like **archive.today (archive.ph)**.

---

## 1. System Overview

Websites frequently disappear due to domain expirations, censorship, lack of maintenance, or author demise (as with the flagship case study **Criminalia.es**, authored by the late criminologist Juan Ignacio Blanco). This preservation suite was engineered to systematically recover 100% of any targeted website—including full article hierarchies, photo galleries, case files, stylesheets, scripts, and media assets—transforming raw archive snapshots into clean, structured Markdown ready for modern Jamstack deployment (Next.js, Astro, Nuxt, Hugo).

### Core Capabilities:
1. **Universal & CMS-Agnostic:** Operates without requiring prior knowledge of the site's underlying engine (WordPress, Drupal, Joomla, Ghost, custom PHP, or static HTML).
2. **Dual Operation Modes (Archive vs. Live Web):**
   - **Archive Mode (Default):** Rebuilds fallen sites from Wayback Machine and archive.today snapshots.
   - **Live Web Mode (`--live`):** Directly scrapes, mirrors, and parses active, live websites without passing through Internet Archive intermediaries.
3. **Autonomous URL Discovery:** Combines XML Sitemaps / `robots.txt` parsing with an adaptive Breadth-First Search (BFS) graph crawler.
4. **Multi-Tier Cascading Fallback:** Mitigates temporal gaps and false 404 errors across multiple archive repositories (in archive mode).
5. **Isolated Multi-Domain Workspaces:** Preserves multiple sites concurrently under isolated directories (`data/<domain_slug>/...`).
6. **Intelligent Heuristic Content Extraction:** Employs readability algorithms (`trafilatura` + `markdownify`) to extract clean body text, titles, authors, and dates without hardcoded CSS selectors.
7. **Local High-Fidelity Replica Server:** Re-serves any archived or scraped site locally with dynamic URL rewriting and on-the-fly missing asset rescue.

---

## 2. Multi-Tier Cascading Fallback Architecture

Web archives do not capture atomic snapshots of an entire domain simultaneously; individual pages and assets are crawled across different dates and years. Querying an archive with a single fixed timestamp often returns `404 Not Found` for resources captured on earlier or later dates.

To achieve maximum completeness, the suite implements an automated **3-Tier Cascading Fallback**:

```
[Target Resource Request: https://example.com/page]
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│  Tier 1: Dynamic Snapshot Timestamp (or CDX latest)    │
│  - Endpoint: web.archive.org/web/<TIMESTAMP>id_/<URL>  │
└────────────────────────────────────────────────────────┘
                     │ (if 404 Not Found)
                     ▼
┌────────────────────────────────────────────────────────┐
│  Tier 2: Historical Wildcard (2id_)                    │
│  - Endpoint: web.archive.org/web/2id_/<URL>            │
│  - Traverses entire historical timeline across years   │
│  - Protocol Swapping: evaluates both http:// & https://│
└────────────────────────────────────────────────────────┘
                     │ (if 404 Not Found)
                     ▼
┌────────────────────────────────────────────────────────┐
│  Tier 3: archive.today Preservation Network            │
│  - Queries archive.is / archive.today / archive.ph     │
│  - Authenticated browser headers to bypass rate limits │
└────────────────────────────────────────────────────────┘
                     │ (if 404 Not Found)
                     ▼
┌────────────────────────────────────────────────────────┐
│  Terminal 404 Logged to Audit Trail (missing_*.json)   │
└────────────────────────────────────────────────────────┘
```

### Protocol Mechanics:
- **Tier 1 (Wayback Timestamp RAW):** Queries `https://web.archive.org/web/{timestamp}id_/{url}`. The `id_` modifier requests the un-wrapped, raw payload without Wayback's injected JavaScript toolbar or analytics scripts.
- **Tier 2 (Wayback 2id_ Wildcard & Protocol Swap):** Queries `https://web.archive.org/web/2id_/{url}`. The `2id_` directive instructs Wayback's CDX cluster to locate the chronologically closest available 200 OK snapshot in its multi-decade index. If the target URL is HTTPS, an immediate fallback request evaluates the HTTP counterpart (critical for sites archived prior to Let's Encrypt / HTTPS adoption).
- **Tier 3 (archive.today Network):** Scans the search index across `archive.is`, `archive.today`, and `archive.ph` mirrors to locate mirror captures taken when Wayback was offline or blocked by `robots.txt`.

---

## 3. Pipeline Modules & Execution Flow

The suite is decomposed into modular, idempotent steps orchestrated by `run_pipeline.py`:

```
┌──────────────────────────────────────┐
│  01_crawler.py                       │ ──► Generates pages_manifest.json & stores HTMLs
│  (Sitemaps check + BFS Graph Crawl)  │
└──────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  02_discover_assets.py               │ ──► Generates assets_manifest.json (CSS/JS/Img/Font)
│  (CDX API query + HTML DOM Scanner)  │
└──────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  03_download_html.py                 │ ──► Downloads any remaining pages in raw_html/
└──────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  04_download_assets.py               │ ──► Downloads static assets & parses CSS @import/fonts
└──────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  05_parse_articles.py                │ ──► Extracts clean Markdown (.md) & database.json
│  (Trafilatura + Markdownify)         │
└──────────────────────────────────────┘
```

### Module Specifications:

#### `config.py` (Central Configuration & Cascading Engine)
- Dynamically initializes workspace settings via `init_project(target_url, custom_timestamp, depth)`.
- If no timestamp is provided, queries the Wayback CDX API (`fastLatest=true`) to discover the most recent active snapshot automatically.
- Sanitizes domain strings into safe filesystem slugs and instantiates directory trees under `data/<domain_slug>/`.
- Provides the thread-safe `fetch_with_retry` method implementing exponential backoff on HTTP 429/503 responses.

#### `01_crawler.py` (Universal Crawler & Sitemap Discoverer)
- **Phase A (Sitemaps & Robots):** Probes for `/sitemap.xml`, `/sitemap_index.xml`, `/robots.txt`, and common sitemap routes. Extracts all canonical internal URLs.
- **Phase B (BFS Graph Crawler):** Starting from the root URL `/`, executes a breadth-first search queue up to `--depth`. Normalizes relative URLs, discards binary attachments, anchors (`#`), and external links.
- Stores discovered HTML directly into `raw_html/` on the fly, eliminating redundant network calls in subsequent steps.
- Exports `pages_manifest.json`.

#### `02_discover_assets.py` (Resource Inventory)
- Queries Wayback CDX API with wildcard filtering for the domain (`url={domain}/*`) to retrieve historical inventories of CSS, JS, fonts, and images.
- Scans all local HTML files using BeautifulSoup to detect referenced stylesheets, deferred scripts (`data-src`), favicons, and `@font-face` fonts.
- Exports `assets_manifest.json`.

#### `03_download_html.py` (Bulk HTML Downloader)
- Reads `pages_manifest.json` and ensures 100% of discovered pages exist locally.
- Automatically skips files that already exist on disk with non-zero size (idempotent resume).
- Persists non-recoverable URLs into `missing_pages.json`.

#### `04_download_assets.py` (Media & Static Downloader)
- Reconstructs original server path hierarchies under `data/<domain_slug>/assets/`.
- Traverses downloaded `.css` files with regular expressions (`url(...)`) to discover nested web fonts (`.woff2`, `.ttf`) and background textures.
- Maintains `missing_assets.json` to avoid redundant HTTP requests during repeated executions.

#### `05_parse_articles.py` (Heuristic Content Extractor)
- Uses **Trafilatura**'s statistical text density algorithms to isolate primary article content from navigational menus, sidebars, cookie notices, and advertisements.
- Falls back to `markdownify` with HTML semantic containers (`<article>`, `<main>`) if heuristic density is low.
- Rewrites all internal image links to local paths (`/assets/<relative_path>`).
- Generates clean YAML Frontmatter and unifies the site catalog into `database.json`.

---

## 4. Local High-Fidelity Replica Server (`preview_server.py`)

A standalone, non-blocking proxy server enabling full local inspection of any preserved website.

### Key Features:
- **Universal Multi-Site Support:** Run `python preview_server.py --domain ejemplo.com` to mount any workspace in `data/`.
- **Dynamic Link Rewriting:** Strips absolute legacy domain URLs (e.g. `https://ejemplo.com/path` or `//ejemplo.com/path`) into relative local paths (`/path`).
- **On-the-Fly Rescue Engine:** If a user clicks an internal link or requests an asset that was not previously downloaded, the server catches the request, fetches it via the 3-tier cascade in ~1 second, caches it on disk, and renders it seamlessly.
- **Real-Time Monitor Dashboard (`/status`):**
  - Live animated countdown timer (2s).
  - Accurate counts of HTML pages, media assets, and generated Markdown files.

---

## 5. Data Formats & Schemas

### Directory Hierarchy:
```
data/<domain_slug>/
├── manifests/
│   ├── pages_manifest.json
│   ├── assets_manifest.json
│   ├── missing_pages.json
│   └── missing_assets.json
├── raw_html/
│   ├── index.html
│   ├── blog/
│   │   └── entry-1.html
│   └── contact.html
├── assets/
│   ├── css/
│   ├── js/
│   └── images/
└── content/
    ├── index.md
    ├── blog/
    │   └── entry-1.md
    └── database.json
```

### YAML Frontmatter Schema:
```yaml
---
title: "Article Title"
slug: "article-slug"
date: "2022-03-10"
author: "Author Name"
featured_image: "/assets/images/header.jpg"
url: "https://example.com/blog/article-slug"
---

# Article Title

Markdown body content with local image links:
![Figure 1](/assets/images/diagram.png)
```

### Global Catalog Schema (`database.json`):
```json
[
  {
    "title": "Article Title",
    "slug": "article-slug",
    "date": "2022-03-10",
    "author": "Author Name",
    "featured_image": "/assets/images/header.jpg",
    "relative_path": "blog/article-slug.md",
    "excerpt": "Opening snippet of article content for card previews..."
  }
]
```

---

## 6. CLI Reference (`run_pipeline.py`)

```bash
# Archive any fallen website from Wayback Machine / archive.today (Default):
python run_pipeline.py --url https://example.com --all

# Scrape an active, live website directly (Live Web Mode):
python run_pipeline.py --url https://example.com --live --all

# Archive with explicit historical snapshot timestamp:
python run_pipeline.py --url https://example.com --date 20210615 --all

# Customize BFS crawl recursion depth and limits:
python run_pipeline.py --url https://example.com --depth 4 --max-pages 10000 --all

# Run individual steps:
python run_pipeline.py --url https://example.com --step 1   # BFS Crawler
python run_pipeline.py --url https://example.com --step 2   # Asset Inventory
python run_pipeline.py --url https://example.com --step 3   # Download HTMLs
python run_pipeline.py --url https://example.com --step 4   # Download Assets
python run_pipeline.py --url https://example.com --step 5   # Parse to Markdown

# Inspect archived projects:
python run_pipeline.py --list
python run_pipeline.py --status

# Launch preview server:
python run_pipeline.py --url https://example.com --serve --port 8080
```

