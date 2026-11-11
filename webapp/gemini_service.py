"""Gemini & Lego vision service for LdrawNova.

Handles:
1. Gemini 2.5 Flash / Imagen image generation and multimodal vision reasoning.
2. In-depth extraction of LDraw-compatible color palettes and official .dat parts.
3. Offline high-fidelity Lego-mosaic/stud stylization when API key is unset or as fallback.
4. Synthesis of specialized LDraw-Nova Internal Prompts.
"""

from __future__ import annotations

import base64
import json
import logging
import math
import os
import re
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageOps

logger = logging.getLogger("ldraw_gemini_service")

# ---------------------------------------------------------------------------
# LLM provider resolution (Google AI Studio vs. local LiteLLM proxy)
# ---------------------------------------------------------------------------
# An ``llm_config`` dict can be threaded through the pipeline to pick the
# backend at request time. Shape:
#   {
#     "provider": "gemini" | "llmproxy",
#     "base_url": "http://127.0.0.1:4000",   # LiteLLM only
#     "secret": "sk-...",                     # LiteLLM master key (optional)
#     "plan_model": "qwen3-coder:30b",        # reasoning / brief phase
#     "act_model": "qwen2.5-coder:7b",        # output generation phase
#     "api_key": "AQ...",                      # Gemini only
#   }
# Defaults fall back to environment variables so the server can be configured
# without the UI sending anything.

