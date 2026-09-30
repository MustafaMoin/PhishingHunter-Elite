# 🚀 PhishingHunter - MongoDB Setup Steps (Urdu/Roman Urdu)

## ✅ Kya Ho Chuka Hai
Maine tumhare liye **sab kuch code** kar diya hai! Sirf **2 cheezein** tumhe karni hain.

---

## 📝 Step 1: MongoDB Atlas Account Banao (5 minutes)

### 1.1 Account Banao
1. Is link pe jao: **https://www.mongodb.com/cloud/atlas/register**
2. Sign up karo (Google ya GitHub se login karo - sabse fast!)
3. Email verify karo agar required ho

### 1.2 Free Cluster Banao
1. Login ke baad **"Create"** ya **"Build a Database"** pe click karo
2. **FREE** tier select karo (M0 Sandbox):
   - ✅ 512 MB Storage
   - ✅ Forever FREE
   - ✅ No credit card required
3. **Cloud Provider**: Koi bhi select karo (AWS/Google/Azure)
4. **Region**: Apne country ke paas wala select karo (fast rahega)
5. **Cluster Name**: `phishinghunter` ya kuch bhi rakh sakte ho
6. **"Create Cluster"** pe click karo
7. Wait karo 1-2 minutes (cluster ban raha hai)

### 1.3 Database User Banao
1. Left menu se **"Database Access"** pe click karo
2. **"Add New Database User"** pe click karo
3. **Username** daalo: `phishuser` (ya jo chahe)
4. **Password**: Strong password banao ya auto-generate karo
5. ⚠️ **YE PASSWORD KAHIN LIKH LO!** Zaroori hai!
6. **User Privileges**: **"Read and write to any database"** select karo
7. **"Add User"** pe click karo

### 1.4 Network Access Allow Karo
1. Left menu se **"Network Access"** pe click karo
2. **"Add IP Address"** pe click karo
3. **"Allow Access from Anywhere"** pe click karo
   - Automatically `0.0.0.0/0` add ho jayega
   - Ye har jagah se access allow karega
4. **"Confirm"** pe click karo

