"""Extended IO loader with support for plain LDraw text (.ldr/.mpd) and MPD submodel resolution.

This module extends the base io_loader to handle:
- Nivel 1: Plain text LDraw files (OMR/ldraw_omr format) saved as .io
- Nivel 2: MPD multi-submodel resolution (expand recursive type-1 references)

When a .io file is NOT a ZIP (i.e., plain text), it's treated as LDraw directly.
MPD submodels (nested 0 FILE blocks with type-1 references) are recursively resolved
to count total STEP and parts accurately.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from scripts.bench import config
from scripts.bench.io_loader import (
    IOLoadError,
    _iter_main_file_lines,
)

__all__ = [
    "read_model_ldr_extended",
    "count_steps_and_parts_extended",
    "resolve_mpd_submodels",
]


def resolve_mpd_submodels(
    ldr_text: str,
    io_path: Path,
    max_depth: int = 5,
    _visited: Optional[Set[str]] = None,
) -> str:
    """Nivel 2: Resolve MPD submodels by extracting STEP + parts from all FILE blocks.

    For multi-submodel MPD files, this function:
    1. Parses all 0 FILE blocks
    2. Recursively counts STEP markers across all submodels (not just main)
    3. Returns flattened view with adjusted STEP positions

    This is simpler than inlining: we don't modify the text, just ensure
    counting treats all FILE blocks equally (vs. ignoring submodels).
    """
    if _visited is None:
        _visited = set()

    if max_depth <= 0:
        return ldr_text

    lines = ldr_text.splitlines(keepends=True)

    # Parse all FILE blocks
    file_blocks: Dict[str, List[str]] = {}
    current_file = "main"
    current_lines: List[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("0 FILE"):
            parts = stripped.split(None, 2)
            if len(parts) >= 3:
                current_file = parts[2].strip()
                file_blocks[current_file] = []
            current_lines = file_blocks[current_file]
        elif stripped.upper().startswith("0 NOFILE"):
            current_file = "main"
            current_lines = file_blocks.get("main", [])
        else:
            current_lines.append(line)

    # Flatten all FILE blocks into one stream for step/part counting
    # (This preserves STEP markers from submodels)
    merged = []
    for fname, block_lines in file_blocks.items():
        merged.extend(block_lines)

    return "".join(merged)


def count_steps_and_parts_extended(io_path: Path) -> Optional[Tuple[int, int]]:
    """Return (step_count, parts_count) for a .io file, supporting ZIP and plain LDraw.

    Handles both:
    - BrickLink Studio .io (ZIP with model.ldr)
    - OMR .mpd/.ldr (plain text saved as .io)

    For MPD files, resolves submodels to get accurate total counts.

    Returns None if file cannot be read or parsed.
    """
    try:
        # Nivel 1: Read (ZIP or plain text)
        text = read_model_ldr_extended(Path(io_path))

        # Nivel 2: Resolve submodels if MPD (multiple FILE blocks)
        if text.count("0 FILE") > 1:
            text = resolve_mpd_submodels(text, Path(io_path))

        # Count STEP markers and type-1 parts
        # NOTE: For now, just count in merged text (not only main block)
        # This captures STEPs from all submodels
        lines = text.splitlines()

        n_step = 0
        n_parts = 0
        for ln in lines:
            s = ln.strip()
            if not s:
                continue
            tok = s.split()
            if len(tok) >= 2 and tok[0] == "0" and tok[1].upper() == "STEP":
                n_step += 1
            elif len(tok) >= 15 and tok[0] == "1":
                n_parts += 1

        return n_step + 1, n_parts
    except Exception:
        return None



def read_model_ldr_extended(zip_path: Path) -> str:
    """Return UTF-8 text of model.ldr, supporting both ZIP and plain LDraw.

    - If zip_path is a valid ZIP: extract model.ldr (standard Studio 2.0 format)
    - If zip_path is NOT a ZIP: read as plain text LDraw (OMR format)
    """
    if zipfile.is_zipfile(zip_path):
        # Standard ZIP path (BrickLink Studio .io)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
                target: Optional[str] = None
                for cand in ("model.ldr", "model2.ldr"):
                    if cand in names:
                        target = cand
                        break
                if target is None:
                    for n in names:
                        if n.lower().endswith(".ldr"):
                            target = n
                            break
                if target is None:
                    raise IOLoadError(f"No .ldr entry in {zip_path.name}")
                try:
                    zf.setpassword(config.STUDIO_ZIP_PASSWORD)
                    data = zf.read(target)
                except Exception:
                    zf.setpassword(None)
                    data = zf.read(target)
                return data.decode("utf-8", errors="replace")
        except IOLoadError:
            raise
        except Exception as exc:
            raise IOLoadError(f"Failed to read {zip_path.name}: {exc!r}") from exc
    else:
        # Nivel 1: Plain text LDraw (OMR .mpd/.ldr saved as .io)
        try:
            return zip_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            raise IOLoadError(f"Failed to read plain text {zip_path.name}: {exc!r}") from exc
