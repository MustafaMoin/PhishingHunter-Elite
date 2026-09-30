# ⚡ QUICK DEPLOYMENT COMMANDS
## Copy-Paste Ready Commands for GitHub → Render

---

## 🔥 PART 1: GITHUB PUSH (5 Minutes)

### Open PowerShell in Project Folder:
```powershell
cd d:\PhishingHunter_v2
```

### Initialize Git & Commit:
```powershell
git init
git add .
git commit -m "Initial commit: PhishingHunter Elite v2.0"
```

### Add GitHub Remote (Replace YOUR_USERNAME):
```powershell
git remote add origin https://github.com/YOUR_USERNAME/PhishingHunter-Elite.git
git branch -M main
git push -u origin main
```

**Enter credentials when asked:**
- Username: your_github_username  
- Password: your_github_token

---

## 🚀 PART 2: RENDER.COM SETUP

### 1. Go to Render Dashboard:
```
https://dashboard.render.com
```

### 2. Create New Web Service:
- Click: **New +** → **Web Service**
- Connect GitHub repository: `PhishingHunter-Elite`

### 3. Build Settings:
```
Name:          phishinghunter-elite
Region:        Singapore
Branch:        main
Runtime:       Python 3
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
Instance Type: Free
```

### 4. Environment Variables (Add These):
```
MONGODB_URI = mongodb+srv://mustafamoin061_db_user:xPuZ76X60ff8fMuA@cluster0.vjg3z4l.mongodb.net

MONGODB_DB_NAME = phishinghunter

ADMIN_USERNAME = admin

ADMIN_PASSWORD = changeme123

PHISHINGHUNTER_SECRET = your-random-secret-key-change-this

FLASK_ENV = production

PYTHON_VERSION = 3.11.0
```

### 5. Click: **Create Web Service**

---

## ✅ DONE!

**Wait 3-5 minutes for build to complete.**

**Your Live URL:**
```
https://phishinghunter-elite.onrender.com
```

**Admin Panel:**
```
https://phishinghunter-elite.onrender.com/admin/login
Username: admin
Password: changeme123
```

---

## 🔄 FUTURE UPDATES (Simple!)

### Make Changes & Push:
```powershell
git add .
git commit -m "Your update message"
git push origin main
```

**Render auto-deploys in 2-3 minutes!** ✅

---

**That's it! Simple hai!** 🚀
