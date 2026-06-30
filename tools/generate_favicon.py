#!/usr/bin/env python3
"""Generate a favicon for the markdown journaling tool."""

from PIL import Image, ImageDraw, ImageFont
import os

def create_favicon(letter='M', dark_bg='#3A3A3A', light_box='#FFFFFF'):
    """Create a favicon with a letter in a rounded box, similar to Wikipedia style."""
    
    size = 256
    img = Image.new('RGB', (size, size), color=dark_bg)
    draw = ImageDraw.Draw(img, 'RGBA')
    
    # Draw rounded rectangle box
    margin = 20
    box_left = margin
    box_top = margin
    box_right = size - margin
    box_bottom = size - margin
    
    draw.rounded_rectangle(
        [(box_left, box_top), (box_right, box_bottom)],
        radius=20,
        fill=light_box,
        outline='#4A4A4A',
        width=2
    )
    
    # Try to use a serif font for the letter
    font_size = 180
    try:
        # Try common serif fonts
        font_paths = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf',
            '/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf',
        ]
        
        font = None
        for font_path in font_paths:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, font_size)
                break
        
        if font is None:
            # Fallback to default font
            font = ImageFont.load_default()
    except Exception as e:
        print(f"Warning: Could not load serif font: {e}")
        font = ImageFont.load_default()
    
    # Draw the letter centered
    bbox = draw.textbbox((0, 0), letter, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size - text_width) // 2 - bbox[0]
    y = (size - text_height) // 2 - bbox[1]
    
    draw.text((x, y), letter, fill='#2C2C2C', font=font)
    
    return img


def create_svg_favicon(letter='M', dark_bg='#3A3A3A', light_box='#FFFFFF'):
    """Create a standalone SVG XML string for the favicon."""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <rect width="256" height="256" rx="48" fill="{dark_bg}"/>
  <rect x="20" y="20" width="216" height="216" rx="20" fill="{light_box}" stroke="#4A4A4A" stroke-width="2"/>
  <text x="128" y="172" text-anchor="middle" font-family="DejaVu Serif, Liberation Serif, Noto Serif, serif" font-size="160" font-weight="700" fill="#2C2C2C">{letter}</text>
</svg>
'''

# Create static folder if it doesn't exist
static_dir = os.path.join(os.path.dirname(__file__), 'static')
os.makedirs(static_dir, exist_ok=True)

# Generate favicon
img = create_favicon(letter='M', dark_bg='#3A3A3A', light_box='#FFFFFF')

png_path = os.path.join(static_dir, 'favicon.png')
ico_path = os.path.join(static_dir, 'favicon.ico')
svg_path = os.path.join(static_dir, 'favicon.svg')

# Save as PNG
img.save(png_path, 'PNG')
print(f"✓ Generated {png_path}")

with open(svg_path, 'w', encoding='utf-8') as svg_file:
    svg_file.write(create_svg_favicon(letter='M', dark_bg='#3A3A3A', light_box='#FFFFFF'))
print(f"✓ Generated {svg_path}")

# Convert to ICO format (with multiple sizes for better compatibility)
ico_images = []
for ico_size in [16, 32, 48, 64, 128, 256]:
    ico_img = img.resize((ico_size, ico_size), Image.Resampling.LANCZOS)
    ico_images.append(ico_img)

# Save as ICO with all sizes
ico_images[0].save(
    ico_path,
    'ICO',
    sizes=[(s, s) for s in [16, 32, 48, 64, 128, 256]],
    append_images=ico_images[1:]
)
print(f"✓ Generated {ico_path}")
print("\nFavicon created successfully!")
