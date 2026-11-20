"""F0 smoke harness for the benchmark pipeline.

Incremental validation on a handful of ``.io`` files before touching the
full 927-file corpus. Produces, per sample:

    output/bench/smoke/<ts>/<sample_id>/
        step_<k>/design_GT.ldr
        step_<k>/spec_oracle.json
        step_<k>/render_spec_oracle.json
        step_<k>/renders/{home,front,right,top}.png
        meta.json
        timings.json

And, per run:

    output/bench/smoke/<ts>/manifest.json

Usage
-----

.. code-block:: console

    # F0a-1: one trivial sample
    python -m scripts.bench.smoke --bucket trivial --n 1 --seed 0

    # F0a-2: two trivial samples (reuses cached, adds more)
    python -m scripts.bench.smoke --bucket trivial --n 2 --seed 1

    # F0b: one simple sample
    python -m scripts.bench.smoke --bucket simple --n 1 --seed 0

    # F0d: one complex sample, cap steps
    python -m scripts.bench.smoke --bucket complex --n 1 --max-steps 10

The timestamp is fixed per invocation; pass ``--ts`` to pin a shared
timestamp across multiple sub-phases (so they all write into the same
run directory).
"""
from __future__ import annotations

import argparse
import json
import hashlib
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from scripts.bench import config
from scripts.bench.io_loader import (
    count_steps,
    load_io_steps,
    sample_id_from_path,
)
from scripts.bench.render_gt import render_sample
from scripts.bench.synth_spec import write_all_specs_for_sample
from scripts.bench.synth_render_spec import write_all_render_specs_for_sample

logger = logging.getLogger("bench.smoke")


# ---------------------------------------------------------------------------
# Sample selection
# ---------------------------------------------------------------------------

@dataclass
class SampleCandidate:
    path: Path
    step_count: int
    bucket: str


def select_samples(
    bucket: str,
    n: int,
    seed: int,
    *,
    io_dir: Path = config.IO_SOURCE_DIR,
    exclude: Optional[set[str]] = None,
) -> List[SampleCandidate]:
    """Pick ``n`` ``.io`` files from the requested bucket.

    Deterministic given ``(bucket, seed)``. ``exclude`` is a set of sample
    IDs already processed in this smoke run (so F0a-2 doesn't pick F0a-1's
    sample again).
    """
    exclude = exclude or set()
    rng = random.Random(f"{bucket}|{seed}")
    files = sorted(io_dir.glob("*.io"))
    if not files:
        raise RuntimeError(f"No .io files under {io_dir}")

    # Partition by bucket using the quick count (fast; avoids full parse).
    candidates: List[SampleCandidate] = []
    for p in files:
        if sample_id_from_path(p) in exclude:
            continue
        sc = count_steps(p)
        if sc is None:
            continue
        b = config.classify_bucket(sc)
        if b != bucket:
            continue
        candidates.append(SampleCandidate(path=p, step_count=sc, bucket=b))
        # We only need to keep scanning if we haven't got enough variety;
        # shuffling the full list and drawing n is more deterministic.

    if len(candidates) < n:
        raise RuntimeError(
            f"Bucket {bucket!r} has only {len(candidates)} candidates "
            f"(need {n}). Try a different bucket or lower --n."
        )
    rng.shuffle(candidates)
    return candidates[:n]


# ---------------------------------------------------------------------------
# Per-sample smoke
# ---------------------------------------------------------------------------

@dataclass
class SampleSmokeResult:
    sample_id: str
    bucket: str
    source_io: Path
    sample_dir: Path
    step_count: int
    parts_count_total: int
    timings: Dict[str, object]
    artifacts: Dict[str, object]
    issues: List[str]


