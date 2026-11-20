"""Select N distinct MICRO tier sets from splits.json for scale testing.

Returns reproducible list of sets by parts_count and step_count.
"""
import json
from pathlib import Path
from typing import List, Tuple


def select_micro_sets(
    splits_file: Path,
    n: int = 10,
    min_parts: int = 6,
    max_parts: int = 50,
    min_steps: int = 1,
    seed: int = 42,
) -> List[Tuple[str, int, int]]:
    """Select N distinct MICRO sets (parts_count in range, steps > 0).
    
    Args:
        splits_file: Path to splits.json
        n: Number of sets to select
        min_parts: Minimum parts (default 6 for MICRO)
        max_parts: Maximum parts (default 50 for MICRO)
        min_steps: Minimum steps (default 1, any)
        seed: Random seed for reproducibility
    
    Returns:
        List of (sample_id, parts_count, step_count) tuples
    """
    import random
    random.seed(seed)
    
    with open(splits_file) as f:
        splits = json.load(f)
    
    samples = splits.get("samples", {})
    
    # Filter MICRO sets
    micro_sets = []
    for sample_id, meta in samples.items():
        parts = meta.get("parts_count", 0)
        steps = meta.get("step_count", 0)
        
        if min_parts <= parts <= max_parts and steps >= min_steps:
            micro_sets.append((sample_id, parts, steps))
    
    # Sort by parts_count (ascending) for diversity
    micro_sets.sort(key=lambda x: (x[1], x[2]))
    
    # Select first N (reproducible, deterministic)
    selected = micro_sets[:n]
    
    print(f"Selected {len(selected)}/{len(micro_sets)} MICRO sets:")
    for sample_id, parts, steps in selected:
        print(f"  {sample_id}: {parts} parts, {steps} steps")
    
    return selected


def get_io_path(sample_id: str, io_dir: Path) -> Path:
    """Get the .io file path for a sample."""
    io_file = io_dir / f"{sample_id}_normalized.io"
    if not io_file.exists():
        raise FileNotFoundError(f"IO file not found: {io_file}")
    return io_file


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--splits", required=True, help="Path to splits.json")
    parser.add_argument("--io-dir", required=True, help="Path to IO corpus dir")
    parser.add_argument("--n", type=int, default=10, help="Number of sets to select")
    parser.add_argument("--output", help="Output file (optional, just lists to console if omitted)")
    
    args = parser.parse_args()
    
    selected = select_micro_sets(Path(args.splits), n=args.n)
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump([{"sample_id": s[0], "parts": s[1], "steps": s[2]} for s in selected], f, indent=2)
        print(f"\nSaved to {args.output}")
