# 🚀 Quick Start: MongoDB Atlas Setup (5 Minutes)

Follow these simple steps to get your PhishingHunter running on cloud database!

---

## Step 1: Create MongoDB Atlas Account (2 minutes)

1. Go to: **https://www.mongodb.com/cloud/atlas/register**
2. Sign up with **Google/GitHub** (fastest) or email
3. Click **"Create"** → Choose **FREE** (M0 Sandbox)
4. Select any region close to you
5. Click **"Create Cluster"** (wait 1-2 minutes)

---

## Step 2: Setup Database Access (1 minute)

1. Click **"Database Access"** (left menu)
2. Click **"Add New Database User"**
3. Username: `phishuser` (or anything you want)
4. Password: **Generate** or create your own
5. ⚠️ **SAVE THIS PASSWORD!**
6. Click **"Add User"**

---

## Step 3: Allow Network Access (30 seconds)

1. Click **"Network Access"** (left menu)
2. Click **"Add IP Address"**
3. Click **"Allow Access from Anywhere"** (0.0.0.0/0)
4. Click **"Confirm"**

---

## Step 4: Get Connection String (1 minute)

1. Click **"Database"** (left menu)
2. Click **"Connect"** button
3. Choose **"Connect your application"**
4. **Copy** the connection string (looks like):
   ```
   mongodb+srv://phishuser:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
5. Replace `<password>` with your actual password from Step 2
6. Add database name at end:
   ```
   mongodb+srv://phishuser:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/phishinghunter?retryWrites=true&w=majority
   ```

---

## Step 5: Configure PhishingHunter (30 seconds)

1. Open your PhishingHunter folder in terminal:
   ```bash
   cd d:\PhishingHunter_v2
   ```

2. Create `.env` file:
   ```bash
   New-Item .env -ItemType File
   ```

3. Open `.env` in notepad and paste:
   ```env
   MONGODB_URI=mongodb+srv://phishuser:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/phishinghunter?retryWrites=true&w=majority
   ```

4. Replace with your actual connection string from Step 4

5. Save and close

---

## Step 6: Test Connection (30 seconds)

1. Activate virtual environment:
   ```bash
   .\venv\Scripts\Activate.ps1
   ```

2. Run setup script:
   ```bash
   python setup_mongodb.py
   ```

3. You should see:
   ```
   ✅ Connected to MongoDB!
   ✅ Database collections initialized
   ✅ Test scan saved
   🎉 MongoDB connection successful!
   ```

---

## Step 7: Start PhishingHunter! 🎉

```bash
python app.py
```

Look for:
```
[INFO] Using MongoDB cloud database
* Running on http://127.0.0.1:5000
```

Open browser: **http://127.0.0.1:5000**

---

## ✅ Done! Your data is now in the cloud! 🎉

### What's different?
- ✅ All scans save to MongoDB Atlas (cloud)
- ✅ No data on your PC
- ✅ Access from anywhere
- ✅ 512MB free storage
- ✅ Automatic backups

### View your data:
1. Go to MongoDB Atlas dashboard
2. Click **"Browse Collections"**
3. See your PhishingHunter data!

---

## 🔑 Optional: Add API Keys (Recommended)

Add these to your `.env` file for better phishing detection:

```env
# Google Safe Browsing (Free)
GOOGLE_SAFE_BROWSING_API_KEY=your_key_here

# VirusTotal (Free)
VIRUSTOTAL_API_KEY=your_key_here
```

**Where to get API keys?**
- Google Safe Browsing: https://console.cloud.google.com/apis/credentials
- VirusTotal: https://www.virustotal.com/gui/join-us

---

## 🆘 Having Issues?

### Connection Error?
```bash
python setup_mongodb.py
```
This will show you what's wrong!

### Need detailed help?
Open **MONGODB_ATLAS_SETUP.md** for complete troubleshooting guide.

---

## 🎯 Summary

```
✅ Step 1: Create MongoDB Atlas account (free)
✅ Step 2: Create database user (username + password)
✅ Step 3: Allow network access (0.0.0.0/0)
✅ Step 4: Copy connection string
✅ Step 5: Create .env file with MONGODB_URI
✅ Step 6: Run python setup_mongodb.py
✅ Step 7: Run python app.py
```

**Total time: 5-10 minutes!** ⚡

---

**Happy Phishing Hunting with Cloud Database! 🎉🔒**
