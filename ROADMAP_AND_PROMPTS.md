# PhishingHunter Elite — Deep Analysis, Roadmap & Build Prompts

This document covers everything asked for: kya missing tha, kya fix/add hua, database
ka sawal, industry tools ke against gap-analysis, accuracy improve karne ka plan, aur
har agle phase ke liye **ready-to-use prompts** jo aap Claude Code (ya kisi bhi AI
coding assistant) ko seedha de sakte hain.

---

## 1. Deep analysis of the original app

**Backend (`app.py`, 199 lines):**
- Pure rule-based scoring — ~10 hardcoded checks (HTTPS, URL length, IP-in-URL, `@`
  symbol, hyphen count, domain entropy, typosquat vs. **6 hardcoded domains**, risky
  TLD list, keyword matching).
- **Real bug found:** the frontend JS referenced `result.details` and `result.offline`
  on every scan — the backend never sent either field, so the results panel silently
  showed `undefined`. Fixed in v2 (backend now returns a full signal breakdown).
- No database. `/stats` re-parsed a flat `.log` file line-by-line on *every* request,
  and that log file was deleted on every server restart (`os.remove(LOG_FILE)` at
  boot) — so all history was lost on every restart.
- No rate limiting → one person could hammer `/hunt` and, since it makes a live HTTP
  request per scan, use your server to indirectly DoS whatever URL they scanned.
- Typosquat detection only compared the **registrable domain** — `paypal.com.evil.tk`
  (brand smuggled into a subdomain) completely bypassed it, because `tldextract`
  would parse `domain=evil`, not `paypal`.
- No WHOIS, no TLS inspection, no redirect-chain tracking, no community blocklist,
  no explainability — a "PHISHING 92" score with zero reasoning shown.

**Frontend (`templates/index.html`):**
The neon cyberpunk direction was already a real aesthetic choice (not a generic
default) — kept and elevated rather than replaced. What it lacked: any breakdown of
*why* something scored high, a history view, non-blocking notifications (it used
`alert()`), loading state that reflected real scan stages, and mobile polish.

---

## 2. Kya database chahiye? (seedha jawab)

**Haan, chahiye — aur ab hai.** Wajah:

| Without a DB (original) | With SQLite (v2) |
|---|---|
| `/stats` re-reads and re-parses a flat log file every request | one indexed SQL query |
| History lost on every restart | persists on disk |
| No caching → same URL re-scanned (slow, and re-hits the target site) every time | 10-minute result cache per URL |
| No abuse protection possible | per-IP rate limiting backed by the DB |
| No way to collect false-positive/negative feedback | `feedback` table — this is also your **future ML training data** |
| No blocklist storage | `blocklist` table refreshed from OpenPhish/URLhaus |

SQLite is the right choice **for now**: zero setup, a single file, more than enough
for a small-to-medium traffic tool. Move to PostgreSQL only when you deploy multiple
app server processes (SQLite's file-locking doesn't handle concurrent writers across
processes well) — see Phase 8 below for that exact migration.

---

## 3. Architecture (as delivered)

```
Browser (HUD dashboard)
      │  POST /hunt
      ▼
Flask app (app.py)  ── rate limit check → cache check
      │
      ▼  (parallel, each with a hard timeout so one slow check can't hang the scan)
      ├── Structure & domain signals   (offline, instant)
      ├── Live checks: WHOIS · TLS · HTTP · redirects · content   (network, timeout-bounded)
      └── Blocklist lookup            (OpenPhish + URLhaus, refreshed every 2h)
      │
      ▼
Scoring engine (detector.py) → explainable signal list + 0-100 score
      │
      ▼
SQLite (scans · cache · blocklist · feedback)  → stats/history served back to UI
```

*(see the diagram rendered above in the chat)*

---

## 4. Gap analysis vs. real industry tools

How this now compares to Google Safe Browsing, VirusTotal, PhishTank, urlscan.io,
IPQualityScore, and CheckPhish — what's matched, and what's still a genuine gap:

