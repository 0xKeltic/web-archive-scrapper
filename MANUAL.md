# Criminalia.es Preservation Suite - Technical Architecture & Developer Manual

A comprehensive guide to the extraction, multi-tier historical recovery, local replication, and structured export pipeline for the true-crime encyclopedia **Criminalia.es**.

---

## 1. System Overview

**Criminalia.es** was a major Spanish-language true-crime encyclopedia founded and authored by criminologist Juan Ignacio Blanco. Following his passing, the site went offline. This preservation suite was engineered to systematically recover 100% of the encyclopedia—including articles, photo galleries, case files, stylesheets, scripts, and media—from **The Internet Archive (Wayback Machine)** and secondary digital preservation networks like **archive.today (archive.ph)**.

### Core Objectives:
1. **Zero-Loss Crawling:** Discover every single archived entry without blind crawling.
2. **Multi-Tier Fallback Engine:** Mitigate false 404s caused by point-in-time snapshot gaps.
3. **Local High-Fidelity Replication:** Re-serve the original site locally with all assets and stylesheets intact.
4. **Structured Knowledge Export:** Transform archaic WordPress markup into clean Markdown (`.md`) with YAML frontmatter and unified JSON schemas for modern Jamstack deployment (Next.js / Astro).

---

## 2. Multi-Tier Cascading Fallback Architecture

Web archives do not take atomic snapshots of an entire domain simultaneously; individual pages and assets are crawled across different dates and years. Querying an archive with a single fixed timestamp often returns `404 Not Found` for files captured on earlier or later dates.

To solve this, our suite implements a **3-Tier Cascading Fallback**:

```
[Target Resource Request]
          │
          ▼
┌────────────────────────────────────────┐
│  Tier 1: Primary Snapshot (2023-07-11) │
└────────────────────────────────────────┘
          │ (if 404 Not Found)
          ▼
┌────────────────────────────────────────┐
│  Tier 2: Historical Wildcard (2id_)    │
│  - Traverses 2015–2022 captures        │
│  - Resolves HTTP / HTTPS protocol skew │
└────────────────────────────────────────┘
          │ (if 404 Not Found)
          ▼
┌────────────────────────────────────────┐
│  Tier 3: archive.today Network         │
│  - archive.is / archive.ph / archive.today
│  - Bypasses anti-bot rate limits       │
└────────────────────────────────────────┘
          │ (if 404 Not Found)
          ▼
┌────────────────────────────────────────┐
│  Terminal 404 Logged to Audit Trail    │
└────────────────────────────────────────┘
```

### Protocol Details:
- **Tier 1 (Wayback 2023):** `https://web.archive.org/web/20230711124744id_/<URL>`. Provides the most recent state before the site went dark.
- **Tier 2 (Wayback 2id_):** `https://web.archive.org/web/2id_/<URL>`. The `2id_` wildcard requests the raw un-wrapped content from the nearest historical capture in the 2000s–2020s. Both `http://` and `https://` schemas are evaluated to catch pre-SSL archives.
- **Tier 3 (archive.today):** Evaluates `archive.is`, `archive.today`, and `archive.ph` search endpoints using authentic browser headers to avoid Cloudflare challenges.

---

## 3. Pipeline Modules & Execution Flow

The suite is broken down into modular, decoupled, idempotent scripts orchestrated by `run_pipeline.py`:

```
┌──────────────────────────┐
│  01_discover_sitemap.py  │ ──► Generates articles_manifest.json (856 items)
└──────────────────────────┘
             │
             ▼
┌──────────────────────────┐
│  02_discover_assets.py   │ ──► Generates assets_manifest.json (CSS, JS, Fonts)
└──────────────────────────┘
             │
             ▼
┌──────────────────────────┐
│  03_download_html.py     │ ──► Downloads 856 main articles + ~800 photo galleries
└──────────────────────────┘
             │
             ▼
┌──────────────────────────┐
│ 03b_download_standalone  │ ──► Downloads 230+ institutional, country feeds & news posts
└──────────────────────────┘
             │
             ▼
┌──────────────────────────┐
│  04_download_assets.py   │ ──► Downloads 9,800+ crime photographs and assets
└──────────────────────────┘
             │
             ▼
┌──────────────────────────┐
│  05_parse_articles.py    │ ──► Generates Markdown (.md) files & database.json
└──────────────────────────┘
```

### Module Breakdown:

#### `01_discover_sitemap.py`
- Crawls the 78 master index query URLs (`?l=[a-z]&g=[hombre|mujer|crimen]`).
- Extracts all `/asesino/<slug>/` links and categorizes them by gender and letter.
- Scrapes the `/actualidad/` chronological archives.
- Produces `data/manifests/articles_manifest.json`.

#### `02_discover_assets.py`
- Parses template assets from key layouts (homepage, article, index).
- Discovers stylesheets (`style.css`, plugin CSS), scripts (`cycle2`, `fancybox`), and theme images.
- Produces `data/manifests/assets_manifest.json`.

