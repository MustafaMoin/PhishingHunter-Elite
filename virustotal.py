"""
virustotal.py
-------------
VirusTotal API v3 integration for PhishingHunter.

VirusTotal aggregates results from 70+ antivirus engines and URL scanners,
providing a community consensus score. Unlike binary blocklist hits, VT
gives us a *ratio* of how many vendors flagged the URL, which we can use
as a weighted signal.

Key differences from Google Safe Browsing:
  - Multi-vendor consensus (not just Google's data)
  - Returns a malicious/suspicious count, not just yes/no
  - Free tier is rate-limited to 4 requests/minute
  - Results are cached aggressively (1 hour) to conserve quota

Setup:
  1. Get a free API key from VirusTotal:
     https://www.virustotal.com/gui/join-us
  2. Set environment variable: VIRUSTOTAL_API_KEY=your_key_here

The detector.py module calls check_url() and uses the malicious-vendor
ratio as a weighted signal (more vendors flagging = higher score).
"""

import os
import time
import logging
import hashlib
import requests
import sqlite3
import threading

logger = logging.getLogger("phishinghunter.virustotal")

API_KEY = os.environ.get("VIRUSTOTAL_API_KEY")
API_BASE = "https://www.virustotal.com/api/v3"
TIMEOUT = 4

# VirusTotal free tier: 4 requests/minute
VT_RATE_LIMIT_REQUESTS = 4
VT_RATE_LIMIT_WINDOW = 60  # seconds

# Cache VT results for 1 hour (they don't change often, and we want to conserve quota)
VT_CACHE_TTL = 3600  # 1 hour

# Database path for rate limiting (reuse existing database)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "phishinghunter.db")
_lock = threading.Lock()


def _get_conn():
    """Get database connection (reuses existing database)."""
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_vt_tables():
    """Initialize VirusTotal-specific tables if they don't exist."""
    with _lock, _get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS vt_rate_limit (
                window_start INTEGER PRIMARY KEY,
                count INTEGER NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS vt_cache (
                url_hash TEXT PRIMARY KEY,
                result_json TEXT NOT NULL,
                cached_at REAL NOT NULL
            );
            """
        )
        conn.commit()


# Initialize tables on import
_init_vt_tables()


def _check_rate_limit():
    """
    Check if we're within VirusTotal's rate limit (4 req/min).
    Returns True if allowed, False if limit exceeded.
    """
    window_start = int(time.time() // VT_RATE_LIMIT_WINDOW) * VT_RATE_LIMIT_WINDOW
    
    with _lock, _get_conn() as conn:
        row = conn.execute(
            "SELECT count FROM vt_rate_limit WHERE window_start = ?",
            (window_start,),
        ).fetchone()
        
        if row is None:
            # New window, reset counter
            conn.execute(
                "DELETE FROM vt_rate_limit WHERE window_start < ?",
                (window_start - VT_RATE_LIMIT_WINDOW * 2,),  # cleanup old windows
            )
            conn.execute(
                "INSERT INTO vt_rate_limit (window_start, count) VALUES (?, 1)",
                (window_start,),
            )
            conn.commit()
            return True
        
        if row["count"] >= VT_RATE_LIMIT_REQUESTS:
            logger.debug("VirusTotal rate limit exceeded, skipping check")
            return False
        
        conn.execute(
            "UPDATE vt_rate_limit SET count = count + 1 WHERE window_start = ?",
            (window_start,),
        )
        conn.commit()
        return True


def _get_cached_result(url):
    """Get cached VT result if available and not expired."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT result_json, cached_at FROM vt_cache WHERE url_hash = ?",
            (url_hash,),
        ).fetchone()
        
        if row and (time.time() - row["cached_at"]) < VT_CACHE_TTL:
            import json
            return json.loads(row["result_json"])
        
        return None


