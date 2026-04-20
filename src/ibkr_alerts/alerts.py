import os
import json
import urllib.request
import logging

logger = logging.getLogger("ibkr_alerts")

def trigger_alert(title: str, message: str):
    """
    Logs the alert and sends push notifications.
    """
    full_msg = f"{title}: {message}"
    
    # Log as WARNING so it routes to the console, main log, AND the alerts-only log file
    logger.warning(full_msg)

    ## TODO: Implement reporting
