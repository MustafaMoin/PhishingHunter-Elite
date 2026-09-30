"""
ml/retrain.py
-------------
Retrain the ML model using feedback data collected from users.

This is the feedback loop that lets the model improve over time:
  1. Users report false positives/negatives via the UI
  2. This data is stored in the feedback table
  3. This script pulls that feedback and appends it as additional
     labeled training examples
  4. Model is retrained with the original dataset + feedback

Usage:
  python -m ml.retrain
"""

import os
import sys
import json

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database
from ml.train import extract_features, download_phishtank_urls, download_tranco_urls

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.joblib")
FEATURES_PATH = os.path.join(os.path.dirname(__file__), "features.json")


def get_feedback_data():
    """Pull feedback from database and convert to training examples."""
    print("\n" + "=" * 60)
    print("Extracting Feedback Data")
    print("=" * 60)
    
    with database.get_conn() as conn:
        rows = conn.execute(
            "SELECT url, feedback_type FROM feedback WHERE url IS NOT NULL AND url != ''"
        ).fetchall()
    
    feedback_X = []
    feedback_y = []
    
    for row in rows:
        url = row["url"]
        ftype = row["feedback_type"]
        
        try:
            features = extract_features(url)
            
            # Map feedback type to label
            if ftype == "false_positive":
                # User said "this was marked as phishing but it's safe"
                label = 0  # legitimate
            elif ftype == "false_negative":
                # User said "this was marked as safe but it's phishing"
                label = 1  # phishing
            elif ftype == "confirmed":
                # User confirmed the detection was correct
                # We need to check what it was marked as...
                # For now, skip these (or you could store original score in feedback table)
                continue
            else:
                continue
            
            feedback_X.append(features)
            feedback_y.append(label)
        
        except Exception as e:
            print(f"  → Error processing feedback URL {url}: {e}")
    
    print(f"  → Processed {len(feedback_X)} feedback examples")
    print(f"    False positives (now labeled legit): {sum(1 for y in feedback_y if y == 0)}")
    print(f"    False negatives (now labeled phish): {sum(1 for y in feedback_y if y == 1)}")
    
    return feedback_X, feedback_y


def retrain_with_feedback():
    """Retrain model with original data + feedback."""
    print("\n" + "=" * 60)
    print("PhishingHunter ML Retraining Pipeline")
    print("=" * 60)
    
    # Get feedback data
    feedback_X, feedback_y = get_feedback_data()
    
    if len(feedback_X) < 10:
        print("\n⚠ Warning: Very few feedback examples (<10).")
        print("  Model retraining works best with at least 50-100 feedback examples.")
        response = input("  Continue anyway? (y/n): ")
        if response.lower() != "y":
            print("Aborted.")
            return
    
    # Download fresh base dataset
    print("\nDownloading base dataset...")
    phishing_urls = download_phishtank_urls(20000)
    legitimate_urls = download_tranco_urls(20000)
    
    # Extract features from base dataset
    print("Extracting features from base dataset...")
    base_X = []
    base_y = []
    
    for url in phishing_urls:
        try:
            base_X.append(extract_features(url))
            base_y.append(1)
        except:
            pass
    
    for url in legitimate_urls:
        try:
            base_X.append(extract_features(url))
            base_y.append(0)
        except:
            pass
    
    print(f"  → Base dataset: {len(base_X)} examples")
    
    # Combine base + feedback
    all_X = base_X + feedback_X
    all_y = base_y + feedback_y
    
    print(f"  → Total dataset: {len(all_X)} examples (base + feedback)")
    
    # Get feature names
    if not os.path.exists(FEATURES_PATH):
        print("❌ Features file not found. Run ml.train first.")
        return
    
    with open(FEATURES_PATH, "r") as f:
        feature_names = json.load(f)
    
    # Convert to numpy arrays
    X_array = np.array([[feat.get(k, 0) for k in feature_names] for feat in all_X])
    y_array = np.array(all_y)
    
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X_array, y_array, test_size=0.2, random_state=42, stratify=y_array
    )
    
    print(f"\nTraining set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")
    
    # Train model
    print("\nRetraining model...")
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
    
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Legitimate", "Phishing"]))
    
    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(f"                  Predicted")
    print(f"                  Legit  Phish")
    print(f"Actual  Legit     {cm[0][0]:5d}  {cm[0][1]:5d}")
    print(f"        Phish     {cm[1][0]:5d}  {cm[1][1]:5d}")
    
    # Save retrained model
    print("\n" + "=" * 60)
    print("Saving Retrained Model")
    print("=" * 60)
    
    joblib.dump(model, MODEL_PATH)
    print(f"  → Model saved to: {MODEL_PATH}")
    
    print("\n✅ Retraining complete!")
    print("   The updated model will be used on the next scan.")


if __name__ == "__main__":
    retrain_with_feedback()
