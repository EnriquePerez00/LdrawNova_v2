#!/usr/bin/env python3
"""
Build the agent training and holdout corpus splits.

Audits available (pdf, io) pairs from two sources:
  1. data/dataset_splits/corpus_all_pairs.json  — 684 OFFICIAL_OMR entries
     (fields: moc_id, io_path, parts_count, complexity_tier, category)
  2. data/catalog/models_catalog.db             — alternate_builds table with
     source='rebrickable_alt', has pdf_file_path + io_file_path columns

Outputs:
  - data/eval/agent_corpus_audit.json   — full audit with pdf_available flag
  - data/eval/agent_train_micro.json    — ≤20 MICRO pairs (≤50 parts) with PDF
  - data/eval/agent_holdout_50.json     — ≤50 holdout pairs stratified by tier

Usage:
  .venv/bin/python scripts/build_agent_training_corpus.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

CORPUS_JSON = os.path.join(REPO_ROOT, "data/dataset_splits/corpus_all_pairs.json")
DB_PATH = os.path.join(REPO_ROOT, "data/catalog/models_catalog.db")
MANUALS_DIR = os.path.join(REPO_ROOT, "data/manuals")
OUTPUT_DIR = os.path.join(REPO_ROOT, "data/eval")

# Tier definitions (parts_count ranges used for stratification)
TIER_MICRO = "MICRO"    # 1–50 parts
TIER_SMALL = "SMALL"    # 51–150 parts
TIER_MEDIUM = "MEDIUM"  # 151–400 parts
TIER_LARGE = "LARGE"    # 401+ parts

HOLDOUT_COUNT_PER_TIER = 12   # ~50 total across 4 tiers (12*4=48 ≈ 50)
# For tiers with few PDF pairs, reserve at least this many for training
MIN_TRAIN_PER_TIER = {"MICRO": 2, "SMALL": 10, "MEDIUM": 5, "LARGE": 3}
TRAIN_MICRO_MAX = 20


def infer_tier(parts_count: int, existing_tier: str = "") -> str:
    """Infer complexity tier from parts count if not already set."""
    if existing_tier and existing_tier.upper() in (TIER_MICRO, TIER_SMALL, TIER_MEDIUM, TIER_LARGE):
        return existing_tier.upper()
    if parts_count <= 50:
        return TIER_MICRO
    if parts_count <= 150:
        return TIER_SMALL
    if parts_count <= 400:
        return TIER_MEDIUM
    return TIER_LARGE


def resolve_pdf_for_io(io_path: str, moc_id: str) -> Optional[str]:
    """Try to find a PDF for a given .io path."""
    # 1. Same directory, same stem
    candidate = os.path.splitext(io_path)[0] + ".pdf"
    if os.path.exists(candidate):
        return candidate
    # 2. data/manuals/<moc_id>.pdf
    from_manuals = os.path.join(MANUALS_DIR, f"{moc_id}.pdf")
    if os.path.exists(from_manuals):
        return from_manuals
    # 3. data/manuals/<basename>.pdf (without set suffix like -1)
    base = os.path.basename(os.path.splitext(io_path)[0])
    base_manuals = os.path.join(MANUALS_DIR, f"{base}.pdf")
    if os.path.exists(base_manuals):
        return base_manuals
    return None


def load_corpus_json() -> List[Dict[str, Any]]:
    """Load entries from corpus_all_pairs.json."""
    if not os.path.exists(CORPUS_JSON):
        print(f"[WARN] corpus_all_pairs.json not found at {CORPUS_JSON}")
        return []
    with open(CORPUS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("pairs", data.get("entries", []))
    return []


def load_db_moc_pairs() -> List[Dict[str, Any]]:
    """Load MOC alternate_builds entries from the SQLite catalog."""
    if not os.path.exists(DB_PATH):
        print(f"[WARN] models_catalog.db not found at {DB_PATH}")
        return []
    pairs: List[Dict[str, Any]] = []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # Only select entries that have BOTH pdf_file_path and io_file_path populated
        cur.execute(
            "SELECT * FROM alternate_builds WHERE source='rebrickable_alt' AND pdf_file_path IS NOT NULL AND io_file_path IS NOT NULL"
        )
        rows = cur.fetchall()
        conn.close()
        for row in rows:
            d = dict(row)
            io_path = (
                d.get("io_file_path")
                or d.get("io_path")
                or d.get("file_path")
                or ""
            )
            pdf_path = (
                d.get("pdf_file_path")
                or d.get("pdf_path")
                or d.get("pdf_url")
                or ""
            )
            moc_id = str(
                d.get("moc_id")
                or d.get("set_num")
                or d.get("set_id")
                or os.path.splitext(os.path.basename(io_path))[0]
            )
            parts_count = int(d.get("num_parts") or d.get("parts_count") or d.get("piece_count") or 0)
            tier = infer_tier(parts_count, str(d.get("complexity_tier", "")))
            if io_path:
                pairs.append({
                    "moc_id": moc_id,
                    "io_path": io_path,
                    "pdf_path": pdf_path,
                    "parts_count": parts_count,
                    "complexity_tier": tier,
                    "source": "db_rebrickable_alt",
                })
    except Exception as e:
        print(f"[WARN] DB load failed: {e}")
    return pairs


def audit_pairs(raw_pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Resolve PDF presence, normalise tiers, and annotate each pair."""
    audited: List[Dict[str, Any]] = []
    for p in raw_pairs:
        io_path = str(p.get("io_path", ""))
        moc_id = str(p.get("moc_id", ""))
        parts_count = int(p.get("parts_count", 0))
        tier = infer_tier(parts_count, str(p.get("complexity_tier", "")))

        # Resolve absolute path for io
        if io_path and not os.path.isabs(io_path):
            io_path = os.path.join(REPO_ROOT, io_path)

        io_exists = os.path.exists(io_path) if io_path else False

        # Resolve PDF
        pdf_path = str(p.get("pdf_path", ""))
        if not pdf_path or not os.path.exists(pdf_path):
            pdf_path = resolve_pdf_for_io(io_path, moc_id) or ""
        pdf_exists = bool(pdf_path and os.path.exists(pdf_path))

        audited.append({
            "moc_id": moc_id,
            "io_path": io_path,
            "pdf_path": pdf_path,
            "parts_count": parts_count,
            "complexity_tier": tier,
            "io_exists": io_exists,
            "pdf_available": pdf_exists,
            "source": p.get("source", "corpus_json"),
            "category": p.get("category", ""),
        })
    return audited


