"""
ml/infer.py
-----------
Runtime inference module for PhishingHunter ML model.

This module loads the trained model once at import time and provides
a score_url() function that returns a probability (0-1) for any URL.

The detector.py module uses this to blend ML probability with
rule-based signals for the final score.
"""

import os
import json
import logging

import numpy as np
import joblib

logger = logging.getLogger("phishinghunter.ml")

# Paths
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.joblib")
FEATURES_PATH = os.path.join(os.path.dirname(__file__), "features.json")

# Load model and feature names once at import time
_model = None
_feature_names = None


def _load_model():
    """Load model and feature names (called once on first use)."""
    global _model, _feature_names
    
    if not os.path.exists(MODEL_PATH):
        logger.warning("ML model not found at %s - ML scoring disabled", MODEL_PATH)
        return False
    
    if not os.path.exists(FEATURES_PATH):
        logger.warning("ML features file not found at %s - ML scoring disabled", FEATURES_PATH)
        return False
    
    try:
        _model = joblib.load(MODEL_PATH)
        with open(FEATURES_PATH, "r") as f:
            _feature_names = json.load(f)
        logger.info("ML model loaded successfully (%d features)", len(_feature_names))
        return True
    except Exception as e:
        logger.error("Failed to load ML model: %s", e)
        return False


def score_url(url: str, features: dict) -> float:
    """
    Score a URL using the trained ML model.
    
    Args:
        url: The URL to score (not directly used, features are extracted by caller)
        features: Feature dict extracted by detector.py using extract_features()
    
    Returns:
        float: Probability of being phishing (0.0 to 1.0)
        Returns None if model is not available
    """
    global _model, _feature_names
    
    # Load model on first call
    if _model is None:
        if not _load_model():
            return None
    
    if _model is None or _feature_names is None:
        return None
    
    try:
        # Build feature vector in correct order
        X = np.array([[features.get(k, 0) for k in _feature_names]])
        
        # Get probability of being phishing (class 1)
        proba = _model.predict_proba(X)[0][1]
        
        return float(proba)
    
    except Exception as e:
        logger.error("ML inference error for URL %s: %s", url[:50], e)
        return None


def is_available():
    """Check if ML model is available."""
    global _model
    if _model is None:
        _load_model()
    return _model is not None
