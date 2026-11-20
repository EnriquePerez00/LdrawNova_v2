"""BrickLink Studio 2.0 ``.io`` → step-aware LDraw reader.

The ``.io`` format is a zip archive (optionally encrypted with the static
LegoGPT password ``soho0909``) containing ``model.ldr`` with ``0 STEP``
markers separating cumulative part additions. This module exposes:

- :class:`StepBlock`: one assembly state (all parts up to and including step k).
- :func:`load_io_steps`: parse a ``.io`` into ``List[StepBlock]``.
- :func:`serialize_step_to_ldr`: write a cumulative state as a flat ``.ldr``.

Design notes
------------

* The loader resolves only the **main FILE block** of ``model.ldr``. Nested
  submodels (``0 FILE … 0 NOFILE`` inside) are intentionally left as
  type-1 references: LeoCAD will resolve them at render time. ``0 STEP``
  markers inside submodels are ignored for step counting (consistent with
  :mod:`LegoGPT.src.io_parser`).
* ``StepBlock[0]`` corresponds to the **first chunk of parts before the first
  STEP marker** (or the whole model if no STEP marker is present). Hence
  ``len(blocks)`` == ``step_count`` (not step_count + 1).
* The parser is byte-light: it never materialises the full file text more than
  once and keeps part lines as raw strings (``str``) to preserve LDraw
  precision for downstream serialisation.
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from scripts.bench import config

__all__ = [
    "StepBlock",
    "IOLoadError",
    "load_io_steps",
    "count_steps",
    "serialize_step_to_ldr",
    "parse_part_line",
    "PartLine",
    "sample_id_from_path",
]


class IOLoadError(RuntimeError):
    """Raised when a ``.io`` file cannot be opened, decrypted, or parsed."""


# ---------------------------------------------------------------------------
# Part lines
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PartLine:
    """A single LDraw type-1 line (one part instance).

    Attributes
    ----------
    raw:
        The exact original line text (no trailing newline). Kept verbatim so
        serialisation round-trips byte-for-byte.
    color:
        LDraw colour ID (int).
    part_id:
        Normalised part filename (e.g. ``3001.dat``). Always ends in ``.dat``.
    x, y, z:
        Translation components (LDU, floats).
    """

    raw: str
    color: int
    part_id: str
    x: float
    y: float
    z: float


def parse_part_line(line: str) -> Optional[PartLine]:
    """Parse one stripped LDraw line. Return ``None`` if it isn't a type-1."""
    tok = line.split()
    if len(tok) < 15 or tok[0] != "1":
        return None
    try:
        color = int(tok[1])
        x = float(tok[2])
        y = float(tok[3])
        z = float(tok[4])
    except ValueError:
        return None
    # Everything after index 14 belongs to the part name (which may contain
    # spaces/backslashes for subparts, e.g. ``8\1-4edge.dat``).
    part_id = " ".join(tok[14:]).strip()
    return PartLine(raw=line, color=color, part_id=part_id, x=x, y=y, z=z)


# ---------------------------------------------------------------------------
# Step blocks
# ---------------------------------------------------------------------------

@dataclass
class StepBlock:
    """One assembly state (cumulative up to and including step ``step_idx``)."""

    step_idx: int
    #: Parts belonging to this step only (the delta vs the previous block).
    new_parts: List[PartLine] = field(default_factory=list)
    #: All parts up to and including this step (``sum(new_parts[0..k])``).
    cumulative_parts: List[PartLine] = field(default_factory=list)

    @property
    def parts_count_new(self) -> int:
        return len(self.new_parts)

    @property
    def parts_count_cum(self) -> int:
        return len(self.cumulative_parts)


# ---------------------------------------------------------------------------
# Reading model.ldr
# ---------------------------------------------------------------------------

def _read_model_ldr(zip_path: Path) -> str:
    """Return UTF-8 text of ``model.ldr`` (or fallback) inside ``zip_path``."""
    if not zipfile.is_zipfile(zip_path):
        raise IOLoadError(f"Not a zip archive: {zip_path}")
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
            # Try password first, then raw read. Studio stores most files
            # encrypted with ``soho0909`` but some (older/MOC) are plain.
            try:
                zf.setpassword(config.STUDIO_ZIP_PASSWORD)
                data = zf.read(target)
            except Exception:
                zf.setpassword(None)
                data = zf.read(target)
            return data.decode("utf-8", errors="replace")
    except IOLoadError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise IOLoadError(f"Failed to read {zip_path.name}: {exc!r}") from exc


# ---------------------------------------------------------------------------
# Public API: load_io_steps
# ---------------------------------------------------------------------------

def _iter_main_file_lines(lines: Sequence[str]) -> List[str]:
    """Return the slice of ``lines`` that belongs to the main FILE block.

    If there is no explicit ``0 FILE`` marker, the entire input is treated as
    the main block. If there are multiple FILE blocks, only the first one is
    returned (the "main" by LegoGPT/BrickLink convention).
    """
    seen_file = False
    inside = False
    collected: List[str] = []
    for ln in lines:
        s = ln.strip()
        tok = s.split()
        if tok[:2] == ["0", "FILE"]:
            if not seen_file:
                seen_file = True
                inside = True
                # Drop the FILE marker itself; serialisation will add its own.
                continue
            # Second FILE block → we exit the main.
            inside = False
            continue
        if tok[:2] == ["0", "NOFILE"]:
            inside = False
            continue
        if seen_file:
            if inside:
                collected.append(ln)
        else:
            # No FILE marker at all → everything counts.
            collected.append(ln)
    return collected


