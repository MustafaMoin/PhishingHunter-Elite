# PhishingHunter Elite v2

Multi-vector phishing/URL detection console — Flask backend + SQLite +
a cyber-HUD dashboard.

## What changed vs the original version

| Area | Before | Now |
|---|---|---|
| Storage | flat `.log` file, wiped on every restart | SQLite (`data/phishinghunter.db`) — scan history, cache, blocklist, feedback |
| Detection signals | ~10 hardcoded checks, 6-domain whitelist | 25+ signals: WHOIS domain age, TLS cert inspection, redirect-chain tracking, homoglyph/punycode detection, brand-in-subdomain detection, form-action-offsite detection, brand-impersonation-in-content, community blocklists (OpenPhish + URLhaus) |
| Explainability | single opaque score | every point traced to a labeled signal, shown in the UI |
| `result.details` / `result.offline` bug | referenced in JS but never sent by backend → showed "undefined" | fixed — backend returns full signal breakdown |
| Abuse protection | none | per-IP rate limiting (SQLite-backed) |
| API | none | `GET /api/check?url=` JSON endpoint for scripts/integrations |
| History/feedback | none | `/history` feed + `/feedback` false-positive/negative reporting (future ML training data) |

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

First boot will try to download the OpenPhish + URLhaus blocklists in the
background — this needs outbound internet access on ports 443. If it
fails (offline dev machine, firewall), the app still works fine, it
just won't have the deterministic blocklist signal until the fetch
succeeds.

### Optional: Google Safe Browsing API (Phase 2)

For enhanced threat detection, you can enable Google Safe Browsing integration:

1. Get a free API key:
   - Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
   - Create a new project (or select existing)
   - Enable "Safe Browsing API" for your project
   - Create credentials → API Key

2. Set the environment variable:
   ```bash
   # Linux/Mac
   export GOOGLE_SAFE_BROWSING_API_KEY=your_key_here
   
   # Windows CMD
   set GOOGLE_SAFE_BROWSING_API_KEY=your_key_here
   
   # Windows PowerShell
   $env:GOOGLE_SAFE_BROWSING_API_KEY="your_key_here"
   ```

3. Restart the app

The app works fine without this key (it just skips the Safe Browsing check), but adding it significantly improves accuracy by checking URLs against Google's massive threat database.

### Optional: VirusTotal API (Phase 3)

For multi-vendor consensus scoring, you can enable VirusTotal integration:

1. Get a free API key:
   - Sign up at [VirusTotal](https://www.virustotal.com/gui/join-us)
   - Go to your profile and copy your API key

2. Set the environment variable:
   ```bash
   # Linux/Mac
   export VIRUSTOTAL_API_KEY=your_key_here
   
   # Windows CMD
   set VIRUSTOTAL_API_KEY=your_key_here
   
   # Windows PowerShell
   $env:VIRUSTOTAL_API_KEY="your_key_here"
   ```

3. Restart the app

**Note:** VirusTotal free tier has a rate limit of 4 requests/minute. The app automatically caches results for 1 hour and respects this limit, so quota is conserved intelligently.

### Optional: Visual Similarity Detection (Phase 5)

For screenshot-based brand clone detection (catches pixel-perfect phishing pages):

1. Install additional dependencies:
   ```bash
   pip install playwright imagehash Pillow
   ```

2. Install Chromium browser for Playwright:
   ```bash
   playwright install chromium
   ```

3. Add reference brand screenshots:
   ```bash
   # Take screenshot of legitimate brand page and store as reference
   python manage_visual_references.py add paypal paypal.com login https://www.paypal.com/signin
   
   # List all reference screenshots
   python manage_visual_references.py list
   
   # Test against a suspicious URL
   python manage_visual_references.py test https://suspicious-site.com
   ```

**How it works:**
- Takes screenshot of submitted URL (cached for 24 hours)
- Computes perceptual hash (resistant to minor visual changes)
- Compares against reference hashes of known brand pages
- If visual match BUT domain mismatch → HIGH RISK signal

**Important:** Visual similarity is the most expensive check (2-8 seconds per first screenshot), but it catches sophisticated attacks that pass all text-based checks. Results are cached aggressively.

### Admin Panel (Phase 9)

PhishingHunter includes a password-protected admin control panel for system monitoring and feedback analysis:

1. Set admin credentials in environment variables:
   ```bash
   # Development (simple)
   export ADMIN_USERNAME=admin
   export ADMIN_PASSWORD=changeme
   
   # Production (secure - generate hash first)
   python admin_auth.py your_secure_password
   # Copy the hash output and set:
   export ADMIN_PASSWORD_HASH=<generated_hash>
   ```

2. Access admin panel:
   - Navigate to: `http://localhost:5000/admin`
   - Login with your credentials
   - View system stats, feedback analysis, and manual triggers

**Admin Features:**
- **System Statistics:** Scans, threats, database size, cache efficiency
- **Feedback Analysis:** View false positives/negatives reported by users
- **Signal Tuning:** See which signals appear most in false reports (helps tune weights)
- **Manual Triggers:** 
  - Force blocklist refresh (OpenPhish + URLhaus)
  - Retrain ML model using feedback data (Phase 4 required)

See `PHASE_9_COMPLETE.md` for detailed admin panel documentation.

## Notes on the checks

- **WHOIS** lookups can be slow or unsupported for some ccTLDs — the
  engine gives it a 4s hard timeout and treats a failed lookup as
  "unavailable" (0 points), never as a false positive.
- **TLS certificate** check opens a raw socket to port 443 — this is
  independent of whether the HTML page fetch succeeds.
- **Rate limiting** is a simple fixed-window counter in SQLite (20
  req/min on `/hunt`, 30 req/min on `/api/check`). Fine for a small
  deployment; swap for Flask-Limiter + Redis at higher traffic (see the
  roadmap doc).

## Scaling up

- Swap SQLite → PostgreSQL: only `database.py` needs to change (all SQL
  is portable, no SQLite-only syntax used).
- Put Redis in front of `scan_cache` / `rate_limit` tables for
  multi-process/multi-server deployments (SQLite file locking doesn't
  work well across multiple app servers).
- Move blocklist refresh to a Celery/cron job instead of an in-process
  thread once you run more than one worker process.
