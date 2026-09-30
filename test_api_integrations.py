"""
test_api_integrations.py
-------------------------
Quick manual test script for Phase 2 & 3 API integrations.

This tests both Google Safe Browsing and VirusTotal modules
in isolation before running them through the full detector.

Usage:
  python test_api_integrations.py
"""

import safebrowsing
import virustotal

print("=" * 60)
print("PhishingHunter API Integration Test")
print("=" * 60)

# Test URLs
test_safe_url = "https://google.com"
test_phishing_url = "http://testsafebrowsing.appspot.com/s/phishing.html"  # Google's test phishing URL

print("\n" + "=" * 60)
print("Testing Google Safe Browsing Integration")
print("=" * 60)

print(f"\n1. Testing SAFE URL: {test_safe_url}")
result = safebrowsing.check_url(test_safe_url)
if result is None:
    print("   → API key not configured or request failed (this is OK for testing)")
else:
    print(f"   → is_threat: {result.get('is_threat')}")
    print(f"   → details: {result.get('details')}")

print(f"\n2. Testing KNOWN PHISHING URL: {test_phishing_url}")
result = safebrowsing.check_url(test_phishing_url)
if result is None:
    print("   → API key not configured or request failed")
else:
    print(f"   → is_threat: {result.get('is_threat')}")
    print(f"   → threat_types: {result.get('threat_types')}")
    print(f"   → details: {result.get('details')}")

print("\n" + "=" * 60)
print("Testing VirusTotal Integration")
print("=" * 60)

print(f"\n3. Testing SAFE URL: {test_safe_url}")
result = virustotal.check_url(test_safe_url)
if result is None:
    print("   → API key not configured, rate limited, or request failed (this is OK)")
else:
    print(f"   → malicious_count: {result.get('malicious_count')}")
    print(f"   → suspicious_count: {result.get('suspicious_count')}")
    print(f"   → total_vendors: {result.get('total_vendors')}")
    print(f"   → ratio: {result.get('ratio'):.2%}")
    print(f"   → details: {result.get('details')}")
    print(f"   → pending: {result.get('pending', False)}")

print(f"\n4. Testing SUSPICIOUS URL: http://malware.wicar.org/data/eicar.com")
result = virustotal.check_url("http://malware.wicar.org/data/eicar.com")
if result is None:
    print("   → API key not configured, rate limited, or request failed")
else:
    print(f"   → malicious_count: {result.get('malicious_count')}")
    print(f"   → suspicious_count: {result.get('suspicious_count')}")
    print(f"   → total_vendors: {result.get('total_vendors')}")
    print(f"   → ratio: {result.get('ratio'):.2%}")
    print(f"   → details: {result.get('details')}")

print("\n" + "=" * 60)
print("Integration Test Complete")
print("=" * 60)
print("\nNotes:")
print("- If 'API key not configured' appears, set the environment variables:")
print("  GOOGLE_SAFE_BROWSING_API_KEY=your_key")
print("  VIRUSTOTAL_API_KEY=your_key")
print("- VirusTotal has a 4 req/min rate limit (free tier)")
print("- Results are cached, so repeated tests use cached data")
print("- The app works fine without these keys (fails soft)")
