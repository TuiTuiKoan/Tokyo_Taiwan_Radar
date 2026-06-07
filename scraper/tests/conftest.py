"""Minimal pytest configuration for scraper unit tests."""
import sys
import os

# Ensure the scraper package root is on sys.path so imports work without
# installing the package (e.g. `from sources.note_creators import ...`).
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
