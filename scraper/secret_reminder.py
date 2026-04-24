"""
Secret rotation reminder — sends a LINE notification listing all secrets
that should be rotated on a 90-day cycle.

Usage:
    python secret_reminder.py
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from line_notify import send_line_message

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


def build_message() -> str:
    today = datetime.now(JST).strftime("%Y-%m-%d")
    # Next rotation is 90 days from today
    next_rotation = (datetime.now(JST) + timedelta(days=90)).strftime("%Y-%m-%d")

    return "\n".join([
        "🔐 Tokyo Taiwan Radar — Secret 輪換提醒",
        f"日期：{today}",
        "",
        "距今 90 天內請完成以下輪換：",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "1. Supabase JWT Secret",
        "   → anon key + service_role key 同時更新",
        "   Supabase Dashboard → Settings → JWT Keys",
        "   更新後同步到：scraper/.env、GitHub Secrets",
        "",
        "2. OpenAI API Key",
        "   https://platform.openai.com/api-keys",
        "   → 建新 key → 刪舊 key",
        "   更新：scraper/.env、GitHub Secrets (OPENAI_API_KEY)",
        "",
        "3. LINE Channel Access Token",
        "   LINE Developers Console → Messaging API → Reissue",
        "   更新：scraper/.env、GitHub Secrets (LINE_CHANNEL_TOKEN)",
        "",
        "4. Sentry Auth Token（如有設定）",
        "   https://sentry.io/settings/account/api/auth-tokens/",
        "   更新：Vercel env (SENTRY_AUTH_TOKEN)",
        "   GitHub Secrets (SENTRY_AUTH_TOKEN)",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"下次提醒：{next_rotation}",
    ])


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    msg = build_message()
    send_line_message(msg)
    logger.info("Secret rotation reminder sent via LINE.")
