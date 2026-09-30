"""Quick script to show what's in your SQLite database"""
import sqlite3

conn = sqlite3.connect('data/phishinghunter.db')
cursor = conn.cursor()

print("\n" + "="*60)
print("📂 YOUR SQLITE DATABASE CONTENTS")
print("="*60)
print(f"\n📍 File: data/phishinghunter.db")
print(f"💾 This file contains all your application data!\n")

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("🗂️  TABLES IN DATABASE:\n")
for table in tables:
    table_name = table[0]
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"  ✅ {table_name:20s} → {count:6,d} records")

print("\n" + "="*60)
print("💡 KEY POINT:")
print("="*60)
print("This SQLite database is just a FILE on your computer.")
print("No external service, no account, no API key needed!")
print("\nWhen you deploy:")
print("  → This file goes WITH your application")
print("  → Data travels with your app")
print("  → No external database server needed")
print("\nIt's like having a USB drive vs using Google Drive!")
print("="*60 + "\n")

conn.close()
