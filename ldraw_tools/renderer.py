"""LeoCAD rendering pipeline - 4 views from MPD."""
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

logger = logging.getLogger(__name__)


class LeoCADRenderer:
    """Renders LDraw models using LeoCAD CLI."""
    
    def __init__(self, leocad_path: str = "leocad", ldraw_dir: str = "/Users/I764690/LDraw"):
        self.leocad_path = leocad_path
        self.ldraw_dir = ldraw_dir
        self._validate_installation()
    
    def _validate_installation(self) -> bool:
        """Check if LeoCAD is available."""
        try:
            result = subprocess.run([self.leocad_path, "-help"], capture_output=True, timeout=5)
            is_available = result.returncode in [0, 1]  # -help might return non-zero
            if is_available:
                logger.info(f"[Renderer] LeoCAD found at {self.leocad_path}")
            return is_available
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning(f"[Renderer] LeoCAD not found at {self.leocad_path}")
            return False
    
    def render_views(
        self,
        mpd_path: Path,
        output_dir: Path,
        views: Optional[List[str]] = None,
    ) -> Dict[str, Path]:
        """
        Render 4 standard views from MPD.
        views: ["home", "front", "right", "top"] (default: all)
        Returns: {"home": Path, "front": Path, ...}
        """
        if views is None:
            views = ["home", "front", "right", "top"]
        
        output_dir.mkdir(parents=True, exist_ok=True)
        rendered = {}
        
        # LeoCAD camera positions (simplified)
        cameras = {
            "home": ["--camera", "0 0 0 1000 1000 500"],  # Default isometric
            "front": ["--camera", "0 0 0 0 1000 0"],      # Front view
            "right": ["--camera", "0 0 0 1000 0 0"],      # Right view  
            "top": ["--camera", "0 0 0 0 0 1000"],        # Top view
        }
        
        for view_name in views:
            output_png = output_dir / f"{view_name}.png"
            
            # Build LeoCAD command
            cmd = [
                self.leocad_path,
                str(mpd_path),
                "-i",  # Render to image
                str(output_png),
                "-w", "800",
                "-h", "600",
            ]
            
            if view_name in cameras:
                cmd.extend(cameras[view_name])
            
            try:
                logger.info(f"[Renderer] Rendering {view_name} view...")
                result = subprocess.run(cmd, capture_output=True, timeout=30)
                
                if output_png.exists():
                    rendered[view_name] = output_png
                    logger.info(f"[Renderer] {view_name}: {output_png.stat().st_size} bytes")
                else:
                    logger.warning(f"[Renderer] {view_name} render produced no output")
            
            except subprocess.TimeoutExpired:
                logger.warning(f"[Renderer] {view_name} render timed out")
            except Exception as e:
                logger.warning(f"[Renderer] {view_name} render failed: {e}")
        
        if rendered:
            logger.info(f"[Renderer] Successfully rendered {len(rendered)}/{len(views)} views")
        else:
            logger.warning(f"[Renderer] No views rendered (LeoCAD may not be available)")
            # Fallback: create placeholder PNGs
            rendered = self._create_placeholder_renders(output_dir, views)
        
        return rendered
    
    def _create_placeholder_renders(self, output_dir: Path, views: List[str]) -> Dict[str, Path]:
        """Create placeholder PNG files for testing (when LeoCAD unavailable)."""
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            logger.warning("[Renderer] PIL not available; cannot create placeholder renders")
            return {}
        
        rendered = {}
        for view_name in views:
            output_png = output_dir / f"{view_name}.png"
            
            # Create simple placeholder image
            img = Image.new('RGB', (800, 600), color=(240, 240, 240))
            draw = ImageDraw.Draw(img)
            draw.text((350, 280), f"View: {view_name}", fill=(100, 100, 100))
            
            img.save(output_png)
            rendered[view_name] = output_png
            logger.info(f"[Renderer] Created placeholder: {output_png}")
        
        return rendered


class ColorExtractor:
    """Extract dominant colors from rendered images."""
    
    def extract_dominant_colors(
        self,
        image_path: Path,
        num_colors: int = 3,
    ) -> List[Tuple[int, int, int]]:
        """
        Extract dominant colors from image using K-means clustering.
        Returns list of RGB tuples.
        """
        try:
            from PIL import Image
            import numpy as np
            from sklearn.cluster import KMeans
        except ImportError:
            logger.warning("[ColorExtractor] PIL/sklearn not available")
            return [(200, 100, 50)]  # Fallback: orange
        
        if not image_path.exists():
            return []
        
        try:
            img = Image.open(image_path)
            # Resize for faster processing
            img = img.resize((200, 150))
            
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Extract pixels
            pixels = np.array(img)
            pixels = pixels.reshape(-1, 3)
            
            # K-means clustering
            kmeans = KMeans(n_clusters=min(num_colors, len(np.unique(pixels, axis=0))), n_init=10)
            kmeans.fit(pixels)
            
            # Get cluster centers (dominant colors)
            colors = kmeans.cluster_centers_.astype(int)
            return [tuple(c) for c in colors]
        
        except Exception as e:
            logger.warning(f"[ColorExtractor] Failed to extract colors: {e}")
            return []


class OverlapDetector:
    """Detects visual overlaps in rendered images (simple edge detection)."""
    
    def detect_overlaps(self, image_path: Path) -> List[Dict[str, any]]:
        """
        Detect potential overlaps using edge detection.
        Returns list of detected issues.
        """
        try:
            from PIL import Image, ImageFilter
            import numpy as np
        except ImportError:
            logger.warning("[OverlapDetector] PIL not available")
            return []
        
        if not image_path.exists():
            return []
        
        try:
            img = Image.open(image_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Simple edge detection using Sobel
            edges = img.filter(ImageFilter.FIND_EDGES)
            edge_array = np.array(edges.convert('L'))
            
            # Count high-gradient regions (potential overlaps)
            high_gradient = (edge_array > 100).sum()
            total_pixels = edge_array.size
            overlap_ratio = high_gradient / total_pixels
            
            issues = []
            if overlap_ratio > 0.15:  # Threshold: >15% high-gradient pixels
                issues.append({
                    "type": "possible_overlap",
                    "confidence": overlap_ratio,
                    "location": "image"
                })
            
            return issues
        
        except Exception as e:
            logger.warning(f"[OverlapDetector] Failed: {e}")
            return []