### 1.5 Connection String Copy Karo
1. Left menu se **"Database"** pe click karo (main dashboard)
2. Apne cluster pe **"Connect"** button pe click karo
3. **"Connect your application"** select karo
4. **Driver**: Python select karo
5. Connection string **copy** karo - aisa dikhega:
   ```
   mongodb+srv://phishuser:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
6. ⚠️ **Important Changes Karo:**
   - `<password>` ko apne actual password se replace karo (Step 1.3 wala)
   - End mein database name add karo: `/phishinghunter?`
   
   **Final string aisa hona chahiye:**
   ```
   mongodb+srv://phishuser:YourPassword123@cluster0.abc12.mongodb.net/phishinghunter?retryWrites=true&w=majority
   ```

7. ✅ **Ye complete connection string copy kar lo!**

---

## 📝 Step 2: PhishingHunter Configure Karo (2 minutes)

### 2.1 .env File Edit Karo
1. Apne project folder mein jao: `d:\PhishingHunter_v2`
2. **`.env`** file kholo (Notepad ya VS Code mein)
3. Ye line dhundo:
   ```env
   MONGODB_URI=YOUR_MONGODB_CONNECTION_STRING_HERE
   ```
4. `YOUR_MONGODB_CONNECTION_STRING_HERE` ko **delete** karo
5. Apna **connection string** paste karo (Step 1.5 se)
6. File **save** karo (Ctrl+S)

**Example:**
```env
MONGODB_URI=mongodb+srv://phishuser:MyPass123@cluster0.abc12.mongodb.net/phishinghunter?retryWrites=true&w=majority
```

### 2.2 Admin Password Change Karo (Optional)
`.env` file mein ye bhi change kar sakte ho:
```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=apna_naya_password
```

---

## 📝 Step 3: MongoDB Connection Test Karo (1 minute)

1. **PowerShell** ya **Command Prompt** kholo
2. Project folder mein jao:
   ```bash
   cd d:\PhishingHunter_v2
   ```
3. Virtual environment activate karo:
   ```bash
   .\venv\Scripts\Activate.ps1
   ```
4. Setup script chalao:
   ```bash
   python setup_mongodb.py
   ```

### ✅ Success! Agar ye dikhega:
```
✅ Connected to MongoDB!
✅ Database collections initialized
✅ Test scan saved
🎉 MongoDB connection successful!
```

### ❌ Error? Agar ye dikhe:
- Connection string check karo (password sahi hai?)
- Internet connection check karo
- MongoDB Atlas mein IP whitelist check karo

---

## 📝 Step 4: PhishingHunter Start Karo (30 seconds)

1. Terminal mein type karo:
   ```bash
   python app.py
   ```

2. ✅ **Success! Ye message dikhna chahiye:**
   ```
   [INFO] Using MongoDB cloud database
   * Running on http://127.0.0.1:5000
   ```

3. Browser kholo aur jao: **http://127.0.0.1:5000**

4. ✅ Website khul jayegi - **Cloud database se connected!** 🎉

---

## 📝 Step 5: Data Check Karo MongoDB Mein (1 minute)

1. MongoDB Atlas dashboard kholo
2. **"Browse Collections"** pe click karo
3. **`phishinghunter`** database dikhega
4. Andar ye collections honge:
   - `scans` - Tumhare scans
   - `blocklist` - Blocked URLs
   - `feedback` - User feedback
   - Aur zyada!

5. Kuch URL scan karo PhishingHunter pe
6. MongoDB dashboard refresh karo
7. ✅ Naya data dikh raha hai? **Perfect!** 🎉

---

## 📝 Step 6: API Keys Add Karo (OPTIONAL - 10 minutes)

Ye optional hai but **highly recommended** - phishing detection kaafi better ho jata hai!

### 6.1 Google Safe Browsing API Key

1. Jao: **https://console.cloud.google.com/apis/credentials**
2. Google account se login karo
3. **"Create Project"** karo (agar pehle se nahi hai)
   - Project name: `PhishingHunter`
4. Left menu se **"Library"** pe click karo
5. Search karo: **"Safe Browsing API"**
6. Click karke **"Enable"** karo
7. Left menu se **"Credentials"** pe click karo
8. **"Create Credentials"** → **"API Key"** select karo
9. API Key **copy** kar lo
10. `.env` file kholo aur paste karo:
    ```env
    GOOGLE_SAFE_BROWSING_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXX
    ```

### 6.2 VirusTotal API Key

1. Jao: **https://www.virustotal.com/gui/join-us**
2. Account banao (email se sign up)
3. Email verify karo
4. Login karo
5. Top-right corner mein apna **profile icon** pe click karo
6. **"API Key"** section mein jao
7. API Key **copy** kar lo
8. `.env` file kholo aur paste karo:
    ```env
    VIRUSTOTAL_API_KEY=1234567890abcdef1234567890abcdef
    ```

9. File **save** karo

10. PhishingHunter **restart** karo:
    ```bash
    # Terminal mein Ctrl+C press karo (stop)
    python app.py  # Phir se start karo
    ```

---

## ✅ DONE! Tumhara Setup Complete! 🎉

### ✅ Checklist:
- [x] MongoDB Atlas account bana
- [x] Cluster bana (free)
- [x] Database user bana
- [x] Connection string copy kiya
- [x] `.env` file mein paste kiya
- [x] `python setup_mongodb.py` run kiya (success!)
- [x] `python app.py` run kiya (cloud database connected!)
- [x] Browser mein test kiya (working!)
- [ ] API keys add kiye (optional but recommended)

---

## 🎯 Ab Kya?

### Tumhara PhishingHunter ab:
- ✅ Cloud database use kar raha hai (MongoDB Atlas)
- ✅ Data apke PC pe nahi, cloud mein save ho raha hai
- ✅ Kahi se bhi access kar sakte ho
- ✅ 512 MB free storage (forever!)
- ✅ Professional, production-ready!

### Test Karo:
1. Kuch URLs scan karo
2. Admin panel kholo: http://127.0.0.1:5000/admin/login
   - Username: `admin`
   - Password: (jo `.env` mein set kiya)
3. MongoDB Atlas dashboard mein data check karo
4. Feedback submit karo, stats dekho

---

## 🆘 Problems?

### ❌ "ServerSelectionTimeoutError"?
**Fix:**
- Internet connection check karo
- MongoDB Atlas mein IP whitelist check karo (0.0.0.0/0 hona chahiye)
- Connection string sahi hai?

### ❌ "Authentication failed"?
**Fix:**
- Username/password sahi hai connection string mein?
- Password mein special characters hain? URL encode karo:
  - `@` → `%40`
  - `:` → `%3A`
  - `/` → `%2F`

### ❌ "Module not found"?
**Fix:**
```bash
pip install pymongo dnspython python-dotenv
```

### ❌ Still stuck?
1. `python setup_mongodb.py` run karo - ye error batayega
2. `MONGODB_ATLAS_SETUP.md` detailed guide padho
3. Mujhse pucho!

---

## 📚 Documentation Files

- **QUICK_START_MONGODB.md** - English quick start (5 mins)
- **MONGODB_ATLAS_SETUP.md** - Detailed English guide
- **MONGODB_READY.md** - Complete checklist
- **SETUP_STEPS_URDU.md** - Ye file (Urdu guide)

---

## 🎉 Congratulations!

Tumhara **PhishingHunter Elite v2** ab fully production-ready hai with cloud database! 🚀🔒

**Data cloud mein safe hai, apke PC pe nahi!** ✅

---

**Happy Phishing Hunting! 🎯**
