"""
LINE Messaging API push helper.

Sends plain-text or structured messages to a single LINE user.
Requires: LINE_CHANNEL_TOKEN and LINE_USER_ID environment variables.
"""

import logging
import os
import requests

logger = logging.getLogger(__name__)

LINE_API_URL = "https://api.line.me/v2/bot/message/push"


def send_line_message(text: str) -> bool:
    """Send a text message to the configured LINE user. Returns True on success."""
    token = os.environ.get("LINE_CHANNEL_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")

    if not token or not user_id:
        logger.warning("LINE_CHANNEL_TOKEN or LINE_USER_ID not set — skipping LINE notification")
        return False

    # LINE has a 5000 char limit per text message; split if needed
    chunks = [text[i:i + 4900] for i in range(0, len(text), 4900)]

    for chunk in chunks:
        resp = requests.post(
            LINE_API_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            json={
                "to": user_id,
                "messages": [{"type": "text", "text": chunk}],
            },
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error("LINE push failed (%d): %s", resp.status_code, resp.text)
            return False

    logger.info("LINE message sent (%d chars)", len(text))
    return True