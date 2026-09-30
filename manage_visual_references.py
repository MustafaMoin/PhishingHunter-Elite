"""
manage_visual_references.py
----------------------------
Utility script to manage reference brand screenshots for visual similarity detection.

This script helps you:
  1. Add reference screenshots for brands
  2. List existing references
  3. Test visual similarity against a URL
  4. Remove outdated references

Usage:
  # Add a reference screenshot
  python manage_visual_references.py add paypal paypal.com login https://www.paypal.com/signin

  # Add from local file
  python manage_visual_references.py add-file google google.com login screenshots/google_login.png

  # List all references
  python manage_visual_references.py list

  # Test against a URL
  python manage_visual_references.py test https://suspicious-site.com

  # Remove a reference
  python manage_visual_references.py remove paypal login
"""

import sys
import argparse

import visual_similarity


def cmd_add(args):
    """Add a reference screenshot by taking a screenshot of a URL."""
    if not visual_similarity.is_available():
        print("❌ Visual similarity features not available.")
        print("   Install with: pip install playwright imagehash Pillow")
        print("   Then run: playwright install chromium")
        return
    
    print(f"📸 Taking screenshot of {args.url}...")
    screenshot_bytes = visual_similarity._take_screenshot(args.url)
    
    if not screenshot_bytes:
        print("❌ Failed to take screenshot")
        return
    
    print(f"✅ Screenshot captured ({len(screenshot_bytes)} bytes)")
    print(f"💾 Adding reference for brand '{args.brand}'...")
    
    visual_similarity.add_reference_screenshot(
        brand=args.brand,
        domain=args.domain,
        page_type=args.page_type,
        screenshot_bytes=screenshot_bytes,
    )
    
    print(f"✅ Reference added: {args.brand} ({args.page_type}) - {args.domain}")


def cmd_add_file(args):
    """Add a reference screenshot from a local file."""
    if not visual_similarity.is_available():
        print("❌ Visual similarity features not available.")
        return
    
    try:
        with open(args.file_path, "rb") as f:
            screenshot_bytes = f.read()
        
        print(f"✅ Loaded screenshot from {args.file_path} ({len(screenshot_bytes)} bytes)")
        print(f"💾 Adding reference for brand '{args.brand}'...")
        
        visual_similarity.add_reference_screenshot(
            brand=args.brand,
            domain=args.domain,
            page_type=args.page_type,
            screenshot_bytes=screenshot_bytes,
        )
        
        print(f"✅ Reference added: {args.brand} ({args.page_type}) - {args.domain}")
    
    except FileNotFoundError:
        print(f"❌ File not found: {args.file_path}")
    except Exception as e:
        print(f"❌ Error: {e}")


def cmd_list(args):
    """List all reference brands."""
    if not visual_similarity.is_available():
        print("❌ Visual similarity features not available.")
        return
    
    brands = visual_similarity.list_reference_brands()
    
    if not brands:
        print("📭 No reference screenshots in database")
        print("\nTo add references:")
        print("  python manage_visual_references.py add <brand> <domain> <page_type> <url>")
        return
    
    print("\n📚 Reference Brand Screenshots:")
    print("=" * 60)
    for brand, page_types in sorted(brands.items()):
        print(f"\n🏷️  {brand.upper()}")
        for page_type in sorted(page_types):
            print(f"   └─ {page_type}")
    
    print(f"\n📊 Total: {len(brands)} brands, {sum(len(pt) for pt in brands.values())} page types")


def cmd_test(args):
    """Test visual similarity against a URL."""
    if not visual_similarity.is_available():
        print("❌ Visual similarity features not available.")
        return
    
    print(f"🔍 Analyzing {args.url}...")
    print("📸 Taking screenshot (this may take 5-10 seconds)...")
    
    from detector import _TLD
    extracted = _TLD(args.url)
    domain = extracted.registered_domain
    
    result = visual_similarity.check_visual_similarity(args.url, domain)
    
    if result is None:
        print("❌ Visual analysis failed (screenshot or hash computation error)")
        return
    
    print("\n" + "=" * 60)
    print("Visual Similarity Analysis Results")
    print("=" * 60)
    print(f"\n🌐 URL: {args.url}")
    print(f"📍 Domain: {domain}")
    print(f"\n{result['details']}")
    
    if result['matched_brand']:
        print(f"\n🏷️  Matched Brand: {result['matched_brand'].upper()}")
        print(f"🔗 Legitimate Domain: {result['matched_domain']}")
        print(f"📏 Hamming Distance: {result['hamming_distance']}")
        print(f"📊 Similarity: {100 - result['hamming_distance'] * 6:.0f}%")
        
        if result['is_clone']:
            print("\n⚠️  WARNING: This appears to be a VISUAL CLONE of a legitimate brand")
            print(f"    but hosted on WRONG domain '{domain}'")
            print("\n🚨 HIGH RISK OF PHISHING!")
        else:
            print("\n✅ Domain matches - appears legitimate")
    else:
        print("\n✅ No visual similarity to known brand pages")
    
    print("=" * 60)


def cmd_remove(args):
    """Remove a reference screenshot."""
    if not visual_similarity.is_available():
        print("❌ Visual similarity features not available.")
        return
    
    conn = visual_similarity._get_conn()
    with visual_similarity._lock, conn:
        cursor = conn.execute(
            "DELETE FROM visual_reference WHERE brand = ? AND page_type = ?",
            (args.brand, args.page_type),
        )
        conn.commit()
        
        if cursor.rowcount > 0:
            print(f"✅ Removed reference: {args.brand} ({args.page_type})")
        else:
            print(f"❌ Reference not found: {args.brand} ({args.page_type})")


def main():
    parser = argparse.ArgumentParser(
        description="Manage visual reference screenshots for PhishingHunter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add reference screenshot from URL")
    add_parser.add_argument("brand", help="Brand name (e.g., paypal, google)")
    add_parser.add_argument("domain", help="Legitimate domain (e.g., paypal.com)")
    add_parser.add_argument("page_type", help="Page type (e.g., login, 2fa, password_reset)")
    add_parser.add_argument("url", help="URL to screenshot")
    
    # Add-file command
    add_file_parser = subparsers.add_parser("add-file", help="Add reference screenshot from file")
    add_file_parser.add_argument("brand", help="Brand name")
    add_file_parser.add_argument("domain", help="Legitimate domain")
    add_file_parser.add_argument("page_type", help="Page type")
    add_file_parser.add_argument("file_path", help="Path to screenshot PNG file")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all reference screenshots")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Test visual similarity against URL")
    test_parser.add_argument("url", help="URL to test")
    
    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove a reference screenshot")
    remove_parser.add_argument("brand", help="Brand name")
    remove_parser.add_argument("page_type", help="Page type")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "add":
        cmd_add(args)
    elif args.command == "add-file":
        cmd_add_file(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "test":
        cmd_test(args)
    elif args.command == "remove":
        cmd_remove(args)


if __name__ == "__main__":
    main()