| Capability | Original app | v2 (delivered) | Industry tools | Still a gap? |
|---|---|---|---|---|
| URL structure heuristics | ✅ basic | ✅ expanded | ✅ | closed |
| Brand/typosquat detection | 6 domains, domain-only | ~40 brands, domain + subdomain + path | 1000s of brands, ML-scored | **partial** — see Phase 4 |
| Homoglyph / IDN attacks | ❌ | ✅ | ✅ | closed |
| Domain age (WHOIS) | ❌ | ✅ | ✅ | closed |
| TLS certificate inspection | ❌ | ✅ | ✅ | closed |
| Redirect chain tracking | ❌ | ✅ | ✅ | closed |
| Community blocklist match | ❌ | ✅ (OpenPhish, URLhaus — free) | ✅ (+ proprietary feeds) | **partial** — paid feeds add coverage, see Phase 2/3 |
| Form-action / credential-harvest detection | ❌ | ✅ | ✅ | closed |
| Explainable "why flagged" breakdown | ❌ | ✅ | partial (most tools hide this) | **you're now ahead here** |
| Visual/screenshot brand-similarity | ❌ | ❌ | ✅ (urlscan.io, CheckPhish) | **open** — Phase 5 |
| ML-scored confidence (not hand-tuned weights) | ❌ | ❌ (weights still hand-tuned) | ✅ | **open** — Phase 4 |
| Real-time global threat feed aggregation (paid APIs) | ❌ | ❌ | ✅ | **open** — Phase 2/3 |
| Browser extension / right-click check | ❌ | ❌ | ✅ (most competitors) | **open** — Phase 6 |
| Public developer API | ❌ | ✅ (`/api/check`) | ✅ | closed |
| Scan history / feedback loop | ❌ | ✅ | varies | closed |

**Bottom line:** v2 closes most of the *structural* gaps for free. The remaining gaps
(visual similarity, ML scoring, paid threat-intel feeds, browser extension) all need
either an API key, a training dataset, or a browser-extension packaging step — which
is why they're written up as prompts below instead of built blind right now.

---

## 5. Accuracy roadmap — how to beat existing tools, in order of leverage

1. **Blocklist coverage is the single highest-leverage lever.** A rule-based score can
   be structurally clean and still be an active phishing kit registered five minutes
   ago. OpenPhish/URLhaus (free, already wired in v2) catch these deterministically.
   Adding Google Safe Browsing (Phase 2) and PhishTank's full feed roughly multiplies
   coverage — this is what most commercial tools rely on *most*, not clever heuristics.
2. **Move from hand-tuned weights to a trained classifier** (Phase 4). Right now every
   number in `SIGNAL_WEIGHTS` is a guess, tuned by eyeballing a handful of URLs. A
   logistic regression / gradient-boosted model trained on a real labeled dataset
   (PhishTank positives + Tranco top-1M negatives) learns the actual weight of each
   signal from data, and gives you a calibrated probability instead of an arbitrary
   0-100.
3. **Visual/brand similarity** (Phase 5) catches the attacks that pass every text-based
   check: a pixel-perfect cloned login page on a clean, aged, HTTPS-secured domain.
   This is what separates "good heuristic tool" from "tool that catches sophisticated
   campaigns."
4. **Feedback loop.** Every false positive/negative your users report (already stored
   in the `feedback` table) becomes labeled training data for #2 — this compounds over
   time and is exactly how commercial tools keep improving without you manually
   re-tuning weights forever.

---

## 6. Feature checklist — what to add next, organized

**Detection**
- [x] Expanded brand/typosquat list, subdomain abuse detection
- [x] Homoglyph/punycode detection
- [x] WHOIS domain age
- [x] TLS certificate inspection
- [x] Redirect chain + final-domain-mismatch detection
- [x] Form-action-offsite (credential harvesting) detection
- [x] Free community blocklists (OpenPhish, URLhaus)
- [ ] Google Safe Browsing / VirusTotal integration (Phase 2/3)
- [ ] Trained ML classifier replacing hand-tuned weights (Phase 4)
- [ ] Screenshot + visual brand-similarity matching (Phase 5)
- [ ] Favicon hash comparison against known brand favicons

**UI/UX**
- [x] Explainable signal breakdown (fixes the old `undefined` bug)
- [x] Domain age / TLS / redirect chips
- [x] Recent-scans live feed
- [x] Toast notifications (replacing `alert()`)
- [x] Multi-stage "what's happening" loading state
- [x] Copy-report and false-positive/negative feedback buttons
- [ ] QR-code scanning ("quishing" is increasingly common)
- [ ] Bulk/batch URL scanning (paste a list, scan all)
- [ ] Shareable permalink per scan result
- [ ] Embeddable "safety badge" for site owners

**Product**
- [ ] Browser extension (Phase 6)
- [ ] PWA / installable app (Phase 7)
- [ ] Public API docs page + API keys for higher rate limits
- [ ] Admin view of feedback submissions to drive retraining

---

## 7. Ready-to-use prompts for the next phases