def _duplicate_views(render_dir: Path) -> List[str]:
    """Return the view names whose PNG is byte-identical to another view.

    Guards against a regression where the LeoCAD camera argument is silently
    ignored and all 4 views render the same default camera (F0 report §3.1).
    Returns the names of the views involved in a duplicate group.
    """
    digests: Dict[str, str] = {}
    for view in ("home", "front", "right", "top"):
        p = Path(render_dir) / f"{view}.png"
        if not p.exists():
            continue
        digests[view] = hashlib.md5(p.read_bytes()).hexdigest()
    counts: Dict[str, List[str]] = {}
    for view, d in digests.items():
        counts.setdefault(d, []).append(view)
    dupes: List[str] = []
    for group in counts.values():
        if len(group) > 1:
            dupes.extend(sorted(group))
    return sorted(dupes)


def smoke_one_sample(
    candidate: SampleCandidate,
    run_dir: Path,
    *,
    max_steps: Optional[int] = None,
    force: bool = False,
) -> SampleSmokeResult:
    sample_id = sample_id_from_path(candidate.path)
    sample_dir = run_dir / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)

    issues: List[str] = []
    timings: Dict[str, object] = {}

    # 1. Load (already done inside render_sample but kept here for timing).
    t0 = time.perf_counter()
    blocks = load_io_steps(candidate.path)
    load_ms = int((time.perf_counter() - t0) * 1000)
    timings["load_io_ms"] = load_ms

    if max_steps is not None:
        effective_blocks = blocks[:max_steps]
    else:
        effective_blocks = blocks
    parts_total = effective_blocks[-1].parts_count_cum if effective_blocks else 0

    # 2. Render (serialises .ldr + 4 views per step).
    t0 = time.perf_counter()
    render_res = render_sample(
        candidate.path, run_dir, max_steps=max_steps, force=force,
    )
    render_total_ms = int((time.perf_counter() - t0) * 1000)
    timings["render_gt_total_ms"] = render_total_ms
    timings["render_gt_per_step_ms"] = [s.duration_ms for s in render_res.steps]
    timings["render_gt_per_step_render_only_ms"] = [s.render_ms for s in render_res.steps]
    timings["render_gt_per_step_parts_cum"] = [s.parts_count_cum for s in render_res.steps]
    timings["render_gt_per_step_reused_cached"] = [s.reused_cached for s in render_res.steps]
    timings["render_gt_per_step_skipped_too_large"] = [s.skipped_too_large for s in render_res.steps]

    for s in render_res.steps:
        if s.skipped_too_large:
            issues.append(f"step_{s.step_idx}: skipped render ({s.parts_count_cum} parts > cap)")
        elif not s.reused_cached and not s.rendered_views:
            issues.append(f"step_{s.step_idx}: no views rendered")
        else:
            dupes = _duplicate_views(s.render_dir)
            if dupes:
                issues.append(
                    f"step_{s.step_idx}: identical views {dupes} "
                    f"(camera preset not applied?)"
                )

    # 3. Oracle specs.
    t0 = time.perf_counter()
    spec_paths = write_all_specs_for_sample(candidate.path, run_dir, max_steps=max_steps)
    timings["synth_spec_total_ms"] = int((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    rspec_paths = write_all_render_specs_for_sample(candidate.path, run_dir, max_steps=max_steps)
    timings["synth_render_spec_total_ms"] = int((time.perf_counter() - t0) * 1000)

    # 4. meta.json per sample.
    meta = {
        "sample_id": sample_id,
        "bucket": candidate.bucket,
        "source_io": str(candidate.path),
        "step_count_raw": candidate.step_count,
        "step_count_effective": len(effective_blocks),
        "parts_count_total_effective": parts_total,
        "parts_per_step_new": [b.parts_count_new for b in effective_blocks],
        "parts_per_step_cum": [b.parts_count_cum for b in effective_blocks],
        "max_steps_cap": max_steps,
    }
    (sample_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # 5. timings.json per sample.
    artifacts = {
        "meta": str(sample_dir / "meta.json"),
        "timings": str(sample_dir / "timings.json"),
        "ldr_files": [str(s.ldr_path) for s in render_res.steps],
        "render_dirs": [str(s.render_dir) for s in render_res.steps],
        "spec_oracle_files": [str(p) for p in spec_paths],
        "render_spec_oracle_files": [str(p) for p in rspec_paths],
    }
    timings_doc = {
        "sample_id": sample_id,
        "bucket": candidate.bucket,
        "step_count": len(effective_blocks),
        "parts_count_total": parts_total,
        "stages": timings,
        "artifacts": artifacts,
        "issues": issues,
    }
    (sample_dir / "timings.json").write_text(json.dumps(timings_doc, indent=2), encoding="utf-8")

    return SampleSmokeResult(
        sample_id=sample_id,
        bucket=candidate.bucket,
        source_io=candidate.path,
        sample_dir=sample_dir,
        step_count=len(effective_blocks),
        parts_count_total=parts_total,
        timings=timings,
        artifacts=artifacts,
        issues=issues,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _run_dir_for(ts: str) -> Path:
    return config.OUTPUT_SMOKE / ts


def _load_manifest(run_dir: Path) -> Dict[str, object]:
    p = run_dir / "manifest.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            logger.warning("manifest.json unreadable; starting fresh")
    return {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "runs": [],  # list of {phase, bucket, n, seed, sample_ids, started_at}
        "samples": {},  # sample_id -> summary dict
    }


def _save_manifest(run_dir: Path, manifest: Dict[str, object]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _cli() -> int:
    parser = argparse.ArgumentParser(description="F0 smoke harness: process N .io files from a bucket.")
    parser.add_argument("--bucket", required=True, choices=list(config.BUCKET_ORDER) + [config.NO_STEPS_BUCKET])
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--ts", type=str, default=None,
                        help="Shared run timestamp (defaults to current UTC). Use the same --ts across sub-phases to share a run dir.")
    parser.add_argument("--max-steps", type=int, default=None,
                        help="Cap the number of steps per sample (useful for complex bucket).")
    parser.add_argument("--force", action="store_true", help="Regenerate cached renders.")
    parser.add_argument("--io-dir", type=Path, default=config.IO_SOURCE_DIR)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    config.validate_io_source()

    ts = args.ts or datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = _run_dir_for(ts)
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = _load_manifest(run_dir)
    already_in_run = set(manifest["samples"].keys())  # type: ignore[arg-type]

    try:
        candidates = select_samples(
            args.bucket, args.n, args.seed,
            io_dir=args.io_dir, exclude=already_in_run,
        )
    except RuntimeError as exc:
        logger.error("Candidate selection failed: %s", exc)
        return 2

    phase_record = {
        "started_at": datetime.utcnow().isoformat() + "Z",
        "bucket": args.bucket,
        "n": args.n,
        "seed": args.seed,
        "max_steps": args.max_steps,
        "sample_ids": [sample_id_from_path(c.path) for c in candidates],
    }

    print(f"\n=== F0 smoke run ts={ts} bucket={args.bucket} n={args.n} seed={args.seed} ===")
    for cand in candidates:
        sid = sample_id_from_path(cand.path)
        print(f"\n--- processing {sid} (bucket={cand.bucket}, step_count={cand.step_count}) ---")
        res = smoke_one_sample(cand, run_dir, max_steps=args.max_steps, force=args.force)
        print(f"    step_count_effective = {res.step_count}")
        print(f"    parts_total          = {res.parts_count_total}")
        print(f"    total_render_ms      = {res.timings.get('render_gt_total_ms')}")
        print(f"    issues               = {res.issues or 'none'}")
        manifest["samples"][sid] = {  # type: ignore[index]
            "bucket": res.bucket,
            "step_count": res.step_count,
            "parts_count_total": res.parts_count_total,
            "render_gt_total_ms": res.timings.get("render_gt_total_ms"),
            "synth_spec_total_ms": res.timings.get("synth_spec_total_ms"),
            "synth_render_spec_total_ms": res.timings.get("synth_render_spec_total_ms"),
            "issues": res.issues,
            "sample_dir": str(res.sample_dir),
        }

    manifest["runs"].append(phase_record)  # type: ignore[attr-defined]
    _save_manifest(run_dir, manifest)
    print(f"\nmanifest: {run_dir / 'manifest.json'}")
    print(f"TS={ts}  (pass --ts {ts} to stack more sub-phases into the same run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
