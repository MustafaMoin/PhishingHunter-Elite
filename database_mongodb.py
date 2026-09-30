"""
MongoDB database layer for PhishingHunter Elite v2
Cloud-based storage using MongoDB Atlas
"""
import os
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("MONGODB_DB_NAME", "phishinghunter")

_client = None
_db = None


def get_db():
    """Get MongoDB database connection"""
    global _client, _db
    if _client is None:
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        _db = _client[DB_NAME]
        init_db()
    return _db


def init_db():
    """Initialize MongoDB collections and indexes"""
    db = get_db()
    
    # Create collections
    collections = {
        'scans': db.scans,
        'scan_cache': db.scan_cache,
        'blocklist': db.blocklist,
        'feedback': db.feedback,
        'rate_limit': db.rate_limit,
        'signal_weights': db.signal_weights,
        'blocked_ips': db.blocked_ips
    }
    
    # Create indexes for scans collection
    db.scans.create_index([("created_at", DESCENDING)])
    db.scans.create_index([("domain", ASCENDING)])
    db.scans.create_index([("ip_hash", ASCENDING)])
    
    # Create indexes for scan_cache
    db.scan_cache.create_index([("url", ASCENDING)], unique=True)
    db.scan_cache.create_index([("created_at", ASCENDING)])
    
    # Create indexes for blocklist
    db.blocklist.create_index([("url", ASCENDING)], unique=True)
    
    # Create indexes for feedback
    db.feedback.create_index([("scan_id", ASCENDING)])
    db.feedback.create_index([("created_at", DESCENDING)])
    
    # Create indexes for rate_limit
    db.rate_limit.create_index([("ip_hash", ASCENDING), ("window_start", ASCENDING)], unique=True)
    
    # Create indexes for signal_weights
    db.signal_weights.create_index([("key", ASCENDING)], unique=True)
    
    # Create indexes for blocked_ips
    db.blocked_ips.create_index([("ip_hash", ASCENDING)], unique=True)
    
    return db


def save_scan(result: dict, ip_hash: str = "") -> str:
    """Save scan result to MongoDB"""
    db = get_db()
    
    scan_doc = {
        "url": result.get("url"),
        "final_url": result.get("final_url"),
        "domain": result.get("domain"),
        "score": result.get("score"),
        "risk": result.get("risk"),
        "offline": result.get("offline", False),
        "blocklist_hit": result.get("blocklist_hit", False),
        "domain_age_days": result.get("domain_age_days"),
        "redirect_count": result.get("redirect_count", 0),
        "signals": result.get("signals", []),
        "scan_time_ms": result.get("scan_time_ms"),
        "ip_hash": ip_hash,
        "created_at": time.time()
    }
    
    inserted = db.scans.insert_one(scan_doc)
    return str(inserted.inserted_id)


def get_stats() -> dict:
    """Get overall statistics"""
    db = get_db()
    
    # Total scans
    total = db.scans.count_documents({})
    
    # Threats detected (HIGH RISK or PHISHING)
    threats = db.scans.count_documents({"risk": {"$in": ["PHISHING", "HIGH RISK"]}})
    
    # Blocked count
    blocked = db.blocklist.count_documents({})
    
    return {
        "hunts": total,
        "threats": threats,
        "blocked": blocked
    }