Each of these is written so you can paste it **directly into Claude Code** (pointed at
this project folder) and it has enough context to just build that phase. Do them in
order — each assumes the previous ones exist.

### Phase 2 — Google Safe Browsing API (free tier, real threat intel)

```
Add Google Safe Browsing v4 API integration to this Flask project (PhishingHunter).
Create a new file `safebrowsing.py` with a function check_url(url) -> dict|None that
calls the Safe Browsing "threatMatches:find" endpoint using an API key read from the
environment variable GOOGLE_SAFE_BROWSING_API_KEY. Check for MALWARE, SOCIAL_ENGINEERING,
UNWANTED_SOFTWARE, and POTENTIALLY_HARMFUL_APPLICATION threat types. Wrap the request
in a 4-second timeout and fail soft (return None) on any error so a missing/invalid key
never breaks a scan. Wire it into detector.py's hunt() method as an additional signal
source alongside the existing blocklist_lookup, with its own SIGNAL_WEIGHTS entry
("google_safebrowsing_hit": 100, deterministic like blocklist_hit). Update
requirements.txt and README.md with setup instructions for getting a free API key from
Google Cloud Console.
```

### Phase 3 — VirusTotal integration (community consensus scoring)

```
Add VirusTotal API v3 integration to this Flask project. Create `virustotal.py` with
check_url(url) -> dict|None that submits the URL for analysis (or fetches an existing
report if already scanned) using an API key from the environment variable
VIRUSTOTAL_API_KEY, and returns the malicious/suspicious vendor counts out of total
vendors. Respect VirusTotal's free-tier rate limit (4 requests/minute) using the
existing SQLite rate-limiting pattern in database.py, and cache VT results for at least
1 hour to conserve quota. Wire the malicious-vendor ratio into detector.py as a new
weighted signal ("virustotal_flagged"), scaled by how many vendors flagged it rather
than a flat deterministic weight. Fail soft if the API key is missing or the call times
out (4s timeout).
```

### Phase 4 — Train a real ML classifier to replace hand-tuned weights

```
I want to replace the hand-tuned SIGNAL_WEIGHTS scoring in detector.py with a trained
ML classifier. Build this as a separate offline training pipeline plus a runtime
inference module:

1. Create `ml/train.py` that:
   - Downloads/loads a labeled phishing URL dataset (use the PhishTank verified feed
     for positives and the Tranco top 1M list for negatives — sample ~20k of each for
     class balance)
   - Extracts the same structural features already computed in detector.py (URL length,
     entropy, hyphen count, subdomain count, TLD risk, Levenshtein distance to top
     500 brands, has_mixed_script, etc.) plus a few new ones (digit ratio, path depth,
     query param count)
   - Trains a gradient-boosted classifier (use scikit-learn's
     HistGradientBoostingClassifier, no GPU needed) with train/test split and reports
     precision/recall/F1 and a confusion matrix
   - Saves the trained model with joblib to `ml/model.joblib` plus a `ml/features.json`
     documenting the exact feature order
2. Create `ml/infer.py` with a function score_url(url) -> float (0-1 probability) that
   loads the saved model once at import time and extracts the same features from a raw
   URL.
3. Wire ml/infer.py into detector.py: keep the existing rule-based signals for
   explainability (they still show in the UI breakdown), but blend the ML probability
   in as the primary score driver — e.g. final_score = 0.6 * ml_probability*100 +
   0.4 * rule_based_score, capped at 100. Add a signal entry showing "ML model
   confidence: X%" in the breakdown.
4. Add a `retrain.py` script that pulls feedback from the `feedback` table (false
   positives/negatives collected from real users) and appends them as additional
   labeled training examples for the next retrain — this is the feedback loop that
   lets the model actually improve over time instead of staying static.
```

### Phase 5 — Visual / screenshot brand-similarity detection

```
Add screenshot-based visual phishing detection to this project. Use Playwright
(headless Chromium) to:
1. Capture a screenshot of the submitted URL's rendered page (with a hard 8-second
   timeout, fail soft if the page doesn't load)
2. Resize it to a small fixed size (e.g. 256x256) and compute a perceptual hash
   (use the `imagehash` library's phash) 
3. Maintain a small reference set of perceptual hashes for known brand login pages
   (start with 10-15 commonly-spoofed brands: PayPal, Google, Microsoft, major banks —
   I will provide/approve the actual reference screenshots, don't scrape them
   automatically) stored in a new `visual_reference` SQLite table
4. If the submitted page's hash is within a close Hamming distance of a reference hash
   BUT the domain doesn't match that brand's real domain, add a high-severity signal
   ("visual_brand_clone") to detector.py's output — this is one of the strongest
   possible phishing signals since it means someone is pixel-cloning a real brand's
   login page.
Add Playwright + imagehash to requirements.txt and document in README that
`playwright install chromium` needs to be run once after pip install.
```

