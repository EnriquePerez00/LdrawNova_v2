#!/usr/bin/env python3
"""Phase 2 Mock: Generate realistic specs sin esperar VLM (para demostración)."""

import json
from pathlib import Path

output_dir = Path("/Users/I764690/Code_personal/LdrawNova/output/sap_logo")

# Mock GT spec (lo que A1 hubiera extrado)
gt_spec = {
    "version": 1,
    "profile": "brand_logo",
    "segments": [
        {
            "id": "sap_main_plate",
            "type": "plate",
            "role": "base_mounting",
            "dimensions": {"length": 240, "width": 100, "height": 8},
            "color": "#0055BF",
            "material": "LEGO ABS plastic"
        },
        {
            "id": "sap_text_white",
            "type": "tiles_2x2",
            "role": "typography",
            "dimensions": {"width": 120, "height": 40, "depth": 9.6},
            "color": "#FFFFFF",
            "description": "SAP logotype in white"
        },
        {
            "id": "sap_backing_grey",
            "type": "plate",
            "role": "structural_support",
            "dimensions": {"length": 200, "width": 80, "height": 8},
            "color": "#A0A5A9",
            "description": "Grey base plate"
        }
    ],
    "colors_detected": ["#0055BF", "#FFFFFF", "#A0A5A9"],
    "overall_dimensions": {"length": 240, "width": 100, "height": 50},
    "inferred_volume": "LEGO brick SAP logo badge"
}

# Mock Render spec
render_spec = {
    "version": 1,
    "profile": "brand_logo",
    "segments": [
        {
            "id": "generated_main_plate",
            "type": "plate",
            "color": "#0055BF",
            "dimensions": {"length": 240, "width": 100, "height": 8}
        },
        {
            "id": "generated_text_white",
            "type": "tiles_2x2",
            "color": "#FFFFFF",
            "dimensions": {"width": 120, "height": 40, "depth": 9.6}
        },
        {
            "id": "generated_backing_grey",
            "type": "plate",
            "color": "#A0A5A9",
            "dimensions": {"length": 200, "width": 80, "height": 8}
        }
    ],
    "colors_detected": ["#0055BF", "#FFFFFF", "#A0A5A9"],
    "overall_dimensions": {"length": 240, "width": 100, "height": 50}
}

# Mock Diff report
diff_report = {
    "version": 1,
    "profile": "brand_logo",
    "iteration": 1,
    "global_score": 87.5,
    "per_axis_scores": {
        "structure": 90.0,
        "color_accuracy": 95.0,
        "typography": 75.0,
        "dimensions": 85.0,
        "material_fidelity": 80.0
    },
    "converged": False,
    "diffs": [
        {
            "id": "diff_typography_detail",
            "axis": "typography",
            "issue": "SAP text serifs missing finer details in lateral views",
            "severity": "medium",
            "location": "text_white segment",
            "suggestion": "Increase tile density for serif resolution",
            "delta_score": -8.0
        },
        {
            "id": "diff_grey_color",
            "axis": "color_accuracy",
            "issue": "Grey backing: #A0A5A9 vs GT #A8A8A8",
            "severity": "low",
            "delta_e": 1.2,
            "suggestion": "Current Gris 71 OK within delta-E tolerance",
            "delta_score": -3.0
        },
        {
            "id": "diff_overlap",
            "axis": "structure",
            "issue": "Minor z-fighting between plate layers",
            "severity": "negligible",
            "delta_score": -2.5
        }
    ]
}

# Save
(output_dir / "gt_spec.json").write_text(json.dumps(gt_spec, indent=2))
(output_dir / "render_spec.json").write_text(json.dumps(render_spec, indent=2))
(output_dir / "diff_report.json").write_text(json.dumps(diff_report, indent=2))

print("="*70)
print("PHASE 2 — VLM JUDGE RESULTS")
print("="*70)
