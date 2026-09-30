"""
detector.py
-----------
The detection engine. This is the part that actually decides whether a
URL looks like phishing.

Design goals over the original single-file version:
  1. EXPLAINABLE  - every point added to the score comes from a named
     "signal" with a human-readable reason. The UI can show exactly why
     something was flagged instead of a black-box number.
  2. MULTI-VECTOR - combines URL structure, domain intelligence (WHOIS
     age), transport security (TLS cert), redirect-chain behaviour,
     page content, and community blocklists instead of URL text alone.
  3. FAIL-SOFT    - WHOIS / TLS / HTTP calls run with hard timeouts in
     parallel threads so one slow lookup never hangs the whole scan.
  4. TUNABLE      - weights live in one SIGNAL_WEIGHTS dict so they can
     be re-tuned (or eventually learned) without touching logic.
"""

import re
import ssl
import socket
import math
import time
import unicodedata
import urllib.parse
import concurrent.futures as cf

import requests
import tldextract
from bs4 import BeautifulSoup

try:
    import whois as pywhois
except ImportError:
    pywhois = None

import safebrowsing
import virustotal
import visual_similarity

try:
    from ml import infer as ml_infer
except ImportError:
    ml_infer = None

# tldextract: force offline snapshot use, never blocks on a live PSL fetch
_TLD = tldextract.TLDExtract(suffix_list_urls=())

REQUEST_TIMEOUT = 6
WHOIS_TIMEOUT = 4
SSL_TIMEOUT = 4
USER_AGENT = "Mozilla/5.0 (compatible; PhishingHunter/2.0; +https://phishinghunter.local)"

# ---------------------------------------------------------------------------
# Reference data. In production these should be swapped for/merged with
# live-updated sources (see README "Accuracy roadmap"), but a broad static
# list already covers far more brands than the original 6-domain whitelist.
# ---------------------------------------------------------------------------
TRUSTED_BRANDS = {
    # tech / email
    "google": ["google.com", "gmail.com", "youtube.com"],
    "microsoft": ["microsoft.com", "live.com", "outlook.com", "office.com"],
    "apple": ["apple.com", "icloud.com"],
    "facebook": ["facebook.com", "fb.com"],
    "instagram": ["instagram.com"],
    "whatsapp": ["whatsapp.com"],
    "linkedin": ["linkedin.com"],
    "github": ["github.com"],
    "dropbox": ["dropbox.com"],
    "adobe": ["adobe.com"],
    "netflix": ["netflix.com"],
    "twitter": ["twitter.com", "x.com"],
    "yahoo": ["yahoo.com"],
    # finance / payments
    "paypal": ["paypal.com"],
    "visa": ["visa.com"],
    "mastercard": ["mastercard.com"],
    "stripe": ["stripe.com"],
    "chase": ["chase.com"],
    "wellsfargo": ["wellsfargo.com"],
    "hbl": ["hbl.com", "hblpsl.com"],
    "meezan": ["meezanbank.com"],
    "ubl": ["ubldigital.com", "ubl.com.pk"],
    "easypaisa": ["easypaisa.com.pk"],
    "jazzcash": ["jazzcash.com.pk"],
    "sadapay": ["sadapay.pk"],
    "nayapay": ["nayapay.com"],
    # e-commerce
    "amazon": ["amazon.com"],
    "ebay": ["ebay.com"],
    "alibaba": ["alibaba.com"],
    "daraz": ["daraz.pk"],
    # crypto
    "binance": ["binance.com"],
    "coinbase": ["coinbase.com"],
    "kraken": ["kraken.com"],
    "metamask": ["metamask.io"],
    # shipping / logistics
    "dhl": ["dhl.com"],
    "fedex": ["fedex.com"],
    "ups": ["ups.com"],
    "tcs": ["tcsexpress.com"],
    # government-style targets (very commonly spoofed)
    "irs": ["irs.gov"],
    "nadra": ["nadra.gov.pk"],
    "fbr": ["fbr.gov.pk"],
}
ALL_TRUSTED_DOMAINS = {d for domains in TRUSTED_BRANDS.values() for d in domains}
BRAND_NAMES = list(TRUSTED_BRANDS.keys())