### Phase 6 — Browser extension (Chrome/Firefox, Manifest V3)

```
Build a Manifest V3 browser extension in a new `extension/` folder that integrates with
this PhishingHunter Flask API. Requirements:
- A background service worker that calls this app's GET /api/check?url= endpoint
  whenever the user navigates to a new page (debounced, and skip chrome://, about:,
  and localhost URLs)
- If the response risk is HIGH RISK or PHISHING, show a non-blocking badge on the
  extension icon (red badge with the score) and optionally inject a dismissible warning
  banner at the top of the page via a content script
- A popup (popup.html) matching the existing cyber-HUD visual style (reuse the color
  variables from templates/index.html) showing the current page's score and signal
  breakdown on click
- A right-click context menu item "Check this link with PhishingHunter" for any link,
  opening the popup with that link's result
- An options page to configure the backend API URL (so it's not hardcoded to
  localhost, for when this is deployed)
- manifest.json requesting only the minimum permissions needed (activeTab, contextMenus,
  storage — avoid broad host_permissions if possible)
```

### Phase 7 — PWA (installable app)

```
Turn the existing Flask-rendered dashboard into an installable PWA. Add a
manifest.json (name, icons at 192/512px in the existing cyber-green/cyan palette,
theme_color, display: standalone) and a service worker (sw.js) that caches the static
shell (HTML/CSS/JS, font files) for offline load, while always fetching /hunt,
/stats, and /history live from the network (never cache scan results). Register the
service worker in index.html. Add the manifest link tag and apple-touch-icon meta
tags. Keep this minimal — the goal is just "Add to Home Screen" working cleanly, not
full offline scanning (scanning inherently needs network access).
```

### Phase 8 — Production deployment (Postgres + Redis + Docker)

```
Prepare this Flask app for production deployment:
1. Add a PostgreSQL-compatible version of database.py (keep the SQLite version too,
   selected via a DATABASE_URL environment variable — use SQLAlchemy Core or plain
   psycopg2, your choice, but preserve the exact same function signatures so app.py
   and detector.py don't need to change) 
2. Move scan_cache and rate_limit tables to Redis instead (they're high-write,
   ephemeral data — better fit than Postgres) using redis-py, again behind a
   REDIS_URL environment variable with an in-memory dict fallback for local dev
   if Redis isn't configured
3. Replace the in-process blocklist refresh thread with a documented cron/Celery
   job pattern (write it as a standalone `refresh_blocklists_job.py` runnable via
   cron, since an in-process thread doesn't work correctly once you run multiple
   gunicorn workers — they'd each run their own refresh loop redundantly)
4. Add a Dockerfile (multi-stage, python:3.12-slim base) and docker-compose.yml
   wiring the app + Postgres + Redis together, with gunicorn (4 workers) as the
   production WSGI server instead of the Flask dev server
5. Add a .env.example listing every environment variable this app now reads
6. Update README.md with the full production deployment steps
```

### Phase 9 — Admin/feedback dashboard

```
Add a password-protected /admin route (use Flask-Login with a single admin user,
credentials from environment variables — don't build multi-user auth) showing:
- A table of all feedback submissions (false_positive / false_negative / confirmed)
  with the original scan's URL, score, and signal breakdown, sortable by date
- A summary chart (signals most commonly present in false-positive reports — this
  tells you which SIGNAL_WEIGHTS entries are too aggressive and need tuning down)
- A manual "trigger blocklist refresh now" button calling blocklists.refresh_blocklists()
- A manual "trigger ML retrain" button calling ml/retrain.py (Phase 4 must exist first)
Keep the same cyber-HUD visual style as the main dashboard for consistency.
```

---

## 8. Quick start

```bash
cd PhishingHunter_v2
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py
# open http://127.0.0.1:5000
```

Everything in this v2 folder is already tested end-to-end (Flask test client: `/`,
`/hunt`, `/stats`, `/history`, `/feedback`, `/health`, rate limiting) and runs with
zero API keys. Phases 2-9 above are exactly the pieces that genuinely need something
from you first — an API key, a labeled dataset, or a packaging step — so they're
handed to you as precise, drop-in prompts instead of guessed at.
