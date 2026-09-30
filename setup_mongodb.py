"""
MongoDB Atlas Setup & Migration Tool for PhishingHunter
This script helps you:
1. Test MongoDB connection
2. Initialize database structure
3. Migrate data from SQLite to MongoDB (optional)
4. Verify everything is working
"""

import os
import sys
import time
from datetime import datetime

def test_mongodb_connection():
    """Test MongoDB connection"""
    print("\n🔍 Testing MongoDB Connection...")
    print("-" * 60)
    
    mongodb_uri = os.getenv("MONGODB_URI")
    
    if not mongodb_uri:
        print("❌ ERROR: MONGODB_URI not set in environment!")
        print("\n📝 Please create .env file with:")
        print("   MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/phishinghunter")
        print("\n📖 See MONGODB_ATLAS_SETUP.md for detailed instructions")
        return False
    
    try:
        import database_mongodb as db
        print("✅ database_mongodb.py imported successfully")
        
        # Test connection
        database = db.get_db()
        print(f"✅ Connected to MongoDB!")
        print(f"   Database: {db.DB_NAME}")
        
        # Initialize database
        db.init_db()
        print("✅ Database collections initialized")
        
        # Test write operation
        test_result = {
            "url": "https://test.example.com",
            "domain": "test.example.com",
            "score": 0,
            "risk": "SAFE",
            "offline": False,
            "blocklist_hit": False,
            "scan_time_ms": 100
        }
        scan_id = db.save_scan(test_result, ip_hash="test")
        print(f"✅ Test scan saved (ID: {scan_id})")
        
        # Test read operation
        stats = db.get_stats()
        print(f"✅ Database stats retrieved: {stats}")
        
        print("\n🎉 MongoDB connection successful!")
        print("=" * 60)
        return True
        
    except ImportError as e:
        print(f"❌ ERROR: Missing dependencies")
        print(f"   {e}")
        print("\n📦 Run: pip install pymongo dnspython")
        return False
        
    except Exception as e:
        print(f"❌ ERROR: Connection failed")
        print(f"   {e}")
        print("\n🔧 Troubleshooting:")
        print("   1. Check MONGODB_URI is correct")
        print("   2. Check username/password")
        print("   3. Check IP is whitelisted in MongoDB Atlas")
        print("   4. Check internet connection")
        print("\n📖 See MONGODB_ATLAS_SETUP.md for help")
        return False