def load_io_steps(io_path: Path) -> List[StepBlock]:
    """Parse ``io_path`` → list of :class:`StepBlock` in step order.

    Guarantees
    ----------
    * At least one block is returned even if the file has 0 STEP markers
      (in that case the single block holds all parts; later code can decide
      whether to classify the sample as ``no_steps``).
    * ``blocks[k].cumulative_parts == sum(blocks[0..k].new_parts)``.
    * Only ``.dat`` type-1 references in the **main FILE block** are counted.
    """
    text = _read_model_ldr(io_path)
    lines = text.splitlines()
    main_lines = _iter_main_file_lines(lines)

    blocks: List[StepBlock] = []
    current = StepBlock(step_idx=0)
    for ln in main_lines:
        s = ln.strip()
        if not s:
            continue
        tok = s.split()
        if tok[0] == "0":
            if len(tok) >= 2 and tok[1].upper() == "STEP":
                # Close out the current block; open a new one.
                blocks.append(current)
                next_idx = current.step_idx + 1
                current = StepBlock(step_idx=next_idx)
                # Carry cumulative forward.
                current.cumulative_parts = list(blocks[-1].cumulative_parts)
            # All other "0 …" lines are metadata/comments; ignore.
            continue
        if tok[0] == "1":
            pl = parse_part_line(s)
            if pl is None:
                continue
            current.new_parts.append(pl)
            current.cumulative_parts.append(pl)
    blocks.append(current)
    return blocks


# ---------------------------------------------------------------------------
# Public API: count_steps (cheap probe, consistent with load_io_steps)
# ---------------------------------------------------------------------------

def count_steps(io_path: Path) -> Optional[int]:
    """Return the number of step blocks for ``io_path`` (= ``0 STEP`` + 1).

    Cheaper than :func:`load_io_steps` — it skips part parsing — but it runs
    the exact same main-FILE isolation (`_iter_main_file_lines`) and STEP
    tokeniser as :func:`load_io_steps`, so bucket classification is
    **guaranteed consistent** across the two call sites (fix for review
    finding #1, replaces the former ``smoke._quick_step_count``).

    Returns ``None`` if the archive cannot be opened or decoded. Does *not*
    short-circuit on the second ``0 FILE`` because the main FILE isolation
    already discards everything that follows.
    """
    counted = count_steps_and_parts(io_path)
    return None if counted is None else counted[0]


def count_steps_and_parts(io_path: Path) -> Optional[Tuple[int, int]]:
    """Return ``(step_count, parts_count)`` for ``io_path`` in a single pass.

    ``step_count`` is the number of step blocks (= ``0 STEP`` markers + 1).
    ``parts_count`` is the number of type-1 part lines in the main FILE block
    — the quantity that actually drives LeoCAD render cost and memory.

    Returns ``None`` if the archive cannot be opened or decoded.
    """
    try:
        text = _read_model_ldr(Path(io_path))
    except IOLoadError:
        return None
    n_step = 0
    n_parts = 0
    for ln in _iter_main_file_lines(text.splitlines()):
        s = ln.strip()
        if not s:
            continue
        tok = s.split()
        if tok[0] == "0":
            if len(tok) >= 2 and tok[1].upper() == "STEP":
                n_step += 1
        elif tok[0] == "1" and len(tok) >= 15:
            n_parts += 1
    return n_step + 1, n_parts


# ---------------------------------------------------------------------------
# Public API: serialize_step_to_ldr
# ---------------------------------------------------------------------------

_LDR_HEADER_TEMPLATE = (
    "0 FILE {name}\n"
    "0 LdrawNova benchmark step dump (sample={sample_id}, step={step_idx}/{step_total})\n"
    "0 Name:  {name}\n"
    "0 Author: LdrawNova scripts.bench.io_loader\n"
    "0 !LDRAW_ORG Unofficial_Model\n"
    "0 CustomBrick\n"
    "0 TotalBricks: {n_parts}\n"
)


def serialize_step_to_ldr(
    step: StepBlock,
    out_path: Path,
    *,
    sample_id: str,
    step_total: int,
) -> Path:
    """Write ``step.cumulative_parts`` as a flat ``.ldr`` file.

    Parameters
    ----------
    step:
        The :class:`StepBlock` to serialise (its cumulative part list).
    out_path:
        Destination path. Parents are created if needed.
    sample_id:
        Identifier embedded in the header for traceability (filename stem).
    step_total:
        Total number of steps in the sample (for the header comment only).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = _LDR_HEADER_TEMPLATE.format(
        name=out_path.name,
        sample_id=sample_id,
        step_idx=step.step_idx,
        step_total=step_total - 1,
        n_parts=step.parts_count_cum,
    )
    body = "\n".join(p.raw for p in step.cumulative_parts)
    out_path.write_text(header + body + "\n0 NOFILE\n", encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Convenience: sample_id derivation
# ---------------------------------------------------------------------------

def sample_id_from_path(io_path: Path) -> str:
    """Strip the ``_normalized.io`` suffix to get a short stable ID."""
    stem = io_path.stem  # removes .io
    if stem.endswith("_normalized"):
        stem = stem[: -len("_normalized")]
    return stem
