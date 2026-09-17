# -*- coding: utf-8 -*-
"""Deprecated: In the universal scraper, all standalone pages and sections are automatically discovered by 01_crawler.py and downloaded by 03_download_html.py."""
import importlib

def download_standalone_pages():
    step3 = importlib.import_module('03_download_html')
    step3.main()

if __name__ == '__main__':
    download_standalone_pages()
