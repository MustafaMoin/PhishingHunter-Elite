# Admin Panel Quick Start Guide

Quick reference for accessing and using the PhishingHunter Admin Dashboard.

---

## 🚀 Quick Access (3 Steps)

### 1. Set Admin Credentials

**Windows CMD:**
```cmd
set ADMIN_USERNAME=admin
set ADMIN_PASSWORD=changeme
```

**Windows PowerShell:**
```powershell
$env:ADMIN_USERNAME="admin"
$env:ADMIN_PASSWORD="changeme"
```

**Linux/Mac:**
```bash
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=changeme
```

### 2. Start the App

```bash
python app.py
```

### 3. Open Admin Panel

Navigate to: **http://localhost:5000/admin**

Login with:
- Username: `admin`
- Password: `changeme`

---

## 🔐 Production Setup (Secure)

For production, use password hashing instead of plaintext:

```bash
# Generate secure hash
python admin_auth.py MySecureP@ssw0rd

# Output will show:
# Password hash for 'MySecureP@ssw0rd':
# 8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918

# Add to .env or set as environment variable:
# ADMIN_PASSWORD_HASH=8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918
```

**Windows:**
```cmd
set ADMIN_PASSWORD_HASH=8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918
```

**Linux/Mac:**
```bash
export ADMIN_PASSWORD_HASH=8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918
```

---

## 📊 Admin Features Overview

### Main Dashboard (`/admin`)
- **System Stats:** Total scans, threats detected, feedback count, DB size
- **System Info:** Cache efficiency, blocklist coverage
- **Signal Analysis:** Which signals trigger false positives/negatives
- **Manual Triggers:** Refresh blocklist, retrain ML model

### Feedback Analysis (`/admin/feedback`)
- **Filter Options:** All / False Positives / False Negatives / Confirmed
- **Detailed Table:** Every feedback submission with full signal breakdown
- **Expandable Rows:** Click "View Signals" to see detection details

---

## 🎯 Common Tasks

### View All Feedback
1. Go to `/admin/feedback`
2. See all user reports

### Find False Positives (Too Aggressive)
1. Go to `/admin/feedback?filter=false_positive`
2. Review which signals appear most
3. Consider reducing weights in `detector.py`

### Find False Negatives (Missed Threats)
1. Go to `/admin/feedback?filter=false_negative`
2. Review which signals were present
3. Consider increasing weights or adding new signals

### Refresh Blocklists
1. Go to `/admin`
2. Click "REFRESH NOW" under Refresh Blocklists
3. Wait for success notification
4. Latest OpenPhish + URLhaus feeds loaded

### Retrain ML Model (Phase 4 Required)
1. Go to `/admin`
2. Click "RETRAIN MODEL"
3. Uses feedback data as training labels
4. Check logs for training progress

---

## 🔍 Understanding Signal Analysis

### False Positive Signals
**What it means:** These signals fire when users report "this is actually safe"

**How to use it:**
- If a signal appears frequently → it's too aggressive
- Consider reducing its weight in `SIGNAL_WEIGHTS` (detector.py)
- Example: If "suspicious keyword" appears in 50% of false positives, it's likely too sensitive

### False Negative Signals
**What it means:** These signals were present in URLs users flagged as "you missed this phishing"

**How to use it:**
- Shows which signals DID fire but didn't prevent the URL from passing
- Indicates signals that need higher weights
- May reveal gaps (missing signals that should exist)

---

## 🛠️ Troubleshooting

### Can't Access Admin Panel
**Problem:** Page redirects to login  
**Solution:** Make sure you're logged in at `/admin/login`

### Invalid Credentials
**Problem:** "Invalid username or password"  
**Solutions:**
1. Check environment variables: `echo %ADMIN_USERNAME%` (CMD) or `echo $ADMIN_USERNAME` (bash)
2. Verify password or regenerate hash: `python admin_auth.py yourpassword`
3. Restart app after changing environment variables

### No Feedback Data
**Problem:** Admin panel shows "No feedback submissions yet"  
**Solution:** Submit feedback from main dashboard first
1. Go to `http://localhost:5000`
2. Scan any URL
3. Click "False Positive" or "False Negative" button
4. Check admin panel again

### Blocklist Refresh Fails
**Problem:** "Error refreshing blocklist"  
**Solutions:**
1. Check internet connection (needs access to openphish.com and urlhaus.abuse.ch)
2. Check logs: `tail -f data/phishinghunter.log` (Linux) or view file in editor (Windows)
3. Verify no firewall blocking HTTPS

### ML Retrain Fails
**Problem:** "ML module not available"  
**Solution:** This is expected if Phase 4 isn't implemented
- Implement Phase 4 (ML classifier) first
- Files needed: `ml/train.py`, `ml/infer.py`, `ml/retrain.py`

---

## 📝 Default Credentials (Change These!)

**Development:**
- Username: `admin`
- Password: `changeme`

**Production:**
- Generate secure password hash: `python admin_auth.py YourSecurePassword123!`
- Set `ADMIN_PASSWORD_HASH` environment variable
- **DO NOT** use default credentials in production!

---

## 🔗 Quick Links

- **Main Dashboard:** http://localhost:5000
- **Admin Login:** http://localhost:5000/admin/login
- **Admin Dashboard:** http://localhost:5000/admin
- **Feedback Analysis:** http://localhost:5000/admin/feedback
- **Logout:** http://localhost:5000/admin/logout

---

## 📚 More Documentation

- **Full Phase 9 Docs:** `PHASE_9_COMPLETE.md`
- **Deployment Guide:** `DEPLOYMENT.md`
- **Main README:** `README.md`
- **Project Overview:** `PROJECT_COMPLETE.md`

---

## 🎓 Tips

1. **Regular Review:** Check feedback weekly to identify patterns
2. **Signal Tuning:** Use false positive analysis to fine-tune weights
3. **User Education:** If many false positives, educate users or reduce sensitivity
4. **Data Collection:** More feedback = better ML training (Phase 4)
5. **Security:** Always use `ADMIN_PASSWORD_HASH` in production, never `ADMIN_PASSWORD`

---

**Need Help?** Check `PHASE_9_COMPLETE.md` for comprehensive documentation.
