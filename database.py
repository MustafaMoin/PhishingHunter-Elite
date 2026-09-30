"""
database.py
------------
Lightweight SQLite persistence layer for PhishingHunter.

Why SQLite (and not "no database" like the original app)?
  - The original app parsed a plaintext .log file on every /stats request.
    That does not scale, cannot be queried, loses data if the file is
    deleted, and cannot support features like history, caching, or
    feedback collection.
  - SQLite needs zero setup (it's a single file on disk), ships with
    Python, and is more than enough for a small-to-medium traffic tool.
  - Everything here is written with plain SQL so it is trivial to swap
    for PostgreSQL later (see README "Scaling up" section) by only
    changing this file.
"""

import sqlite3
import os
import time
import json
import threading

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "phishinghunter.db")
_lock = threading.Lock()


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _lock, get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                final_url TEXT,
                domain TEXT,
                score INTEGER NOT NULL,
                risk TEXT NOT NULL,
                offline INTEGER NOT NULL DEFAULT 0,
                blocklist_hit INTEGER NOT NULL DEFAULT 0,
                domain_age_days INTEGER,
                redirect_count INTEGER DEFAULT 0,
                signals_json TEXT,
                scan_time_ms INTEGER,
                ip_hash TEXT,
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at);
            CREATE INDEX IF NOT EXISTS idx_scans_domain ON scans(domain);

            CREATE TABLE IF NOT EXISTS scan_cache (
                url TEXT PRIMARY KEY,
                result_json TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS blocklist (
                url TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                added_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER,
                url TEXT,
                feedback_type TEXT CHECK(feedback_type IN ('false_positive','false_negative','confirmed')),
                comment TEXT,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rate_limit (
                ip_hash TEXT NOT NULL,
                window_start REAL NOT NULL,
                count INTEGER NOT NULL,
                PRIMARY KEY (ip_hash, window_start)
            );

            CREATE TABLE IF NOT EXISTS signal_weights (
                key   TEXT PRIMARY KEY,
                value REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS blocked_ips (
                ip_hash    TEXT PRIMARY KEY,
                reason     TEXT,
                blocked_at REAL NOT NULL
            );
            """
        )
        conn.commit()


def save_scan(result: dict, ip_hash: str = ""):
    with _lock, get_conn() as conn:
        conn.execute(
            """INSERT INTO scans
               (url, final_url, domain, score, risk, offline, blocklist_hit,
                domain_age_days, redirect_count, signals_json, scan_time_ms, ip_hash, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                result.get("url"),
                result.get("final_url"),
                result.get("domain"),
                result.get("score"),
                result.get("risk"),
                int(result.get("offline", False)),
                int(result.get("blocklist_hit", False)),
                result.get("domain_age_days"),
                result.get("redirect_count", 0),
                json.dumps(result.get("signals", [])),
                result.get("scan_time_ms"),
                ip_hash,
                time.time(),
            ),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]


def get_stats():
    with get_conn() as conn:
        row = conn.execute(
            """SELECT
                 COUNT(*) AS hunts,
                 SUM(CASE WHEN risk IN ('PHISHING','HIGH RISK') THEN 1 ELSE 0 END) AS threats,
                 SUM(CASE WHEN risk = 'LOW RISK' THEN 1 ELSE 0 END) AS low_risk,
                 SUM(CASE WHEN risk = 'SAFE' THEN 1 ELSE 0 END) AS safes,
                 SUM(blocklist_hit) AS blocklist_hits
               FROM scans"""
        ).fetchone()
        return {k: (row[k] or 0) for k in row.keys()}


def get_recent_scans(limit=12):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT url, domain, score, risk, created_at FROM scans ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def cache_get(url, max_age_seconds=600):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT result_json, created_at FROM scan_cache WHERE url = ?", (url,)
        ).fetchone()
        if row and (time.time() - row["created_at"]) < max_age_seconds:
            return json.loads(row["result_json"])
        return None


def cache_set(url, result: dict):
    with _lock, get_conn() as conn:
        conn.execute(
            "INSERT INTO scan_cache (url, result_json, created_at) VALUES (?,?,?) "
            "ON CONFLICT(url) DO UPDATE SET result_json=excluded.result_json, created_at=excluded.created_at",
            (url, json.dumps(result), time.time()),
        )
        conn.commit()


def bulk_insert_blocklist(urls, source):
    now = time.time()
    with _lock, get_conn() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO blocklist (url, source, added_at) VALUES (?,?,?)",
            [(u, source, now) for u in urls],
        )
        conn.commit()


