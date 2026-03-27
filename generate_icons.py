#!/usr/bin/env python3
"""Generate StreamContext extension icons using PIL"""
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    os.system('pip3 install Pillow --break-system-packages -q')
    from PIL import Image, ImageDraw, ImageFont

def create_icon(size):
    # Create image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Background circle
    padding = size * 0.05
    draw.ellipse([padding, padding, size-padding, size-padding],
                 fill=(8, 8, 20, 255))
    
    # Gradient ring effect (multiple arcs)
    ring_width = max(2, size // 20)
    ring_pad = size * 0.08
    for i in range(ring_width):
        alpha = int(255 * (1 - i / ring_width) * 0.8)
        draw.ellipse([ring_pad+i, ring_pad+i, size-ring_pad-i, size-ring_pad-i],
                     outline=(0, 200, 255, alpha), width=1)
    
    # Wave emoji approximation — draw stylized 'S' wave
    center = size // 2
    wave_size = int(size * 0.45)
    
    # Draw wave lines
    line_w = max(1, size // 16)
    
    # Simple wave pattern
    points1 = []
    points2 = []
    for x in range(-wave_size//2, wave_size//2 + 1, 1):
        import math
        y1 = int(math.sin(x * math.pi / (wave_size/3)) * wave_size * 0.15)
        y2 = int(math.sin(x * math.pi / (wave_size/3) + math.pi) * wave_size * 0.15)
        points1.append((center + x, center - wave_size//4 + y1))
        points2.append((center + x, center + wave_size//4 + y2))
    
    if len(points1) > 1:
        draw.line(points1, fill=(0, 200, 255, 255), width=line_w)
        draw.line(points2, fill=(0, 112, 243, 200), width=line_w)
    
    return img

icons_dir = os.path.join(os.path.dirname(__file__), 'icons')
os.makedirs(icons_dir, exist_ok=True)

for size in [16, 32, 48, 128]:
    icon = create_icon(size)
    path = os.path.join(icons_dir, f'icon{size}.png')
    icon.save(path, 'PNG')
    print(f'Created icon{size}.png')

print('All icons created!')
