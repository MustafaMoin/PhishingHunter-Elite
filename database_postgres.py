"""
database_postgres.py
--------------------
PostgreSQL-compatible database layer for PhishingHunter production deployment.

This is a drop-in replacement for database.py (SQLite version).
Function signatures are identical, so app.py and detector.py don't need changes.

Usage:
  - Set DATABASE_URL environment variable
  - If not set, falls back to SQLite (database.py)
"""

import os
import time
import json
import logging
from contextlib import contextmanager

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from psycopg2.pool import SimpleConnectionPool
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    psycopg2 = None

logger = logging.getLogger("phishinghunter.database")

# Connection pool
_pool = None

DATABASE_URL = os.environ.get("DATABASE_URL")

# If no DATABASE_URL, fall back to SQLite
if not DATABASE_URL:
    logger.warning("DATABASE_URL not set, using SQLite fallback")
    from database import *  # Import everything from SQLite version
else:
    if not POSTGRES_AVAILABLE:
        raise ImportError("psycopg2 not installed. Run: pip install psycopg2-binary")


def init_pool():
    """Initialize connection pool."""
    global _pool
    if _pool is None and DATABASE_URL:
        _pool = SimpleConnectionPool(
            minconn=2,
            maxconn=20,
            dsn=DATABASE_URL
        )
        logger.info("PostgreSQL connection pool initialized")


@contextmanager
def get_conn():
    """Get database connection from pool."""
    if not DATABASE_URL:
        # Fallback to SQLite
        from database import get_conn as sqlite_conn
        with sqlite_conn() as conn:
            yield conn
        return
    
    if _pool is None:
        init_pool()
    
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