def migrate_sqlite_to_mongodb():
    """Migrate existing SQLite data to MongoDB"""
    print("\n📦 SQLite to MongoDB Migration")
    print("-" * 60)
    
    # Check if SQLite database exists
    sqlite_path = "data/phishinghunter.db"
    if not os.path.exists(sqlite_path):
        print("ℹ️  No SQLite database found - skipping migration")
        return True
    
    print(f"📂 Found SQLite database: {sqlite_path}")
    
    response = input("\n⚠️  Migrate existing SQLite data to MongoDB? (yes/no): ").lower().strip()
    if response not in ['yes', 'y']:
        print("⏭️  Skipping migration")
        return True
    
    try:
        import database as sqlite_db
        import database_mongodb as mongo_db
        
        print("\n🔄 Starting migration...")
        
        # Migrate blocklist
        print("\n📋 Migrating blocklist...")
        blocklist_count = sqlite_db.blocklist_size()
        print(f"   Found {blocklist_count} blocklist entries")
        
        if blocklist_count > 0:
            # Get all blocklist entries
            conn = sqlite_db.get_conn()
            cursor = conn.execute("SELECT url, source FROM blocklist")
            entries = cursor.fetchall()
            
            for i, row in enumerate(entries):
                mongo_db.add_blocklist_entry(row['url'], row['source'])
                if (i + 1) % 1000 == 0:
                    print(f"   Migrated {i + 1}/{blocklist_count} entries...")
            
            print(f"✅ Migrated {blocklist_count} blocklist entries")
        
        # Migrate scans (last 1000 only to save space)
        print("\n📊 Migrating recent scans (last 1000)...")
        recent_scans = sqlite_db.get_recent_scans(limit=1000)
        
        if recent_scans:
            for scan in recent_scans:
                # Reconstruct scan result
                result = {
                    "url": scan.get("url"),
                    "final_url": scan.get("final_url"),
                    "domain": scan.get("domain"),
                    "score": scan.get("score"),
                    "risk": scan.get("risk"),
                    "offline": bool(scan.get("offline")),
                    "blocklist_hit": bool(scan.get("blocklist_hit")),
                    "domain_age_days": scan.get("domain_age_days"),
                    "redirect_count": scan.get("redirect_count"),
                    "signals": [],
                    "scan_time_ms": scan.get("scan_time_ms")
                }
                mongo_db.save_scan(result, ip_hash=scan.get("ip_hash", ""))
            
            print(f"✅ Migrated {len(recent_scans)} scans")
        
        # Migrate feedback
        print("\n💬 Migrating feedback...")
        feedback_list = sqlite_db.get_all_feedback(limit=1000)
        
        if feedback_list:
            for fb in feedback_list:
                mongo_db.save_feedback(
                    scan_id=str(fb.get("scan_id", "")),
                    url=fb.get("url", ""),
                    feedback_type=fb.get("feedback_type", ""),
                    comment=fb.get("comment", "")
                )
            
            print(f"✅ Migrated {len(feedback_list)} feedback entries")
        
        print("\n🎉 Migration completed successfully!")
        print("\n📝 Note: Old SQLite data is still in data/phishinghunter.db")
        print("   You can keep it as backup or delete it later")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR during migration: {e}")
        print("⚠️  Some data may not have been migrated")
        return False


def verify_setup():
    """Verify complete setup"""
    print("\n✅ Final Verification")
    print("-" * 60)
    
    try:
        import database_mongodb as db
        
        stats = db.get_stats()
        blocklist = db.blocklist_size()
        system_stats = db.get_system_stats()
        
        print(f"📊 Database Statistics:")
        print(f"   Total Scans: {stats.get('hunts', 0)}")
        print(f"   Threats Detected: {stats.get('threats', 0)}")
        print(f"   Blocklist Size: {blocklist}")
        print(f"   Cache Entries: {system_stats.get('cache_size', 0)}")
        print(f"   Feedback Count: {system_stats.get('feedback_count', 0)}")
        
        print("\n✅ All systems operational!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def main():
    """Main setup routine"""
    print("=" * 60)
    print("  🍃 MongoDB Atlas Setup for PhishingHunter Elite v2")
    print("=" * 60)
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Environment variables loaded from .env")
    except ImportError:
        print("ℹ️  python-dotenv not installed (optional)")
    
    # Step 1: Test connection
    if not test_mongodb_connection():
        print("\n❌ Setup failed - fix connection issues first")
        print("📖 Read MONGODB_ATLAS_SETUP.md for detailed instructions")
        sys.exit(1)
    
    # Step 2: Migrate data (optional)
    migrate_sqlite_to_mongodb()
    
    # Step 3: Verify
    verify_setup()
    
    # Final message
    print("\n" + "=" * 60)
    print("  🎉 SETUP COMPLETE!")
    print("=" * 60)
    print("\n✅ MongoDB Atlas is ready!")
    print("✅ PhishingHunter will now use cloud database")
    print("\n📝 Next Steps:")
    print("   1. Start PhishingHunter: python app.py")
    print("   2. Look for: [INFO] Using MongoDB cloud database")
    print("   3. Test by scanning a URL")
    print("   4. Check MongoDB Atlas dashboard to see data")
    print("\n🔑 Optional: Add API keys to .env for better detection:")
    print("   - GOOGLE_SAFE_BROWSING_API_KEY")
    print("   - VIRUSTOTAL_API_KEY")
    print("\n📖 Documentation: MONGODB_ATLAS_SETUP.md")
    print("=" * 60)


if __name__ == "__main__":
    main()
