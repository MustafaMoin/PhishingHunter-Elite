"""
Complete fix script:
1. Clear Python cache
2. Clear test data
3. Verify database_mongodb updates loaded
"""
import os
import shutil
from dotenv import load_dotenv

load_dotenv()

print("\n🔧 PHISHINGHUNTER - COMPLETE FIX SCRIPT")
print("=" * 70)

# Step 1: Clear Python cache
print("\n[1/3] Clearing Python cache...")
cache_dirs = ['__pycache__', 'ml/__pycache__']
for cache_dir in cache_dirs:
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
        print(f"   ✅ Removed {cache_dir}")

# Step 2: Import fresh database
print("\n[2/3] Loading MongoDB database module...")
MONGODB_URI = os.getenv("MONGODB_URI")
if MONGODB_URI:
    import database_mongodb as database
    print("   ✅ Using MongoDB cloud database")
    
    # Verify get_system_stats has blocklist_by_source
    import inspect
    source = inspect.getsource(database.get_system_stats)
    if 'blocklist_by_source' in source:
        print("   ✅ Updated get_system_stats() loaded with blocklist_by_source")
    else:
        print("   ❌ WARNING: get_system_stats() still old version!")
        print("   📌 Solution: Manually restart VS Code or Python process")
else:
    print("   ❌ ERROR: MONGODB_URI not found in .env")
    exit(1)

# Step 3: Clear test data
print("\n[3/3] Clearing test scan data...")
print("-" * 70)

# Clear scans
scans_deleted = database.clear_all_scans()
print(f"   ✅ Deleted {scans_deleted} scan records")

# Clear cache
cache_deleted = database.clear_scan_cache()
print(f"   ✅ Cleared {cache_deleted} cache entries")

# Clear feedback
feedback_deleted = database.clear_all_feedback()
print(f"   ✅ Deleted {feedback_deleted} feedback records")

# Show final stats
print("\n" + "=" * 70)
print("📊 FINAL DATABASE STATUS")
print("=" * 70)
info = database.get_database_size_info()
print(f"   Scans:     {info['scans']:>10,} (should be 0)")
print(f"   Blocklist: {info['blocklist']:>10,} URLs (preserved)")
print(f"   Cache:     {info['cache']:>10,} (should be 0)")
print(f"   Feedback:  {info['feedback']:>10,} (should be 0)")

print("\n" + "=" * 70)
print("✅ FIX COMPLETE!")
print("=" * 70)
print("\n📌 NEXT STEPS:")
print("   1. Close any running app.py process (Ctrl+C)")
print("   2. Run: python app.py")
print("   3. Go to: http://127.0.0.1:5000/admin/login")
print("   4. Login: admin / changeme123")
print("\n")