#### `03_download_html.py`
- Sequentially fetches raw HTML pages using the cascading fetcher.
- Automatically scans each downloaded article for related photo gallery links (`/material/<slug>-fotos/`) and queues them for download.
- Idempotent: Skips files already stored locally with non-zero size.

#### `03b_download_standalone.py`
- Discovers all standalone pages across the site (institutional pages like `/contacto/`, `/colabora/`, `/ultimas-entradas/`, `/politica-de-cookies/`, regional country hubs `/actualidad/<pais>/`, date archives, and standalone crime news posts).
- Saves catalog to `data/manifests/standalone_manifest.json`.
- Downloads all pages into `data/raw_html/paginas/<slug>.html`.

#### `04_download_assets.py`
- Scans all downloaded HTML files for image tags (`<img>`, `data-src`, `data-lazy-src`).
- Downloads thousands of crime scene photos, mugshots, newspaper clippings, and evidence documents into `data/assets/wp-content/`.
- Traverses CSS files to discover background textures and font files (`@font-face`, `url(...)`).

#### `05_parse_articles.py`
- Strips legacy WordPress noise, tracking pixels, ads, and inline styling.
- Converts DOM trees into clean Markdown (`#`, `##`, `>`, lists, bold, italics).
- Rewrites image paths to point to local relative assets (`/assets/wp-content/...`).
- Generates YAML Frontmatter with metadata and exports individual `.md` files to `data/content/articles/` and the master index to `data/content/database.json`.

---

## 4. Local High-Fidelity Replica Server (`preview_server.py`)

To verify the scraped archive and browse the historical content without needing a live internet connection, a lightweight multi-threaded HTTP server is provided.

### Capabilities:
- **Port 8080:** Accessible at `http://localhost:8080/`.
- **Exact Visual Reproduction:** Serves the original homepage (`index.html`), slider, typography, and red header.
- **Dynamic Asset & Link Rewriting:** Intercepts legacy `https://criminalia.es/...` and `wp-criminalia/...` URLs, converting them into relative local paths.
- **Universal Catch-All Routing:** Any link clicked anywhere on the site (`/contacto/`, `/colabora/`, `/ultimas-entradas/`, crime news, country feeds) is dynamically resolved, downloaded on the fly if missing, and cached on disk.
- **Interactive Live Status Dashboard (`/status` & `/progreso`):**
  - Interactive JavaScript client-side countdown timer (2s → 1s → Refreshing...).
  - Real-time progress bars for:
    - Main biographical articles count (out of 850).
    - Photo gallery count (out of 798).
    - Institutional & standalone pages stored in disk.
    - Actualidad articles.
    - Downloaded media assets on disk.
    - Exported Markdown articles.

---

## 5. Data Specifications

### YAML Frontmatter Schema:
Every Markdown file generated in `data/content/articles/<slug>.md` conforms to this format:

```yaml
---
title: "Theodore Robert Bundy"
slug: "ted-bundy"
category: "hombre"
featured_image: "/assets/wp-content/uploads/2015/04/Ted-Bundy.jpg"
galleries: ["ted-bundy-fotos", "ted-bundy-fotos-1"]
url: "https://criminalia.es/asesino/ted-bundy/"
---

# Theodore Robert Bundy

... [Clean Markdown body text] ...
```

### `database.json` Schema:
The global database file `data/content/database.json` exports an array of article objects suitable for instant client-side search (e.g. Pagefind, MiniSearch, Algolia) or database seeding (PostgreSQL, SQLite):

```json
[
  {
    "title": "Theodore Robert Bundy",
    "slug": "ted-bundy",
    "category": "hombre",
    "featured_image": "/assets/wp-content/uploads/2015/04/Ted-Bundy.jpg",
    "galleries": ["ted-bundy-fotos", "ted-bundy-fotos-1"],
    "url": "https://criminalia.es/asesino/ted-bundy/",
    "excerpt": "Ted Bundy fue uno de los asesinos en serie más notorios de la historia de los Estados Unidos..."
  }
]
```

---

## 6. Command-Line Reference

```bash
# Full automated pipeline execution
python run_pipeline.py --all

# Granular step execution
python run_pipeline.py --step 1   # Discover site structure and index pages
python run_pipeline.py --step 2   # Audit and map static assets
python run_pipeline.py --step 3   # Download HTML articles and galleries
python run_pipeline.py --step 4   # Download photos, media, and fonts
python run_pipeline.py --step 5   # Export Markdown files and database.json

# Start the preview server
python preview_server.py
```

---

## 7. Rate Limiting & Etiquette

When crawling digital libraries like The Internet Archive:
- Keep concurrency between 1 and 3 worker threads.
- Implement exponential backoff upon encountering HTTP 429 or 503 status codes.
- Do not repeat requests for assets that are already verified on disk.
- Use explicit User-Agent identification.
