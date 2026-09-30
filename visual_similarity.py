"""
visual_similarity.py
--------------------
Screenshot-based visual phishing detection for PhishingHunter.

This module catches the most sophisticated phishing attacks: pixel-perfect
clones of brand login pages hosted on clean, aged, HTTPS-secured domains
that pass every text-based heuristic check.

How it works:
  1. Use Playwright (headless Chromium) to screenshot the submitted URL
  2. Resize to fixed size (256x256) and compute perceptual hash
  3. Compare against reference hashes of known brand login pages
  4. If visual match BUT domain mismatch → high-severity signal

This is what separates "good heuristic tool" from "tool that catches
sophisticated campaigns."

Setup:
  1. pip install playwright imagehash Pillow
  2. playwright install chromium
  3. Reference screenshots are stored in database (visual_reference table)

IMPORTANT: Screenshots are cached aggressively (24 hours) to avoid
repeatedly screenshotting the same page.
"""

import os
import io
import time
import logging
import hashlib
import sqlite3
import threading
from typing import Optional, Tuple

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    from PIL import Image
    import imagehash
    VISUAL_AVAILABLE = True
except ImportError:
    VISUAL_AVAILABLE = False
    sync_playwright = None
    Image = None
    imagehash = None
    PlaywrightTimeout = Exception

logger = logging.getLogger("phishinghunter.visual")

# Configuration
SCREENSHOT_TIMEOUT = 8000  # 8 seconds max
SCREENSHOT_WIDTH = 1280
SCREENSHOT_HEIGHT = 800
HASH_SIZE = 16  # perceptual hash size (16x16 = 256 bits)
SCREENSHOT_CACHE_TTL = 86400  # 24 hours
HAMMING_DISTANCE_THRESHOLD = 10  # Similar if distance <= 10

# Database path
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "phishinghunter.db")
_lock = threading.Lock()

# Check if running in production (Render) or local
IS_PRODUCTION = os.getenv("RENDER") is not None or not os.path.exists(os.path.dirname(DB_PATH))


