"""
ml/train.py
-----------
Machine Learning training pipeline for PhishingHunter.

This script replaces hand-tuned SIGNAL_WEIGHTS with a trained classifier
that learns the actual weight of each signal from real labeled data.

Data sources:
  - PhishTank verified feed (phishing URLs)
  - Tranco top 1M list (legitimate URLs)

The trained model is saved to ml/model.joblib and used by ml/infer.py
at runtime for scoring.

Usage:
  python -m ml.train
"""

import os
import sys
import json
import re
import math
import unicodedata
import urllib.parse
from collections import Counter

import requests
import tldextract
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support
import joblib

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from detector import (
    TRUSTED_BRANDS, ALL_TRUSTED_DOMAINS, RISKY_TLDS, URL_SHORTENERS,
    SENSITIVE_KEYWORDS, levenshtein, shannon_entropy, has_mixed_script,
)

# tldextract: force offline
_TLD = tldextract.TLDExtract(suffix_list_urls=())

# Data sources
PHISHTANK_URL = "http://data.phishtank.com/data/online-valid.csv"
TRANCO_URL = "https://tranco-list.eu/top-1m.csv.zip"  # Top 1M list (current)

# Sample sizes (for class balance)
SAMPLE_SIZE = 20000  # 20k phishing + 20k legitimate = 40k total

# Output paths
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.joblib")
FEATURES_PATH = os.path.join(os.path.dirname(__file__), "features.json")
SCALER_PATH = os.path.join(os.path.dirname(__file__), "scaler.joblib")


def download_phishtank_urls(limit=SAMPLE_SIZE):
    """Download PhishTank verified phishing URLs."""
    print(f"Downloading PhishTank verified feed...")
    try:
        resp = requests.get(PHISHTANK_URL, timeout=30)
        resp.raise_for_status()
        lines = resp.text.strip().split("\n")[1:]  # Skip header
        urls = []
        for line in lines[:limit]:
            parts = line.split(",")
            if len(parts) >= 2:
                url = parts[1].strip('"')
                if url.startswith("http"):
                    urls.append(url)
        print(f"  → Downloaded {len(urls)} phishing URLs")
        return urls
    except Exception as e:
        print(f"  → Error downloading PhishTank: {e}")
        return []


def download_tranco_urls(limit=SAMPLE_SIZE):
    """Download Tranco top domains (legitimate URLs)."""
    print(f"Downloading Tranco top domains...")
    try:
        import io
        import zipfile
        
        resp = requests.get(TRANCO_URL, timeout=60)
        resp.raise_for_status()
        
        # Extract zip file in memory
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            # Find the CSV file in the zip
            csv_files = [f for f in zf.namelist() if f.endswith('.csv')]
            if not csv_files:
                raise Exception("No CSV file found in zip")
            
            # Read the first CSV file
            with zf.open(csv_files[0]) as f:
                lines = f.read().decode('utf-8').strip().split("\n")
        
        urls = []
        for line in lines[:limit]:
            parts = line.split(",")
            if len(parts) >= 2:
                domain = parts[1].strip()
                if domain:
                    urls.append(f"https://{domain}")
        print(f"  → Downloaded {len(urls)} legitimate URLs")
        return urls
    except Exception as e:
        print(f"  → Error downloading Tranco: {e}")
        return []


def extract_features(url):
    """
    Extract features from a URL (same structural features as detector.py).
    
    Returns a dict of features that will be used for training.
    """
    parsed = urllib.parse.urlparse(url)
    extracted = _TLD(url)
    url_lower = url.lower()
    
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
    features["sensitive_keyword_count"] = min(keyword_count, 5)  # cap at 5
    
    # Port
    features["has_nonstandard_port"] = 1 if parsed.port and parsed.port not in (80, 443) else 0
    
    # Path characteristics
    features["path_depth"] = parsed.path.count("/")
    features["has_suspicious_path"] = 1 if any(s in parsed.path.lower() for s in ["login", "verify", "account", "update", "signin"]) else 0
    
    # Query parameters
    features["query_param_count"] = len(urllib.parse.parse_qs(parsed.query))
    
    return features


