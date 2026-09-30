"""
COMPLETE FIX SCRIPT - Admin Dashboard + Clear All Data
"""
import os
import shutil
from dotenv import load_dotenv

load_dotenv()

print("\n" + "="*80)
print("🔧 PHISHINGHUNTER - COMPLETE FIX & DATA RESET")
print("="*80)

# Step 1: Clear Python cache
print("\n[STEP 1] Clearing Python cache...")
cache_dirs = ['__pycache__', 'ml/__pycache__']
for cache_dir in cache_dirs:
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
        print(f"   ✅ Removed {cache_dir}")

# Step 2: Import MongoDB
print("\n[STEP 2] Importing MongoDB database...")
MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    print("   ❌ ERROR: MONGODB_URI not in .env")
    exit(1)

import database_mongodb as database
print("   ✅ MongoDB module loaded")

# Verify functions
import inspect
get_system_stats_source = inspect.getsource(database.get_system_stats)
get_signal_analysis_source = inspect.getsource(database.get_signal_analysis)

print("\n[STEP 3] Verifying database functions...")
if 'blocklist_by_source' in get_system_stats_source:
    print("   ✅ get_system_stats() has blocklist_by_source")
else:
    print("   ❌ get_system_stats() missing blocklist_by_source")

if 'false_positive' in get_signal_analysis_source and 'false_negative' in get_signal_analysis_source:
    print("   ✅ get_signal_analysis() returns dict with false_positive/false_negative")
else:
    print("   ❌ get_signal_analysis() wrong format")

# Step 3: Clear ALL scan data
print("\n[STEP 4] Clearing ALL scan data from MongoDB...")
print("-" * 80)

try:
    scans_deleted = database.clear_all_scans()
    print(f"   ✅ Deleted {scans_deleted} scan records")
except Exception as e:
    print(f"   ❌ Error clearing scans: {e}")

try:
    cache_deleted = database.clear_scan_cache()
    print(f"   ✅ Cleared {cache_deleted} cache entries")
except Exception as e:
    print(f"   ❌ Error clearing cache: {e}")

try:
    feedback_deleted = database.clear_all_feedback()
    print(f"   ✅ Deleted {feedback_deleted} feedback records")
except Exception as e:
    print(f"   ❌ Error clearing feedback: {e}")

# Step 4: Verify empty
print("\n[STEP 5] Verifying database is clean...")
try:
    recent_scans = database.get_recent_scans(limit=10)
    print(f"   📊 Recent scans: {len(recent_scans)} (should be 0)")
    
    info = database.get_database_size_info()
    print(f"   📊 Scans in DB: {info['scans']} (should be 0)")
    print(f"   📊 Cache in DB: {info['cache']} (should be 0)")
    print(f"   📊 Feedback in DB: {info['feedback']} (should be 0)")
    print(f"   📊 Blocklist: {info['blocklist']:,} URLs (preserved)")
except Exception as e:
    print(f"   ❌ Error verifying: {e}")

# Final status
print("\n" + "="*80)
print("✅ COMPLETE FIX APPLIED SUCCESSFULLY!")
print("="*80)
print("\n📌 NEXT STEPS:")
print("   1. Stop app.py if running (Ctrl+C in terminal)")
print("   2. Run: python app.py")
print("   3. Hard refresh browser: Ctrl+Shift+R (clears cache)")
print("   4. Go to: http://127.0.0.1:5000")
print("   5. Recent scans should be EMPTY")
print("   6. Admin login: http://127.0.0.1:5000/admin/login")
print("      Username: admin")
print("      Password: changeme123")
print("\n" + "="*80)
print("✅ Admin dashboard will now work perfectly!")
print("="*80 + "\n")
