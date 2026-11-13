#!/usr/bin/env python3
"""
Parallel downloader for PDF+IO corpus from query_pdf_io_pairs.py output.

Downloads:
- PDFs to data/manuals/{moc_id}.pdf
- IO files to data/mocs/{moc_id}.io

Features:
- Parallel downloads with rate limiting (semaphore)
- Resume capability (skips existing files)
- Progress tracking
- Retry with exponential backoff

Usage:
    .venv/bin/python scripts/download_pdf_io_corpus.py --input data/eval/pdf_io_pairs.json [--workers 8] [--rate-limit 2]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from tqdm.asyncio import tqdm as async_tqdm

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MANUALS_DIR = os.path.join(REPO_ROOT, "data/manuals")
MOCS_DIR = os.path.join(REPO_ROOT, "data/mocs")


@dataclass
class DownloadResult:
    moc_id: str
    pdf_ok: bool
    io_ok: bool
    pdf_error: Optional[str] = None
    io_error: Optional[str] = None


async def download_file(
    session: aiohttp.ClientSession,
    url: str,
    dest_path: Path,
    semaphore: asyncio.Semaphore,
    max_retries: int = 3,
    timeout_sec: int = 60,
) -> tuple[bool, Optional[str]]:
    """Download a single file with retries. Returns (success, error_message)."""
    if dest_path.exists() and dest_path.stat().st_size > 0:
        return True, None

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    async with semaphore:
        for attempt in range(max_retries):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout_sec)) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        if content:
                            dest_path.write_bytes(content)
                            return True, None
                        return False, "Empty response"
                    elif resp.status == 404:
                        return False, f"HTTP 404 Not Found"
                    elif resp.status == 429:
                        wait = min(2 ** attempt * 2, 60)
                        await asyncio.sleep(wait)
                        continue
                    else:
                        return False, f"HTTP {resp.status}"
            except asyncio.TimeoutError:
                return False, f"Timeout after {timeout_sec}s"
            except aiohttp.ClientError as e:
                if attempt == max_retries - 1:
                    return False, f"Client error: {e}"
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                return False, f"Unexpected error: {e}"

    return False, f"Max retries ({max_retries}) exceeded"


async def download_pair(
    session: aiohttp.ClientSession,
    pair: Dict[str, Any],
    semaphore: asyncio.Semaphore,
    repo_root: Path,
) -> DownloadResult:
    """Download both PDF and IO for a single MOC."""
    moc_id = pair["moc_id"]

    # Determine PDF URL (prefer direct pdf_url, fallback to instructions_url)
    pdf_url = pair.get("pdf_url") or pair.get("instructions_url")
    # Determine IO URL
    io_url = pair.get("io_url")

    # Destination paths from DB (relative to repo root)
    pdf_rel = pair.get("pdf_file_path") or pair.get("pdf_path") or ""
    io_rel = pair.get("io_file_path") or pair.get("io_path") or pair.get("file_path") or ""

    # If DB paths not available, fall back to MOC ID based naming
    if not pdf_rel and pdf_url:
        pdf_rel = f"data/manuals/{moc_id}.pdf"
    if not io_rel and io_url:
        io_rel = f"data/mocs/{moc_id}.io"

    pdf_dest = repo_root / pdf_rel if pdf_rel else None
    io_dest = repo_root / io_rel if io_rel else None

    pdf_ok, pdf_err = True, None
    io_ok, io_err = True, None

    if pdf_dest:
        pdf_ok, pdf_err = await download_file(session, pdf_url, pdf_dest, semaphore) if pdf_url else (False, "No PDF URL provided")
    else:
        pdf_ok, pdf_err = False, "No PDF destination path"

    if io_dest:
        io_ok, io_err = await download_file(session, io_url, io_dest, semaphore) if io_url else (False, "No IO URL provided")
    else:
        io_ok, io_err = False, "No IO destination path"

    return DownloadResult(
        moc_id=moc_id,
        pdf_ok=pdf_ok,
        io_ok=io_ok,
        pdf_error=pdf_err,
        io_error=io_err,
    )


async def main_async(args: argparse.Namespace) -> int:
    # Load input JSON
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    pairs = data.get("pairs", [])
    if not pairs:
        print("[ERROR] No pairs found in input JSON")
        return 1

    print(f"Loaded {len(pairs)} pairs from {args.input}")

    # Filter by tier if specified
    if args.tier:
        pairs = [p for p in pairs if p["complexity_tier"].upper() == args.tier.upper()]
        print(f"Filtered to {len(pairs)} pairs in tier {args.tier}")

    # Filter by parts range
    if args.min_parts > 0:
        pairs = [p for p in pairs if p["parts_count"] >= args.min_parts]
    if args.max_parts < 10000:
        pairs = [p for p in pairs if p["parts_count"] <= args.max_parts]

    print(f"Downloading {len(pairs)} pairs...")

    # Rate limiting semaphore
    semaphore = asyncio.Semaphore(args.workers)

    # Connector with connection limit
    connector = aiohttp.TCPConnector(limit=args.workers, limit_per_host=2)

    repo_root = Path(REPO_ROOT)

    async with aiohttp.ClientSession(
        connector=connector,
        headers={"User-Agent": "LegoGPT-CorpusDownloader/1.0"},
    ) as session:
        tasks = [
            download_pair(
                session,
                pair,
                semaphore,
                repo_root,
            )
            for pair in pairs
        ]

        results: List[DownloadResult] = []
        for coro in async_tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Downloading"):
            result = await coro
            results.append(result)

    # Summary
    pdf_ok = sum(1 for r in results if r.pdf_ok)
    io_ok = sum(1 for r in results if r.io_ok)
    both_ok = sum(1 for r in results if r.pdf_ok and r.io_ok)

    print(f"\n=== Download Summary ===")
    print(f"Total pairs:     {len(results)}")
    print(f"PDF success:     {pdf_ok} ({pdf_ok/len(results)*100:.1f}%)")
    print(f"IO success:      {io_ok} ({io_ok/len(results)*100:.1f}%)")
    print(f"Both success:    {both_ok} ({both_ok/len(results)*100:.1f}%)")

    # Print failures
    failures = [r for r in results if not r.pdf_ok or not r.io_ok]
    if failures and args.verbose:
        print(f"\nFailures ({len(failures)}):")
        for r in failures:
            if not r.pdf_ok:
                print(f"  {r.moc_id} PDF: {r.pdf_error}")
            if not r.io_ok:
                print(f"  {r.moc_id} IO:  {r.io_error}")

    # Write results JSON
    output_path = args.output or os.path.join(os.path.dirname(args.input), "download_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(results),
            "pdf_success": pdf_ok,
            "io_success": io_ok,
            "both_success": both_ok,
            "results": [
                {
                    "moc_id": r.moc_id,
                    "pdf_ok": r.pdf_ok,
                    "io_ok": r.io_ok,
                    "pdf_error": r.pdf_error,
                    "io_error": r.io_error,
                }
                for r in results
            ],
        }, f, indent=2)
    print(f"\nResults written to: {output_path}")

    return 0 if both_ok > 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Parallel download PDF+IO corpus")
    parser.add_argument("--input", "-i", required=True, help="Input JSON from query_pdf_io_pairs.py")
    parser.add_argument("--output", "-o", help="Output results JSON (default: alongside input)")
    parser.add_argument("--workers", "-w", type=int, default=8, help="Max concurrent downloads")
    parser.add_argument("--tier", choices=["MICRO", "SMALL", "MEDIUM", "LARGE"], help="Filter by tier")
    parser.add_argument("--min-parts", type=int, default=0, help="Minimum parts count")
    parser.add_argument("--max-parts", type=int, default=10000, help="Maximum parts count")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print failure details")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"[ERROR] Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    try:
        exit_code = asyncio.run(main_async(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()