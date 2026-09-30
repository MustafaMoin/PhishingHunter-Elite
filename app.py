"""
app.py
------
PhishingHunter ELITE v2 — Flask entrypoint.

Routes:
  GET  /            dashboard UI
  POST /hunt         scan a URL  (form field: target)
  GET  /api/check     same scan, JSON GET API for developers (?url=)
  GET  /stats         aggregate counters for the dashboard
  GET  /history        recent scans (for the live feed panel)
  POST /feedback        report a false positive / false negative
  GET  /health          liveness probe
  
Admin Routes:
  GET  /admin/login   login page
  POST /admin/login   process login
  GET  /admin/logout  logout
  GET  /admin         admin dashboard (requires auth)
  GET  /admin/feedback feedback analysis (requires auth)
  POST /admin/trigger  manual triggers for blocklist refresh & ML retrain (requires auth)
"""

import os
import hashlib
import logging
from logging.handlers import RotatingFileHandler

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, use system env vars

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, Response

# Auto-detect database type (MongoDB, PostgreSQL, or SQLite)
DATABASE_URL = os.environ.get("DATABASE_URL")
MONGODB_URI = os.environ.get("MONGODB_URI")

if MONGODB_URI:
    import database_mongodb as database
    print("[INFO] Using MongoDB cloud database")
elif DATABASE_URL and DATABASE_URL.startswith("postgresql"):
    import database_postgres as database
    print("[INFO] Using PostgreSQL database")
else:
    import database
    print("[INFO] Using SQLite database")

import blocklists
from detector import PhishingDetector, DEFAULT_SIGNAL_WEIGHTS, SIGNAL_WEIGHTS
from admin_auth import init_auth, verify_password, admin_required
from flask_login import login_user, logout_user, current_user

app = Flask(__name__)
app.secret_key = os.environ.get("PHISHINGHUNTER_SECRET", "change-this-in-production")

