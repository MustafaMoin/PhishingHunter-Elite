"""
resize_icon.py
--------------
Resize your master icon to all required sizes for PhishingHunter

Usage:
    python resize_icon.py <path_to_your_master_icon>

Example:
    python resize_icon.py downloads/phishinghunter-master.png
"""

import sys
import os
from PIL import Image

# Required sizes
EXTENSION_SIZES = [16, 32, 48, 128]
PWA_SIZES = [72, 96, 128, 144, 152, 192, 384, 512]

def resize_icon(input_path):
    """Resize master icon to all required sizes."""
    if not os.path.exists(input_path):
        print(f"❌ Error: File not found: {input_path}")
        return False
    
    print("\n" + "=" * 60)
    print("PhishingHunter Icon Resizer")
    print("=" * 60)
    print(f"\n📂 Input: {input_path}")
    
    try:
        # Load master icon
        img = Image.open(input_path)
        print(f"✅ Loaded image: {img.size[0]}x{img.size[1]} pixels")
        
        # Ensure directories exist
        os.makedirs("extension/icons", exist_ok=True)
        os.makedirs("static/icons", exist_ok=True)
        
        # Create extension icons
        print("\n📱 Creating Browser Extension Icons:")
        for size in EXTENSION_SIZES:
            output_path = f"extension/icons/icon{size}.png"
            resized = img.resize((size, size), Image.Resampling.LANCZOS)
            resized.save(output_path, 'PNG', optimize=True)
            file_size = os.path.getsize(output_path) / 1024
            print(f"  ✅ {output_path} ({file_size:.1f} KB)")
        
        # Create PWA icons
        print("\n🌐 Creating PWA Icons:")
        for size in PWA_SIZES:
            output_path = f"static/icons/icon-{size}x{size}.png"
            resized = img.resize((size, size), Image.Resampling.LANCZOS)
            resized.save(output_path, 'PNG', optimize=True)
            file_size = os.path.getsize(output_path) / 1024
            print(f"  ✅ {output_path} ({file_size:.1f} KB)")
        
        print("\n" + "=" * 60)
        print("✅ SUCCESS! All Icons Created!")
        print("=" * 60)
        
        print("\n📊 Summary:")
        print(f"  Extension icons: {len(EXTENSION_SIZES)} files")
        print(f"  PWA icons: {len(PWA_SIZES)} files")
        print(f"  Total: {len(EXTENSION_SIZES) + len(PWA_SIZES)} files")
        
        print("\n🎉 Your PhishingHunter app now has perfect custom icons!")
        print("   Browser extension and PWA ready to use.")
        
        print("\n💡 Next steps:")
        print("   1. Test browser extension: Load in Chrome")
        print("   2. Test PWA: Open app and try 'Add to Home Screen'")
        print("   3. Deploy your perfectly branded app!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("\n🎨 PhishingHunter Icon Resizer")
    
    if len(sys.argv) < 2:
        print("\n❌ Error: No input file specified")
        print("\nUsage:")
        print("  python resize_icon.py <path_to_your_icon>")
        print("\nExample:")
        print("  python resize_icon.py downloads/phishinghunter-master.png")
        print("  python resize_icon.py C:/Users/YourName/Downloads/icon.png")
        sys.exit(1)
    
    input_file = sys.argv[1]
    success = resize_icon(input_file)
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