def _get_conn():
    """Get database connection."""
    if IS_PRODUCTION:
        return None  # Skip SQLite in production
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_visual_tables():
    """Initialize visual similarity tables if they don't exist."""
    if IS_PRODUCTION:
        return  # Skip table creation in production
    conn = _get_conn()
    if conn:
        try:
            with _lock, conn:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS visual_reference (
                        brand TEXT NOT NULL,
                        domain TEXT NOT NULL,
                        page_type TEXT NOT NULL,
                        phash TEXT NOT NULL,
                        screenshot_blob BLOB,
                        added_at REAL NOT NULL,
                        PRIMARY KEY (brand, page_type)
                    );
                    
                    CREATE TABLE IF NOT EXISTS visual_cache (
                        url_hash TEXT PRIMARY KEY,
                        phash TEXT NOT NULL,
                        screenshot_blob BLOB,
                        cached_at REAL NOT NULL
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_visual_cache_time ON visual_cache(cached_at);
                    """
                )
                conn.commit()
        finally:
            conn.close()


# Initialize tables on import (only if visual features are available)
if VISUAL_AVAILABLE:
    try:
        _init_visual_tables()
    except Exception as e:
        logger.warning(f"Could not initialize visual tables: {e}")


def is_available():
    """Check if visual similarity features are available."""
    return VISUAL_AVAILABLE


def _take_screenshot(url: str) -> Optional[bytes]:
    """
    Take a screenshot of the URL using Playwright.
    
    Returns:
        bytes: PNG screenshot data
        None: if screenshot failed
    """
    if not VISUAL_AVAILABLE:
        return None
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": SCREENSHOT_WIDTH, "height": SCREENSHOT_HEIGHT},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            page = context.new_page()
            
            # Navigate with timeout
            page.goto(url, timeout=SCREENSHOT_TIMEOUT, wait_until="networkidle")
            
            # Take screenshot
            screenshot_bytes = page.screenshot(type="png", full_page=False)
            
            browser.close()
            return screenshot_bytes
    
    except PlaywrightTimeout:
        logger.warning("Screenshot timeout for URL: %s", url[:50])
        return None
    
    except Exception as e:
        logger.warning("Screenshot failed for URL %s: %s", url[:50], e)
        return None


def _compute_phash(screenshot_bytes: bytes) -> Optional[str]:
    """
    Compute perceptual hash from screenshot bytes.
    
    Returns:
        str: Hex string of perceptual hash
        None: if computation failed
    """
    if not VISUAL_AVAILABLE:
        return None
    
    try:
        img = Image.open(io.BytesIO(screenshot_bytes))
        # Resize to fixed size for consistent hashing
        img = img.resize((256, 256), Image.Resampling.LANCZOS)
        phash = imagehash.phash(img, hash_size=HASH_SIZE)
        return str(phash)
    
    except Exception as e:
        logger.error("Perceptual hash computation failed: %s", e)
        return None


def _get_cached_screenshot(url: str) -> Optional[Tuple[str, bytes]]:
    """Get cached screenshot phash and data if available."""
    if IS_PRODUCTION:
        return None  # Skip caching in production
    
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    
    conn = _get_conn()
    if not conn:
        return None
    
    try:
        row = conn.execute(
            "SELECT phash, screenshot_blob, cached_at FROM visual_cache WHERE url_hash = ?",
            (url_hash,),
        ).fetchone()
        
        if row and (time.time() - row["cached_at"]) < SCREENSHOT_CACHE_TTL:
            return row["phash"], row["screenshot_blob"]
        
        return None
    finally:
        conn.close()


def _cache_screenshot(url: str, phash: str, screenshot_bytes: bytes):
    """Cache screenshot and phash for 24 hours."""
    if IS_PRODUCTION:
        return  # Skip caching in production
    
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    
    conn = _get_conn()
    if not conn:
        return
    
    try:
        with _lock, conn:
            conn.execute(
                """INSERT INTO visual_cache (url_hash, phash, screenshot_blob, cached_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(url_hash) 
                   DO UPDATE SET phash=excluded.phash, screenshot_blob=excluded.screenshot_blob, cached_at=excluded.cached_at""",
                (url_hash, phash, screenshot_bytes, time.time()),
            )
            
            # Cleanup old cache entries (older than 48 hours)
            conn.execute(
                "DELETE FROM visual_cache WHERE cached_at < ?",
                (time.time() - SCREENSHOT_CACHE_TTL * 2,),
            )
            
            conn.commit()
    finally:
        conn.close()


def get_reference_hashes():
    """Get all reference brand hashes from database."""
    if IS_PRODUCTION:
        return []  # No references in production yet
    
    conn = _get_conn()
    if not conn:
        return []
    
    try:
        rows = conn.execute(
            "SELECT brand, domain, page_type, phash FROM visual_reference"
        ).fetchall()
        
        return [{
            "brand": row["brand"],
            "domain": row["domain"],
            "page_type": row["page_type"],
            "phash": row["phash"],
        } for row in rows]
    finally:
        conn.close()


def add_reference_screenshot(brand: str, domain: str, page_type: str, screenshot_bytes: bytes):
    """
    Add a reference screenshot for a brand.
    
    Args:
        brand: Brand name (e.g., "paypal", "google")
        domain: Legitimate domain (e.g., "paypal.com")
        page_type: Page type (e.g., "login", "2fa", "password_reset")
        screenshot_bytes: PNG screenshot data
    """
    if not VISUAL_AVAILABLE:
        logger.warning("Visual similarity features not available")
        return
    
    if IS_PRODUCTION:
        logger.warning("Cannot add references in production")
        return
    
    phash = _compute_phash(screenshot_bytes)
    if not phash:
        logger.error("Failed to compute phash for reference screenshot")
        return
    
    conn = _get_conn()
    if not conn:
        return
    
    try:
        with _lock, conn:
            conn.execute(
                """INSERT INTO visual_reference (brand, domain, page_type, phash, screenshot_blob, added_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(brand, page_type)
                   DO UPDATE SET domain=excluded.domain, phash=excluded.phash, 
                                screenshot_blob=excluded.screenshot_blob, added_at=excluded.added_at""",
                (brand, domain, page_type, phash, screenshot_bytes, time.time()),
            )
            conn.commit()
        logger.info("Added reference screenshot for %s (%s)", brand, page_type)
    finally:
        conn.close()


def check_visual_similarity(url: str, actual_domain: str) -> Optional[dict]:
    """
    Check if URL visually resembles a known brand page.
    
    Args:
        url: URL to check
        actual_domain: The actual registered domain of the URL
    
    Returns:
        dict with keys:
          - is_clone: bool, True if visual match with wrong domain
          - matched_brand: str, brand name that was matched
          - matched_domain: str, legitimate domain of that brand
          - hamming_distance: int, similarity score (lower = more similar)
          - details: human-readable description
        
        Returns None if:
          - Visual features not available
          - Screenshot failed
          - No reference hashes in database
          - Any error occurs (fail-soft pattern)
    """
    if not VISUAL_AVAILABLE:
        logger.debug("Visual similarity features not available (Playwright/imagehash not installed)")
        return None
    
    # Check cache first
    cached = _get_cached_screenshot(url)
    if cached:
        phash_str, screenshot_bytes = cached
        logger.debug("Visual cache hit for URL: %s", url[:50])
    else:
        # Take screenshot
        screenshot_bytes = _take_screenshot(url)
        if not screenshot_bytes:
            return None
        
        # Compute phash
        phash_str = _compute_phash(screenshot_bytes)
        if not phash_str:
            return None
        
        # Cache for future requests
        _cache_screenshot(url, phash_str, screenshot_bytes)
    
    # Get reference hashes
    references = get_reference_hashes()
    if not references:
        logger.debug("No reference screenshots in database - visual similarity disabled")
        return None
    
    # Compare against all references
    try:
        page_phash = imagehash.hex_to_hash(phash_str)
    except Exception as e:
        logger.error("Failed to parse phash: %s", e)
        return None
    
    best_match = None
    min_distance = 999
    
    for ref in references:
        try:
            ref_phash = imagehash.hex_to_hash(ref["phash"])
            distance = page_phash - ref_phash  # Hamming distance
            
            if distance < min_distance:
                min_distance = distance
                best_match = ref
        
        except Exception:
            continue
    
    # Check if we have a suspicious match
    if best_match and min_distance <= HAMMING_DISTANCE_THRESHOLD:
        # Visual match found - is it the legitimate domain?
        matched_domain = best_match["domain"]
        
        # Check if actual domain matches the brand's legitimate domain
        # (simple check - can be enhanced to handle subdomains properly)
        if matched_domain not in actual_domain and actual_domain not in matched_domain:
            # Visual match but WRONG domain → PHISHING!
            return {
                "is_clone": True,
                "matched_brand": best_match["brand"],
                "matched_domain": matched_domain,
                "hamming_distance": min_distance,
                "details": f"Page visually resembles {best_match['brand'].title()} {best_match['page_type']} page (similarity: {100-min_distance*6:.0f}%) but domain '{actual_domain}' is NOT '{matched_domain}'",
            }
        else:
            # Visual match AND correct domain → legitimate
            return {
                "is_clone": False,
                "matched_brand": best_match["brand"],
                "matched_domain": matched_domain,
                "hamming_distance": min_distance,
                "details": f"Page visually matches legitimate {best_match['brand'].title()} {best_match['page_type']} page",
            }
    
    # No significant visual match
    return {
        "is_clone": False,
        "matched_brand": None,
        "matched_domain": None,
        "hamming_distance": min_distance if best_match else None,
        "details": "No visual similarity to known brand pages",
    }


def list_reference_brands():
    """List all brands with reference screenshots."""
    refs = get_reference_hashes()
    brands = {}
    for ref in refs:
        brand = ref["brand"]
        if brand not in brands:
            brands[brand] = []
        brands[brand].append(ref["page_type"])
    return brands