# Security headers
@app.after_request
def set_security_headers(response):
    """Add security headers to all responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    # Only add CSP if not already set (allows override for specific routes)
    if 'Content-Security-Policy' not in response.headers:
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; img-src 'self' data:;"
    return response

# Initialize Flask-Login
login_manager = init_auth(app)

# Jinja2 custom filters
@app.template_filter('timestamp_to_date')
def timestamp_to_date(timestamp):
    """Convert Unix timestamp to readable date string."""
    from datetime import datetime
    try:
        dt = datetime.fromtimestamp(float(timestamp))
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return 'N/A'

# ---------------------------------------------------------------------
# logging: rotating file handler instead of manually re-writing a flat
# file on every boot (the original app deleted its log on every restart)
# ---------------------------------------------------------------------
os.makedirs("data", exist_ok=True)
handler = RotatingFileHandler("data/phishinghunter.log", maxBytes=2_000_000, backupCount=3)
handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

database.init_db()
blocklists.start_background_refresh()
detector = PhishingDetector(blocklist_lookup=database.is_in_blocklist,
                            weight_loader=database.get_signal_weights)


def client_ip_hash():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def run_scan(target: str):
    target = target.strip()
    if not target:
        return None, "Target URL required"

    cached = database.cache_get(target)
    if cached:
        cached["cached"] = True
        return cached, None

    result = detector.hunt(target)
    result["cached"] = False
    database.cache_set(target, result)
    scan_id = database.save_scan(result, client_ip_hash())
    result["scan_id"] = scan_id
    app.logger.info("SCAN %s | score=%s risk=%s", result["url"], result["score"], result["risk"])
    return result, None


@app.route("/")
def dashboard():
    return render_template("index.html")


@app.route("/hunt", methods=["POST"])
def hunt_target():
    ip = client_ip_hash()
    if database.is_ip_blocked(ip):
        return jsonify({"success": False, "error": "Access denied"}), 403
    if not database.check_rate_limit(ip):
        return jsonify({"success": False, "error": "Rate limit exceeded. Please wait a moment."}), 429

    target = request.form.get("target", "")
    
    # Input validation: check for malicious input
    if not target or len(target) > 2048:  # Max reasonable URL length
        return jsonify({"success": False, "error": "Invalid URL length"}), 400
    
    # Basic sanitization
    target = target.strip()
    
    result, error = run_scan(target)
    if error:
        return jsonify({"success": False, "error": error}), 400
    return jsonify({"success": True, "result": result})


@app.route("/api/check")
def api_check():
    """Simple GET-based JSON API so other tools/scripts can integrate.
    Example: GET /api/check?url=http://example.com
    """
    ip = client_ip_hash()
    if database.is_ip_blocked(ip):
        return jsonify({"success": False, "error": "Access denied"}), 403
    if not database.check_rate_limit(ip, max_requests=30):
        return jsonify({"success": False, "error": "Rate limit exceeded"}), 429

    target = request.args.get("url", "")
    
    # Input validation
    if not target or len(target) > 2048:
        return jsonify({"success": False, "error": "Invalid URL length"}), 400
    
    result, error = run_scan(target)
    if error:
        return jsonify({"success": False, "error": error}), 400
    return jsonify({"success": True, "result": result})


@app.route("/stats")
def stats():
    return jsonify(database.get_stats())


@app.route("/history")
def history():
    limit = min(int(request.args.get("limit", 12)), 50)
    return jsonify(database.get_recent_scans(limit))


@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.get_json(silent=True) or {}
    scan_id = data.get("scan_id")
    url = data.get("url", "")
    ftype = data.get("feedback_type")
    comment = data.get("comment", "")
    if ftype not in ("false_positive", "false_negative", "confirmed"):
        return jsonify({"success": False, "error": "Invalid feedback_type"}), 400
    database.save_feedback(scan_id, url, ftype, comment)
    return jsonify({"success": True})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "blocklist_entries": database.blocklist_size()})


# =====================================================================
# ADMIN ROUTES (Phase 9)
# =====================================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Admin login page."""
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        
        if verify_password(username, password):
            from admin_auth import AdminUser
            user = AdminUser(username)
            login_user(user, remember=True)
            flash("Login successful!", "success")
            
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('admin_dashboard'))
        else:
            flash("Invalid username or password", "error")
    
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    """Admin logout."""
    logout_user()
    flash("Logged out successfully", "success")
    return redirect(url_for('dashboard'))


@app.route("/admin")
@admin_required
def admin_dashboard():
    """Main admin dashboard with stats and controls."""
    stats = database.get_stats()
    system_stats = database.get_system_stats()
    feedback_stats = database.get_feedback_stats()
    signal_analysis = database.get_signal_analysis()
    
    return render_template(
        "admin.html",
        stats=stats,
        system_stats=system_stats,
        feedback_stats=feedback_stats,
        signal_analysis=signal_analysis,
        signal_weights=SIGNAL_WEIGHTS,
        default_weights=DEFAULT_SIGNAL_WEIGHTS,
    )


@app.route("/admin/feedback")
@admin_required
def admin_feedback():
    """Detailed feedback analysis page."""
    feedback_filter = request.args.get("filter")  # false_positive, false_negative, confirmed
    limit = min(int(request.args.get("limit", 50)), 200)
    
    feedback_list = database.get_all_feedback(limit=limit, feedback_filter=feedback_filter)
    feedback_stats = database.get_feedback_stats()
    
    return render_template(
        "admin_feedback.html",
        feedback_list=feedback_list,
        feedback_stats=feedback_stats,
        current_filter=feedback_filter
    )