def blocklist_size():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS c FROM blocklist").fetchone()["c"]


def is_in_blocklist(url_or_domain: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT source FROM blocklist WHERE url = ? LIMIT 1", (url_or_domain,)
        ).fetchone()
        return row["source"] if row else None


def save_feedback(scan_id, url, feedback_type, comment=""):
    with _lock, get_conn() as conn:
        conn.execute(
            "INSERT INTO feedback (scan_id, url, feedback_type, comment, created_at) VALUES (?,?,?,?,?)",
            (scan_id, url, feedback_type, comment, time.time()),
        )
        conn.commit()


def check_rate_limit(ip_hash, window_seconds=60, max_requests=20):
    """Simple fixed-window rate limiter stored in SQLite. Returns True if allowed."""
    window_start = int(time.time() // window_seconds) * window_seconds
    with _lock, get_conn() as conn:
        row = conn.execute(
            "SELECT count FROM rate_limit WHERE ip_hash=? AND window_start=?",
            (ip_hash, window_start),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO rate_limit (ip_hash, window_start, count) VALUES (?,?,1)",
                (ip_hash, window_start),
            )
            conn.commit()
            return True
        if row["count"] >= max_requests:
            return False
        conn.execute(
            "UPDATE rate_limit SET count = count + 1 WHERE ip_hash=? AND window_start=?",
            (ip_hash, window_start),
        )
        conn.commit()
        return True


# ---------- Admin queries ----------

def get_all_feedback(limit=100, feedback_filter=None):
    """Get all feedback submissions with scan details."""
    with get_conn() as conn:
        query = """
            SELECT 
                f.id, f.scan_id, f.url, f.feedback_type, f.comment, f.created_at,
                s.score, s.risk, s.signals_json, s.domain
            FROM feedback f
            LEFT JOIN scans s ON f.scan_id = s.id
        """
        params = []
        if feedback_filter:
            query += " WHERE f.feedback_type = ?"
            params.append(feedback_filter)
        query += " ORDER BY f.created_at DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item['signals_json']:
                item['signals'] = json.loads(item['signals_json'])
            result.append(item)
        return result


def get_feedback_stats():
    """Get aggregated feedback statistics."""
    with get_conn() as conn:
        stats = conn.execute("""
            SELECT 
                feedback_type,
                COUNT(*) as count
            FROM feedback
            GROUP BY feedback_type
        """).fetchall()
        return {row['feedback_type']: row['count'] for row in stats}


def get_signal_analysis():
    """Analyze which signals appear most in false positives."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT 
                s.signals_json,
                s.score,
                s.risk,
                f.feedback_type
            FROM scans s
            JOIN feedback f ON s.id = f.scan_id
            WHERE f.feedback_type IN ('false_positive', 'false_negative')
        """).fetchall()
        
        # Count signal occurrences by feedback type
        signal_counts = {
            'false_positive': {},
            'false_negative': {}
        }
        
        for row in rows:
            if not row['signals_json']:
                continue
            signals = json.loads(row['signals_json'])
            feedback_type = row['feedback_type']
            
            for signal in signals:
                detail = signal.get('detail', 'Unknown')
                signal_counts[feedback_type][detail] = signal_counts[feedback_type].get(detail, 0) + 1
        
        return signal_counts


