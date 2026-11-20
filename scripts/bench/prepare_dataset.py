"""F1 — dataset preparation: classify the .io corpus and build the splits.

Scans every ``.io`` file in :data:`scripts.bench.config.IO_SOURCE_DIR`,
classifies it by ``step_count`` (buckets defined in ``config``), and writes a
stratified ``dev`` / ``eval`` / ``hold-out`` split to
``output/bench/dataset/splits.json``.

A bucket-classification cache (``output/bench/.bucket_cache.json``) is
maintained so repeated invocations do not re-decode every ``model.ldr``
(review finding #4: the corpus scan used to cost O(927 × model.ldr) per run).

Usage
-----

.. code-block:: console

    python -m scripts.bench.prepare_dataset
    python -m scripts.bench.prepare_dataset --no-cache --seed 7
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import statistics
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from scripts.bench import config
from scripts.bench.io_loader import count_steps_and_parts, sample_id_from_path

logger = logging.getLogger("bench.prepare_dataset")

__all__ = ["classify_corpus", "build_splits", "write_splits", "main"]


# ---------------------------------------------------------------------------
# Bucket cache
# ---------------------------------------------------------------------------

def _cache_key(p: Path) -> str:
    st = p.stat()
    return f"{p.name}|{st.st_mtime_ns}|{st.st_size}"


def _load_cache(path: Path) -> Dict[str, int]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        logger.warning("[prepare_dataset] cache unreadable; ignoring")
        return {}
    return raw if isinstance(raw, dict) else {}


def _save_cache(path: Path, cache: Dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=0, sort_keys=True))


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_corpus(
    io_dir: Path,
    *,
    use_cache: bool = True,
    cache_path: Optional[Path] = None,
) -> Tuple[List[Dict[str, object]], List[Dict[str, str]]]:
    """Classify every ``.io`` under ``io_dir``.

    Returns ``(samples, failures)`` where each sample is::

        {"sample_id", "source_io", "step_count", "parts_count",
         "bucket", "size_bytes"}

    and each failure is ``{"sample_id", "source_io", "reason"}``.
    """
    cache_path = cache_path or (config.OUTPUT_ROOT / ".bucket_cache.json")
    cache = _load_cache(cache_path) if use_cache else {}
    dirty = False

    samples: List[Dict[str, object]] = []
    failures: List[Dict[str, str]] = []

    files = sorted(io_dir.glob("*.io"))
    if not files:
        raise RuntimeError(f"No .io files under {io_dir}")

    t0 = time.perf_counter()
    for i, p in enumerate(files):
        sid = sample_id_from_path(p)
        key = _cache_key(p)
        cached = cache.get(key)
        if cached is None:
            counted = count_steps_and_parts(p)
            if counted is not None:
                cached = [counted[0], counted[1]]
                cache[key] = cached
                dirty = True
        if cached is None:
            failures.append({
                "sample_id": sid,
                "source_io": str(p),
                "reason": "unreadable_or_no_model_ldr",
            })
            continue
        sc, parts = int(cached[0]), int(cached[1])
        samples.append({
            "sample_id": sid,
            "source_io": str(p),
            "step_count": sc,
            "parts_count": parts,
            "bucket": config.classify_bucket(sc),
            "render_class": config.classify_render_cost(parts),
            "size_bytes": p.stat().st_size,
        })
        if (i + 1) % 100 == 0:
            logger.info("[prepare_dataset] classified %d/%d", i + 1, len(files))

    if use_cache and dirty:
        _save_cache(cache_path, cache)

    logger.info(
        "[prepare_dataset] classified %d samples (%d failures) in %.1fs",
        len(samples), len(failures), time.perf_counter() - t0,
    )
    return samples, failures


# ---------------------------------------------------------------------------
# Splits
# ---------------------------------------------------------------------------

#: Target size per split (per the plan).
SPLIT_TARGETS: Dict[str, int] = {"dev": 100, "eval": 400, "holdout": 200}


def build_splits(
    samples: List[Dict[str, object]],
    *,
    seed: int = 42,
    targets: Optional[Dict[str, int]] = None,
    include_no_steps: bool = True,
) -> Dict[str, object]:
    """Build a stratified ``dev`` / ``eval`` / ``hold-out`` split.

    Stratification is by bucket. Samples in the ``no_steps`` bucket (no
    ``0 STEP`` markers) are excluded from the curriculum-oriented splits by
    default because they carry no step structure; set ``include_no_steps`` to
    True to include them.

    The split order is fixed (``dev`` → ``eval`` → ``hold-out``) so a sample
    used in ``dev`` can never leak into ``eval`` or ``hold-out``.
    """
    targets = targets or SPLIT_TARGETS
    rng = random.Random(seed)

    by_bucket: Dict[str, List[Dict[str, object]]] = {}
    for s in samples:
        by_bucket.setdefault(str(s["bucket"]), []).append(s)

    # Only the 4 curriculum buckets participate in the stratified quota.
    quota_buckets = [b for b in config.BUCKET_ORDER if b in by_bucket]

    # Allocation order: `dev` → `eval` → `holdout`. `dev` is the gating
    # split and must stay exactly stratified (25/bucket per the plan), so it
    # is served first at its full quota. The scarcer buckets (e.g. `trivial`
    # has 107 samples but the three splits ask for 25 + 100 + 50 = 175) are
    # then split between `eval` and `hold-out` in that priority order, and
    # the remainder lands in `hold-out`.
    priority = ("dev", "eval", "holdout")

    assigned: Dict[str, List[Dict[str, object]]] = {split: [] for split in targets}
    leftovers: Dict[str, List[Dict[str, object]]] = {}
    shortfalls: Dict[str, Dict[str, int]] = {}

    for bucket in quota_buckets:
        pool = list(by_bucket[bucket])
        rng.shuffle(pool)
        cursor = 0
        for split in priority:
            want = targets[split] // len(quota_buckets)
            take = pool[cursor:cursor + want]
            cursor += len(take)
            assigned[split].extend(take)
            if len(take) < want:
                shortfalls.setdefault(split, {})[bucket] = want - len(take)
        leftovers[bucket] = pool[cursor:]

    # Everything not consumed by the per-bucket quotas goes to `holdout`
    # (it is the only split that may be over-quota or unbalanced).
    for bucket in quota_buckets:
        if leftovers.get(bucket):
            assigned["holdout"].extend(leftovers[bucket])
            leftovers[bucket] = []

    # Optional: no_steps samples go to hold-out only (never to dev/eval),
    # so they don't distort the curriculum metrics but remain usable.
    no_steps = list(by_bucket.get(config.NO_STEPS_BUCKET, []))
    rng.shuffle(no_steps)
    if include_no_steps and no_steps:
        assigned["holdout"].extend(no_steps[:targets["holdout"]])

    # Stable ordering in the output.
    for split in assigned:
        assigned[split].sort(key=lambda s: str(s["sample_id"]))

    bucket_counts = {
        split: _count_by_bucket(assigned[split]) for split in assigned
    }

    return {
        "seed": seed,
        "targets": targets,
        "buckets": {
            "thresholds": config.BUCKET_THRESHOLDS,
            "order": list(config.BUCKET_ORDER),
            "no_steps_bucket": config.NO_STEPS_BUCKET,
        },
        "splits": {
            "dev": [str(s["sample_id"]) for s in assigned["dev"]],
            "eval": [str(s["sample_id"]) for s in assigned["eval"]],
            "holdout": [str(s["sample_id"]) for s in assigned["holdout"]],
        },
        "bucket_counts": bucket_counts,
        "shortfalls": shortfalls,
        "samples": {str(s["sample_id"]): s for s in samples},
    }


def _count_by_bucket(rows: List[Dict[str, object]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        b = str(r["bucket"])
        out[b] = out.get(b, 0) + 1
    return dict(sorted(out.items()))


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _histogram(samples: List[Dict[str, object]]) -> str:
    steps = sorted(int(s["step_count"]) for s in samples)
    n = len(steps)
    if n == 0:
        return "(empty)"
    def pct(p: float) -> int:
        return steps[min(n - 1, int(p * n))]
    return (
        f"n={n} min={steps[0]} p10={pct(0.10)} p50={pct(0.50)} "
        f"p90={pct(0.90)} max={steps[-1]} mean={statistics.mean(steps):.1f}"
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Classify the .io corpus and build splits.")
    parser.add_argument("--io-dir", type=Path, default=config.IO_SOURCE_DIR)
    parser.add_argument("--out", type=Path, default=config.OUTPUT_DATASET / "splits.json")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-cache", action="store_true", help="Ignore and do not write the bucket cache.")
    parser.add_argument("--dev", type=int, default=SPLIT_TARGETS["dev"])
    parser.add_argument("--eval", type=int, default=SPLIT_TARGETS["eval"])
    parser.add_argument("--holdout", type=int, default=SPLIT_TARGETS["holdout"])
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    config.validate_io_source()

    samples, failures = classify_corpus(
        args.io_dir, use_cache=not args.no_cache,
    )

    print("\n=== Corpus classification ===")
    print(f"step_count distribution: {_histogram(samples)}")
    counts = _count_by_bucket(samples)
    print("bucket distribution:")
    for b, c in counts.items():
        print(f"  {b:10s} {c}")
    if failures:
        print(f"failures: {len(failures)}")
        for f in failures[:10]:
            print(f"  {f['sample_id']}: {f['reason']}")

    targets = {"dev": args.dev, "eval": args.eval, "holdout": args.holdout}
    splits = build_splits(samples, seed=args.seed, targets=targets)

    print("\n=== Splits ===")
    for split, ids in splits["splits"].items():
        print(f"  {split:8s} n={len(ids):4d} buckets={splits['bucket_counts'][split]}")
    if splits["shortfalls"]:
        print(f"  shortfalls: {splits['shortfalls']}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(splits, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