@app.route("/admin/trigger", methods=["POST"])
@admin_required
def admin_trigger():
    """Manual trigger endpoints for maintenance tasks."""
    action = request.json.get("action") if request.json else request.form.get("action")
    
    # Whitelist allowed actions
    allowed_actions = ["refresh_blocklist", "retrain_ml"]
    if not action or action not in allowed_actions:
        return jsonify({"success": False, "error": "Invalid action"}), 400
    
    if action == "refresh_blocklist":
        try:
            blocklists.refresh_blocklists()
            app.logger.info(f"Admin {current_user.username} triggered blocklist refresh")
            return jsonify({"success": True, "message": "Blocklist refresh triggered successfully"})
        except Exception as e:
            app.logger.error(f"Blocklist refresh failed: {e}")
            return jsonify({"success": False, "error": "Blocklist refresh failed"}), 500
    
    elif action == "retrain_ml":
        # Check if ML module exists (Phase 4)
        try:
            from ml import retrain
            app.logger.info(f"Admin {current_user.username} triggered ML retraining")
            retrain.run_retrain()
            return jsonify({"success": True, "message": "ML retraining started (check logs for progress)"})
        except ImportError:
            return jsonify({"success": False, "error": "ML module not available (Phase 4 not implemented)"}), 404
        except Exception as e:
            app.logger.error(f"ML retrain failed: {e}")
            return jsonify({"success": False, "error": "ML retrain failed"}), 500


# ---------- Signal Weight Editor ----------

@app.route("/admin/weights", methods=["POST"])
@admin_required
def admin_save_weights():
    """Save updated signal weights to the database."""
    data = request.get_json(silent=True)
    if not data or "weights" not in data:
        return jsonify({"success": False, "error": "No weights provided"}), 400
    weights = {}
    for key, val in data["weights"].items():
        if key in DEFAULT_SIGNAL_WEIGHTS:
            try:
                weights[key] = float(val)
            except (ValueError, TypeError):
                return jsonify({"success": False, "error": f"Invalid value for {key}"}), 400
    database.save_signal_weights(weights)
    detector.reload_weights()
    app.logger.info(f"Admin {current_user.username} updated {len(weights)} signal weights")
    return jsonify({"success": True, "message": f"{len(weights)} weights saved"})


# ---------- Blocklist Manager ----------

@app.route("/admin/api/blocklist")
@admin_required
def admin_blocklist_api():
    """Paginated blocklist entries with optional search."""
    search = request.args.get("search", "")
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    return jsonify(database.get_blocklist_page(search=search, page=page))


@app.route("/admin/blocklist/remove", methods=["POST"])
@admin_required
def admin_blocklist_remove():
    """Remove a URL from the blocklist."""
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"success": False, "error": "URL required"}), 400
    removed = database.remove_blocklist_entry(url)
    app.logger.info(f"Admin {current_user.username} removed blocklist entry: {url}")
    return jsonify({"success": True, "removed": removed})


@app.route("/admin/blocklist/add", methods=["POST"])
@admin_required
def admin_blocklist_add():
    """Add a URL to the blocklist manually."""
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"success": False, "error": "URL required"}), 400
    database.add_blocklist_entry(url, source="manual")
    app.logger.info(f"Admin {current_user.username} added blocklist entry: {url}")
    return jsonify({"success": True, "message": f"Added {url} to blocklist"})


# ---------- Scan Volume Chart ----------

@app.route("/admin/api/scan-volume")
@admin_required
def admin_scan_volume():
    """Return 30-day scan volume data for Chart.js."""
    return jsonify(database.get_scan_volume_30d())


# ---------- IP Abuse Monitor ----------

@app.route("/admin/api/top-ips")
@admin_required
def admin_top_ips():
    """Return top 20 IP hashes by request count in last 24h."""
    return jsonify(database.get_top_ips_24h())


@app.route("/admin/block-ip", methods=["POST"])
@admin_required
def admin_block_ip():
    """Block an IP hash."""
    data = request.get_json(silent=True) or {}
    ip_hash = data.get("ip_hash", "").strip()
    if not ip_hash:
        return jsonify({"success": False, "error": "IP hash required"}), 400
    database.block_ip(ip_hash, reason=f"Blocked by admin {current_user.username}")
    app.logger.info(f"Admin {current_user.username} blocked IP hash: {ip_hash}")
    return jsonify({"success": True, "message": f"IP {ip_hash} blocked"})


