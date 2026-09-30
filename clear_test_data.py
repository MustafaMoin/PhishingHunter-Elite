"""
Quick script to clear test scan data
Keeps blocklist intact
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Check which database
MONGODB_URI = os.getenv("MONGODB_URI")
if MONGODB_URI:
    import database_mongodb as database
    print("[INFO] Using MongoDB database")
else:
    import database
    print("[INFO] Using SQLite database")

print("\n🗑️  Clearing test scan data...")
print("=" * 60)

# Clear scans
scans_deleted = database.clear_all_scans()
print(f"✅ Deleted {scans_deleted} scan records")

# Clear cache
cache_deleted = database.clear_scan_cache()
print(f"✅ Cleared {cache_deleted} cache entries")

# Clear feedback
feedback_deleted = database.clear_all_feedback()
print(f"✅ Deleted {feedback_deleted} feedback records")

# Show final stats
print("\n📊 Current Database Stats:")
print("=" * 60)
info = database.get_database_size_info()
print(f"Scans: {info['scans']}")
print(f"Blocklist: {info['blocklist']} (kept intact ✅)")
print(f"Cache: {info['cache']}")
print(f"Feedback: {info['feedback']}")

print("\n✅ Test data cleared! Stats are now 0!")
print("🔒 Blocklist preserved: {:,} URLs\n".format(info['blocklist']))