def resolve_llm_config(llm_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalizes an incoming llm_config dict, applying environment defaults."""
    cfg = dict(llm_config or {})
    provider = (cfg.get("provider") or os.environ.get("LLM_PROVIDER") or "gemini").strip().lower()
    if provider not in ("gemini", "llmproxy"):
        provider = "gemini"
    return {
        "provider": provider,
        "base_url": (cfg.get("base_url") or os.environ.get("LLM_BASE_URL") or "http://127.0.0.1:4000").rstrip("/"),
        "secret": cfg.get("secret") or os.environ.get("LLM_SECRET") or "",
        "plan_model": cfg.get("plan_model") or os.environ.get("LLM_PLAN_MODEL") or "qwen3-coder:30b",
        "act_model": cfg.get("act_model") or os.environ.get("LLM_ACT_MODEL") or "qwen2.5-coder:7b",
        "api_key": cfg.get("api_key") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"),
    }


def _b64_data_uri(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    return f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"


def litellm_chat(
    base_url: str,
    secret: str,
    model: str,
    prompt_text: str,
    image_bytes: Optional[bytes] = None,
    image_mime: str = "image/jpeg",
    timeout: int = 180,
) -> str:
    """Calls a LiteLLM (OpenAI-compatible) proxy /v1/chat/completions endpoint.

    Returns the assistant text content, or raises on transport/HTTP errors.
    Runs synchronously via ``requests``; callers should offload to a thread.
    """
    import requests  # local import keeps module import cheap

    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"

    if image_bytes:
        content: Any = [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": _b64_data_uri(image_bytes, image_mime)}},
        ]
    else:
        content = prompt_text

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.4,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("LiteLLM devolvió una respuesta sin 'choices'.")
    message = choices[0].get("message") or {}
    return (message.get("content") or "").strip()

# Expanded LDraw Colors with verified codes, names and RGB values
LDRAW_COLORS: Dict[int, Dict[str, Any]] = {
    0: {"name": "Black", "hex": "#1B2A34", "rgb": (27, 42, 52), "role": "pedestal / pupilas / sombras profundas"},
    1: {"name": "Blue", "hex": "#1E5AA8", "rgb": (30, 90, 168), "role": "ropa / acento / agua"},
    2: {"name": "Green", "hex": "#00852B", "rgb": (0, 133, 43), "role": "vegetación / césped"},
    4: {"name": "Red", "hex": "#B40000", "rgb": (180, 0, 0), "role": "núcleo interno / acentos"},
    5: {"name": "Dark Pink", "hex": "#D3359D", "rgb": (211, 53, 157), "role": "flores / detalles"},
    10: {"name": "Bright Green", "hex": "#58AB41", "rgb": (88, 171, 65), "role": "follaje brillante"},
    14: {"name": "Yellow", "hex": "#FAC80A", "rgb": (250, 200, 10), "role": "núcleo estructural / iluminación"},
    15: {"name": "White", "hex": "#F4F4F4", "rgb": (244, 244, 244), "role": "brillo de ojos / muros / blanco"},
    19: {"name": "Tan", "hex": "#D7BA8C", "rgb": (215, 186, 140), "role": "piel base / frente / pómulos / arena"},
    25: {"name": "Orange", "hex": "#D67923", "rgb": (214, 121, 35), "role": "acentos / terracota"},
    26: {"name": "Magenta", "hex": "#901F76", "rgb": (144, 31, 118), "role": "flores / vegetación viva"},
    28: {"name": "Dark Tan", "hex": "#897D62", "rgb": (137, 125, 98), "role": "sombras de piel / puente nasal / labio"},
    33: {"name": "Trans Dark Blue", "hex": "#0020A0", "rgb": (0, 32, 160), "role": "cristales / agua profunda"},
    43: {"name": "Trans Light Blue", "hex": "#AEE9E5", "rgb": (174, 233, 229), "role": "agua de piscina / ventanas"},
    70: {"name": "Reddish Brown", "hex": "#694027", "rgb": (105, 64, 39), "role": "cabello castaño / cejas / madera"},
    71: {"name": "Light Bluish Gray", "hex": "#A0A5A9", "rgb": (160, 165, 169), "role": "barba (canas / luz) / acero"},
    72: {"name": "Dark Bluish Gray", "hex": "#595D60", "rgb": (89, 93, 96), "role": "barba (tono principal) / base"},
    78: {"name": "Light Nougat", "hex": "#F6D7B3", "rgb": (246, 215, 179), "role": "piel clara / frente / mejillas"},
    84: {"name": "Medium Nougat", "hex": "#AA7D55", "rgb": (170, 125, 85), "role": "pliegues de piel / labios / sombras"},
    179: {"name": "Flat Silver", "hex": "#898788", "rgb": (137, 135, 136), "role": "detalles metálicos"},
    272: {"name": "Dark Blue", "hex": "#0A3463", "rgb": (10, 52, 99), "role": "jersey / ropa / hombros"},
    288: {"name": "Dark Green", "hex": "#184632", "rgb": (24, 70, 50), "role": "vegetación densa"},
    308: {"name": "Dark Brown", "hex": "#352100", "rgb": (53, 33, 0), "role": "cabello oscuro / volumen capilar"},
    484: {"name": "Dark Orange", "hex": "#91501C", "rgb": (145, 80, 28), "role": "sombras cálidas / macetas"},
}

# Standard official LDraw library parts with geometry semantics
CORE_LDRAW_PARTS = {
    # Structural / Base
    "baseplate_48": {"ref": "4186.dat", "name": "Baseplate 48 x 48", "category": "Baseplates", "dims": "48x48 studs"},
    "baseplate_16": {"ref": "91405.dat", "name": "Plate 16 x 16", "category": "Plates", "dims": "16x16 studs"},
    # Standard Bricks
    "brick_1x1": {"ref": "3005.dat", "name": "Brick 1 x 1", "category": "Bricks", "dims": "1x1 studs, 24 LDU"},
    "brick_1x2": {"ref": "3004.dat", "name": "Brick 1 x 2", "category": "Bricks", "dims": "1x2 studs, 24 LDU"},
    "brick_1x4": {"ref": "3010.dat", "name": "Brick 1 x 4", "category": "Bricks", "dims": "1x4 studs, 24 LDU"},
    "brick_1x6": {"ref": "3009.dat", "name": "Brick 1 x 6", "category": "Bricks", "dims": "1x6 studs, 24 LDU"},
    "brick_2x2": {"ref": "3003.dat", "name": "Brick 2 x 2", "category": "Bricks", "dims": "2x2 studs, 24 LDU"},
    "brick_2x4": {"ref": "3001.dat", "name": "Brick 2 x 4", "category": "Bricks", "dims": "2x4 studs, 24 LDU"},
    "column_masonry": {"ref": "98283.dat", "name": "Brick 1 x 2 with Embossed Masonry", "category": "Bricks", "dims": "1x2 studs, 24 LDU"},
    # Plates
    "plate_1x1": {"ref": "3024.dat", "name": "Plate 1 x 1", "category": "Plates", "dims": "1x1 studs, 8 LDU"},
    "plate_1x2": {"ref": "3023.dat", "name": "Plate 1 x 2", "category": "Plates", "dims": "1x2 studs, 8 LDU"},
    "plate_1x4": {"ref": "3710.dat", "name": "Plate 1 x 4", "category": "Plates", "dims": "1x4 studs, 8 LDU"},
    "plate_2x2": {"ref": "3022.dat", "name": "Plate 2 x 2", "category": "Plates", "dims": "2x2 studs, 8 LDU"},
    "plate_2x4": {"ref": "3020.dat", "name": "Plate 2 x 4", "category": "Plates", "dims": "2x4 studs, 8 LDU"},
    # Tiles (smooth)
    "tile_1x1": {"ref": "3070b.dat", "name": "Tile 1 x 1 with Groove", "category": "Tiles", "dims": "1x1 studs, 8 LDU"},
    "tile_1x2": {"ref": "3069b.dat", "name": "Tile 1 x 2 with Groove", "category": "Tiles", "dims": "1x2 studs, 8 LDU"},
    "tile_2x2": {"ref": "3068b.dat", "name": "Tile 2 x 2 with Groove", "category": "Tiles", "dims": "2x2 studs, 8 LDU"},
    "tile_2x4": {"ref": "87079.dat", "name": "Tile 2 x 4 with Groove", "category": "Tiles", "dims": "2x4 studs, 8 LDU"},
    # Windows & Doors
    "window_frame": {"ref": "60594.dat", "name": "Window 1 x 4 x 3", "category": "Windows", "dims": "1x4x3"},
    "window_lattice": {"ref": "6016.dat", "name": "Window 1 x 4 x 3 Lattice", "category": "Windows", "dims": "1x4x3"},
    "door_frame": {"ref": "60596.dat", "name": "Door Frame 1 x 4 x 6", "category": "Doors", "dims": "1x4x6"},
    "door_leaf": {"ref": "60616b.dat", "name": "Door 1 x 4 x 6 with 4 Panes", "category": "Doors", "dims": "1x4x6"},
    # Nature & Vegetation
    "palm_base": {"ref": "2563a.dat", "name": "Tree Palm Base", "category": "Plants", "dims": "2x2"},
    "palm_trunk": {"ref": "2536a.dat", "name": "Tree Palm Trunk Short", "category": "Plants", "dims": "1.5x1.5"},
    "palm_leaf_lg": {"ref": "2518.dat", "name": "Plant Palm Leaf Large 10 x 5", "category": "Plants", "dims": "10x5"},
    "leaves_6x5": {"ref": "2417.dat", "name": "Plant Leaves 6 x 5", "category": "Plants", "dims": "6x5"},
    "leaves_4x3": {"ref": "2423.dat", "name": "Plant Leaves 4 x 3", "category": "Plants", "dims": "4x3"},
    "flower_round": {"ref": "24866.dat", "name": "Plant Flower 1 x 1 Round with 5 Petals", "category": "Plants", "dims": "1x1"},
    "planter_cone": {"ref": "6233.dat", "name": "Cone 3 x 3 x 2", "category": "Cones", "dims": "3x3x2"},
    "plant_small": {"ref": "37695.dat", "name": "Plant Leaf 1 x 1 with 3 Leaves", "category": "Plants", "dims": "1x1"},
    # Details & Fittings
    "ladder": {"ref": "15118.dat", "name": "Ladder with Curved Handrails", "category": "Accessories", "dims": "1x2x3"},
    "seat": {"ref": "4079.dat", "name": "Minifig Seat 2 x 2", "category": "Town", "dims": "2x2"},
    "table_dish": {"ref": "43898.dat", "name": "Dish 3 x 3 Inverted", "category": "Dishes", "dims": "3x3"},
    "antenna": {"ref": "3957a.dat", "name": "Antenna 1 x 4", "category": "Antennae", "dims": "1x4"},
}


def _color_distance(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
    """Perceptually weighted RGB color distance."""
    rmean = (c1[0] + c2[0]) / 2.0
    r = c1[0] - c2[0]
    g = c1[1] - c2[1]
    b = c1[2] - c2[2]
    return math.sqrt(((512.0 + rmean) * r * r) / 256.0 + 4.0 * g * g + ((767.0 - rmean) * b * b) / 256.0)


def find_closest_ldraw_color(rgb: Tuple[int, int, int]) -> Tuple[int, Dict[str, Any]]:
    """Map any RGB color to the closest authentic LDraw color."""
    best_code = 15
    best_dist = float("inf")
    for code, info in LDRAW_COLORS.items():
        dist = _color_distance(rgb, info["rgb"])
        if dist < best_dist:
            best_dist = dist
            best_code = code
    return best_code, LDRAW_COLORS[best_code]


def extract_dominant_ldraw_colors(image_path: Path, max_colors: int = 6) -> List[Dict[str, Any]]:
    """Analyzes image pixels and returns dominant LDraw colors with usage percentages."""
    with Image.open(image_path) as img:
        img_rgb = img.convert("RGB")
        img_small = img_rgb.resize((100, 100), Image.Resampling.BOX)

    counts: Dict[int, int] = {}
    pixels = list(img_small.getdata())
    total = len(pixels)

    for p in pixels:
        code, _ = find_closest_ldraw_color(p)
        counts[code] = counts.get(code, 0) + 1

    sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:max_colors]
    result = []
    for code, count in sorted_counts:
        info = LDRAW_COLORS[code]
        pct = round((count / total) * 100, 1)
        result.append({
            "code": code,
            "name": info["name"],
            "hex": info["hex"],
            "rgb": info["rgb"],
            "role": info["role"],
            "percent": pct
        })
    return result


def _remove_background(image: "Image.Image") -> "Image.Image":
    """Removes the background of an RGB image using rembg (u2net).

    Returns an RGBA image with alpha=0 on the background. If rembg is not
    installed or fails for any reason, returns the original image unchanged
    and logs a warning. Caller is expected to crop by the alpha bounding box.
    """
    try:
        from rembg import remove  # type: ignore
    except Exception as e:  # pragma: no cover - optional dep
        logger.warning(f"rembg no está disponible ({e}); se omite el recorte de fondo.")
        return image
    try:
        buf = BytesIO()
        image.convert("RGB").save(buf, format="PNG")
        data = buf.getvalue()
        out = remove(data)
        return Image.open(BytesIO(out)).convert("RGBA")
    except Exception as e:  # pragma: no cover - runtime failure
        logger.warning(f"rembg falló al procesar la imagen: {e}; se omite el recorte.")
        return image


def create_lego_filter_preview(
    input_path: Path,
    output_path: Path,
    grid_size: int = 48,
    cell_px: int = 16,
    rembg_enabled: bool = False,
) -> Path:
    """Procedurally transforms an image into an authentic LEGO brick/stud diorama preview.

    Draws quantified color bricks with raised 3D cylindrical studs with top highlights and edge shadows.

    Parameters
    ----------
    grid_size: int
        Number of studs per side (controls mosaic resolution).
    cell_px: int
        Pixels per stud (controls output sharpness per brick).
    rembg_enabled: bool
        When True, remove the background with rembg before gridding and crop
        to the subject's bounding box.
    """
    # Clamp to sane bounds in case callers pass garbage.
    grid_size = max(8, min(int(grid_size), 512))
    cell_px = max(2, min(int(cell_px), 64))

    with Image.open(input_path) as src_img:
        src = src_img.convert("RGB")

    if rembg_enabled:
        rgba = _remove_background(src)
        if rgba.mode == "RGBA":
            bbox = rgba.split()[-1].getbbox()
            if bbox:
                rgba = rgba.crop(bbox)
            # Composite over a neutral baseplate-matching background so the
            # downstream mosaic has sensible colors.
            bg = Image.new("RGB", rgba.size, (30, 30, 35))
            bg.paste(rgba, mask=rgba.split()[-1])
            src = bg
        else:
            # rembg not available – fall back to the unmodified image.
            pass

    # Aspect-ratio preserving square crop from the center of whatever we have
    # (either the bbox from rembg or the original image).
    w, h = src.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    src = src.crop((left, top, left + side, top + side))

    # Downsample to stud grid
    pixelated = src.resize((grid_size, grid_size), Image.Resampling.BILINEAR)
    pixel_data = list(pixelated.getdata())

    # Create target high-res image
    stud_r = max(2, cell_px // 3)
    out_size = grid_size * cell_px
    out_img = Image.new("RGB", (out_size, out_size), (30, 30, 35))
    draw = ImageDraw.Draw(out_img)

    for y in range(grid_size):
        for x in range(grid_size):
            orig_rgb = pixel_data[y * grid_size + x]
            code, color_info = find_closest_ldraw_color(orig_rgb)
            cr, cg, cb = color_info["rgb"]

            x0 = x * cell_px
            y0 = y * cell_px
            x1 = x0 + cell_px
            y1 = y0 + cell_px

            # Draw brick tile background
            draw.rectangle([x0, y0, x1 - 1, y1 - 1], fill=(cr, cg, cb))

            # Brick seam / bevel shadow (right and bottom edge)
            shadow_rgb = (max(0, cr - 35), max(0, cg - 35), max(0, cb - 35))
            draw.line([(x0, y1 - 1), (x1 - 1, y1 - 1)], fill=shadow_rgb, width=1)
            draw.line([(x1 - 1, y0), (x1 - 1, y1 - 1)], fill=shadow_rgb, width=1)

            # Raised round stud with 3D highlight
            cx = (x0 + x1) // 2
            cy = (y0 + y1) // 2
            stud_base_rgb = (min(255, cr + 15), min(255, cg + 15), min(255, cb + 15))
            stud_hi_rgb = (min(255, cr + 45), min(255, cg + 45), min(255, cb + 45))
            stud_sh_rgb = (max(0, cr - 25), max(0, cg - 25), max(0, cb - 25))

            # Stud shadow
            draw.ellipse([cx - stud_r, cy - stud_r + 1, cx + stud_r, cy + stud_r + 1], fill=stud_sh_rgb)
            # Stud main body
            draw.ellipse([cx - stud_r, cy - stud_r, cx + stud_r, cy + stud_r], fill=stud_base_rgb)
            # Stud top specular highlight
            inner = max(1, stud_r - 2)
            draw.ellipse([cx - inner, cy - stud_r + 1, cx + inner, cy - 1], fill=stud_hi_rgb)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(output_path, "PNG", quality=95)
    return output_path


async def generate_legolized_with_gemini(
    image_path: Path,
    prompt: str,
    output_legolized_path: Path,
    api_key: Optional[str] = None,
    llm_config: Optional[Dict[str, Any]] = None,
    grid_size: int = 48,
    cell_px: int = 16,
    rembg_enabled: bool = False,
) -> Tuple[bool, str]:
    """Generates a legolized reference image via Gemini / Imagen API, falling back to local procedural Lego filter.

    Extra parameters:
      - ``grid_size``, ``cell_px``: propagated to the procedural fallback and
        hinted to Gemini so the generated image reflects the chosen mosaic
        resolution.
      - ``rembg_enabled``: when True, remove the background with rembg before
        either the procedural path or the Gemini upload so only the subject
        gets legolized.
    """
    cfg = resolve_llm_config(llm_config)
    provider = cfg["provider"]

    # The local LiteLLM proxy (routing to text/code models like Ollama's qwen)
    # cannot synthesize images, so we go straight to the high-fidelity
    # procedural LEGO filter for the "act" (output) image phase.
    if provider == "llmproxy":
        create_lego_filter_preview(
            image_path,
            output_legolized_path,
            grid_size=grid_size,
            cell_px=cell_px,
            rembg_enabled=rembg_enabled,
        )
        extras = []
        if rembg_enabled:
            extras.append("fondo recortado con rembg")
        extras.append(f"mosaico {grid_size}x{grid_size} studs, {cell_px}px/stud")
        return True, (
            "LLMproxy local (LiteLLM) no genera imágenes: se usó el motor procedural "
            f"de alta fidelidad ({', '.join(extras)}). Comentarios de estilo se aplicarán en la Fase 3."
        )

    resolved_key = api_key or cfg.get("api_key")

    if resolved_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=resolved_key)
            lego_prompt_parts = [
                f"Official LEGO Creator Expert diorama scale model of: {prompt}.",
                "Crafted entirely from physical LEGO bricks, tiles, and standard LDraw parts.",
                "Realistic LEGO stud textures, shiny ABS plastic material, studio photography,",
                "sitting on a baseplate display with clean background lighting, 8k resolution.",
                f"Rendered as a {grid_size}x{grid_size} stud mosaic with {cell_px}px per stud fine detail.",
            ]
            if rembg_enabled:
                lego_prompt_parts.append(
                    "Isolated subject on a neutral baseplate background, do not include scenery or background objects."
                )
            lego_prompt = " ".join(lego_prompt_parts)

            # Preprocess the input image if the user asked for a background cut.
            if rembg_enabled:
                try:
                    with Image.open(image_path) as _src:
                        rgba = _remove_background(_src.convert("RGB"))
                    if rgba.mode == "RGBA":
                        bbox = rgba.split()[-1].getbbox()
                        if bbox:
                            rgba = rgba.crop(bbox)
                        bg = Image.new("RGB", rgba.size, (255, 255, 255))
                        bg.paste(rgba, mask=rgba.split()[-1])
                        buf = BytesIO()
                        bg.save(buf, format="JPEG", quality=92)
                        img_bytes = buf.getvalue()
                    else:
                        with open(image_path, "rb") as f:
                            img_bytes = f.read()
                except Exception as e:
                    logger.warning(f"rembg preprocess en Gemini falló: {e}; usando imagen original.")
                    with open(image_path, "rb") as f:
                        img_bytes = f.read()
            else:
                with open(image_path, "rb") as f:
                    img_bytes = f.read()

            # Target Google AI Studio's most powerful image generation models first:
            # 1. gemini-3-pro-image (Nano Banana Pro) - 131k context with thinking reasoning & high-res image synthesis
            # 2. gemini-3-pro-image-preview
            # 3. gemini-3.1-flash-image (Nano Banana 2)
            pro_image_models = ["gemini-3-pro-image", "gemini-3-pro-image-preview", "gemini-3.1-flash-image"]

            for model_name in pro_image_models:
                try:
                    resp = client.models.generate_content(
                        model=model_name,
                        contents=[
                            types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                            lego_prompt
                        ],
                        config=dict(
                            response_modalities=["IMAGE"]
                        )
                    )
                    if resp and resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts:
                        for part in resp.candidates[0].content.parts:
                            if getattr(part, "inline_data", None) and part.inline_data.data:
                                data = part.inline_data.data
                                if isinstance(data, str):
                                    import base64
                                    data = base64.b64decode(data)
                                output_legolized_path.write_bytes(data)
                                return True, f"Google AI Studio ({model_name} - Nano Banana Pro) generó la imagen legolizada con máxima calidad."
                except Exception as pro_err:
                    err_text = str(pro_err)
                    if "402" in err_text or "prepayment" in err_text.lower():
                        logger.warning(f"Google AI Studio ({model_name}): créditos de prepago agotados en proyecto.")
                        break
                    continue

            # Fallback to Imagen 3 if available
            try:
                result = client.models.generate_images(
                    model="imagen-3.0-generate-002",
                    prompt=lego_prompt,
                    config=dict(
                        number_of_images=1,
                        output_mime_type="image/png",
                        aspect_ratio="1:1"
                    )
                )
                if result and result.generated_images:
                    gen_data = result.generated_images[0].image.image_bytes
                    output_legolized_path.write_bytes(gen_data)
                    return True, "Imagen 3 (imagen-3.0-generate-002) generó la imagen legolizada exitosamente."
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"Error invoking Google AI Studio image generation: {e}")

    # High-fidelity procedural Lego filter
    create_lego_filter_preview(
        image_path,
        output_legolized_path,
        grid_size=grid_size,
        cell_px=cell_px,
        rembg_enabled=rembg_enabled,
    )
    return True, (
        f"Generada vista previa legolizada de alta fidelidad "
        f"(mosaico {grid_size}x{grid_size} studs, {cell_px}px/stud"
        + (", fondo recortado con rembg" if rembg_enabled else "")
        + ")."
    )


async def analyze_and_synthesize_brief(
    image_path: Path,
    legolized_path: Path,
    user_prompt: str,
    slug_name: str,
    api_key: Optional[str] = None,
    strategy: str = "auto",
    llm_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Extracts design parameters, color palette, parts list, and synthesizes the LDraw-Nova Internal Prompt."""
    cfg = resolve_llm_config(llm_config)
    provider = cfg["provider"]
    resolved_key = api_key or cfg.get("api_key")

    dominant_colors = extract_dominant_ldraw_colors(legolized_path)

    # Base design parameters
    title = user_prompt.strip().capitalize() or "Modelo LDraw Nova"
    if len(title) > 60:
        title = title[:57] + "..."

    # Determine building type / theme from prompt keywords or explicit strategy
    prompt_lower = user_prompt.lower()
    is_bust = (strategy == "bust") or (strategy == "auto" and any(k in prompt_lower for k in ["busto", "bust", "retrato", "portrait", "persona", "hombre", "man", "cara", "face", "cabeza", "head", "barba", "escultura"]))
    is_vehicle = (strategy == "vehicle") or (strategy == "auto" and any(k in prompt_lower for k in ["coche", "auto", "car", "camion", "truck", "moto", "barco", "avion"]))
    is_space = (strategy == "space") or (strategy == "auto" and any(k in prompt_lower for k in ["nave", "espacial", "spaceship", "starfighter", "cohete", "rocket"]))

    if is_bust:
        submodels = [
            {"filename": "pedestal-peana.ldr", "desc": "Base de apoyo, columna central y biseles inferiores", "parts": ["41539.dat", "3036.dat", "3001.dat", "3039.dat"]},
            {"filename": "hombros-jersey.ldr", "desc": "Escalado por capas studs-up y caída curva de hombros/pecho", "parts": ["3020.dat", "3795.dat", "3710.dat", "11477.dat", "15068.dat", "50950.dat"]},
            {"filename": "cuello-mandibula.ldr", "desc": "Núcleo estructural interno, cuello y base de mandíbula", "parts": ["3003.dat", "3001.dat", "3004.dat"]},
            {"filename": "barba-bigote.ldr", "desc": "Textura SNOT frontal, relieve estriado de patillas y canas", "parts": ["87087.dat", "11211.dat", "2412b.dat", "3024.dat", "4073.dat", "3070b.dat", "54200.dat"]},
            {"filename": "rostro-facciones.ldr", "desc": "Soportes SNOT, pómulos lisos, nariz, cejas, ojos y orejas", "parts": ["99781.dat", "44728.dat", "3069b.dat", "2431.dat", "11477.dat", "54200.dat", "26601.dat", "3024.dat", "3070b.dat", "3023.dat"]},
            {"filename": "cabello-superior.ldr", "desc": "Volumen superior, entradas y textura en sienes", "parts": ["11477.dat", "50950.dat", "43722.dat", "2412b.dat", "3023.dat"]},
        ]
        dimensions = {"x_studs": 24, "z_studs": 20, "height_bricks": 22}

        # Detailed LDraw parts table by submodel
        parts_breakdown = [
            {"zone": "1. Pedestal y Peana", "function": "Base de apoyo", "official_name": "Plate 8 x 8 / Plate 6 x 8", "ref": "41539.dat / 3036.dat"},
            {"zone": "1. Pedestal y Peana", "function": "Columna central y biseles", "official_name": "Brick 2 x 4 + Slope 45° 2 x 2", "ref": "3001.dat + 3039.dat"},
            {"zone": "2. Hombros (Jersey)", "function": "Escalado por capas (Studs-Up)", "official_name": "Plate 2 x 4 / 2 x 6 / 1 x 4", "ref": "3020.dat / 3795.dat / 3710.dat"},
            {"zone": "2. Hombros (Jersey)", "function": "Caída curva de hombros y pecho", "official_name": "Slope Curved 2 x 1 / 2 x 2 / 3 x 1", "ref": "11477.dat / 15068.dat / 50950.dat"},
            {"zone": "3. Cuello y Mandíbula", "function": "Núcleo estructural interno", "official_name": "Brick 2 x 2 / 2 x 4 / 1 x 2", "ref": "3003.dat / 3001.dat / 3004.dat"},
            {"zone": "3. Barba y Bigote", "function": "Textura SNOT (studs frontales vista)", "official_name": "Brick 1 x 1 / 1 x 2 con Studs en 1 lado", "ref": "87087.dat / 11211.dat"},
            {"zone": "3. Barba y Patillas", "function": "Relieve estriado lateral (grille)", "official_name": "Tile 1 x 2 Grille (Rejilla)", "ref": "2412b.dat"},
            {"zone": "3. Barba y Bigote", "function": "Textura granulada y canas", "official_name": "Plate 1 x 1 / Plate Round 1 x 1 / Tile 1 x 1", "ref": "3024.dat / 4073.dat / 3070b.dat"},
            {"zone": "3. Barba y Boca", "function": "Recorte diagonal del bigote y mentón", "official_name": "Slope 30° 1 x 1 x 2/3 (Cheese Slope)", "ref": "54200.dat"},
            {"zone": "4. Rostro y Mejillas", "function": "Soportes SNOT para paneles faciales", "official_name": "Bracket 1 x 2 - 1 x 2 / 1 x 2 - 2 x 2", "ref": "99781.dat / 44728.dat"},
            {"zone": "4. Rostro y Frente", "function": "Superficie lisa de piel y pómulos", "official_name": "Tile 1 x 2 / Tile 1 x 4 / Curved Slope 2 x 1", "ref": "3069b.dat / 2431.dat / 11477.dat"},
            {"zone": "4. Nariz y Cejas", "function": "Puente nasal, fosas y arco superciliar", "official_name": "Slope 45° 1 x 1 / Wedge Plate 2 x 2 Cut Corner", "ref": "54200.dat / 26601.dat"},
            {"zone": "4. Ojos", "function": "Esclerótica, pupila y párpado", "official_name": "Plate 1 x 1 + Tile 1 x 1", "ref": "3024.dat / 3070b.dat"},
            {"zone": "4. Orejas", "function": "Pabellón auricular", "official_name": "Slope Curved 2 x 1 + Plate 1 x 2", "ref": "11477.dat + 3023.dat"},
            {"zone": "5. Cabello", "function": "Volumen superior y entradas", "official_name": "Slope Curved 2 x 1 / 3 x 1 + Wedge Slopes", "ref": "11477.dat / 50950.dat / 43722.dat"},
            {"zone": "5. Cabello (Laterales)", "function": "Textura de pelo corto en sienes", "official_name": "Tile 1 x 2 Grille + Plate 1 x 2", "ref": "2412b.dat + 3023.dat"}
        ]

        # Detailed Color palette for sculpture
        color_assignments = [
            {"zone": "Piel (Base)", "name": "Tan / Light Nougat", "code": "19 / 78", "use": "Frente, mejillas, puente de la nariz, cuello y orejas (19 Tan o 78 Light Flesh)."},
            {"zone": "Piel (Sombras / Labio)", "name": "Medium Nougat / Dark Tan", "code": "84 / 28", "use": "Pliegues bajo los pómulos, sombra bajo la nariz y línea del labio inferior."},
            {"zone": "Barba (Tono Principal)", "name": "Dark Bluish Gray", "code": "72", "use": "Masa principal de la barba, bigote y transición de patillas."},
            {"zone": "Barba (Canas / Luz)", "name": "Light Bluish Gray", "code": "71", "use": "Puntos de luz y zonas canosas en mentón y laterales de la mandíbula."},
            {"zone": "Barba y Pelo (Castaño)", "name": "Reddish Brown / Dark Brown", "code": "70 / 308", "use": "Volumen principal del cabello, cejas y matices cálidos intercalados en la barba."},
            {"zone": "Barba (Sombras) y Peana", "name": "Black", "code": "0", "use": "Pedestal inferior, pupilas de los ojos y zonas profundas del cabello/barba."},
            {"zone": "Brillo de Ojos", "name": "White", "code": "15", "use": "Punto de luz lateral (1x1) junto a la pupila negra."},
            {"zone": "Jersey / Hombros", "name": "Dark Blue", "code": "272", "use": "Toda la estructura escalonada de los hombros y el cuello redondo."},
            {"zone": "Relleno Interno (Core)", "name": "Yellow / Red (Cualquiera)", "code": "14 / 4", "use": "Ladrillos 3001.dat ocultos dentro del torso y cráneo para dar rigidez sin colisiones."}
        ]
    elif is_vehicle:
        submodels = [
            {"filename": "chasis-rodaje.ldr", "desc": "Chasis y tren de rodaje con ejes y ruedas", "parts": ["3020.dat", "3022.dat", "3068b.dat"]},
            {"filename": "carroceria-cabina.ldr", "desc": "Carrocería principal, parabrisas y asiento", "parts": ["3004.dat", "4079.dat", "60594.dat"]},
            {"filename": "frontal-luces.ldr", "desc": "Paragolpes, parrilla y detalles luminosos", "parts": ["3069b.dat", "3070b.dat", "3024.dat"]},
        ]
        dimensions = {"x_studs": 12, "z_studs": 24, "height_bricks": 6}
        parts_breakdown = [
            {"zone": "1. Chasis", "function": "Estructura portante", "official_name": "Plate 2 x 4 / Plate 2 x 6", "ref": "3020.dat / 3795.dat"},
            {"zone": "1. Rodaje", "function": "Puntos de anclaje de ruedas", "official_name": "Plate Modified 2 x 2 with Wheel Bearing", "ref": "2415.dat"},
            {"zone": "2. Carrocería", "function": "Laterales y puertas", "official_name": "Brick 1 x 4 / Brick 1 x 2", "ref": "3010.dat / 3004.dat"},
            {"zone": "2. Habitáculo", "function": "Asiento de conducción", "official_name": "Minifig Seat 2 x 2", "ref": "4079.dat"},
            {"zone": "3. Acabados", "function": "Faros y pilotos", "official_name": "Tile 1 x 1 Round Trans-Clear / Trans-Red", "ref": "35381.dat"}
        ]
        color_assignments = [
            {"zone": "Carrocería", "name": "Red / Blue / White", "code": "4 / 1 / 15", "use": "Superficies visibles exteriores del vehículo."},
            {"zone": "Chasis", "name": "Dark Bluish Gray / Black", "code": "72 / 0", "use": "Estructura inferior y parachoques."},
            {"zone": "Faros", "name": "Trans-Clear / Trans-Yellow", "code": "12 / 14", "use": "Ópticas delanteras e intermitentes."}
        ]
    elif is_space:
        submodels = [
            {"filename": "fuselaje-central.ldr", "desc": "Estructura interna, cabina y soporte", "parts": ["3010.dat", "3001.dat", "4079.dat"]},
            {"filename": "alas-propulsion.ldr", "desc": "Alas inclinadas con motores y toberas", "parts": ["3020.dat", "6233.dat", "87079.dat"]},
            {"filename": "cabina-detalles.ldr", "desc": "Cúpula translúcida, mandos y armamento", "parts": ["60594.dat", "3069b.dat", "3957a.dat"]},
        ]
        dimensions = {"x_studs": 28, "z_studs": 32, "height_bricks": 8}
        parts_breakdown = [
            {"zone": "1. Espina Central", "function": "Viga longitudinal reforzada", "official_name": "Technic Brick 1 x 6 / 1 x 8", "ref": "3894.dat / 3700.dat"},
            {"zone": "2. Alas", "function": "Placas de sustentación anguladas", "official_name": "Wedge Plate 6 x 3 Left / Right", "ref": "54383.dat / 54384.dat"},
            {"zone": "3. Toberas", "function": "Salida de impulsores traseros", "official_name": "Cone 3 x 3 x 2", "ref": "6233.dat"}
        ]
        color_assignments = [
            {"zone": "Fuselaje", "name": "Light Bluish Gray / White", "code": "71 / 15", "use": "Blindaje exterior de la nave."},
            {"zone": "Líneas de acento", "name": "Dark Red / Dark Blue", "code": "320 / 272", "use": "Franjas de escuadrón y distintivos."},
            {"zone": "Motores", "name": "Trans-Light Blue / Trans-Neon", "code": "43 / 42", "use": "Efecto de propulsión activa."}
        ]
    else:
        # Architectural / Diorama default
        submodels = [
            {"filename": "terreno-base.ldr", "desc": "Baseplate, losas de patio, caminos y lámina de agua/césped", "parts": ["4186.dat", "3022.dat", "3068b.dat"]},
            {"filename": "edificacion-principal.ldr", "desc": "Muros, porche, ventanas con rejas y tejado", "parts": ["3004.dat", "3010.dat", "60594.dat", "60596.dat", "98283.dat"]},
            {"filename": "vegetacion-fittings.ldr", "desc": "Árboles/palmeras, buganvillas, macetas y mobiliario", "parts": ["2563a.dat", "2536a.dat", "2518.dat", "2423.dat", "24866.dat", "6233.dat", "4079.dat"]},
        ]
        dimensions = {"x_studs": 48, "z_studs": 48, "height_bricks": 12}
        parts_breakdown = [
            {"zone": "1. Baseplate", "function": "Plataforma general de apoyo", "official_name": "Baseplate 48 x 48", "ref": "4186.dat"},
            {"zone": "1. Patio y Losas", "function": "Superficie transitable y borde", "official_name": "Plate 2 x 2 / Tile 2 x 2", "ref": "3022.dat / 3068b.dat"},
            {"zone": "2. Muros Edificio", "function": "Cerramientos verticales y esquinas", "official_name": "Brick 1 x 4 / Brick 1 x 2 / Brick 1x1", "ref": "3010.dat / 3004.dat / 3005.dat"},
            {"zone": "2. Porche", "function": "Pilar de soporte visto", "official_name": "Brick 1 x 2 Masonry Profile", "ref": "98283.dat"},
            {"zone": "3. Palmera", "function": "Tronco segmentado y frondas", "official_name": "Palm Base + Trunk + Leaf Large", "ref": "2563a.dat / 2536a.dat / 2518.dat"},
            {"zone": "3. Buganvilla", "function": "Masa de hojas y flores", "official_name": "Plant Leaves 4 x 3 + Flower Round", "ref": "2423.dat / 24866.dat"}
        ]
        color_assignments = [
            {"zone": "Muros", "name": "White", "code": "15", "use": "Hiladas de ladrillo en muros principales."},
            {"zone": "Patio y Porche", "name": "Tan / Medium Nougat", "code": "19 / 84", "use": "Losas de suelo y columna de ladrillo."},
            {"zone": "Agua / Piscina", "name": "Trans-Light-Blue", "code": "43", "use": "Lámina de agua hundida con tiles."},
            {"zone": "Follaje", "name": "Green / Dark-Green", "code": "2 / 288", "use": "Césped perimetral y hojas de palmera."},
            {"zone": "Buganvilla", "name": "Magenta / Dark-Pink", "code": "26 / 5", "use": "Cúpula floral sobre el jardín."}
        ]

    # Selected parts mapping
    selected_parts = []
    for key, pinfo in CORE_LDRAW_PARTS.items():
        selected_parts.append({
            "key": key,
            "ref": pinfo["ref"],
            "name": pinfo["name"],
            "category": pinfo["category"],
            "dims": pinfo["dims"]
        })

    # Call Multimodal Reasoning (PLAN model) if a provider is available for a fine-tuned dynamic brief
    ai_feedback = ""

    def _apply_parsed_brief(raw_text: str) -> bool:
        """Parses a model's JSON reply and mutates the enclosing brief vars. Returns True on success."""
        nonlocal title, dimensions, submodels, parts_breakdown, color_assignments, ai_feedback
        json_match = re.search(r"```json\s*(.*?)\s*```", raw_text, re.DOTALL)
        json_str = json_match.group(1) if json_match else raw_text
        try:
            parsed_llm = json.loads(json_str)
        except Exception:
            ai_feedback += f"\nRespuesta del modelo:\n{raw_text[:400]}"
            return False
        if isinstance(parsed_llm, dict):
            if parsed_llm.get("title"):
                title = parsed_llm["title"]
            if isinstance(parsed_llm.get("dimensions"), dict):
                dimensions.update(parsed_llm["dimensions"])
            if isinstance(parsed_llm.get("submodels"), list) and parsed_llm["submodels"]:
                submodels = parsed_llm["submodels"]
            if isinstance(parsed_llm.get("parts_breakdown"), list) and parsed_llm["parts_breakdown"]:
                parts_breakdown = parsed_llm["parts_breakdown"]
            if isinstance(parsed_llm.get("color_assignments"), list) and parsed_llm["color_assignments"]:
                color_assignments = parsed_llm["color_assignments"]
            if "design_notes" in parsed_llm:
                ai_feedback += f"\nNotas de diseño: {parsed_llm['design_notes']}"
        return True

    if resolved_key or provider == "llmproxy":
        try:
            prompt_text = (
                f"Eres el arquitecto maestro de diseño LEGO y CAD LDraw (ldraw-nova).\n"
                f"Analiza detalladamente la imagen adjunta y el objetivo del usuario: '{user_prompt}'.\n\n"
                f"TU MISIÓN:\n"
                f"Realizar una descomposición DINÁMICA de la imagen en zonas u objetos concretos y diferenciados.\n"
                f"Para CADA zona identificada en esta imagen específica, debes inferir:\n"
                f"1. Nombre de la zona / submodelo y su nombre de archivo LDraw (.ldr).\n"
                f"2. Función geométrica específica (e.g. Base de apoyo, Estructura SNOT frontal, Caída curva, Relieve estriado grille, Biseles cheese slopes, Cubierta, etc.).\n"
                f"3. Pieza oficial LEGO correspondiente con su nombre en el catálogo LDraw y su ID oficial exacto de archivo (.dat) existente en LDraw (e.g. 3001.dat, 3020.dat, 87087.dat, 11477.dat, 54200.dat, 2412b.dat, 4186.dat, etc.).\n"
                f"4. Paleta oficial de colores LDraw (LDConfig.ldr) con su nombre oficial, código numérico exacto (0=Black, 15=White, 19=Tan, 78=Light Nougat, 72=Dark Bluish Gray, 71=Light Bluish Gray, 272=Dark Blue, 70=Reddish Brown, etc.) y su rol específico en el script Python generator (generate.py).\n\n"
                f"Debes responder ÚNICAMENTE con un objeto JSON válido con la siguiente estructura exacta:\n"
                f"{{\n"
                f'  "title": "Nombre descriptivo del modelo",\n'
                f'  "dimensions": {{"x_studs": 24, "z_studs": 20, "height_bricks": 20}},\n'
                f'  "submodels": [\n'
                f'    {{"filename": "nombre-zona.ldr", "desc": "Descripción funcional de la zona", "parts": ["ref1.dat", "ref2.dat"]}}\n'
                f'  ],\n'
                f'  "parts_breakdown": [\n'
                f'    {{"zone": "Nombre de la Zona", "function": "Función geométrica", "official_name": "Nombre oficial", "ref": "xxxx.dat"}}\n'
                f'  ],\n'
                f'  "color_assignments": [\n'
                f'    {{"zone": "Zona del modelo", "name": "Nombre oficial LDraw", "code": "Código o Códigos LDraw", "use": "Instrucción de uso en generate.py"}}\n'
                f'  ],\n'
                f'  "design_notes": "Observaciones estéticas y de estabilidad para el ensamblador"\n'
                f"}}"
            )

            # --- Provider: LLMproxy local (LiteLLM, OpenAI-compatible) -> PLAN model ---
            if provider == "llmproxy":
                import asyncio

                with open(image_path, "rb") as f:
                    img_data = f.read()
                plan_model = cfg["plan_model"]
                try:
                    # LiteLLM call is blocking; run it off the event loop.
                    raw_text = await asyncio.to_thread(
                        litellm_chat,
                        cfg["base_url"],
                        cfg["secret"],
                        plan_model,
                        prompt_text,
                        img_data,
                        "image/jpeg",
                    )
                    if raw_text:
                        ai_feedback = f"Descomposición dinámica efectuada con LLMproxy LiteLLM (modelo plan: {plan_model})."
                        _apply_parsed_brief(raw_text)
                except Exception as proxy_err:
                    ai_feedback = (
                        f"No se pudo contactar el LLMproxy local (LiteLLM) en {cfg['base_url']}: {proxy_err}. "
                        "Se activó el motor de descomposición semántica y catálogo local LDConfig."
                    )

            # --- Provider: Google AI Studio (google-genai) ---
            else:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=resolved_key)
                with open(image_path, "rb") as f:
                    img_data = f.read()

                # Try Gemini 2.5 Flash (primary), fall back to latest variant
                models_to_try = ["gemini-2.5-flash", "gemini-flash-latest"]
                for mod in models_to_try:
                    try:
                        response = client.models.generate_content(
                            model=mod,
                            contents=[
                                types.Part.from_bytes(data=img_data, mime_type="image/jpeg"),
                                prompt_text
                            ]
                        )
                        if response and response.text:
                            raw_text = response.text.strip()
                            ai_feedback = f"Descomposición dinámica efectuada con {mod}."
                            _apply_parsed_brief(raw_text)
                            break
                    except Exception as mod_err:
                        err_str = str(mod_err)
                        if "402" in err_str or "prepayment" in err_str.lower():
                            ai_feedback = (
                                f"Nota de Google AI Studio ({mod}): Créditos de prepago agotados en el proyecto. "
                                "Se activó el motor de descomposición semántica y catálogo local LDConfig."
                            )
                            break
                        continue
        except Exception:
            pass

    # Build internal prompt in Markdown following ldraw-nova specification
    brief_md = synthesize_internal_prompt(
        title=title,
        slug=slug_name,
        user_prompt=user_prompt,
        dimensions=dimensions,
        colors=dominant_colors,
        submodels=submodels,
        parts=selected_parts,
        parts_breakdown=parts_breakdown,
        color_assignments=color_assignments,
        ai_notes=ai_feedback
    )

    return {
        "slug": slug_name,
        "title": title,
        "user_prompt": user_prompt,
        "dimensions": dimensions,
        "colors": dominant_colors,
        "submodels": submodels,
        "parts": selected_parts,
        "parts_breakdown": parts_breakdown,
        "color_assignments": color_assignments,
        "internal_prompt_md": brief_md,
        "ai_feedback": ai_feedback
    }


