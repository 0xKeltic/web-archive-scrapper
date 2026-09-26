<img width="1536" height="1024" alt="imagen" src="https://github.com/user-attachments/assets/9ca9a9b7-e5f7-49fc-a98f-66a7c08e52a0" />


# 🌐 Universal Web Archive Scraper & Rebuilder Suite

A universal digital preservation and archival recovery tool engineered to systematically rescue, locally reconstruct, and convert **any fallen or live website** into structured Markdown from **The Internet Archive (Wayback Machine)**, secondary preservation networks like **archive.today (archive.ph)**, or **active live web servers**.

Originally developed and field-tested in production during large-scale digital preservation initiatives, this suite has been completely universalized to operate autonomously and platform-agnostically with any target domain.

---

## 🌟 Key Features

* **Universal & Platform-Agnostic:**
  * Compatible with any content management system (WordPress, Drupal, Joomla, Ghost, custom dynamic PHP, or static sites).
  * Supports preserving multiple websites concurrently in isolated domain workspaces (`data/<domain>/...`).
* **Dual Operation Modes (Historical Archive vs. Live Web):**
  * **Historical Archive Mode (Default):** Reconstructs offline sites from historical snapshots in Wayback Machine and archive.today using intelligent cascading fallback.
  * **Live Web Mode (`--live`):** Crawls, mirrors, and parses active, live websites directly from their active servers in real time without passing through archive intermediaries.
* **Autonomous URL Discovery:**
  * **Sitemap & Robots Ingestion:** Automatically detects, verifies, and ingests `/sitemap.xml`, `/sitemap_index.xml`, and directives from archived `/robots.txt`.
  * **Recursive BFS Graph Crawler:** Traverses internal site links breadth-first up to configurable depth (`--depth`).
* **3-Tier Cascading Fallback Engine:**
  * **Tier 1:** Standard snapshot at selected timestamp (or auto-detected via the Wayback CDX Server API).
  * **Tier 2 (Full Historical Wildcard):** If 404 is encountered, automatically searches the complete timeline using wildcard `2id_` and protocol swapping (`http` <-> `https`).
  * **Tier 3 (archive.today):** If absent in Wayback, queries the `archive.today` / `archive.ph` network with authentic browser headers.
* **Intelligent Heuristic Markdown Extraction (Trafilatura + Markdownify):**
  * Eliminates manual CSS selector configuration: automatically detects article titles, authors, publication dates, featured images, and clean body text while discarding navigation and ads.
  * Automatic rewriting of image references to local `/assets/...` paths.
  * Generates standardized YAML Frontmatter and a unified `database.json` index.
* **Local High-Fidelity Preview & On-The-Fly Rescue Server (`preview_server.py`):**
  * Browse any archived website locally at `http://localhost:8080/` with exact CSS layouts, fonts, and images.
  * Dynamic on-the-fly rescue: navigating to any un-downloaded page or asset instantly triggers background recovery and injects it into disk in real time.
  * Real-time preservation status monitor at `/status` with automatic interactive refresh.

---

## 🚀 Quick Start

Requires **Python 3.10+**:

```bash
# 1. Clone the repository
git clone https://github.com/0xKeltic/web-archive-scrapper.git
cd web-archive-scrapper

# 2. Install dependencies
pip install -r requirements.txt
```

---

## 💻 CLI Usage (`run_pipeline.py`)

### 1. Archiving or Scraping a Complete Website:
```bash
# Historical Archive Mode (default):
# Automatically detects the most recent snapshot in Wayback Machine and archive.today:
python run_pipeline.py --url https://example.com --all

# Live Web Mode (--live):
# Scrapes directly from the live, active web server (bypassing Wayback Machine):
python run_pipeline.py --url https://example.com --live --all

# Archive with a specific historical snapshot timestamp (e.g. May 12, 2020):
python run_pipeline.py --url https://example.com --date 20200512 --all

# Adjust BFS crawling depth (default: 3) and page ceiling:
python run_pipeline.py --url https://example.com --depth 4 --max-pages 10000 --all
```

