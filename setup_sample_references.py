"""
setup_sample_references.py
---------------------------
Quick setup script to add reference screenshots for commonly-spoofed brands.

This script takes screenshots of real brand login pages and stores them as
visual references for phishing detection.

WARNING: This script makes actual HTTP requests to these sites and takes
screenshots. Only run this if you have:
  1. Installed Playwright: pip install playwright imagehash Pillow
  2. Installed Chromium: playwright install chromium
  3. Good internet connection (will download pages)

Usage:
  python setup_sample_references.py
"""

import time
import visual_similarity

# List of commonly-spoofed brands with their login pages
SAMPLE_REFERENCES = [
    # Format: (brand, domain, page_type, url)
    ("paypal", "paypal.com", "login", "https://www.paypal.com/signin"),
    ("google", "google.com", "login", "https://accounts.google.com/"),
    ("microsoft", "microsoft.com", "login", "https://login.live.com/"),
    ("facebook", "facebook.com", "login", "https://www.facebook.com/login"),
    ("amazon", "amazon.com", "login", "https://www.amazon.com/ap/signin"),
    ("apple", "apple.com", "login", "https://appleid.apple.com/"),
    ("netflix", "netflix.com", "login", "https://www.netflix.com/login"),
    ("linkedin", "linkedin.com", "login", "https://www.linkedin.com/login"),
    ("instagram", "instagram.com", "login", "https://www.instagram.com/accounts/login/"),
    ("dropbox", "dropbox.com", "login", "https://www.dropbox.com/login"),
]


def main():
    if not visual_similarity.is_available():
        print("❌ Visual similarity features not available!")
        print("\nPlease install:")
        print("  1. pip install playwright imagehash Pillow")
        print("  2. playwright install chromium")
        return
    
    print("=" * 60)
    print("PhishingHunter - Setup Sample Visual References")
    print("=" * 60)
    print(f"\nThis will screenshot {len(SAMPLE_REFERENCES)} brand login pages")
    print("and store them as visual references for phishing detection.")
    print("\nThis may take 5-10 minutes depending on your internet speed.")
    print("\nPress Ctrl+C to cancel, or Enter to continue...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        return
    
    print("\n" + "=" * 60)
    successful = 0
    failed = 0
    
    for i, (brand, domain, page_type, url) in enumerate(SAMPLE_REFERENCES, 1):
        print(f"\n[{i}/{len(SAMPLE_REFERENCES)}] {brand.upper()} - {url}")
        print(f"    📸 Taking screenshot...")
        
        try:
            screenshot_bytes = visual_similarity._take_screenshot(url)
            
            if not screenshot_bytes:
                print(f"    ❌ Failed to take screenshot")
                failed += 1
                continue
            
            print(f"    ✅ Screenshot captured ({len(screenshot_bytes)} bytes)")
            print(f"    💾 Adding to database...")
            
            visual_similarity.add_reference_screenshot(
                brand=brand,
                domain=domain,
                page_type=page_type,
                screenshot_bytes=screenshot_bytes,
            )
            
            print(f"    ✅ Reference added!")
            successful += 1
            
            # Small delay to be nice to servers
            time.sleep(2)
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            break
        
        except Exception as e:
            print(f"    ❌ Error: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print(f"\n✅ Successfully added: {successful} references")
    if failed > 0:
        print(f"❌ Failed: {failed} references")
    
    print("\nYou can now:")
    print("  1. Start the app: python app.py")
    print("  2. Test visual detection: python manage_visual_references.py test <url>")
    print("  3. List references: python manage_visual_references.py list")
    
    print("\nVisual similarity detection is now enabled!")


if __name__ == "__main__":
    main()