def get_system_stats():
    """Get system-wide statistics for admin dashboard."""
    with get_conn() as conn:
        # Database size
        db_size_row = conn.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()").fetchone()
        db_size = db_size_row['size'] if db_size_row else 0
        
        # Cache stats
        cache_stats = conn.execute("""
            SELECT 
                COUNT(*) as total_entries,
                SUM(CASE WHEN (? - created_at) < 600 THEN 1 ELSE 0 END) as fresh_entries
            FROM scan_cache
        """, (time.time(),)).fetchone()
        
        # Blocklist stats
        blocklist_stats = conn.execute("""
            SELECT 
                source,
                COUNT(*) as count
            FROM blocklist
            GROUP BY source
        """).fetchall()
        
        return {
            'db_size_mb': round(db_size / 1024 / 1024, 2),
            'cache_total': cache_stats['total_entries'] if cache_stats else 0,
            'cache_fresh': cache_stats['fresh_entries'] if cache_stats else 0,
            'blocklist_by_source': {row['source']: row['count'] for row in blocklist_stats}
        }


# ---------- Signal Weights ----------

def get_signal_weights():
    """Return all custom signal weights as {key: value} dict."""
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM signal_weights").fetchall()
        return {row['key']: row['value'] for row in rows}


def save_signal_weights(weights_dict):
    """Upsert all keys into the signal_weights table."""
    with _lock, get_conn() as conn:
        for key, value in weights_dict.items():
            conn.execute(
                "INSERT INTO signal_weights (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, float(value)),
            )
        conn.commit()


# ---------- Blocklist Manager ----------

def _escape_like(s):
    """Escape SQL LIKE wildcards so user input is matched literally."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_blocklist_page(search="", page=1, per_page=25):
    """Return paginated blocklist entries with optional LIKE search."""
    offset = (page - 1) * per_page
    with get_conn() as conn:
        if search:
            pattern = f"%{_escape_like(search)}%"
            total = conn.execute(
                "SELECT COUNT(*) AS c FROM blocklist WHERE url LIKE ? ESCAPE '\\'", (pattern,)
            ).fetchone()['c']
            rows = conn.execute(
                "SELECT url, source, added_at FROM blocklist WHERE url LIKE ? ESCAPE '\\' "
                "ORDER BY added_at DESC LIMIT ? OFFSET ?",
                (pattern, per_page, offset),
            ).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) AS c FROM blocklist").fetchone()['c']
            rows = conn.execute(
                "SELECT url, source, added_at FROM blocklist "
                "ORDER BY added_at DESC LIMIT ? OFFSET ?",
                (per_page, offset),
            ).fetchall()
        return {
            'entries': [dict(r) for r in rows],
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': max(1, -(-total // per_page)),  # ceil division
        }


def remove_blocklist_entry(url):
    """Remove a single URL from the blocklist. Returns True if deleted."""
    with _lock, get_conn() as conn:
        cur = conn.execute("DELETE FROM blocklist WHERE url = ?", (url,))
        conn.commit()
        return cur.rowcount > 0


def add_blocklist_entry(url, source="manual"):
    """Manually add a URL to the blocklist."""
    with _lock, get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO blocklist (url, source, added_at) VALUES (?, ?, ?)",
            (url, source, time.time()),
        )
        conn.commit()


# ---------- Scan Volume Chart ----------

def get_scan_volume_30d():
    """Aggregate scans per day × risk level for the last 30 days."""
    cutoff = time.time() - 30 * 86400
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                DATE(created_at, 'unixepoch') AS day,
                risk,
                COUNT(*) AS cnt
            FROM scans
            WHERE created_at >= ?
            GROUP BY day, risk
            ORDER BY day
        """, (cutoff,)).fetchall()

    # Build {date: {SAFE:0, LOW RISK:0, HIGH RISK:0, PHISHING:0}}
    from collections import OrderedDict
    data = OrderedDict()
    for row in rows:
        d = row['day']
        if d not in data:
            data[d] = {'SAFE': 0, 'LOW RISK': 0, 'HIGH RISK': 0, 'PHISHING': 0}
        if row['risk'] in data[d]:
            data[d][row['risk']] = row['cnt']

    return {
        'labels': list(data.keys()),
        'safe': [v['SAFE'] for v in data.values()],
        'low_risk': [v['LOW RISK'] for v in data.values()],
        'high_risk': [v['HIGH RISK'] for v in data.values()],
        'phishing': [v['PHISHING'] for v in data.values()],
    }