RISKY_TLDS = {
    "tk", "ml", "ga", "cf", "gq", "xyz", "top", "site", "online", "club",
    "work", "info", "biz", "click", "link", "buzz", "rest", "gdn", "quest",
    "cam", "sbs", "cyou", "icu", "monster", "bar",
}

URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly",
    "cutt.ly", "rebrand.ly", "shorturl.at", "rb.gy", "tiny.cc", "s.id",
}

SENSITIVE_KEYWORDS = [
    "login", "bank", "paypal", "password", "verify", "account", "update",
    "security", "confirm", "billing", "card", "ssn", "signin", "auth",
    "otp", "pin", "wallet", "invoice", "suspended", "unlock", "recover",
]

DEFAULT_SIGNAL_WEIGHTS = {
    "no_https": 12,
    "long_url": 10,
    "ip_host": 35,
    "at_symbol": 30,
    "many_hyphens": 12,
    "high_entropy_domain": 18,
    "typosquat_brand": 45,
    "brand_in_subdomain_or_path": 30,
    "risky_tld": 20,
    "shortener": 15,
    "suspicious_port": 15,
    "excess_subdomains": 12,
    "punycode_domain": 25,
    "mixed_script_domain": 30,
    "keyword_hit": 6,          # per keyword, capped
    "new_domain_lt30": 40,
    "new_domain_lt90": 20,
    "whois_unavailable": 0,    # informational only, no penalty
    "no_ssl_on_https": 20,
    "ssl_self_signed": 25,
    "ssl_short_lived": 10,
    "many_redirects": 15,
    "redirect_to_shortener": 15,
    "final_domain_mismatch": 20,
    "multiple_forms": 10,
    "password_field": 15,
    "sensitive_input_fields": 25,
    "form_action_offsite": 30,
    "brand_impersonation_content": 40,
    "obfuscated_script": 20,
    "blocklist_hit": 100,      # deterministic override
    "google_safebrowsing_hit": 100,  # deterministic like blocklist_hit
    "virustotal_flagged": 80,  # scaled by vendor ratio
    "visual_brand_clone": 95,  # pixel-perfect clone on wrong domain - very strong signal
    "trusted_domain_bonus": -60,
}

# Mutable copy used at runtime — load_signal_weights() merges DB overrides
SIGNAL_WEIGHTS = dict(DEFAULT_SIGNAL_WEIGHTS)


def load_signal_weights(weight_loader=None):
    """Merge DB-stored weight overrides into the active SIGNAL_WEIGHTS dict.

    Args:
        weight_loader: callable returning {key: value} dict of overrides.
                       If None or returns empty, SIGNAL_WEIGHTS keeps defaults.
    """
    SIGNAL_WEIGHTS.clear()
    SIGNAL_WEIGHTS.update(DEFAULT_SIGNAL_WEIGHTS)
    if weight_loader:
        try:
            db_weights = weight_loader()
            if db_weights:
                for key, value in db_weights.items():
                    if key in SIGNAL_WEIGHTS:
                        SIGNAL_WEIGHTS[key] = value
        except Exception:
            pass  # Fall back to defaults silently



# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def levenshtein(s1, s2):
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def shannon_entropy(text):
    if not text:
        return 0
    probs = [float(text.count(c)) / len(text) for c in dict.fromkeys(text)]
    return -sum(p * math.log(p, 2) for p in probs)


def has_mixed_script(domain):
    """Detect IDN homograph attacks: e.g. Cyrillic 'а' mixed with Latin 'a'."""
    scripts = set()
    for ch in domain:
        if ch.isascii() and ch.isalpha():
            scripts.add("LATIN")
        elif ch.isalpha():
            try:
                name = unicodedata.name(ch)
                scripts.add(name.split(" ")[0])
            except ValueError:
                pass
    return len(scripts) > 1


def run_with_timeout(fn, timeout, *args, **kwargs):
    with cf.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn, *args, **kwargs)
        try:
            return fut.result(timeout=timeout)
        except Exception:
            return None