### 2. Modular Step-by-Step Execution:
```bash
# Step 1: BFS Crawler and internal URL discovery
python run_pipeline.py --url https://example.com --step 1

# Step 2: Static asset inventory (CSS, JS, fonts, and images)
python run_pipeline.py --url https://example.com --step 2

# Step 3: Bulk HTML page downloads
python run_pipeline.py --url https://example.com --step 3

# Step 4: Bulk asset and media downloads
python run_pipeline.py --url https://example.com --step 4

# Step 5: Heuristic extraction to Markdown (.md) and database.json
python run_pipeline.py --url https://example.com --step 5
```

> **Note:** All pipeline modules are strictly idempotent. If a file already exists on disk with size > 0, it is automatically skipped. You can safely interrupt execution (`Ctrl+C`) and resume at any time.

### 3. Project Management & Browser Preview:
```bash
# List all preserved websites on your machine:
python run_pipeline.py --list

# Show detailed statistics for the active project:
python run_pipeline.py --status

# Launch the local preview server:
python run_pipeline.py --url https://example.com --serve
# Or start preview server directly on default port (8080):
python preview_server.py --domain example.com
```

* **Browse Preserved Web:** [http://localhost:8080](http://localhost:8080)
* **Live Status Dashboard:** [http://localhost:8080/status](http://localhost:8080/status)

---

## 📂 Directory Structure

```
web-archive-scrapper/
├── config.py                 # Dynamic project configuration & 3-tier cascading fallback engine
├── 01_crawler.py             # Step 1: Recursive BFS crawler & sitemap/robots detector
├── 02_discover_assets.py     # Step 2: Static asset inventory (CSS, JS, fonts, images)
├── 03_download_html.py       # Step 3: Bulk HTML downloader with relative path mapping
├── 04_download_assets.py     # Step 4: Multimedia downloader & recursive CSS asset scanner
├── 05_parse_articles.py      # Step 5: Heuristic article extractor (Trafilatura) to Markdown & JSON
├── preview_server.py         # Local proxy server with on-the-fly rescue & /status dashboard
├── run_pipeline.py           # Universal CLI and multi-project pipeline orchestrator
├── requirements.txt          # Python dependencies
├── README.md                 # Primary project documentation (English)
├── MANUAL.md                 # Technical Architecture & Developer Manual (English)
├── ROADMAP_UNIVERSAL_SCRAPER.md # Architectural specification and universalization roadmap
└── data/                     # Isolated local preservation storage (gitignored)
    └── <domain_slug>/        # Dedicated workspace for each preserved domain
        ├── manifests/        # pages_manifest.json, assets_manifest.json, missing_*.json
        ├── raw_html/         # Exact mirror of website HTML directory hierarchy
        ├── assets/           # Local CSS, JS, images, and fonts
        └── content/          # Clean .md articles with YAML Frontmatter & unified database.json
```

---

## 📄 Markdown Output Format

Each extracted document under `data/<domain>/content/<path>.md` includes standard YAML Frontmatter compatible with Next.js, Nuxt, Astro, and Hugo:

```yaml
---
title: "Extracted Article Title"
slug: "sample-slug-name"
date: "2021-04-15"
author: "Editorial Team"
featured_image: "/assets/uploads/featured-cover.jpg"
url: "https://example.com/news/sample-slug-name"
---

# Extracted Article Title

Clean extracted article body in Markdown with rewritten asset links...
```

Additionally, `data/<domain>/content/database.json` provides a unified searchable catalog of all parsed records for instant search integration or relational database ingestion.

---

## 🏆 Case Study: vintage-press.org

This suite successfully rescued and preserved 100% of the contents of the historical publication archive **vintage-press.org**:
- **850 comprehensive archival articles and feature stories**
- **620 photo galleries and investigative reports** (100% of historical captures)
- **227 documentation pages and news feeds**
- **3,726 media and static assets**
- Preserved cleanly into structured Markdown with YAML Frontmatter and complete local media.

---

## 📖 Further Documentation

* Refer to [MANUAL.md](MANUAL.md) for deep technical details on HTTP protocol headers, crawler heuristics, and advanced fallback configuration.

