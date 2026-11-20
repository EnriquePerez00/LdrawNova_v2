"""F1 — GT materialisation driver for a whole split.

Renders every step of every sample in a split (as defined in
``output/bench/dataset/splits.json``) into ``output/bench/gt/`` and writes the
oracle specs next to each step.

The driver is:

* **resumable** — a step whose 4 PNGs already exist is skipped, so the run
  can be interrupted and restarted without losing work;
* **parallel** — samples are processed in a process pool, because LeoCAD is
  the bottleneck (3–40 s per step depending on part count);
* **instrumented** — a per-sample ``timings.json`` and a global
  ``gt_report.json`` capture wall-clock, per-bucket totals and every issue.

Usage
-----

.. code-block:: console

    # dev split, 8 workers
    python -m scripts.bench.render_split --split dev --workers 8

    # a single bucket, to calibrate timings
    python -m scripts.bench.render_split --split dev --bucket trivial --workers 4
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from scripts.bench import config
from scripts.bench.io_loader import sample_id_from_path
from scripts.bench.render_gt import render_sample
from scripts.bench.synth_render_spec import write_all_render_specs_for_sample
from scripts.bench.synth_spec import write_all_specs_for_sample

logger = logging.getLogger("bench.render_split")

__all__ = ["SplitRenderResult", "render_split", "main"]


@dataclass
class SplitRenderResult:
    sample_id: str
    bucket: str
    step_count: int
    parts_count_total: int
    duration_ms: int
    steps_rendered: int
    steps_cached: int
    steps_skipped: int
    issues: List[str]


def _process_sample(args_tuple) -> SplitRenderResult:
    """Worker: materialise one sample (renders + oracle specs).

    Must be module-level (picklable) for :class:`ProcessPoolExecutor`.
    """
    io_path_str, out_root_str, sample_id, bucket, max_steps, force, max_parts = args_tuple
    io_path = Path(io_path_str)
    out_root = Path(out_root_str)

    t0 = time.perf_counter()
    issues: List[str] = []

    res = render_sample(
        io_path, out_root, max_steps=max_steps, force=force,
    )

    rendered = cached = skipped = 0
    for s in res.steps:
        if s.skipped_too_large:
            skipped += 1
            issues.append(
                f"step_{s.step_idx}: skipped render ({s.parts_count_cum} parts > cap)"
            )
        elif s.reused_cached:
            cached += 1
        else:
            rendered += 1
            if not s.rendered_views:
                issues.append(f"step_{s.step_idx}: no views rendered")

    # Oracle specs (both flavours) for every step.
    spec_paths = write_all_specs_for_sample(io_path, out_root, max_steps=max_steps)
    rspec_paths = write_all_render_specs_for_sample(io_path, out_root, max_steps=max_steps)

    if len(spec_paths) != len(res.steps) or len(rspec_paths) != len(res.steps):
        issues.append(
            f"spec/render_spec count mismatch: steps={len(res.steps)} "
            f"specs={len(spec_paths)} render_specs={len(rspec_paths)}"
        )

    # Per-sample metadata.
    sample_dir = out_root / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "sample_id": sample_id,
        "bucket": bucket,
        "source_io": str(io_path),
        "step_count": res.step_count,
        "parts_count_total": res.steps[-1].parts_count_cum if res.steps else 0,
        "max_steps_cap": max_steps,
        "steps": [
            {
                "step_idx": s.step_idx,
                "parts_count_cum": s.parts_count_cum,
                "parts_count_new": (
                    s.parts_count_cum - (res.steps[i - 1].parts_count_cum if i else 0)
                ),
                "rendered": bool(s.rendered_views),
                "skipped_too_large": s.skipped_too_large,
                "render_ms": s.render_ms,
            }
            for i, s in enumerate(res.steps)
        ],
    }
    (sample_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    timings = {
        "sample_id": sample_id,
        "bucket": bucket,
        "step_count": res.step_count,
        "parts_count_total": meta["parts_count_total"],
        "duration_ms": int((time.perf_counter() - t0) * 1000),
        "render_total_ms": res.total_ms,
        "steps_rendered": rendered,
        "steps_cached": cached,
        "steps_skipped": skipped,
        "issues": issues,
    }
    (sample_dir / "timings.json").write_text(json.dumps(timings, indent=2), encoding="utf-8")

    return SplitRenderResult(
        sample_id=sample_id,
        bucket=bucket,
        step_count=res.step_count,
        parts_count_total=meta["parts_count_total"],
        duration_ms=timings["duration_ms"],
        steps_rendered=rendered,
        steps_cached=cached,
        steps_skipped=skipped,
        issues=issues,
    )


def render_split(
    split: str,
    *,
    splits_path: Optional[Path] = None,
    out_root: Optional[Path] = None,
    bucket: Optional[str] = None,
    workers: int = 4,
    max_steps: Optional[int] = None,
    force: bool = False,
    limit: Optional[int] = None,
) -> Dict[str, object]:
    """Materialise the GT for a whole split. Returns a report dict."""
    splits_path = splits_path or (config.OUTPUT_DATASET / "splits.json")
    out_root = out_root or config.OUTPUT_GT

    data = json.loads(splits_path.read_text())
    if split not in data["splits"]:
        raise RuntimeError(f"Unknown split {split!r}; have {list(data['splits'])}")
    sample_meta = data["samples"]

    ids: List[str] = list(data["splits"][split])
    if bucket:
        ids = [i for i in ids if sample_meta[i]["bucket"] == bucket]
    if limit is not None:
        ids = ids[:limit]

    jobs = []
    skipped_oversized: List[Dict[str, object]] = []
    for sid in ids:
        meta = sample_meta[sid]
        parts = int(meta.get("parts_count", 0))
        if parts > config.MAX_PARTS_PER_SAMPLE:
            skipped_oversized.append({
                "sample_id": sid,
                "bucket": meta["bucket"],
                "parts_count": parts,
                "step_count": meta["step_count"],
            })
            continue
        jobs.append((
            meta["source_io"], str(out_root), sid, meta["bucket"], max_steps, force,
            config.MAX_PARTS_PER_SAMPLE,
        ))

    out_root.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    results: List[SplitRenderResult] = []
    if workers <= 1:
        for i, job in enumerate(jobs, 1):
            r = _process_sample(job)
            results.append(r)
            logger.info(
                "[%s %d/%d] %s (%s, %d steps) %.1fs issues=%d",
                split, i, len(jobs), r.sample_id, r.bucket, r.step_count,
                r.duration_ms / 1000, len(r.issues),
            )
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_process_sample, job): job for job in jobs}
            for i, fut in enumerate(as_completed(futures), 1):
                job = futures[fut]
                sid, job_bucket = job[2], job[3]
                try:
                    r = fut.result()
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "[%s %d/%d] %s FAILED: %r", split, i, len(jobs), sid, exc,
                    )
                    results.append(SplitRenderResult(
                        sample_id=sid, bucket=job_bucket, step_count=0,
                        parts_count_total=0, duration_ms=0, steps_rendered=0,
                        steps_cached=0, steps_skipped=0,
                        issues=[f"worker_failed: {exc!r}"],
                    ))
                    continue
                results.append(r)
                logger.info(
                    "[%s %d/%d] %s (%s, %d steps) %.1fs issues=%d",
                    split, i, len(jobs), r.sample_id, r.bucket, r.step_count,
                    r.duration_ms / 1000, len(r.issues),
                )

    wall_ms = int((time.perf_counter() - t0) * 1000)

    by_bucket: Dict[str, Dict[str, object]] = {}
    for r in results:
        b = by_bucket.setdefault(r.bucket, {
            "samples": 0, "steps": 0, "duration_ms": 0, "issues": 0,
        })
        b["samples"] = int(b["samples"]) + 1
        b["steps"] = int(b["steps"]) + r.step_count
        b["duration_ms"] = int(b["duration_ms"]) + r.duration_ms
        b["issues"] = int(b["issues"]) + len(r.issues)

    report = {
        "split": split,
        "bucket_filter": bucket,
        "workers": workers,
        "max_steps": max_steps,
        "max_parts_per_sample": config.MAX_PARTS_PER_SAMPLE,
        "max_parts_per_step_render": config.MAX_PARTS_PER_STEP_RENDER,
        "wall_ms": wall_ms,
        "samples_requested": len(ids),
        "samples_submitted": len(jobs),
        "samples_completed": len(results),
        "samples_skipped_oversized": skipped_oversized,
        "total_steps": sum(r.step_count for r in results),
        "steps_rendered": sum(r.steps_rendered for r in results),
        "steps_cached": sum(r.steps_cached for r in results),
        "steps_skipped_too_large": sum(r.steps_skipped for r in results),
        "samples_with_issues": sum(1 for r in results if r.issues),
        "by_bucket": by_bucket,
        "per_sample": [
            {
                "sample_id": r.sample_id,
                "bucket": r.bucket,
                "step_count": r.step_count,
                "parts_count_total": r.parts_count_total,
                "duration_ms": r.duration_ms,
                "steps_rendered": r.steps_rendered,
                "steps_cached": r.steps_cached,
                "steps_skipped": r.steps_skipped,
                "issues": r.issues,
            }
            for r in sorted(results, key=lambda x: x.sample_id)
        ],
    }
    report_path = out_root / f"gt_report_{split}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("[%s] wrote %s", split, report_path)
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Materialise GT renders + oracle specs for a split.")
    parser.add_argument("--split", required=True, choices=["dev", "eval", "holdout"])
    parser.add_argument("--splits", type=Path, default=config.OUTPUT_DATASET / "splits.json")
    parser.add_argument("--out", type=Path, default=config.OUTPUT_GT)
    parser.add_argument("--bucket", default=None, choices=list(config.BUCKET_ORDER) + [config.NO_STEPS_BUCKET])
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) // 2))
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    report = render_split(
        args.split,
        splits_path=args.splits,
        out_root=args.out,
        bucket=args.bucket,
        workers=args.workers,
        max_steps=args.max_steps,
        force=args.force,
        limit=args.limit,
    )

    print(f"\n=== {args.split} ===")
    print(f"samples completed : {report['samples_completed']}/{report['samples_requested']}")
    print(f"steps total       : {report['total_steps']}")
    print(f"  rendered        : {report['steps_rendered']}")
    print(f"  cached          : {report['steps_cached']}")
    print(f"  skipped (cap)   : {report['steps_skipped_too_large']}")
    print(f"wall time         : {report['wall_ms']/1000:.1f}s")
    print(f"samples w/issues  : {report['samples_with_issues']}")
    print("by bucket:")
    for b, v in report["by_bucket"].items():
        print(f"  {b:10s} samples={v['samples']:4d} steps={v['steps']:6d} "
              f"cpu={v['duration_ms']/1000:8.1f}s issues={v['issues']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
