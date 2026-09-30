# MongoDB Atlas Setup Guide for PhishingHunter Elite v2

This guide will help you set up MongoDB Atlas cloud database so your PhishingHunter data is stored in the cloud, not on your local PC.

## 🎯 Why MongoDB Atlas?

- ✅ **Cloud Storage**: Your data is stored on MongoDB's secure cloud servers, not your PC
- ✅ **Free Tier**: 512MB storage free forever (perfect for PhishingHunter)
- ✅ **Automatic Backups**: MongoDB handles backups automatically
- ✅ **Global Access**: Access your data from anywhere
- ✅ **Scalable**: Easy to upgrade as your needs grow

---

## 📋 Step-by-Step Setup

### Step 1: Create MongoDB Atlas Account

1. Go to **MongoDB Atlas**: https://www.mongodb.com/cloud/atlas/register
2. Sign up with:
   - Email address
   - Or use Google/GitHub login (fastest)
3. Verify your email if required

### Step 2: Create a Free Cluster

1. After login, click **"Create"** or **"Build a Database"**
2. Choose **FREE tier** (M0 Sandbox):
   - ✅ 512 MB Storage
   - ✅ Shared RAM
   - ✅ No credit card required
3. Select **Cloud Provider & Region**:
   - Provider: AWS, Google Cloud, or Azure (any is fine)
   - Region: Choose closest to your location for best performance
4. **Cluster Name**: Leave default or name it `phishinghunter`
5. Click **"Create Cluster"** (takes 1-3 minutes)

### Step 3: Create Database User

1. In the **Security** section, click **"Database Access"**
2. Click **"Add New Database User"**
3. Choose **"Password"** authentication
4. Enter credentials:
   - **Username**: `phishuser` (or your choice)
   - **Password**: Generate a strong password or create your own
   - ⚠️ **SAVE THIS PASSWORD** - you'll need it in Step 5
5. **Database User Privileges**: Choose **"Read and write to any database"**
6. Click **"Add User"**

### Step 4: Configure Network Access

1. In the **Security** section, click **"Network Access"**
2. Click **"Add IP Address"**
3. Choose one option:
   - **Option A (Recommended for Development)**: Click **"Allow Access from Anywhere"**
     - IP: `0.0.0.0/0`
     - This allows access from any location
   - **Option B (Production)**: Click **"Add Current IP Address"**
     - Adds only your current IP (more secure)
     - You'll need to add new IPs when connecting from different locations
4. Click **"Confirm"**

### Step 5: Get Your Connection String

1. Go back to **"Database"** (main dashboard)
2. Click **"Connect"** button on your cluster
3. Choose **"Connect your application"**
4. Select:
   - **Driver**: Python
   - **Version**: 3.12 or later
5. **Copy the connection string** - it looks like:
   ```
   mongodb+srv://phishuser:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
6. **Important**: Replace `<password>` with your actual password from Step 3
7. **Important**: Add your database name at the end:
   ```
   mongodb+srv://phishuser:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/phishinghunter?retryWrites=true&w=majority
   ```

### Step 6: Configure PhishingHunter

1. In your PhishingHunter folder, create a file named `.env`:
   ```bash
   # On Windows PowerShell:
   New-Item .env -ItemType File
   ```

2. Open `.env` file and add your MongoDB connection string:
   ```env
   MONGODB_URI=mongodb+srv://phishuser:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/phishinghunter?retryWrites=true&w=majority
   MONGODB_DB_NAME=phishinghunter
   ```

3. Replace:
   - `YOUR_PASSWORD` with your actual database user password
   - `cluster0.xxxxx.mongodb.net` with your actual cluster address
   - `phishinghunter` is your database name (you can change it)

### Step 7: Test the Connection

1. Make sure your virtual environment is activated:
   ```bash
   .\venv\Scripts\Activate.ps1
   ```

2. Run PhishingHunter:
   ```bash
   python app.py
   ```

3. You should see:
   ```
   [INFO] Using MongoDB cloud database
   * Running on http://127.0.0.1:5000
   ```

4. Open your browser and test: http://127.0.0.1:5000

### Step 8: Verify Data in MongoDB Atlas

1. Go to your MongoDB Atlas dashboard
2. Click **"Browse Collections"** on your cluster
3. You should see the `phishinghunter` database
4. Inside, you'll see collections like:
   - `scans` - All URL scans
   - `blocklist` - Blocked URLs
   - `feedback` - User feedback
   - And more!

---

## 🔍 Collections Structure

Your PhishingHunter MongoDB database has these collections:

| Collection | Purpose |
|------------|---------|
| `scans` | All URL scan results with risk scores |
| `scan_cache` | Cached scan results (10 min TTL) |
| `blocklist` | Known phishing URLs database |
| `feedback` | User feedback (false positives/negatives) |
| `rate_limit` | API rate limiting data |
| `signal_weights` | ML signal weight configuration |
| `blocked_ips` | Blocked IP addresses |

---

## ⚡ Quick Reference

### Connection String Format
```
mongodb+srv://username:password@cluster.mongodb.net/database_name?options
```

### Environment Variables
```env
# Required
MONGODB_URI=your_connection_string_here

