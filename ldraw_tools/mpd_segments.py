"""Helpers to parse and rewrite semantic MPD submodels emitted by A2.

Phase 2 of the loop-v2-physical-gate plan requires A2 to emit one
`0 FILE segment_<id>.ldr` submodel per spec segment. This module provides:

- ``parse_segment_blocks``: locate every submodel block by segment id and
  return its (start_line, end_line, raw_text) span. Start/end are 1-indexed
  line numbers inclusive, matching the convention used by diffs with
  ``mpd_line_range``.
- ``rewrite_segment``: replace the body of a single submodel with new text,
  keeping the rest of the MPD untouched.
- ``find_segment_for_line``: reverse lookup from an MPD line number to the
  segment id that owns it.

Segment id resolution:
- First, honor an explicit ``0 // SEGMENT_ID: <id>`` comment in the block.
- Otherwise, parse the submodel filename and strip the leading ``segment_``
  prefix (``segment_head.ldr`` -> ``head``). Submodels that don't match this
  convention are ignored.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_SEGMENT_ID_COMMENT = re.compile(r"^\s*0\s*//\s*SEGMENT_ID\s*:\s*(\S+)", re.IGNORECASE)
_FILE_HEADER = re.compile(r"^\s*0\s+FILE\s+(.+?)\s*$", re.IGNORECASE)
_NOFILE = re.compile(r"^\s*0\s+NOFILE\s*$", re.IGNORECASE)


def _segment_id_from_filename(name: str) -> Optional[str]:
    stem = name.strip().rsplit(".", 1)[0]
    if stem.lower().startswith("segment_"):
        return stem[len("segment_"):] or None
    return None


def _iter_blocks(lines: List[str]):
    """Yield (filename, start_line_1idx, end_line_1idx_inclusive, block_lines)."""
    start: Optional[int] = None
    filename: Optional[str] = None
    block: List[str] = []
    for i, line in enumerate(lines, start=1):
        if _FILE_HEADER.match(line):
            if start is not None and filename is not None:
                # Previous block had no explicit NOFILE; close it just before
                # the new header.
                yield filename, start, i - 1, block
            filename = _FILE_HEADER.match(line).group(1).strip()
            start = i
            block = [line]
            continue
        if start is not None:
            block.append(line)
            if _NOFILE.match(line):
                yield filename, start, i, block
                start = None
                filename = None
                block = []
    if start is not None and filename is not None:
        yield filename, start, len(lines), block


def parse_segment_blocks(mpd_path: Path) -> Dict[str, Tuple[int, int, str]]:
    """Return ``{segment_id: (start_line, end_line, raw_text)}``.

    - start_line / end_line are 1-indexed and inclusive.
    - raw_text preserves the original line endings of the input file.
    - If the file has no submodels (single flat model), the dictionary is empty.
    - If the same segment id appears twice, the first block wins and a note is
      raised through the returned dict (``__ambiguous_<id>__`` key).
    """
    mpd_path = Path(mpd_path)
    text = mpd_path.read_text(encoding="utf-8-sig")
    # Keep line endings so rewrite is lossless.
    raw_lines = text.splitlines(keepends=True)
    if not raw_lines:
        return {}

    result: Dict[str, Tuple[int, int, str]] = {}
    for filename, start, end, block in _iter_blocks(raw_lines):
        seg_id: Optional[str] = None
        for line in block:
            m = _SEGMENT_ID_COMMENT.match(line)
            if m:
                seg_id = m.group(1).strip()
                break
        if seg_id is None:
            seg_id = _segment_id_from_filename(filename or "")
        if seg_id is None:
            continue
        if seg_id in result:
            # Record ambiguity but keep the first occurrence as canonical.
            result[f"__ambiguous_{seg_id}__"] = (start, end, "".join(block))
            continue
        result[seg_id] = (start, end, "".join(block))
    return result


def find_segment_for_line(blocks: Dict[str, Tuple[int, int, str]],
                          line_number: int) -> Optional[str]:
    """Return the segment id that owns ``line_number`` (1-indexed), if any."""
    for seg_id, (start, end, _) in blocks.items():
        if seg_id.startswith("__ambiguous_"):
            continue
        if start <= line_number <= end:
            return seg_id
    return None


def rewrite_segment(mpd_path: Path, segment_id: str, new_raw_text: str) -> None:
    """Replace the body of ``segment_id`` with ``new_raw_text`` in place.

    ``new_raw_text`` must be a full submodel block including its ``0 FILE``
    header and ``0 NOFILE`` footer. The function does not validate the new
    content beyond that it is non-empty; the caller is responsible for making
    sure it is syntactically valid LDraw.
    """
    if not new_raw_text.strip():
        raise ValueError("new_raw_text is empty; refusing to blank out submodel")

    blocks = parse_segment_blocks(Path(mpd_path))
    if segment_id not in blocks:
        raise KeyError(f"segment_id {segment_id!r} not found in {mpd_path}")
    start, end, _ = blocks[segment_id]

    text = Path(mpd_path).read_text(encoding="utf-8-sig")
    lines = text.splitlines(keepends=True)

    # Normalize the trailing newline of the replacement so the file stays
    # well-formed even if the caller forgot one.
    if not new_raw_text.endswith("\n"):
        new_raw_text = new_raw_text + "\n"

    new_lines = lines[: start - 1] + [new_raw_text] + lines[end:]
    Path(mpd_path).write_text("".join(new_lines), encoding="utf-8")