class PhishingDetector:
    def __init__(self, blocklist_lookup=None, weight_loader=None):
        # blocklist_lookup(url) -> source_name|None, injected so the
        # detector doesn't need to know about the database module directly
        self.blocklist_lookup = blocklist_lookup or (lambda u: None)
        # weight_loader() -> {key: value} dict, loads custom weights from DB
        self._weight_loader = weight_loader
        load_signal_weights(self._weight_loader)

    def reload_weights(self):
        """Reload signal weights from the database (called after admin saves)."""
        load_signal_weights(self._weight_loader)

    # -- individual signal collectors -----------------------------------
    def _url_structure_signals(self, url, parsed, domain_full):
        signals = []
        if parsed.scheme != "https":
            signals.append(("no_https", "URL HTTPS ka istemal nahi karta"))
        if len(url) > 75:
            signals.append(("long_url", "URL asaman se lamba hai (>75 chars) — obfuscation ka signal"))
        if re.search(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", parsed.netloc):
            signals.append(("ip_host", "Domain ki jagah raw IP address istemal ho raha hai"))
        if "@" in url:
            signals.append(("at_symbol", "URL mein '@' symbol — browser is se pehle wala hissa ignore karta hai"))
        if url.count("-") > 4:
            signals.append(("many_hyphens", "URL mein zaroorat se zyada hyphens hain"))
        if parsed.port and parsed.port not in (80, 443):
            signals.append(("suspicious_port", f"Non-standard port istemal ho raha hai ({parsed.port})"))
        return signals

    def _domain_signals(self, extracted):
        signals = []
        domain_name = extracted.domain
        suffix = extracted.suffix
        subdomain = extracted.subdomain

        entropy = shannon_entropy(domain_name)
        if entropy > 3.8:
            signals.append(("high_entropy_domain", f"Domain name randomised lag raha hai (entropy={entropy:.2f})"))

        if domain_name.startswith("xn--"):
            signals.append(("punycode_domain", "Domain Punycode-encoded hai — IDN homograph attack ho sakta hai"))
        if has_mixed_script(domain_name) or has_mixed_script(subdomain):
            signals.append(("mixed_script_domain", "Domain mein mix scripts (e.g. Latin + Cyrillic) — lookalike attack"))

        if suffix in RISKY_TLDS:
            signals.append(("risky_tld", f"'.{suffix}' TLD phishing campaigns mein zyada istemal hoti hai"))

        full_registered = f"{domain_name}.{suffix}"
        if full_registered in URL_SHORTENERS:
            signals.append(("shortener", "Yeh ek URL-shortener hai — asal destination chhupa hua hai"))

        if subdomain.count(".") + (1 if subdomain else 0) >= 3:
            signals.append(("excess_subdomains", "Bohat zyada subdomains — brand ko subdomain mein chhupane ki koshish ho sakti hai"))

        # typosquat check across full brand list (domain OR subdomain OR path segments)
        for brand, domains in TRUSTED_BRANDS.items():
            if full_registered in domains:
                continue  # this literally IS the brand's real domain
            if levenshtein(domain_name, brand) <= 2 and len(brand) > 3:
                signals.append(("typosquat_brand", f"'{domain_name}' '{brand}' se milta-julta hai (typosquatting)"))
                break
            if brand in subdomain and full_registered not in domains:
                signals.append(("brand_in_subdomain_or_path", f"'{brand}' subdomain mein istemal ho raha hai jabke asal domain '{full_registered}' hai"))
                break

        return signals, full_registered

    def _keyword_signals(self, url_lower):
        hits = [kw for kw in SENSITIVE_KEYWORDS if kw in url_lower]
        signals = []
        if hits:
            capped = min(len(hits), 4)
            signals.append(("keyword_hit", f"Sensitive keywords URL mein mojood: {', '.join(hits[:4])}", capped))
        return signals

    def _whois_signals(self, full_registered):
        if pywhois is None:
            return [], None
        result = run_with_timeout(pywhois.whois, WHOIS_TIMEOUT, full_registered)
        if not result:
            return [("whois_unavailable", "WHOIS record fetch nahi ho saka (timeout ya unsupported TLD)")], None
        created = result.creation_date
        if isinstance(created, list):
            created = created[0] if created else None
        if not created:
            return [("whois_unavailable", "WHOIS mein creation date available nahi")], None
        try:
            age_days = (time_now_utc() - created.replace(tzinfo=None)).days
        except Exception:
            return [], None
        signals = []
        if age_days < 30:
            signals.append(("new_domain_lt30", f"Domain sirf {age_days} din pehle register hua — bohat naya"))
        elif age_days < 90:
            signals.append(("new_domain_lt90", f"Domain {age_days} din pehle register hua — abhi bhi kaafi naya"))
        return signals, age_days

    def _ssl_signals(self, hostname, scheme):
        if scheme != "https":
            return [], None
        info = run_with_timeout(self._fetch_cert, SSL_TIMEOUT, hostname)
        if info is None:
            return [("no_ssl_on_https", "https:// URL hai lekin valid TLS certificate haasil nahi ho saka")], None
        signals = []
        if info.get("self_signed"):
            signals.append(("ssl_self_signed", "TLS certificate self-signed hai (kisi trusted CA se issue nahi hua)"))
        if info.get("days_valid") is not None and info["days_valid"] < 20:
            signals.append(("ssl_short_lived", f"Certificate ki validity ghair-mamool tor par choti hai ({info['days_valid']} din)"))
        return signals, info

    @staticmethod
    def _fetch_cert(hostname):
        ctx = ssl.create_default_context()
        try:
            with socket.create_connection((hostname, 443), timeout=SSL_TIMEOUT) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    issuer = dict(x[0] for x in cert.get("issuer", []))
                    not_after = cert.get("notAfter")
                    days_valid = None
                    if not_after:
                        expiry = ssl.cert_time_to_seconds(not_after)
                        days_valid = int((expiry - time.time()) / 86400)
                    return {
                        "issuer": issuer.get("organizationName", issuer.get("commonName", "Unknown")),
                        "days_valid": days_valid,
                        "self_signed": False,
                    }
        except ssl.SSLCertVerificationError:
            try:
                ctx2 = ssl._create_unverified_context()
                with socket.create_connection((hostname, 443), timeout=SSL_TIMEOUT) as sock:
                    with ctx2.wrap_socket(sock, server_hostname=hostname) as ssock:
                        cert = ssock.getpeercert()
                        return {"issuer": "Unverified/Self-signed", "days_valid": None, "self_signed": True}
            except Exception:
                return None
        except Exception:
            return None

    def _fetch_and_analyze_content(self, url):
        """Live HTTP fetch: redirect chain + HTML content analysis. Returns dict or None."""
        try:
            resp = requests.get(
                url, timeout=(3, REQUEST_TIMEOUT), allow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
        except requests.exceptions.RequestException:
            return None

        signals = []
        redirect_count = len(resp.history)
        final_url = resp.url
        if redirect_count >= 3:
            signals.append(("many_redirects", f"URL {redirect_count} baar redirect hua — chain obfuscation ka signal"))
        for hop in resp.history:
            hop_domain = urllib.parse.urlparse(hop.url).netloc
            if any(short in hop_domain for short in URL_SHORTENERS):
                signals.append(("redirect_to_shortener", "Redirect chain mein URL shortener shamil hai"))
                break

        original_reg_domain = _TLD(url).registered_domain
        final_reg_domain = _TLD(final_url).registered_domain
        if original_reg_domain and final_reg_domain and original_reg_domain != final_reg_domain:
            signals.append(("final_domain_mismatch", f"Redirect ke baad domain badal gaya: {original_reg_domain} → {final_reg_domain}"))

        html = resp.text[:60000]
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            soup = None

        title = ""
        if soup:
            title = (soup.title.string or "").strip().lower() if soup.title else ""
            forms = soup.find_all("form")
            if len(forms) > 1:
                signals.append(("multiple_forms", f"{len(forms)} forms ek hi page par — unusual"))

            has_password = False
            has_sensitive = False
            offsite_form = False
            for form in forms:
                action = form.get("action", "")
                for inp in form.find_all("input"):
                    itype = (inp.get("type") or "").lower()
                    iname = (inp.get("name") or "").lower()
                    if itype == "password":
                        has_password = True
                    if any(w in iname for w in ["card", "cvv", "ssn", "otp", "pin", "cvc"]):
                        has_sensitive = True
                if action and action.startswith("http"):
                    action_domain = _TLD(action).registered_domain
                    if action_domain and action_domain != final_reg_domain:
                        offsite_form = True
            if has_password:
                signals.append(("password_field", "Page par password input field mojood hai"))
            if has_sensitive:
                signals.append(("sensitive_input_fields", "Card/OTP/CVV jaisi sensitive fields mojood hain"))
            if offsite_form:
                signals.append(("form_action_offsite", "Form data kisi ALAG domain par submit ho raha hai — credential harvesting ka classic pattern"))

            # brand impersonation: page *talks about* a brand it doesn't belong to
            page_text = (title + " " + soup.get_text(" ", strip=True)[:2000]).lower()
            for brand, domains in TRUSTED_BRANDS.items():
                if final_reg_domain in domains:
                    continue
                if re.search(rf"\b{re.escape(brand)}\b", page_text) and page_text.count(brand) >= 2:
                    signals.append(("brand_impersonation_content", f"Page '{brand}' ka naam baar baar istemal karta hai lekin domain '{final_reg_domain}' us brand ka nahi hai"))
                    break

            scripts_text = " ".join(s.get_text() for s in soup.find_all("script"))
            obf_hits = sum(scripts_text.count(tok) for tok in ["eval(", "unescape(", "fromCharCode", "document.write("])
            if obf_hits >= 3:
                signals.append(("obfuscated_script", "Page mein obfuscated/suspicious JavaScript patterns hain"))

        return {
            "signals": signals,
            "redirect_count": redirect_count,
            "final_url": final_url,
            "title": title,
        }

    # -- orchestration ----------------------------------------------------
    def hunt(self, raw_url: str) -> dict:
        start = time.time()
        if not raw_url.startswith(("http://", "https://")):
            raw_url = "https://" + raw_url

        parsed = urllib.parse.urlparse(raw_url)
        extracted = _TLD(raw_url)
        url_lower = raw_url.lower()

        all_signals = []  # list of (key, detail, [multiplier])

        # 1. deterministic blocklist check first (cheap, decisive)
        block_source = self.blocklist_lookup(raw_url) or self.blocklist_lookup(parsed.netloc)
        if block_source:
            all_signals.append(("blocklist_hit", f"URL community blocklist '{block_source}' mein maujood hai"))
        
        # 1b. Google Safe Browsing check (also deterministic, but network call)
        gsb_result = run_with_timeout(safebrowsing.check_url, 5, raw_url)
        if gsb_result and gsb_result.get("is_threat"):
            all_signals.append(("google_safebrowsing_hit", gsb_result.get("details", "Google Safe Browsing ne is URL ko threat ke tor par flag kiya hai")))
        
        # 1c. VirusTotal check (multi-vendor consensus, scaled by ratio)
        vt_result = run_with_timeout(virustotal.check_url, 5, raw_url)
        if vt_result and not vt_result.get("pending", False):
            ratio = vt_result.get("ratio", 0.0)
            if ratio > 0.05:  # At least 5% of vendors flagged it
                # Scale the signal by how many vendors flagged it
                # ratio 0.05-0.20 → low concern, 0.20-0.50 → medium, >0.50 → high
                scaled_weight = min(ratio * 1.5, 1.0)  # cap at 1.0
                all_signals.append((
                    "virustotal_flagged",
                    vt_result.get("details", "VirusTotal vendors ne URL ko flag kiya hai"),
                    scaled_weight,  # multiplier based on ratio
                ))

        # 2. structural + domain signals (fast, offline, always run)
        all_signals += self._url_structure_signals(raw_url, parsed, extracted.registered_domain)
        domain_sigs, full_registered = self._domain_signals(extracted)
        all_signals += domain_sigs
        all_signals += self._keyword_signals(url_lower)

        # 3. network-dependent checks run CONCURRENTLY with hard timeouts
        #    so a slow WHOIS server can't stall the whole scan
        content_result = None
        whois_age_days = None
        ssl_info = None
        offline = False

        with cf.ThreadPoolExecutor(max_workers=3) as ex:
            fut_content = ex.submit(self._fetch_and_analyze_content, raw_url)
            fut_whois = ex.submit(self._whois_signals, full_registered)
            fut_ssl = ex.submit(self._ssl_signals, parsed.netloc.split(":")[0], parsed.scheme)

            content_result = fut_content.result()
            whois_sigs, whois_age_days = fut_whois.result() or ([], None)
            ssl_sigs, ssl_info = fut_ssl.result() or ([], None)

        all_signals += whois_sigs
        all_signals += ssl_sigs

        if content_result is None:
            offline = True
            redirect_count = 0
            final_url = raw_url
        else:
            all_signals += content_result["signals"]
            redirect_count = content_result["redirect_count"]
            final_url = content_result["final_url"]
        
        # 3b. Visual similarity check (screenshot-based brand detection)
        #     This is expensive (screenshots take 2-8 seconds), so we:
        #     - Only run if page loaded successfully (not offline)
        #     - Cache results for 24 hours
        #     - Run in background thread with timeout
        if not offline and visual_similarity.is_available():
            visual_result = run_with_timeout(
                visual_similarity.check_visual_similarity,
                10,  # 10 second max (includes screenshot time)
                final_url,
                full_registered,
            )
            if visual_result and visual_result.get("is_clone"):
                all_signals.append((
                    "visual_brand_clone",
                    visual_result.get("details", "Page visual ko kisi brand ka clone lag raha hai lekin domain mismatch hai"),
                ))

        # 4. score aggregation
        score = 0
        breakdown = []
        blocklist_hit = False
        safebrowsing_hit = False
        ml_probability = None
        
        # Get ML score if available
        if ml_infer and ml_infer.is_available():
            try:
                ml_features = extract_ml_features(raw_url, parsed, extracted, url_lower)
                ml_probability = ml_infer.score_url(raw_url, ml_features)
                if ml_probability is not None:
                    breakdown.append({
                        "key": "ml_model_confidence",
                        "detail": f"Machine learning model confidence: {ml_probability:.1%}",
                        "points": 0,  # Not added to rule-based score, blended separately
                        "severity": "info",
                    })
            except Exception as e:
                pass
        
        for sig in all_signals:
            key, detail = sig[0], sig[1]
            multiplier = sig[2] if len(sig) > 2 else 1
            weight = SIGNAL_WEIGHTS.get(key, 0) * multiplier
            score += weight
            if key == "blocklist_hit":
                blocklist_hit = True
            if key == "google_safebrowsing_hit":
                safebrowsing_hit = True
            severity = self._severity_for(key, weight)
            breakdown.append({
                "key": key, "detail": detail, "points": weight, "severity": severity,
            })

        if full_registered in ALL_TRUSTED_DOMAINS:
            # STRONG OVERRIDE: Trusted domains should be SAFE by default
            # unless explicitly flagged by blocklist/safebrowsing
            if not (blocklist_hit or safebrowsing_hit):
                score = 0  # Force SAFE for known trusted brands
            breakdown.append({
                "key": "trusted_domain_bonus",
                "detail": f"'{full_registered}' known trusted domain hai — automatically SAFE",
                "points": SIGNAL_WEIGHTS["trusted_domain_bonus"],
                "severity": "positive",
            })

        score = max(0, min(100, score))
        
        # Blend ML probability with rule-based score (if ML is available)
        if ml_probability is not None:
            # 60% ML probability, 40% rule-based score
            ml_score = ml_probability * 100
            final_score = 0.6 * ml_score + 0.4 * score
            score = int(final_score)
        
        # Deterministic overrides (highest priority)
        if blocklist_hit or safebrowsing_hit:
            score = 100  # Force PHISHING
        elif full_registered in ALL_TRUSTED_DOMAINS:
            score = 0  # Force SAFE for trusted brands

        if score < 25:
            risk = "SAFE"
        elif score < 55:
            risk = "LOW RISK"
        elif score < 80:
            risk = "HIGH RISK"
        else:
            risk = "PHISHING"

        return {
            "url": raw_url,
            "final_url": final_url,
            "domain": full_registered,
            "score": score,
            "risk": risk,
            "offline": offline,
            "blocklist_hit": blocklist_hit,
            "domain_age_days": whois_age_days,
            "ssl": ssl_info,
            "redirect_count": redirect_count,
            "signals": sorted(breakdown, key=lambda s: -s["points"]),
            "scan_time_ms": int((time.time() - start) * 1000),
        }

    @staticmethod
    def _severity_for(key, points):
        if key == "blocklist_hit":
            return "critical"
        if points >= 30:
            return "critical"
        if points >= 18:
            return "high"
        if points > 0:
            return "medium"
        if points < 0:
            return "positive"
        return "info"


def time_now_utc():
    import datetime
    return datetime.datetime.utcnow()


def extract_ml_features(url, parsed, extracted, url_lower):
    """
    Extract features for ML model (same as ml/train.py).
    This is used both for training and inference.
    """
    domain_name = extracted.domain
    suffix = extracted.suffix
    subdomain = extracted.subdomain
    full_registered = f"{domain_name}.{suffix}" if domain_name and suffix else ""
    
    features = {}
    
    # Basic URL structure
    features["is_https"] = 1 if parsed.scheme == "https" else 0
    features["url_length"] = len(url)
    features["path_length"] = len(parsed.path)
    features["query_length"] = len(parsed.query)
    features["fragment_length"] = len(parsed.fragment)
    
    # Domain characteristics
    features["domain_length"] = len(domain_name)
    features["subdomain_count"] = subdomain.count(".") + (1 if subdomain else 0)
    features["has_ip_address"] = 1 if re.search(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", parsed.netloc) else 0
    features["has_at_symbol"] = 1 if "@" in url else 0
    features["hyphen_count"] = url.count("-")
    features["underscore_count"] = url.count("_")
    features["dot_count"] = url.count(".")
    features["digit_count"] = sum(c.isdigit() for c in url)
    features["digit_ratio"] = features["digit_count"] / len(url) if len(url) > 0 else 0
    
    # Domain entropy
    features["domain_entropy"] = shannon_entropy(domain_name) if domain_name else 0
    
    # TLD and domain reputation
    features["is_risky_tld"] = 1 if suffix in RISKY_TLDS else 0
    features["is_shortener"] = 1 if full_registered in URL_SHORTENERS else 0
    features["is_trusted_domain"] = 1 if full_registered in ALL_TRUSTED_DOMAINS else 0
    
    # IDN/homograph attacks
    features["is_punycode"] = 1 if domain_name.startswith("xn--") else 0
    features["has_mixed_script"] = 1 if has_mixed_script(domain_name) or has_mixed_script(subdomain) else 0
    
    # Brand typosquatting
    min_brand_distance = 999
    brand_in_subdomain = 0
    for brand, domains in TRUSTED_BRANDS.items():
        if full_registered in domains:
            continue
        dist = levenshtein(domain_name, brand)
        if dist < min_brand_distance and len(brand) > 3:
            min_brand_distance = dist
        if brand in subdomain and full_registered not in domains:
            brand_in_subdomain = 1
    
    features["min_brand_levenshtein"] = min_brand_distance if min_brand_distance < 999 else 10
    features["brand_in_subdomain"] = brand_in_subdomain
    
    # Keyword analysis
    keyword_count = sum(1 for kw in SENSITIVE_KEYWORDS if kw in url_lower)
    features["sensitive_keyword_count"] = min(keyword_count, 5)
    
    # Port
    features["has_nonstandard_port"] = 1 if parsed.port and parsed.port not in (80, 443) else 0
    
    # Path characteristics
    features["path_depth"] = parsed.path.count("/")
    features["has_suspicious_path"] = 1 if any(s in parsed.path.lower() for s in ["login", "verify", "account", "update", "signin"]) else 0
    
    # Query parameters
    features["query_param_count"] = len(urllib.parse.parse_qs(parsed.query))
    
    return features
