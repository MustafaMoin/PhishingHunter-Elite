"""
blocklists.py
--------------
Pulls free, no-API-key-required community phishing/malware feeds and
loads them into the local SQLite blocklist table:

  - OpenPhish community feed   (https://openphish.com/feed.txt)
  - URLhaus (abuse.ch) recent  (https://urlhaus.abuse.ch/downloads/text_recent/)

A blocklist hit is a DETERMINISTIC signal — if a URL is on one of these
feeds we don't need heuristics to guess, we already know. This is the
single highest-leverage accuracy upgrade over pure heuristic scoring,
because it catches real, currently-active phishing kits that look
"structurally clean" (short URL, valid TLS, aged domain bought just for
the campaign) and would otherwise slip past rule-based scoring.

Both feeds are free for reasonable use but rate-limited — refresh on a
schedule (default: every 2 hours), not on every request.
"""

import requests
import logging
import threading
import time

import database

logger = logging.getLogger("phishinghunter.blocklists")

OPENPHISH_URL = "https://openphish.com/feed.txt"
URLHAUS_URL = "https://urlhaus.abuse.ch/downloads/text_recent/"
FETCH_TIMEOUT = 15
REFRESH_INTERVAL_SECONDS = 2 * 60 * 60  # 2 hours


def _fetch_lines(url):
    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT, headers={"User-Agent": "PhishingHunter/2.0"})
        resp.raise_for_status()
        return [line.strip() for line in resp.text.splitlines() if line.strip() and not line.startswith("#")]
    except requests.exceptions.RequestException as e:
        logger.warning("Blocklist fetch failed for %s: %s", url, e)
        return []


def refresh_blocklists():
    openphish_urls = _fetch_lines(OPENPHISH_URL)
    urlhaus_urls = _fetch_lines(URLHAUS_URL)

    if openphish_urls:
        database.bulk_insert_blocklist(openphish_urls, "OpenPhish")
    if urlhaus_urls:
        database.bulk_insert_blocklist(urlhaus_urls, "URLhaus")

    logger.info(
        "Blocklist refresh done: +%d OpenPhish, +%d URLhaus, total=%d",
        len(openphish_urls), len(urlhaus_urls), database.blocklist_size(),
    )


def start_background_refresh():
    """Fire-and-forget: initial fetch, then repeat on a timer thread.
    Safe to call once at app startup. Never blocks the caller."""

    def loop():
        while True:
            try:
                refresh_blocklists()
            except Exception as e:
                logger.error("Blocklist refresh loop error: %s", e)
            time.sleep(REFRESH_INTERVAL_SECONDS)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
