# -*- coding: utf-8 -*-
"""Backward compatible wrapper redirecting to universal 01_crawler.py"""
import importlib

def main():
    crawler = importlib.import_module('01_crawler')
    crawler.main()

if __name__ == '__main__':
    main()
