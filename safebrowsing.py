"""
safebrowsing.py
---------------
Google Safe Browsing v4 API integration for PhishingHunter.

This provides deterministic threat intelligence from Google's massive
threat database, checking URLs against:
  - MALWARE
  - SOCIAL_ENGINEERING (phishing)
  - UNWANTED_SOFTWARE
  - POTENTIALLY_HARMFUL_APPLICATION

This is a free API (with reasonable rate limits) that significantly
improves detection accuracy by adding real threat intelligence on top
of heuristic scoring.

Setup:
  1. Get a free API key from Google Cloud Console:
     https://console.cloud.google.com/apis/credentials
  2. Enable "Safe Browsing API" for your project
  3. Set environment variable: GOOGLE_SAFE_BROWSING_API_KEY=your_key_here

The detector.py module calls check_url() and treats any match as a
deterministic high-severity signal (similar to blocklist hits).
"""

import os
import logging
import requests

logger = logging.getLogger("phishinghunter.safebrowsing")

API_KEY = os.environ.get("GOOGLE_SAFE_BROWSING_API_KEY")
API_ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
TIMEOUT = 4

# Threat types we care about
THREAT_TYPES = [
    "MALWARE",
    "SOCIAL_ENGINEERING",  # phishing
    "UNWANTED_SOFTWARE",
    "POTENTIALLY_HARMFUL_APPLICATION",
]

# Platform types (we check all major platforms)
PLATFORM_TYPES = [
    "ANY_PLATFORM",
    "WINDOWS",
    "LINUX",
    "ANDROID",
    "OSX",
    "IOS",
]

# Threat entry types
THREAT_ENTRY_TYPES = ["URL"]


def check_url(url: str) -> dict:
    """
    Check a URL against Google Safe Browsing API.
    
    Args:
        url: The URL to check
    
    Returns:
        dict with keys:
          - is_threat: bool, True if URL matches any threat list
          - threat_types: list of matched threat types
          - details: human-readable description
        
        Returns None if:
          - API key is not configured
          - API call fails/times out
          - Any error occurs (fail-soft pattern)
    """
    if not API_KEY:
        logger.debug("Google Safe Browsing API key not configured, skipping check")
        return None
    
    if not url:
        return None
    
    try:
        payload = {
            "client": {
                "clientId": "PhishingHunter",
                "clientVersion": "2.0",
            },
            "threatInfo": {
                "threatTypes": THREAT_TYPES,
                "platformTypes": PLATFORM_TYPES,
                "threatEntryTypes": THREAT_ENTRY_TYPES,
                "threatEntries": [{"url": url}],
            },
        }
        
        response = requests.post(
            API_ENDPOINT,
            params={"key": API_KEY},
            json=payload,
            timeout=TIMEOUT,
            headers={"User-Agent": "PhishingHunter/2.0"},
        )
        
        # If status is not 200, fail soft
        if response.status_code != 200:
            logger.warning(
                "Safe Browsing API returned status %d: %s",
                response.status_code,
                response.text[:200],
            )
            return None
        
        data = response.json()
        
        # Empty response means no threats found
        if not data or "matches" not in data:
            return {
                "is_threat": False,
                "threat_types": [],
                "details": "Google Safe Browsing: Clean (no threats detected)",
            }
        
        # Parse matched threats
        matches = data.get("matches", [])
        threat_types = list(set(m.get("threatType", "UNKNOWN") for m in matches))
        
        # Build human-readable description
        threat_names = {
            "MALWARE": "Malware",
            "SOCIAL_ENGINEERING": "Phishing/Social Engineering",
            "UNWANTED_SOFTWARE": "Unwanted Software",
            "POTENTIALLY_HARMFUL_APPLICATION": "Potentially Harmful App",
        }
        
        threat_labels = [threat_names.get(t, t) for t in threat_types]
        details = f"Google Safe Browsing flagged as: {', '.join(threat_labels)}"
        
        return {
            "is_threat": True,
            "threat_types": threat_types,
            "details": details,
        }
    
    except requests.exceptions.Timeout:
        logger.warning("Safe Browsing API timeout for URL: %s", url)
        return None
    
    except requests.exceptions.RequestException as e:
        logger.warning("Safe Browsing API request failed: %s", e)
        return None
    
    except Exception as e:
        logger.error("Unexpected error in Safe Browsing check: %s", e)
        return None
