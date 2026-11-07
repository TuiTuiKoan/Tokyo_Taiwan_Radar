"""Minimal pytest configuration for scraper unit tests."""
import sys
import os

# Ensure the scraper package root is on sys.path so imports work without
# installing the package (e.g. `from sources.note_creators import ...`).
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Never report test-generated errors to the production Sentry project.
# main.py calls load_dotenv() (which does not override existing variables) and
# initialises Sentry only when SENTRY_DSN is truthy, so an empty value here
# keeps Sentry disabled even when a local .env defines the real DSN (#542).
os.environ["SENTRY_DSN"] = ""