def build_dataset():
    """Download and build training dataset."""
    print("\n" + "=" * 60)
    print("Building ML Training Dataset")
    print("=" * 60)
    
    # Download data
    phishing_urls = download_phishtank_urls(SAMPLE_SIZE)
    legitimate_urls = download_tranco_urls(SAMPLE_SIZE)
    
    if len(phishing_urls) < 1000 or len(legitimate_urls) < 1000:
        print("\n⚠ Warning: Insufficient data downloaded.")
        print("  Using fallback synthetic data for demonstration...")
        # In production, you'd exit here or use cached data
        return None, None, None
    
    # Balance classes
    min_size = min(len(phishing_urls), len(legitimate_urls))
    phishing_urls = phishing_urls[:min_size]
    legitimate_urls = legitimate_urls[:min_size]
    
    print(f"\nExtracting features from {len(phishing_urls) + len(legitimate_urls)} URLs...")
    
    # Extract features
    X = []
    y = []
    
    for url in phishing_urls:
        try:
            features = extract_features(url)
            X.append(features)
            y.append(1)  # phishing
        except Exception:
            pass
    
    for url in legitimate_urls:
        try:
            features = extract_features(url)
            X.append(features)
            y.append(0)  # legitimate
        except Exception:
            pass
    
    print(f"  → Extracted features from {len(X)} URLs")
    print(f"  → Phishing: {sum(y)}, Legitimate: {len(y) - sum(y)}")
    
    return X, y, list(X[0].keys()) if X else []


def train_model(X, y, feature_names):
    """Train gradient boosted classifier."""
    print("\n" + "=" * 60)
    print("Training Model")
    print("=" * 60)
    
    # Convert to numpy arrays
    X_array = np.array([[feat[k] for k in feature_names] for feat in X])
    y_array = np.array(y)
    
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X_array, y_array, test_size=0.2, random_state=42, stratify=y_array
    )
    
    print(f"Training set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")
    
    # Train model
    print("\nTraining HistGradientBoostingClassifier...")
    model = HistGradientBoostingClassifier(
        max_iter=200,
        learning_rate=0.1,
        max_depth=6,
        random_state=42,
        verbose=1,
    )
    
    model.fit(X_train, y_train)
    
    # Evaluate
    print("\n" + "=" * 60)
    print("Evaluation on Test Set")
    print("=" * 60)
    
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Legitimate", "Phishing"]))
    
    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(f"                  Predicted")
    print(f"                  Legit  Phish")
    print(f"Actual  Legit     {cm[0][0]:5d}  {cm[0][1]:5d}")
    print(f"        Phish     {cm[1][0]:5d}  {cm[1][1]:5d}")
    
    # Feature importance (HistGradientBoostingClassifier doesn't expose feature_importances_)
    # Skip for now - model is trained successfully
    print("\n✅ Model trained successfully!")
    print(f"   Test Accuracy: {(y_pred == y_test).mean() * 100:.2f}%")
    
    return model, feature_names


def save_model(model, feature_names):
    """Save trained model and feature list."""
    print("\n" + "=" * 60)
    print("Saving Model")
    print("=" * 60)
    
    joblib.dump(model, MODEL_PATH)
    print(f"  → Model saved to: {MODEL_PATH}")
    
    with open(FEATURES_PATH, "w") as f:
        json.dump(feature_names, f, indent=2)
    print(f"  → Features saved to: {FEATURES_PATH}")


def main():
    """Main training pipeline."""
    print("\n" + "=" * 60)
    print("PhishingHunter ML Training Pipeline")
    print("=" * 60)
    
    # Build dataset
    X, y, feature_names = build_dataset()
    
    if X is None or len(X) < 100:
        print("\n❌ Insufficient data for training. Exiting.")
        return
    
    # Train model
    model, feature_names = train_model(X, y, feature_names)
    
    # Save model
    save_model(model, feature_names)
    
    print("\n" + "=" * 60)
    print("✅ Training Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. The model is now saved and will be used by detector.py")
    print("  2. Test it with: python app.py")
    print("  3. Retrain periodically with: python -m ml.retrain")


if __name__ == "__main__":
    main()