# Optional (defaults to "phishinghunter")
MONGODB_DB_NAME=phishinghunter
```

### Database Priority
When you start PhishingHunter, it checks in this order:
1. **MongoDB Atlas** (if `MONGODB_URI` is set) ⭐
2. **PostgreSQL** (if `DATABASE_URL` is set)
3. **SQLite** (local file fallback)

---

## 🚀 Migration from SQLite (Optional)

If you have existing data in SQLite and want to move it to MongoDB:

### Option 1: Fresh Start (Recommended)
Just start using MongoDB - your old SQLite data stays in `data/phishinghunter.db` but new data goes to MongoDB.

### Option 2: Manual Migration
If you need to migrate existing data, I can create a migration script. Let me know!

---

## 🔧 Troubleshooting

### Issue: "ServerSelectionTimeoutError"
**Solution**: Check:
- ✅ Connection string is correct
- ✅ Password has no special characters or is URL-encoded
- ✅ IP address is whitelisted in Network Access
- ✅ Internet connection is working

### Issue: "Authentication failed"
**Solution**: 
- ✅ Verify username/password in connection string
- ✅ Check Database User was created correctly
- ✅ Password should not have `<` or `>` brackets

### Issue: "Database name not found"
**Solution**: 
- ✅ MongoDB auto-creates databases on first write
- ✅ Try scanning a URL, then check MongoDB Atlas dashboard
- ✅ Database appears after first data insert

### Issue: Special characters in password
**Solution**: URL-encode special characters:
```
@ → %40
: → %3A
/ → %2F
? → %3F
# → %23
```

Example: If password is `P@ss:word#123`
Use: `P%40ss%3Aword%23123`

---

## 📊 Free Tier Limits

MongoDB Atlas Free Tier (M0):
- ✅ **Storage**: 512 MB (enough for ~100,000+ scans)
- ✅ **RAM**: Shared
- ✅ **Connections**: 500 concurrent
- ✅ **Backups**: Not included (upgrade for backups)
- ✅ **Bandwidth**: Unlimited
- ✅ **Duration**: Forever free! 🎉

---

## 🎓 Additional Resources

- **MongoDB Atlas Docs**: https://docs.atlas.mongodb.com/
- **Connection String Guide**: https://docs.mongodb.com/manual/reference/connection-string/
- **MongoDB Python Driver**: https://pymongo.readthedocs.io/
- **Get Support**: https://support.mongodb.com/

---

## ✅ Setup Complete!

Once you see `[INFO] Using MongoDB cloud database` when starting PhishingHunter:

🎉 **Congratulations!** Your data is now stored in the cloud, not on your PC!

### What's Different?
- ✅ All scans saved to MongoDB Atlas
- ✅ Blocklist stored in cloud
- ✅ Admin panel data in cloud
- ✅ Feedback and stats in cloud
- ✅ Access from anywhere
- ✅ Automatic scaling

### What to Do Next?
1. Scan some URLs to test
2. Check MongoDB Atlas dashboard to see data
3. Share your PhishingHunter with others
4. Consider upgrading to paid tier for backups (optional)

---

## 💡 Tips

1. **Save Your Connection String**: Store it securely, don't share it publicly
2. **Monitor Usage**: Check your MongoDB Atlas dashboard regularly
3. **Upgrade Later**: When you need more storage, easily upgrade to paid tier
4. **Multiple Environments**: Create separate clusters for development/production
5. **Connection Pooling**: PyMongo handles this automatically

---

## 🆘 Need Help?

If you encounter any issues:

1. Check the troubleshooting section above
2. Verify all steps were completed
3. Check MongoDB Atlas status page
4. Contact me for assistance

---

**Happy Phishing Hunting! 🎯🔒**