def synthesize_internal_prompt(
    title: str,
    slug: str,
    user_prompt: str,
    dimensions: Dict[str, int],
    colors: List[Dict[str, Any]],
    submodels: List[Dict[str, Any]],
    parts: List[Dict[str, Any]],
    parts_breakdown: Optional[List[Dict[str, str]]] = None,
    color_assignments: Optional[List[Dict[str, str]]] = None,
    ai_notes: str = ""
) -> str:
    """Formats the strict ldraw-nova design brief compliant with instructions.md."""
    # 1. Tabla de piezas por submodelo y función
    if parts_breakdown:
        parts_table_rows = "\n".join(
            f"| {p['zone']} | {p['function']} | {p['official_name']} | `{p['ref']}` |"
            for p in parts_breakdown
        )
    else:
        parts_table_rows = "\n".join(
            f"| Zona Principal | {p['category']} | {p['name']} | `{p['ref']}` |"
            for p in parts[:16]
        )

    # 2. Paleta oficial de colores LDraw
    if color_assignments:
        color_table_rows = "\n".join(
            f"| {c['zone']} | {c['name']} | `{c['code']}` | {c['use']} |"
            for c in color_assignments
        )
    else:
        color_table_rows = "\n".join(
            f"| Superficie ({c['name']}) | {c['name']} | `{c['code']}` | {c['role']} |"
            for c in colors
        )

    submodel_list = "\n".join(
        f"{i+1}. **`{sm['filename']}`** — {sm['desc']}."
        for i, sm in enumerate(submodels)
    )

    notes_section = ""
    if ai_notes:
        notes_section = f"\n### Observaciones Gemini 2.5 Flash / Vision\n{ai_notes}\n"

    return f"""# LDraw Nova Design Brief: {title}

**Slug:** `{slug}`  
**Objetivo del modelo:** {user_prompt}

---

## 1. Tabla de Piezas LDraw por Submodelo (.dat)
| Submodelo / Zona | Función Geometría | Pieza Oficial LEGO / LDraw | LDraw ID (.dat) |
|---|---|---|---|
{parts_table_rows}

---

## 2. Paleta Oficial de Colores LDraw (LDConfig.ldr)
| Zona del Modelo | Nombre Oficial LDraw | Código LDraw | Uso específico en el script Python (generate.py) |
|---|---|---|---|
{color_table_rows}

---

## 3. Arquitectura del Modelo (Root MPD + Submodelos)
El archivo raíz `{slug}.mpd` referencia coordinadamente a los siguientes submodelos `.ldr`:
{submodel_list}

---

## 4. Alcance, Dimensiones y Coordenadas
- **Dimensiones de planta:** {dimensions.get('x_studs', 24)}×{dimensions.get('z_studs', 20)} studs ({dimensions.get('x_studs', 24)*20}×{dimensions.get('z_studs', 20)*20} LDU).
- **Altura aproximada:** {dimensions.get('height_bricks', 20)} hiladas de bricks / plates ({dimensions.get('height_bricks', 20)*24} LDU).
- **Convención de Coordenadas LDraw:**
  - `+Y` es **HACIA ABAJO** (el mundo se eleva hacia valores negativos de Y).
  - `-Z` es **HACIA ADELANTE**, `+X` es **HACIA LA DERECHA**.
  - `1 stud = 20 LDU`, `1 brick = 24 LDU`, `1 plate = 8 LDU`.
  - La base inferior se apoya sobre `Y = 0` o el pedestal de base.
{notes_section}
## 5. Reglas de Validación y Calidad
1. **Sin piezas flotantes:** Toda pieza debe tener soporte inferior o estar debidamente anclada al grid de studs o clips SNOT.
2. **Cero colisiones:** Validar que los volúmenes no intersequen con `./ldraw-agent validate`.
3. **Colores estrictos:** Usar únicamente códigos enteros de la tabla oficial (p. ej. Dark Blue=272, Black=0, Tan=19, Light Nougat=78, etc.).
4. **Reproducibilidad:** El generador `generate.py` debe emitir `{slug}.plan.json`, el cual se compila con `./ldraw-agent build`.
"""
