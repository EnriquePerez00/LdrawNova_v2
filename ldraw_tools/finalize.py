"""Finalize: Render + evaluate LDraw models (gate pattern)."""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ModelFinalizer:
    """Render 4 views + validate metrics."""
    
    def __init__(self, ldraw_dir: str = "/Users/I764690/LDraw"):
        self.ldraw_dir = ldraw_dir
        from ldraw_tools.renderer import LeoCADRenderer, ColorExtractor, OverlapDetector
        from ldraw_tools.validators import GeometryValidator, BOMValidator, ColorValidator
        self.renderer = LeoCADRenderer(ldraw_dir=ldraw_dir)
        self.color_extractor = ColorExtractor()
        self.overlap_detector = OverlapDetector()
        self.geometry_validator = GeometryValidator()
        self.bom_validator = BOMValidator()
        self.color_validator = ColorValidator()
    
    def finalize_model(
        self,
        mpd_path: Path,
        output_dir: Path,
        whitelist: Optional[Dict[str, Any]] = None,
        bom_constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Render + validate, produce evaluation.json"""
        output_dir = Path(output_dir)
        renders_dir = output_dir / "renders"
        renders_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[Finalizer] {mpd_path.name} → {output_dir}")
        
        evaluation = {
            "timestamp": datetime.now().isoformat(),
            "mpd_path": str(mpd_path),
            "stages": {},
        }
        
        # Render
        try:
            logger.info("[Finalizer] Rendering 4 views...")
            rendered = self.renderer.render_views(mpd_path, renders_dir, ["home","front","right","top"])
            evaluation["stages"]["render"] = {"status": "ok", "views": list(rendered.keys())}
            logger.info(f"[Finalizer] ✓ {len(rendered)} views rendered")
        except Exception as e:
            logger.error(f"[Finalizer] Render failed: {e}")
            evaluation["stages"]["render"] = {"status": "error", "error": str(e)}
            return evaluation
        
        # Geometry
        try:
            if whitelist:
                is_valid, errs = self.geometry_validator.validate_mpd(mpd_path, whitelist)
                evaluation["stages"]["geometry"] = {"status": "ok" if is_valid else "error", "errors": errs}
            else:
                evaluation["stages"]["geometry"] = {"status": "skipped"}
        except Exception as e:
            evaluation["stages"]["geometry"] = {"status": "error", "error": str(e)}
        
        # BOM
        try:
            bom = self.bom_validator.extract_bom(mpd_path)
            total = sum(bom.values())
            evaluation["stages"]["bom"] = {"status": "ok", "total_parts": total, "unique": len(bom)}
            logger.info(f"[Finalizer] BOM: {total} parts")
        except Exception as e:
            evaluation["stages"]["bom"] = {"status": "error"}
        
        # Color
        try:
            if rendered.get("home"):
                colors = self.color_extractor.extract_dominant_colors(rendered["home"], num_colors=5)
                is_valid, errs = self.color_validator.validate_colors(colors)
                evaluation["stages"]["color"] = {"status": "ok" if is_valid else "warning", "colors": len(colors)}
        except Exception as e:
            evaluation["stages"]["color"] = {"status": "error"}
        
        # Overlaps
        try:
            overlap_results = {}
            for vname, vpath in rendered.items():
                issues = self.overlap_detector.detect_overlaps(vpath)
                overlap_results[vname] = {"issues": len(issues)}
            evaluation["stages"]["overlaps"] = overlap_results
        except Exception as e:
            evaluation["stages"]["overlaps"] = {"status": "error"}
        
        # Save
        eval_path = output_dir / "evaluation.json"
        eval_path.write_text(json.dumps(evaluation, indent=2))
        logger.info(f"[Finalizer] ✓ evaluation.json")
        
        return evaluation
