"""
generate_icons.py
-----------------
Quick icon generator for PhishingHunter Elite v2

Creates simple but functional placeholder icons for:
- Browser extension (16px, 32px, 48px, 128px)
- PWA (72px, 96px, 128px, 144px, 152px, 192px, 384px, 512px)

Usage:
    python generate_icons.py

Colors: PhishingHunter brand colors (#00ff88, #00d4ff, #0a0e1a)
"""

import os
from PIL import Image, ImageDraw, ImageFont

# PhishingHunter brand colors
BG_COLOR = (10, 14, 26)      # #0a0e1a (dark background)
PRIMARY = (0, 255, 136)      # #00ff88 (neon green)
SECONDARY = (0, 212, 255)    # #00d4ff (cyan)

# Icon sizes
EXTENSION_SIZES = [16, 32, 48, 128]
PWA_SIZES = [72, 96, 128, 144, 152, 192, 384, 512]

# Output directories
EXTENSION_DIR = "extension/icons"
PWA_DIR = "static/icons"


def create_icon(size, text="PH", output_path=None):
    """
    Create a simple icon with text on colored background.
    
    Args:
        size: Icon size in pixels (square)
        text: Text to display (default: "PH" for PhishingHunter)
        output_path: Where to save the icon
    """
    # Create image with dark background
    img = Image.new('RGB', (size, size), BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    # Draw a circle border (shield-like)
    border_width = max(2, size // 20)
    margin = size // 8
    circle_box = [margin, margin, size - margin, size - margin]
    
    # Draw gradient-like circles (primary to secondary)
    for i in range(3):
        offset = i * 2
        box = [
            circle_box[0] + offset,
            circle_box[1] + offset,
            circle_box[2] - offset,
            circle_box[3] - offset
        ]
        color = PRIMARY if i == 0 else SECONDARY if i == 1 else PRIMARY
        draw.ellipse(box, outline=color, width=border_width)
    
    # Draw text in center
    font_size = size // 3
    try:
        # Try to use a nice font if available
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        # Fallback to default font
        font = ImageFont.load_default()
    
    # Get text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Center text
    x = (size - text_width) // 2
    y = (size - text_height) // 2 - bbox[1]
    
    # Draw text with glow effect
    for offset in [(0, 0), (1, 1), (-1, -1)]:
        draw.text((x + offset[0], y + offset[1]), text, fill=PRIMARY, font=font)
    
    # Save icon
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, 'PNG')
        print(f"  ✅ Created: {output_path} ({size}x{size})")
    
    return img


def create_shield_icon(size, output_path=None):
    """
    Create a shield-style security icon.
    
    Args:
        size: Icon size in pixels (square)
        output_path: Where to save the icon
    """
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Shield shape (simplified polygon)
    margin = size // 6
    points = [
        (size // 2, margin),                    # Top center
        (size - margin, margin + size // 6),    # Top right
        (size - margin, size // 2),             # Middle right
        (size // 2, size - margin),             # Bottom point
        (margin, size // 2),                    # Middle left
        (margin, margin + size // 6),           # Top left
    ]
    
    # Draw shield background
    draw.polygon(points, fill=BG_COLOR, outline=PRIMARY, width=max(2, size // 30))
    
    # Draw inner design (checkmark or target)
    center_x = size // 2
    center_y = size // 2
    
    # Draw concentric circles (target style)
    for i, radius_factor in enumerate([0.4, 0.3, 0.2]):
        radius = int(size * radius_factor)
        circle_box = [
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius
        ]
        color = PRIMARY if i % 2 == 0 else SECONDARY
        draw.ellipse(circle_box, outline=color, width=max(2, size // 40))
    
    # Draw crosshair
    line_length = int(size * 0.15)
    line_width = max(2, size // 40)
    
    # Horizontal line
    draw.line([
        (center_x - line_length, center_y),
        (center_x + line_length, center_y)
    ], fill=SECONDARY, width=line_width)
    
    # Vertical line
    draw.line([
        (center_x, center_y - line_length),
        (center_x, center_y + line_length)
    ], fill=SECONDARY, width=line_width)
    
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, 'PNG')
        print(f"  ✅ Created: {output_path} ({size}x{size})")
    
    return img


def generate_all_icons():
    """Generate all icons for extension and PWA."""
    print("\n" + "=" * 60)
    print("PhishingHunter Icon Generator")
    print("=" * 60)
    
    # Create extension icons
    print("\n📱 Creating Browser Extension Icons...")
    for size in EXTENSION_SIZES:
        output_path = os.path.join(EXTENSION_DIR, f"icon{size}.png")
        create_shield_icon(size, output_path)
    
    # Create PWA icons
    print("\n🌐 Creating PWA Icons...")
    for size in PWA_SIZES:
        output_path = os.path.join(PWA_DIR, f"icon-{size}x{size}.png")
        create_shield_icon(size, output_path)
    
    print("\n" + "=" * 60)
    print("✅ All Icons Created Successfully!")
    print("=" * 60)
    
    print("\n📂 Files created:")
    print(f"  Extension: {EXTENSION_DIR}/ ({len(EXTENSION_SIZES)} files)")
    print(f"  PWA: {PWA_DIR}/ ({len(PWA_SIZES)} files)")
    
    print("\n✅ Browser extension and PWA now have professional icons!")
    print("   You can replace these with custom designs anytime.")
    print("\n💡 To use custom icons:")
    print("   1. Design your own icon (512x512)")
    print("   2. Use https://realfavicongenerator.net to resize")
    print("   3. Replace the generated files")


if __name__ == "__main__":
    generate_all_icons()