# ---------- Domain Search ----------

@app.route("/admin/api/domain-search")
@admin_required
def admin_domain_search():
    """Search scan history by domain."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    return jsonify(database.search_scans_by_domain(q))


# ---------- CSV Export ----------

@app.route("/admin/export-csv")
@admin_required
def admin_export_csv():
    """Stream scans table as downloadable CSV."""
    import csv
    import io

    domain_filter = request.args.get("domain", "").strip() or None

    def generate():
        output = io.StringIO()
        writer = csv.writer(output)
        # Header row
        header = ["id", "url", "final_url", "domain", "score", "risk", "offline",
                  "blocklist_hit", "domain_age_days", "redirect_count",
                  "scan_time_ms", "ip_hash", "created_at"]
        writer.writerow(header)
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
        # Data rows
        for row in database.export_scans_iter(domain_filter=domain_filter):
            writer.writerow([row.get(h, "") for h in header])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    filename = "phishinghunter_scans.csv"
    if domain_filter:
        safe_name = "".join(c for c in domain_filter if c.isalnum() or c in ".-_")
        filename = f"scans_{safe_name}.csv"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# =====================================================================
# SEO & CRAWLER FILES
# =====================================================================

@app.route("/robots.txt")
def robots_txt():
    """Serve robots.txt for search engine crawlers."""
    return app.send_static_file("../robots.txt") if os.path.exists("robots.txt") else Response(
        "User-agent: *\nAllow: /\nSitemap: https://phishinghunter.onrender.com/sitemap.xml",
        mimetype="text/plain"
    )


@app.route("/sitemap.xml")
def sitemap_xml():
    """Serve sitemap.xml for search engines."""
    return app.send_static_file("../sitemap.xml") if os.path.exists("sitemap.xml") else Response(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://phishinghunter.onrender.com/</loc></url></urlset>',
        mimetype="application/xml"
    )


@app.route("/humans.txt")
def humans_txt():
    """Serve humans.txt - credits and team information."""
    return app.send_static_file("../humans.txt") if os.path.exists("humans.txt") else Response(
        "/* TEAM */\nFounder & Developer: Mustafa Moin\nRole: Full-Stack Developer & Security Engineer\nLocation: Karachi, Pakistan",
        mimetype="text/plain"
    )


# =====================================================================
# DATABASE CLEANUP (Admin Only)
# =====================================================================

@app.route("/admin/api/database-info")
@admin_required
def admin_database_info():
    """Get database size information."""
    try:
        info = database.get_database_size_info()
        return jsonify({"success": True, "data": info})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/admin/api/clear-scans", methods=["POST"])
@admin_required
def admin_clear_scans():
    """Clear all scan history."""
    try:
        count = database.clear_all_scans()
        app.logger.warning(f"Admin {current_user.username} cleared {count} scan records")
        return jsonify({"success": True, "message": f"Deleted {count} scan records", "count": count})
    except Exception as e:
        app.logger.error(f"Error clearing scans: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/admin/api/clear-cache", methods=["POST"])
@admin_required
def admin_clear_cache():
    """Clear scan cache."""
    try:
        count = database.clear_scan_cache()
        app.logger.info(f"Admin {current_user.username} cleared {count} cache entries")
        return jsonify({"success": True, "message": f"Deleted {count} cache entries", "count": count})
    except Exception as e:
        app.logger.error(f"Error clearing cache: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/admin/api/clear-feedback", methods=["POST"])
@admin_required
def admin_clear_feedback():
    """Clear all feedback."""
    try:
        count = database.clear_all_feedback()
        app.logger.warning(f"Admin {current_user.username} cleared {count} feedback records")
        return jsonify({"success": True, "message": f"Deleted {count} feedback records", "count": count})
    except Exception as e:
        app.logger.error(f"Error clearing feedback: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# =====================================================================


if __name__ == "__main__":
    print("PHISHINGHUNTER ELITE v2 — starting on http://127.0.0.1:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
