
import sys
import os
from pathlib import Path

# Add src to sys.path
sys.path.append(os.getcwd())

from src.infrastructure.equipment_config import get_equipment_config

def test_config_images():
    model = "cctv-psu-24w-v1"
    config = get_equipment_config(model)
    
    print(f"Checking images for {model}...")
    for img_id, img in config.images.items():
        print(f"  Image: {img_id} ({img.filename})")
        print(f"    Test points: {img.test_points}")

    print("\nChecking test point guidance (TP2)...")
    guidance = config.get_test_point_guidance("TP2")
    if guidance.get("image_url"):
        print(f"  SUCCESS: TP2 image URL: {guidance['image_url']}")
    else:
        print(f"  FAILED: TP2 image URL not found")

if __name__ == "__main__":
    test_config_images()
