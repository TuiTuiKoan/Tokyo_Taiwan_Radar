"""Session-wide test settings for everything under scraper/.

Many modules call load_dotenv() at import, which can load real Supabase
credentials from scraper/.env. Keep the LLM usage ledger off so test doubles
never write rows into production llm_usage (scraper/llm_client.py).
"""
import os

os.environ["LLM_USAGE_DISABLED"] = "1"
