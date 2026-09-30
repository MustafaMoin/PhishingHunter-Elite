"""
Database Cleanup Script for PhishingHunter Elite
Quick script to clear test data from database
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check which database is in use
MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_URL = os.getenv("DATABASE_URL")

if MONGODB_URI:
    import database_mongodb as database
    print("[INFO] Using MongoDB database")
elif DATABASE_URL and DATABASE_URL.startswith("postgresql"):
    import database_postgres as database
    print("[INFO] Using PostgreSQL database")
else:
    import database
    print("[INFO] Using SQLite database")


def show_database_info():
    """Display current database statistics"""
    print("\n" + "="*60)
    print("  📊 DATABASE INFORMATION")
    print("="*60)
    
    info = database.get_database_size_info()
    
    print(f"\n  Scans:           {info['scans']:,} records")
    print(f"  Cache:           {info['cache']:,} entries")
    print(f"  Blocklist:       {info['blocklist']:,} URLs")
    print(f"  Feedback:        {info['feedback']:,} records")
    print(f"  Rate Limits:     {info['rate_limit']:,} records")
    print(f"  Blocked IPs:     {info['blocked_ips']:,} IPs")
    
    print("\n" + "="*60)


def clear_scans():
    """Clear all scan history"""
    print("\n⚠️  WARNING: This will delete ALL scan history!")
    confirm = input("Type 'yes' to confirm: ").lower().strip()
    
    if confirm == 'yes':
        count = database.clear_all_scans()
        print(f"✅ Deleted {count} scan records")
    else:
        print("❌ Cancelled")


def clear_cache():
    """Clear scan cache"""
    count = database.clear_scan_cache()
    print(f"✅ Cleared {count} cache entries")


def clear_feedback():
    """Clear all feedback"""
    print("\n⚠️  WARNING: This will delete ALL user feedback!")
    confirm = input("Type 'yes' to confirm: ").lower().strip()
    
    if confirm == 'yes':
        count = database.clear_all_feedback()
        print(f"✅ Deleted {count} feedback records")
    else:
        print("❌ Cancelled")


def main_menu():
    """Main cleanup menu"""
    while True:
        print("\n" + "="*60)
        print("  🗑️  DATABASE CLEANUP TOOL")
        print("="*60)
        print("\n  1. Show Database Info")
        print("  2. Clear All Scans (Test Data)")
        print("  3. Clear Cache")
        print("  4. Clear Feedback")
        print("  5. Clear Everything (Scans + Cache + Feedback)")
        print("  0. Exit")
        print("\n" + "="*60)
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '1':
            show_database_info()
        
        elif choice == '2':
            clear_scans()
            show_database_info()
        
        elif choice == '3':
            clear_cache()
            show_database_info()
        
        elif choice == '4':
            clear_feedback()
            show_database_info()
        
        elif choice == '5':
            print("\n⚠️  WARNING: This will delete ALL data (scans, cache, feedback)!")
            print("⚠️  Blocklist will NOT be affected")
            confirm = input("\nType 'DELETE EVERYTHING' to confirm: ").strip()
            
            if confirm == 'DELETE EVERYTHING':
                scans = database.clear_all_scans()
                cache = database.clear_scan_cache()
                feedback = database.clear_all_feedback()
                print(f"\n✅ Deleted:")
                print(f"   - {scans} scan records")
                print(f"   - {cache} cache entries")
                print(f"   - {feedback} feedback records")
                show_database_info()
            else:
                print("❌ Cancelled")
        
        elif choice == '0':
            print("\n👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid option")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  PhishingHunter Elite - Database Cleanup Tool")
    print("  ⚠️  USE WITH CAUTION - DELETES DATA PERMANENTLY")
    print("="*60)
    
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
