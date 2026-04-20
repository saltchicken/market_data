import os
import json
import urllib.request
import logging

logger = logging.getLogger("ibkr_alerts")

def trigger_alert(title: str, message: str):
    """
    Logs the alert and sends push notifications if webhooks are configured.
    Set DISCORD_WEBHOOK_URL or TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID in your .env
    """
    full_msg = f"{title}: {message}"
    
    # Log as WARNING so it routes to the console, main log, AND the alerts-only log file
    logger.warning(full_msg)

    # --- Discord Integration ---
    discord_url = os.getenv("DISCORD_WEBHOOK_URL")
    if discord_url:
        try:
            req = urllib.request.Request(discord_url, method="POST")
            req.add_header('Content-Type', 'application/json')
            req.add_header('User-Agent', 'Mozilla/5.0')
            data = json.dumps({"content": full_msg}).encode('utf-8')
            urllib.request.urlopen(req, data=data, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")

    # --- Telegram Integration ---
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if telegram_token and telegram_chat_id:
        try:
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            req = urllib.request.Request(url, method="POST")
            req.add_header('Content-Type', 'application/json')
            data = json.dumps({"chat_id": telegram_chat_id, "text": full_msg}).encode('utf-8')
            urllib.request.urlopen(req, data=data, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