def _cache_result(url, result):
    """Cache VT result for 1 hour."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    import json
    
    with _lock, _get_conn() as conn:
        conn.execute(
            """INSERT INTO vt_cache (url_hash, result_json, cached_at) 
               VALUES (?, ?, ?)
               ON CONFLICT(url_hash) 
               DO UPDATE SET result_json=excluded.result_json, cached_at=excluded.cached_at""",
            (url_hash, json.dumps(result), time.time()),
        )
        conn.commit()


def check_url(url: str) -> dict:
    """
    Check a URL against VirusTotal API v3.
    
    Args:
        url: The URL to check
    
    Returns:
        dict with keys:
          - malicious_count: number of vendors that flagged as malicious
          - suspicious_count: number of vendors that flagged as suspicious
          - total_vendors: total number of vendors that analyzed the URL
          - ratio: (malicious + suspicious) / total (0.0 to 1.0)
          - details: human-readable description
        
        Returns None if:
          - API key is not configured
          - Rate limit exceeded
          - API call fails/times out
          - Any error occurs (fail-soft pattern)
    """
    if not API_KEY:
        logger.debug("VirusTotal API key not configured, skipping check")
        return None
    
    if not url:
        return None
    
    # Check cache first
    cached = _get_cached_result(url)
    if cached:
        logger.debug("VirusTotal cache hit for URL: %s", url[:50])
        return cached
    
    # Check rate limit
    if not _check_rate_limit():
        return None
    
    try:
        # Step 1: Submit URL for analysis (or get existing report)
        # We use the /urls endpoint which accepts a URL and returns analysis ID
        import base64
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        
        # Try to get existing report first
        response = requests.get(
            f"{API_BASE}/urls/{url_id}",
            headers={
                "x-apikey": API_KEY,
                "User-Agent": "PhishingHunter/2.0",
            },
            timeout=TIMEOUT,
        )
        
        # If URL hasn't been scanned yet (404), submit it
        if response.status_code == 404:
            logger.debug("URL not in VT database, submitting for analysis: %s", url[:50])
            submit_response = requests.post(
                f"{API_BASE}/urls",
                headers={
                    "x-apikey": API_KEY,
                    "User-Agent": "PhishingHunter/2.0",
                },
                data={"url": url},
                timeout=TIMEOUT,
            )
            
            if submit_response.status_code not in (200, 201):
                logger.warning(
                    "VT URL submission failed with status %d: %s",
                    submit_response.status_code,
                    submit_response.text[:200],
                )
                return None
            
            # URL submitted, but analysis not ready yet
            # Return a neutral result indicating analysis is pending
            result = {
                "malicious_count": 0,
                "suspicious_count": 0,
                "total_vendors": 0,
                "ratio": 0.0,
                "details": "VirusTotal: Analysis queued (check again later)",
                "pending": True,
            }
            _cache_result(url, result)
            return result
        
        if response.status_code != 200:
            logger.warning(
                "VT API returned status %d: %s",
                response.status_code,
                response.text[:200],
            )
            return None
        
        data = response.json()
        
        # Parse analysis results
        attributes = data.get("data", {}).get("attributes", {})
        stats = attributes.get("last_analysis_stats", {})
        
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        harmless = stats.get("harmless", 0)
        undetected = stats.get("undetected", 0)
        
        total = malicious + suspicious + harmless + undetected
        
        if total == 0:
            # No vendors have analyzed this URL yet
            result = {
                "malicious_count": 0,
                "suspicious_count": 0,
                "total_vendors": 0,
                "ratio": 0.0,
                "details": "VirusTotal: No analysis available yet",
                "pending": True,
            }
            _cache_result(url, result)
            return result
        
        ratio = (malicious + suspicious) / total if total > 0 else 0.0
        
        # Build human-readable description
        if malicious == 0 and suspicious == 0:
            details = f"VirusTotal: Clean ({total} vendors, 0 flagged)"
        else:
            details = f"VirusTotal: {malicious} malicious, {suspicious} suspicious (out of {total} vendors)"
        
        result = {
            "malicious_count": malicious,
            "suspicious_count": suspicious,
            "total_vendors": total,
            "ratio": ratio,
            "details": details,
            "pending": False,
        }
        
        # Cache the result
        _cache_result(url, result)
        
        return result
    
    except requests.exceptions.Timeout:
        logger.warning("VirusTotal API timeout for URL: %s", url[:50])
        return None
    
    except requests.exceptions.RequestException as e:
        logger.warning("VirusTotal API request failed: %s", e)
        return None
    
    except Exception as e:
        logger.error("Unexpected error in VirusTotal check: %s", e)
        return None