def stratified_sample(
    pairs: List[Dict[str, Any]], n_per_tier: int, seed: int = 42
) -> List[Dict[str, Any]]:
    """Sample up to n_per_tier pairs per tier, only from pdf_available=True entries.
    
    Reserves MIN_TRAIN_PER_TIER pairs per tier for training.
    """
    rng = random.Random(seed)
    by_tier: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for p in pairs:
        if p["pdf_available"] and p["io_exists"]:
            by_tier[p["complexity_tier"]].append(p)
    result: List[Dict[str, Any]] = []
    for tier in (TIER_MICRO, TIER_SMALL, TIER_MEDIUM, TIER_LARGE):
        pool = by_tier.get(tier, [])
        rng.shuffle(pool)
        # Reserve minimum for training
        min_train = MIN_TRAIN_PER_TIER.get(tier, 0)
        max_holdout = max(0, len(pool) - min_train)
        take = min(n_per_tier, max_holdout, len(pool))
        result.extend(pool[:take])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build agent training/holdout corpus splits")
    parser.add_argument("--dry-run", action="store_true", help="Print stats without writing files")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    args = parser.parse_args()

    print("=== Loading source data ===")
    corpus_pairs = load_corpus_json()
    print(f"  corpus_all_pairs.json: {len(corpus_pairs)} entries")

    db_pairs = load_db_moc_pairs()
    print(f"  DB alternate_builds:   {len(db_pairs)} entries")

    # Merge and deduplicate by moc_id
    all_raw: Dict[str, Dict[str, Any]] = {}
    for p in corpus_pairs:
        p["source"] = "corpus_json"
        all_raw[str(p.get("moc_id", ""))] = p
    for p in db_pairs:
        mid = str(p.get("moc_id", ""))
        if mid not in all_raw:
            all_raw[mid] = p
        elif p.get("pdf_path") and not all_raw[mid].get("pdf_path"):
            all_raw[mid]["pdf_path"] = p["pdf_path"]

    print(f"  Total unique pairs:    {len(all_raw)}")

    print("\n=== Auditing PDF availability ===")
    audited = audit_pairs(list(all_raw.values()))

    with_pdf = [p for p in audited if p["pdf_available"] and p["io_exists"]]
    print(f"  Pairs with PDF + IO:   {len(with_pdf)} / {len(audited)}")

    # Stats by tier
    tier_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "with_pdf": 0})
    for p in audited:
        tier_counts[p["complexity_tier"]]["total"] += 1
        if p["pdf_available"] and p["io_exists"]:
            tier_counts[p["complexity_tier"]]["with_pdf"] += 1
    print("\n  Tier breakdown (total | with_pdf):")
    for tier in (TIER_MICRO, TIER_SMALL, TIER_MEDIUM, TIER_LARGE):
        tc = tier_counts.get(tier, {"total": 0, "with_pdf": 0})
        print(f"    {tier:8s}: {tc['total']:4d} total, {tc['with_pdf']:4d} with PDF")

    if args.dry_run:
        print("\n[dry-run] No files written.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Write full audit
    audit_path = os.path.join(OUTPUT_DIR, "agent_corpus_audit.json")
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump({"total": len(audited), "with_pdf": len(with_pdf), "pairs": audited}, f, indent=2)
    print(f"\n  Wrote: {audit_path}")

    # holdout: stratified 50 pairs, must NOT overlap with any existing training runs
    holdout = stratified_sample(audited, n_per_tier=HOLDOUT_COUNT_PER_TIER, seed=args.seed)
    holdout_path = os.path.join(OUTPUT_DIR, "agent_holdout_50.json")
    with open(holdout_path, "w", encoding="utf-8") as f:
        json.dump({"count": len(holdout), "pairs": holdout}, f, indent=2)
    print(f"  Wrote: {holdout_path}  ({len(holdout)} pairs)")

    # train_micro: ≤20 MICRO pairs NOT in holdout
    holdout_ids = {p["moc_id"] for p in holdout}
    micro_pool = [
        p for p in audited
        if p["pdf_available"] and p["io_exists"]
        and p["complexity_tier"] == TIER_MICRO
        and p["moc_id"] not in holdout_ids
    ]
    rng = random.Random(args.seed)
    rng.shuffle(micro_pool)
    train_micro = micro_pool[:TRAIN_MICRO_MAX]
    micro_path = os.path.join(OUTPUT_DIR, "agent_train_micro.json")
    with open(micro_path, "w", encoding="utf-8") as f:
        json.dump({"count": len(train_micro), "pairs": train_micro}, f, indent=2)
    print(f"  Wrote: {micro_path}  ({len(train_micro)} pairs)")

    print("\n=== Done ===")
    if len(with_pdf) < 50:
        print(
            f"\n[WARNING] Only {len(with_pdf)} pairs have both PDF and IO. "
            "Training corpus is limited — prioritize oracle geometric training first."
        )


if __name__ == "__main__":
    main()