# ---------- IP Abuse Monitor ----------

def get_top_ips_24h(limit=20):
    """Top IP hashes by total request count in the last 24 hours."""
    cutoff = time.time() - 86400
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT ip_hash, COUNT(*) AS cnt, MAX(created_at) AS last_seen
            FROM scans
            WHERE created_at >= ? AND ip_hash IS NOT NULL AND ip_hash != ''
            GROUP BY ip_hash
            ORDER BY cnt DESC
            LIMIT ?
        """, (cutoff, limit)).fetchall()
        return [dict(r) for r in rows]


def block_ip(ip_hash, reason="Blocked by admin"):
    """Add an IP hash to the blocked_ips table."""
    with _lock, get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO blocked_ips (ip_hash, reason, blocked_at) VALUES (?, ?, ?)",
            (ip_hash, reason, time.time()),
        )
        conn.commit()


def is_ip_blocked(ip_hash):
    """Return True if the ip_hash is in the blocked_ips table."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM blocked_ips WHERE ip_hash = ? LIMIT 1", (ip_hash,)
        ).fetchone()
        return row is not None


# ---------- Domain Search ----------

def search_scans_by_domain(domain, limit=100):
    """Search scans by domain (LIKE match), return history."""
    pattern = f"%{_escape_like(domain)}%"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, url, domain, score, risk, created_at "
            "FROM scans WHERE domain LIKE ? ESCAPE '\\' ORDER BY created_at DESC LIMIT ?",
            (pattern, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------- CSV Export ----------

def export_scans_iter(domain_filter=None):
    """Generator yielding scan rows for CSV streaming."""
    with get_conn() as conn:
        if domain_filter:
            pattern = f"%{_escape_like(domain_filter)}%"
            rows = conn.execute(
                "SELECT id, url, final_url, domain, score, risk, offline, blocklist_hit, "
                "domain_age_days, redirect_count, scan_time_ms, ip_hash, created_at "
                "FROM scans WHERE domain LIKE ? ESCAPE '\\' ORDER BY created_at DESC",
                (pattern,),
            )
        else:
            rows = conn.execute(
                "SELECT id, url, final_url, domain, score, risk, offline, blocklist_hit, "
                "domain_age_days, redirect_count, scan_time_ms, ip_hash, created_at "
                "FROM scans ORDER BY created_at DESC"
            )
        for row in rows:
            yield dict(row)


def clear_all_scans():
    """Delete all scan records (admin function)"""
    with _lock, get_conn() as conn:
        cursor = conn.execute("DELETE FROM scans")
        conn.commit()
        return cursor.rowcount


def clear_scan_cache():
    """Clear all cached scan results"""
    with _lock, get_conn() as conn:
        cursor = conn.execute("DELETE FROM scan_cache")
        conn.commit()
        return cursor.rowcount


def clear_all_feedback():
    """Delete all feedback records"""
    with _lock, get_conn() as conn:
        cursor = conn.execute("DELETE FROM feedback")
        conn.commit()
        return cursor.rowcount


def get_database_size_info():
    """Get database collection sizes"""
    with get_conn() as conn:
        return {
            "scans": conn.execute("SELECT COUNT(*) as cnt FROM scans").fetchone()["cnt"],
            "cache": conn.execute("SELECT COUNT(*) as cnt FROM scan_cache").fetchone()["cnt"],
            "blocklist": conn.execute("SELECT COUNT(*) as cnt FROM blocklist").fetchone()["cnt"],
            "feedback": conn.execute("SELECT COUNT(*) as cnt FROM feedback").fetchone()["cnt"],
            "rate_limit": conn.execute("SELECT COUNT(*) as cnt FROM rate_limit").fetchone()["cnt"],
            "blocked_ips": conn.execute("SELECT COUNT(*) as cnt FROM blocked_ips").fetchone()["cnt"]
        }