def get_recent_scans(limit=12) -> list:
    """Get recent scans"""
    db = get_db()
    
    scans = list(db.scans.find().sort("created_at", DESCENDING).limit(limit))
    
    # Convert MongoDB _id to string and created_at to readable format
    for scan in scans:
        scan["id"] = str(scan["_id"])
        scan["created_at"] = datetime.fromtimestamp(scan["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
        del scan["_id"]
    
    return scans


def cache_get(url: str, max_age_seconds=600) -> Optional[dict]:
    """Get cached scan result"""
    db = get_db()
    
    cutoff = time.time() - max_age_seconds
    cached = db.scan_cache.find_one({
        "url": url,
        "created_at": {"$gte": cutoff}
    })
    
    if cached:
        return cached.get("result")
    return None


def cache_set(url: str, result: dict):
    """Set cached scan result"""
    db = get_db()
    
    db.scan_cache.update_one(
        {"url": url},
        {
            "$set": {
                "result": result,
                "created_at": time.time()
            }
        },
        upsert=True
    )


def bulk_insert_blocklist(urls: list, source: str):
    """Bulk insert URLs into blocklist"""
    db = get_db()
    
    timestamp = time.time()
    docs = [{"url": url, "source": source, "added_at": timestamp} for url in urls]
    
    try:
        db.blocklist.insert_many(docs, ordered=False)
    except Exception:
        # Ignore duplicate key errors
        pass


def blocklist_size() -> int:
    """Get blocklist size"""
    db = get_db()
    return db.blocklist.count_documents({})


def is_in_blocklist(url_or_domain: str) -> bool:
    """Check if URL or domain is in blocklist"""
    db = get_db()
    
    # Check exact match or domain match
    count = db.blocklist.count_documents({
        "$or": [
            {"url": url_or_domain},
            {"url": {"$regex": f".*{url_or_domain}.*"}}
        ]
    })
    
    return count > 0


def save_feedback(scan_id: str, url: str, feedback_type: str, comment: str = ""):
    """Save user feedback"""
    db = get_db()
    
    db.feedback.insert_one({
        "scan_id": scan_id,
        "url": url,
        "feedback_type": feedback_type,
        "comment": comment,
        "created_at": time.time()
    })


def check_rate_limit(ip_hash: str, window_seconds=60, max_requests=20) -> tuple:
    """Check if IP is rate limited"""
    db = get_db()
    
    now = time.time()
    window_start = now - (now % window_seconds)
    
    # Get or create rate limit record
    record = db.rate_limit.find_one({
        "ip_hash": ip_hash,
        "window_start": window_start
    })
    
    if record:
        count = record.get("count", 0)
        if count >= max_requests:
            return False, count
        
        # Increment count
        db.rate_limit.update_one(
            {"ip_hash": ip_hash, "window_start": window_start},
            {"$inc": {"count": 1}}
        )
        return True, count + 1
    else:
        # Create new record
        db.rate_limit.insert_one({
            "ip_hash": ip_hash,
            "window_start": window_start,
            "count": 1
        })
        return True, 1


def get_all_feedback(limit=100, feedback_filter=None) -> list:
    """Get all feedback"""
    db = get_db()
    
    query = {}
    if feedback_filter:
        query["feedback_type"] = feedback_filter
    
    feedback_list = list(db.feedback.find(query).sort("created_at", DESCENDING).limit(limit))
    
    # Convert timestamps
    for fb in feedback_list:
        fb["id"] = str(fb["_id"])
        fb["created_at"] = datetime.fromtimestamp(fb["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
        del fb["_id"]
    
    return feedback_list


def get_feedback_stats() -> dict:
    """Get feedback statistics"""
    db = get_db()
    
    total = db.feedback.count_documents({})
    false_positives = db.feedback.count_documents({"feedback_type": "false_positive"})
    false_negatives = db.feedback.count_documents({"feedback_type": "false_negative"})
    confirmed = db.feedback.count_documents({"feedback_type": "confirmed"})
    
    return {
        "total": total,
        "false_positive": false_positives,
        "false_negative": false_negatives,
        "confirmed": confirmed
    }


def get_signal_analysis() -> dict:
    """Analyze which signals appear most in false positives/negatives"""
    db = get_db()
    
    # Get scans with feedback
    feedback_scans = list(db.feedback.find(
        {"feedback_type": {"$in": ["false_positive", "false_negative"]}},
        {"scan_id": 1, "feedback_type": 1}
    ))
    
    # Build scan_id -> feedback_type mapping
    scan_feedback = {str(f["scan_id"]): f["feedback_type"] for f in feedback_scans}
    
    # Count signal occurrences by feedback type
    signal_counts = {
        'false_positive': {},
        'false_negative': {}
    }
    
    # Get scans with signals that have feedback
    for scan_id, feedback_type in scan_feedback.items():
        try:
            from bson.objectid import ObjectId
            scan = db.scans.find_one({"_id": ObjectId(scan_id)})
            if not scan:
                continue
            
            signals = scan.get("signals", [])
            if not signals:
                continue
            
            for signal in signals:
                # Get signal name/detail
                detail = signal.get("detail") or signal.get("name") or "Unknown"
                signal_counts[feedback_type][detail] = signal_counts[feedback_type].get(detail, 0) + 1
        except:
            continue
    
    return signal_counts


def get_system_stats() -> dict:
    """Get system statistics"""
    db = get_db()
    
    # Total scans
    total_scans = db.scans.count_documents({})
    
    # Scans in last 24h
    cutoff_24h = time.time() - (24 * 3600)
    scans_24h = db.scans.count_documents({"created_at": {"$gte": cutoff_24h}})
    
    # Blocklist size
    blocklist_count = db.blocklist.count_documents({})
    
    # Cache size
    cache_count = db.scan_cache.count_documents({})
    
    # Feedback count
    feedback_count = db.feedback.count_documents({})
    
    # Risk distribution
    high_risk = db.scans.count_documents({"risk": {"$in": ["PHISHING", "HIGH RISK"]}})
    medium_risk = db.scans.count_documents({"risk": "MEDIUM RISK"})
    low_risk = db.scans.count_documents({"risk": "LOW RISK"})
    safe = db.scans.count_documents({"risk": "SAFE"})
    
    # Blocklist by source (grouped)
    blocklist_by_source = {}
    pipeline = [
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    for result in db.blocklist.aggregate(pipeline):
        source = result["_id"] if result["_id"] else "unknown"
        blocklist_by_source[source] = result["count"]
    
    # Cache stats (fresh = last 10 minutes)
    cutoff_10m = time.time() - 600
    cache_fresh = db.scan_cache.count_documents({"created_at": {"$gte": cutoff_10m}})
    
    return {
        "total_scans": total_scans,
        "scans_24h": scans_24h,
        "blocklist_size": blocklist_count,
        "cache_size": cache_count,
        "cache_total": cache_count,
        "cache_fresh": cache_fresh,
        "feedback_count": feedback_count,
        "blocklist_by_source": blocklist_by_source,
        "risk_distribution": {
            "high": high_risk,
            "medium": medium_risk,
            "low": low_risk,
            "safe": safe
        }
    }


def get_signal_weights() -> dict:
    """Get signal weights configuration"""
    db = get_db()
    
    weights = {}
    for doc in db.signal_weights.find():
        weights[doc["key"]] = doc["value"]
    
    # Return defaults if empty
    if not weights:
        return {
            "blocklist": 50,
            "blacklist_api": 40,
            "ssl_invalid": 30,
            "domain_age": 25,
            "suspicious_tld": 20,
            "suspicious_keywords": 15,
            "redirects": 10,
            "visual_similarity": 35
        }
    
    return weights


def save_signal_weights(weights_dict: dict):
    """Save signal weights configuration"""
    db = get_db()
    
    for key, value in weights_dict.items():
        db.signal_weights.update_one(
            {"key": key},
            {"$set": {"value": float(value)}},
            upsert=True
        )


def get_blocklist_page(search="", page=1, per_page=25) -> dict:
    """Get paginated blocklist"""
    db = get_db()
    
    query = {}
    if search:
        query["url"] = {"$regex": search, "$options": "i"}
    
    total = db.blocklist.count_documents(query)
    skip = (page - 1) * per_page
    
    items = list(db.blocklist.find(query).sort("added_at", DESCENDING).skip(skip).limit(per_page))
    
    # Convert timestamps
    for item in items:
        item["id"] = str(item["_id"])
        item["added_at"] = datetime.fromtimestamp(item["added_at"]).strftime("%Y-%m-%d %H:%M:%S")
        del item["_id"]
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }


def remove_blocklist_entry(url: str):
    """Remove URL from blocklist"""
    db = get_db()
    db.blocklist.delete_one({"url": url})


def add_blocklist_entry(url: str, source: str = "manual"):
    """Add URL to blocklist"""
    db = get_db()
    
    try:
        db.blocklist.insert_one({
            "url": url,
            "source": source,
            "added_at": time.time()
        })
    except DuplicateKeyError:
        pass  # Already exists


def get_scan_volume_30d() -> list:
    """Get scan volume for last 30 days"""
    db = get_db()
    
    cutoff = time.time() - (30 * 24 * 3600)
    
    # Aggregate by day
    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": {"$toDate": {"$multiply": ["$created_at", 1000]}}
                    }
                },
                "count": {"$sum": 1}
            }
        },
        {"$sort": {"_id": 1}}
    ]
    
    results = list(db.scans.aggregate(pipeline))
    
    return [{"date": r["_id"], "count": r["count"]} for r in results]


