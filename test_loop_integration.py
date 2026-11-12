#!/usr/bin/env python3
"""Test loop integration with structural diff."""
import json
from pathlib import Path
import sys
sys.path.insert(0, '/Users/I764690/Code_personal/LdrawNova')

from scripts.bench.loop_structural_diff_integration import compute_structural_diffs_for_loop, inject_structural_feedback

print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║        FASE C: LOOP INTEGRATION TEST (Structural Diff)          ║
╚═══════════════════════════════════════════════════════════════════════════════╝
""")

io_path = Path('/tmp/phase_a_test/OMR-30103-1.io')
mpd_gen_path = Path('/tmp/phase_a_test/OMR-30103-1_generated.mpd')
output_dir = Path('/tmp/phase_c_test')
output_dir.mkdir(exist_ok=True)

# Check if test files exist
if not io_path.exists():
    print(f"❌ IO file not found: {io_path}")
    print(f"   Creating dummy for demo...\n")
    # For demo, use the GT json we have as source
    gt_path = Path('/tmp/phase_a_test/OMR-30103-1_assembly_graph_GT.json')
    if gt_path.exists():
        io_path = gt_path
    else:
        print(f"   No test data available, skipping test\n")
        sys.exit(1)

if not mpd_gen_path.exists():
    print(f"⚠️  MPD gen file not found: {mpd_gen_path}")
    print(f"   Using IO as both for demo...\n")
    mpd_gen_path = io_path

print(f"💫 INPUT")
print(f"  GT source:     {io_path}")
print(f"  Gen source:    {mpd_gen_path}")
print(f"  Output dir:    {output_dir}\n")

try:
    # Step 1: Compute structural diffs
    print("🔄 Computing structural diffs...\n")
    structural_result = compute_structural_diffs_for_loop(
        io_path,
        mpd_gen_path,
        "OMR-30103-1",
        output_dir
    )
    
    print(f"📊 STRUCTURAL DIFF RESULT")
    print(f"  Overall score:     {structural_result['scores']['overall_score']:.1f}/100")
    print(f"  BOM score:         {structural_result['scores']['bom_score']:.1f}/100")
    print(f"  Edge score:        {structural_result['scores']['edge_score']:.1f}/100")
    print(f"  Stud score:        {structural_result['scores']['stud_score']:.1f}/100")
    print(f"  Total diffs:       {structural_result['summary']['total_diffs']}")
    print(f"  Max severity:      {structural_result['summary']['max_severity']}\n")
    
    # Step 2: Simulate A4 report
    print("🔐 Simulating A4 report...\n")
    a4_report = {
        "global_score": 78.0,
        "diffs": [
            {
                "type": "visual_mismatch",
                "severity": 3,
                "description": "Proportions slightly off",
            },
            {
                "type": "color_palette",
                "severity": 2,
                "description": "Secondary colors need adjustment",
            }
        ],
        "per_axis_scores": {"proportions": 80, "colors": 75, "symmetry": 82}
    }
    
    print(f"  A4 score:          {a4_report['global_score']:.1f}/100")
    print(f"  A4 diffs:          {len(a4_report['diffs'])}")
    print(f"  A4 sources:        {list(a4_report.keys())}\n")
    
    # Step 3: Blend reports
    print("🔐 Blending structural + A4 feedback...\n")
    blended_report = inject_structural_feedback(
        a4_report,
        structural_result,
        weight_structural=0.4,
        weight_a4=0.6,
    )
    
    print(f"✅ BLENDED REPORT")
    print(f"  Original A4 score:    {a4_report['global_score']:.1f}/100")
    print(f"  Structural score:     {structural_result['scores']['overall_score']:.1f}/100")
    print(f"  Blended score:        {blended_report['global_score']:.1f}/100")
    print(f"  Total diffs:          {len(blended_report['diffs'])}")
    print(f"\n  Top diffs after blend:")
    for diff in blended_report['diffs'][:5]:
        sev_name = {5: 'CRITICAL', 4: 'HIGH', 3: 'MEDIUM-H', 2: 'MEDIUM', 1: 'LOW'}.get(diff['severity'], 'UNK')
        source = diff.get('source', 'a4')
        print(f"    [{sev_name:10s}] [{source:15s}] {diff['type']}: {diff['description'][:45]}")
    
    # Step 4: Save result
    result_path = output_dir / 'blended_report.json'
    with open(result_path, 'w') as f:
        json.dump(blended_report, f, indent=2, default=str)
    
    meta = blended_report.get('_meta', {})
    print(f"\n📊 INTEGRATION METADATA")
    print(f"  Weight structural:    {meta.get('weight_structural', 0.0):.1f}")
    print(f"  Weight A4:            {meta.get('weight_a4', 0.0):.1f}")
    print(f"  Structural diffs:     {meta.get('structural_diffs_count', 0)}")
    
    print(f"\n✅ Blended report saved: {result_path}")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("")
