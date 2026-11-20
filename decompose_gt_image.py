#!/usr/bin/env python3
"""
Decompose a 2x2 grid of isometric SAP logo views into 4 separate images.

Usage:
  python decompose_gt_image.py <input_image_path>

Expected layout:
  [Cenital]        [Frontal]
  [Lateral Izq]    [Lateral Der]
"""

import sys
from pathlib import Path
from PIL import Image

def decompose_2x2_grid(image_path):
    """Split 2x2 grid image into 4 quadrants."""
    
    img_path = Path(image_path)
    if not img_path.exists():
        print(f"✗ File not found: {img_path}")
        return False
    
    img = Image.open(img_path)
    width, height = img.size
    
    print(f"Image: {width}×{height}")
    
    # Split into 2x2 grid
    half_w = width // 2
    half_h = height // 2
    
    views = [
        ("cenital", (0, 0, half_w, half_h)),
        ("frontal", (half_w, 0, width, half_h)),
        ("lateral_izq", (0, half_h, half_w, height)),
        ("lateral_der", (half_w, half_h, width, height)),
    ]
    
    output_dir = Path("/Users/I764690/Code_personal/LdrawNova/output/sap_logo/gt")
    output_dir.mkdir(exist_ok=True, parents=True)
    
    for view_name, bbox in views:
        cropped = img.crop(bbox)
        output_path = output_dir / f"gt_{view_name}.png"
        cropped.save(output_path)
        print(f"✓ Saved: {output_path} ({cropped.size})")
    
    print(f"\n✓ 4 GT images saved to {output_dir}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    decompose_2x2_grid(sys.argv[1])