def get_top_ips_24h(limit=20) -> list:
    """Get top IPs in last 24 hours"""
    db = get_db()
    
    cutoff = time.time() - (24 * 3600)
    
    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}, "ip_hash": {"$ne": ""}}},
        {"$group": {"_id": "$ip_hash", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit}
    ]
    
    results = list(db.scans.aggregate(pipeline))
    
    return [{"ip_hash": r["_id"], "count": r["count"]} for r in results]


def block_ip(ip_hash: str, reason: str = "Blocked by admin"):
    """Block an IP address"""
    db = get_db()
    
    db.blocked_ips.update_one(
        {"ip_hash": ip_hash},
        {
            "$set": {
                "reason": reason,
                "blocked_at": time.time()
            }
        },
        upsert=True
    )


def is_ip_blocked(ip_hash: str) -> bool:
    """Check if IP is blocked"""
    db = get_db()
    return db.blocked_ips.count_documents({"ip_hash": ip_hash}) > 0


def search_scans_by_domain(domain: str, limit=100) -> list:
    """Search scans by domain"""
    db = get_db()
    
    scans = list(db.scans.find(
        {"domain": {"$regex": domain, "$options": "i"}}
    ).sort("created_at", DESCENDING).limit(limit))
    
    # Convert timestamps
    for scan in scans:
        scan["id"] = str(scan["_id"])
        scan["created_at"] = datetime.fromtimestamp(scan["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
        del scan["_id"]
    
    return scans


def export_scans_iter(domain_filter=None):
    """Export scans as iterator"""
    db = get_db()
    
    query = {}
    if domain_filter:
        query["domain"] = {"$regex": domain_filter, "$options": "i"}
    
    for scan in db.scans.find(query).sort("created_at", DESCENDING):
        scan["id"] = str(scan["_id"])
        scan["created_at"] = datetime.fromtimestamp(scan["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
        del scan["_id"]
        yield scan


def clear_all_scans():
    """Delete all scan records (admin function)"""
    db = get_db()
    result = db.scans.delete_many({})
    return result.deleted_count


def clear_scan_cache():
    """Clear all cached scan results"""
    db = get_db()
    result = db.scan_cache.delete_many({})
    return result.deleted_count


def clear_all_feedback():
    """Delete all feedback records"""
    db = get_db()
    result = db.feedback.delete_many({})
    return result.deleted_count


def get_database_size_info():
    """Get database collection sizes"""
    db = get_db()
    return {
        "scans": db.scans.count_documents({}),
        "cache": db.scan_cache.count_documents({}),
        "blocklist": db.blocklist.count_documents({}),
        "feedback": db.feedback.count_documents({}),
        "rate_limit": db.rate_limit.count_documents({}),
        "blocked_ips": db.blocked_ips.count_documents({})
    }
