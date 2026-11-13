#!/usr/bin/env python3
"""
Query the SQLite catalog for ALL PDF+IO pairs in the alternate_builds table,
regardless of whether files exist locally.

Outputs JSON with:
- moc_id, pdf_url/pdf_file_path, io_url/io_file_path, parts_count, complexity_tier, source

Usage:
    .venv/bin/python scripts/query_pdf_io_pairs.py [--output FILE] [--min-parts N] [--max-parts N]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from typing import Any, Dict, List, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(REPO_ROOT, "data/catalog/models_catalog.db")


def infer_tier(parts_count: int, existing_tier: str = "") -> str:
    """Infer complexity tier from parts count if not already set."""
    if existing_tier and existing_tier.upper() in ("MICRO", "SMALL", "MEDIUM", "LARGE"):
        return existing_tier.upper()
    if parts_count <= 50:
        return "MICRO"
    if parts_count <= 150:
        return "SMALL"
    if parts_count <= 400:
        return "MEDIUM"
    return "LARGE"


def query_pdf_io_pairs(
    min_parts: int = 0,
    max_parts: int = 10000,
) -> List[Dict[str, Any]]:
    """Query alternate_builds for entries with both pdf_file_path and io_file_path populated."""
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database not found at {DB_PATH}", file=sys.stderr)
        return []

    pairs: List[Dict[str, Any]] = []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Check what columns exist
        cur.execute("PRAGMA table_info(alternate_builds)")
        columns = {row[1] for row in cur.fetchall()}

        # Build query dynamically based on available columns
        select_cols = []
        for col in [
            "moc_id", "set_num", "set_id", "name",
            "pdf_file_path", "pdf_path", "pdf_url",
            "io_file_path", "io_path", "file_path", "io_url",
            "num_parts", "parts_count", "piece_count",
            "complexity_tier", "category", "source",
            "source_url", "instructions_url",
        ]:
            if col in columns:
                select_cols.append(col)

        if not select_cols:
            print("[ERROR] No recognized columns in alternate_builds table", file=sys.stderr)
            conn.close()
            return []

        query = f"SELECT {', '.join(select_cols)} FROM alternate_builds"
        cur.execute(query)
        rows = cur.fetchall()
        conn.close()

        for row in rows:
            d = dict(row)

            # Extract moc_id
            moc_id = str(
                d.get("moc_id")
                or d.get("set_num")
                or d.get("set_id")
                or ""
            )

            # Extract IO path/URL
            io_path = (
                d.get("io_file_path")
                or d.get("io_path")
                or d.get("file_path")
                or d.get("io_url")
                or ""
            )

            # Extract PDF path/URL
            pdf_path = (
                d.get("pdf_file_path")
                or d.get("pdf_path")
                or d.get("pdf_url")
                or ""
            )

            # Extract parts count (prefer num_parts)
            parts_count = int(d.get("num_parts") or d.get("parts_count") or d.get("piece_count") or 0)

            # Filter by parts range
            if parts_count < min_parts or parts_count > max_parts:
                continue

            # Only include entries that have BOTH pdf and io paths/URLs populated
            if not pdf_path or not io_path:
                continue

            tier = infer_tier(parts_count, str(d.get("complexity_tier", "")))
            source = str(d.get("source", "rebrickable_alt"))

            pairs.append({
                "moc_id": moc_id,
                "pdf_file_path": d.get("pdf_file_path") or d.get("pdf_path") or "",
                "pdf_url": d.get("pdf_url") or "",
                "io_file_path": d.get("io_file_path") or d.get("io_path") or d.get("file_path") or "",
                "io_url": d.get("io_url") or "",
                "parts_count": parts_count,
                "complexity_tier": tier,
                "source": source,
                "category": str(d.get("category", "")),
                "source_url": d.get("source_url") or "",
                "instructions_url": d.get("instructions_url") or "",
            })

    except Exception as e:
        print(f"[ERROR] DB query failed: {e}", file=sys.stderr)
        return []

    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="Query DB for all PDF+IO pairs in alternate_builds")
    parser.add_argument("--output", "-o", type=str, help="Output JSON file (default: stdout)")
    parser.add_argument("--min-parts", type=int, default=0, help="Minimum parts count filter")
    parser.add_argument("--max-parts", type=int, default=10000, help="Maximum parts count filter")
    parser.add_argument("--stats-only", action="store_true", help="Print only summary statistics")
    args = parser.parse_args()

    pairs = query_pdf_io_pairs(min_parts=args.min_parts, max_parts=args.max_parts)

    if args.stats_only:
        tier_counts: Dict[str, int] = {}
        for p in pairs:
            tier_counts[p["complexity_tier"]] = tier_counts.get(p["complexity_tier"], 0) + 1
        print(f"Total pairs with both PDF and IO paths: {len(pairs)}")
        for tier in ("MICRO", "SMALL", "MEDIUM", "LARGE"):
            print(f"  {tier}: {tier_counts.get(tier, 0)}")
        return

    output_data = {
        "total": len(pairs),
        "pairs": pairs,
    }

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
        print(f"Wrote {len(pairs)} pairs to {args.output}")
    else:
        json.dump(output_data, sys.stdout, indent=2)


if __name__ == "__main__":
    main()