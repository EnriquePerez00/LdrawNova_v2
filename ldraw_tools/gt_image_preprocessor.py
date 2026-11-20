"""Image pre-processor for GT images - Detect and mark white background."""
import logging
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Any
import json

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

logger = logging.getLogger(__name__)


class GTImagePreprocessor:
    """Pre-process Ground Truth images to help VLM ignore white background."""
    
    def __init__(self, white_threshold: int = 240, min_component_size: int = 50):
        """
        Args:
            white_threshold: RGB values >= this are considered white (0-255, default 240)
            min_component_size: Minimum pixels for valid component
        """
        self.white_threshold = white_threshold
        self.min_component_size = min_component_size
    
    def detect_background_mask(self, image_path: Path) -> Optional[np.ndarray]:
        """
        Detect white background regions in image.
        Returns: Binary mask (1=white, 0=content) or None
        """
        if not PILLOW_AVAILABLE:
            logger.warning("[GTPreprocessor] PIL not available")
            return None
        
        if not image_path.exists():
            logger.warning(f"[GTPreprocessor] Image not found: {image_path}")
            return None
        
        try:
            img = Image.open(image_path).convert("RGB")
            img_array = np.array(img)
            r, g, b = img_array[:,:,0], img_array[:,:,1], img_array[:,:,2]
            white_mask = (r >= self.white_threshold) & (g >= self.white_threshold) & (b >= self.white_threshold)
            logger.debug(f"[GTPreprocessor] {image_path.name}: {white_mask.sum()} white pixels")
            return white_mask.astype(np.uint8)
        except Exception as e:
            logger.warning(f"[GTPreprocessor] Failed: {e}")
            return None
    
    def generate_hint_metadata(self, image_path: Path) -> Optional[dict]:
        """Generate metadata hint for VLM about background."""
        mask = self.detect_background_mask(image_path)
        if mask is None:
            return None
        
        height, width = mask.shape
        white_pct = (mask.sum() / (height * width)) * 100
        
        return {
            "image_file": image_path.name,
            "white_percentage": round(white_pct, 1),
            "white_pixels": int(mask.sum()),
            "hint": f"~{white_pct:.0f}% white background detected. Focus on non-white regions.",
            "threshold": self.white_threshold
        }
    
    def create_visual_hint_overlay(self, image_path: Path, output_path: Optional[Path] = None) -> Optional[Path]:
        """Create visual hint showing content vs background."""
        if not PILLOW_AVAILABLE:
            return None
        
        mask = self.detect_background_mask(image_path)
        if mask is None:
            return None
        
        try:
            img = Image.open(image_path).convert("RGB")
            img_array = np.array(img)
            faded = img_array.copy()
            faded[mask == 1] = (faded[mask == 1] * 0.7).astype(np.uint8)
            hint_img = Image.fromarray(faded)
            
            if output_path is None:
                output_path = image_path.parent / f"{image_path.stem}_hint.png"
            
            hint_img.save(output_path)
            logger.debug(f"[GTPreprocessor] Hint overlay saved: {output_path}")
            return output_path
        except Exception as e:
            logger.warning(f"[GTPreprocessor] Hint creation failed: {e}")
            return None


def preprocess_gt_images_batch(image_paths: list, create_hint: bool = False, metadata_output: Optional[Path] = None) -> dict:
    """Batch pre-process multiple GT images."""
    preprocessor = GTImagePreprocessor()
    results = {"images_processed": 0, "images_with_white_bg": 0, "metadata": []}
    
    for img_path in image_paths:
        metadata = preprocessor.generate_hint_metadata(Path(img_path))
        if metadata:
            results["metadata"].append(metadata)
            results["images_processed"] += 1
            
            if metadata.get("white_percentage", 0) > 50:
                results["images_with_white_bg"] += 1
            
            if create_hint:
                preprocessor.create_visual_hint_overlay(Path(img_path))
    
    if metadata_output:
        Path(metadata_output).write_text(json.dumps(results, indent=2))
        logger.info(f"[GTPreprocessor] Metadata saved to {metadata_output}")
    
    return results