def init_db():
    """Initialize database schema."""
    if not DATABASE_URL:
        # Fallback to SQLite
        from database import init_db as sqlite_init
        sqlite_init()
        return
    
    init_pool()
    
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scans (
                    id SERIAL PRIMARY KEY,
                    url TEXT NOT NULL,
                    final_url TEXT,
                    domain TEXT,
                    score INTEGER NOT NULL,
                    risk TEXT NOT NULL,
                    offline BOOLEAN NOT NULL DEFAULT FALSE,
                    blocklist_hit BOOLEAN NOT NULL DEFAULT FALSE,
                    domain_age_days INTEGER,
                    redirect_count INTEGER DEFAULT 0,
                    signals_json TEXT,
                    scan_time_ms INTEGER,
                    ip_hash TEXT,
                    created_at DOUBLE PRECISION NOT NULL
                );
                
                CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at);
                CREATE INDEX IF NOT EXISTS idx_scans_domain ON scans(domain);
                
                CREATE TABLE IF NOT EXISTS scan_cache (
                    url TEXT PRIMARY KEY,
                    result_json TEXT NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS blocklist (
                    url TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    added_at DOUBLE PRECISION NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS feedback (
                    id SERIAL PRIMARY KEY,
                    scan_id INTEGER,
                    url TEXT,
                    feedback_type TEXT CHECK(feedback_type IN ('false_positive','false_negative','confirmed')),
                    comment TEXT,
                    created_at DOUBLE PRECISION NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS rate_limit (
                    ip_hash TEXT NOT NULL,
                    window_start DOUBLE PRECISION NOT NULL,
                    count INTEGER NOT NULL,
                    PRIMARY KEY (ip_hash, window_start)
                );
                
                -- Phase 3: VirusTotal tables
                CREATE TABLE IF NOT EXISTS vt_rate_limit (
                    window_start BIGINT PRIMARY KEY,
                    count INTEGER NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS vt_cache (
                    url_hash TEXT PRIMARY KEY,
                    result_json TEXT NOT NULL,
                    cached_at DOUBLE PRECISION NOT NULL
                );
                
                -- Phase 5: Visual similarity tables
                CREATE TABLE IF NOT EXISTS visual_reference (
                    brand TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    page_type TEXT NOT NULL,
                    phash TEXT NOT NULL,
                    screenshot_blob BYTEA,
                    added_at DOUBLE PRECISION NOT NULL,
                    PRIMARY KEY (brand, page_type)
                );
                
                CREATE TABLE IF NOT EXISTS visual_cache (
                    url_hash TEXT PRIMARY KEY,
                    phash TEXT NOT NULL,
                    screenshot_blob BYTEA,
                    cached_at DOUBLE PRECISION NOT NULL
                );
                
                CREATE INDEX IF NOT EXISTS idx_visual_cache_time ON visual_cache(cached_at);
            """)
        conn.commit()
    
    logger.info("PostgreSQL database schema initialized")


def save_scan(result: dict, ip_hash: str = ""):
    """Save scan result to database."""
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO scans
                   (url, final_url, domain, score, risk, offline, blocklist_hit,
                    domain_age_days, redirect_count, signals_json, scan_time_ms, ip_hash, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id""",
                (
                    result.get("url"),
                    result.get("final_url"),
                    result.get("domain"),
                    result.get("score"),
                    result.get("risk"),
                    result.get("offline", False),
                    result.get("blocklist_hit", False),
                    result.get("domain_age_days"),
                    result.get("redirect_count", 0),
                    json.dumps(result.get("signals", [])),
                    result.get("scan_time_ms"),
                    ip_hash,
                    time.time(),
                ),
            )
            scan_id = cursor.fetchone()[0]
            conn.commit()
            return scan_id


def get_stats():
    """Get aggregate statistics."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """SELECT
                     COUNT(*) AS hunts,
                     SUM(CASE WHEN risk IN ('PHISHING','HIGH RISK') THEN 1 ELSE 0 END) AS threats,
                     SUM(CASE WHEN risk = 'LOW RISK' THEN 1 ELSE 0 END) AS low_risk,
                     SUM(CASE WHEN risk = 'SAFE' THEN 1 ELSE 0 END) AS safes,
                     SUM(CASE WHEN blocklist_hit THEN 1 ELSE 0 END) AS blocklist_hits
                   FROM scans"""
            )
            row = cursor.fetchone()
            return {k: (row[k] or 0) for k in row.keys()}


def get_recent_scans(limit=12):
    """Get recent scans."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT url, domain, score, risk, created_at FROM scans ORDER BY id DESC LIMIT %s",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]


def cache_get(url, max_age_seconds=600):
    """Get cached scan result."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT result_json, created_at FROM scan_cache WHERE url = %s",
                (url,),
            )
            row = cursor.fetchone()
            if row and (time.time() - row["created_at"]) < max_age_seconds:
                return json.loads(row["result_json"])
            return None


def cache_set(url, result: dict):
    """Cache scan result."""
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO scan_cache (url, result_json, created_at) 
                   VALUES (%s,%s,%s)
                   ON CONFLICT (url) 
                   DO UPDATE SET result_json=EXCLUDED.result_json, created_at=EXCLUDED.created_at""",
                (url, json.dumps(result), time.time()),
            )
        conn.commit()


def bulk_insert_blocklist(urls, source):
    """Bulk insert blocklist URLs."""
    now = time.time()
    with get_conn() as conn:
        with conn.cursor() as cursor:
            # PostgreSQL: use INSERT ... ON CONFLICT DO NOTHING
            for url in urls:
                cursor.execute(
                    "INSERT INTO blocklist (url, source, added_at) VALUES (%s,%s,%s) ON CONFLICT (url) DO NOTHING",
                    (url, source, now),
                )
        conn.commit()


def blocklist_size():
    """Get blocklist size."""
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM blocklist")
            return cursor.fetchone()[0]


def is_in_blocklist(url_or_domain: str):
    """Check if URL is in blocklist."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT source FROM blocklist WHERE url = %s LIMIT 1",
                (url_or_domain,),
            )
            row = cursor.fetchone()
            return row["source"] if row else None


def save_feedback(scan_id, url, feedback_type, comment=""):
    """Save user feedback."""
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO feedback (scan_id, url, feedback_type, comment, created_at) VALUES (%s,%s,%s,%s,%s)",
                (scan_id, url, feedback_type, comment, time.time()),
            )
        conn.commit()


def check_rate_limit(ip_hash, window_seconds=60, max_requests=20):
    """Check rate limit (fixed window)."""
    window_start = int(time.time() // window_seconds) * window_seconds
    
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT count FROM rate_limit WHERE ip_hash=%s AND window_start=%s",
                (ip_hash, window_start),
            )
            row = cursor.fetchone()
            
            if row is None:
                cursor.execute(
                    "INSERT INTO rate_limit (ip_hash, window_start, count) VALUES (%s,%s,1)",
                    (ip_hash, window_start),
                )
                conn.commit()
                return True
            
            if row["count"] >= max_requests:
                return False
            
            cursor.execute(
                "UPDATE rate_limit SET count = count + 1 WHERE ip_hash=%s AND window_start=%s",
                (ip_hash, window_start),
            )
            conn.commit()
            return True
