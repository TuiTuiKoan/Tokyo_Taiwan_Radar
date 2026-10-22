# Keep the LLM usage ledger off under unittest too (see scraper/conftest.py).
import os

os.environ["LLM_USAGE_DISABLED"] = "1"
