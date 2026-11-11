"""FastAPI web application for LdrawNova generative pipeline."""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from webapp.generator_service import (
    ACTIVE_JOBS,
    OUTPUT_ROOT,
    JobManager,
    execute_generation_pipeline,
    generate_slug_from_prompt,
)

app = FastAPI(title="LdrawNova Generative Studio", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure output directory exists and mount it
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/output", StaticFiles(directory=str(OUTPUT_ROOT)), name="output")

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>LdrawNova Web Studio</h1><p>Index file not found.</p>")
    return HTMLResponse(index_file.read_text(encoding="utf-8"))


@app.post("/api/generate")
async def start_generation(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    slug: Optional[str] = Form(None),
    api_key: Optional[str] = Form(None),
    strategy: Optional[str] = Form("auto"),
    provider: Optional[str] = Form(None),
    llm_base_url: Optional[str] = Form(None),
    llm_secret: Optional[str] = Form(None),
    plan_model: Optional[str] = Form(None),
    act_model: Optional[str] = Form(None),
):
    if not prompt or not prompt.strip():
        raise HTTPException(status_code=400, detail="El prompt inicial no puede estar vacío.")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="La imagen subida está vacía.")

    # Determine slug name
    final_slug = (slug or "").strip()
    if not final_slug:
        final_slug = generate_slug_from_prompt(prompt)
    else:
        # Sanitize slug
        import re
        final_slug = re.sub(r"[^a-zA-Z0-9_-]", "-", final_slug).lower()

    job_id = JobManager.create_job(final_slug, prompt)

    # Assemble LLM provider configuration
    # NOTE: provider is fixed to 'gemini' + 'llmproxy' via .env
    # (UI no longer allows user selection)
    llm_config = {
        "provider": "gemini",  # Fixed: always use Gemini for Phase 1-2
        "api_key": api_key.strip() if api_key else None,
        "base_url": os.getenv("LLM_BASE_URL", "http://localhost:6655/litellm"),  # From .env
        "secret": os.getenv("LLM_SECRET"),  # From .env
        "plan_model": os.getenv("LLM_A2_MODEL", "claude-haiku-5"),  # From .env
        "act_model": os.getenv("LLM_A3_MODEL", "gemini-2.5-flash"),  # From .env
    }

    # Launch background task
    asyncio.create_task(
        execute_generation_pipeline(
            job_id=job_id,
            slug=final_slug,
            user_prompt=prompt,
            input_image_bytes=image_bytes,
            api_key=api_key.strip() if api_key else None,
            strategy=(strategy or "auto").strip().lower(),
            llm_config=llm_config
        )
    )

    return JSONResponse({
        "job_id": job_id,
        "slug": final_slug,
        "status": "started"
    })


@app.post("/api/validate/{job_id}")
async def validate_legolized(
    job_id: str,
    action: str = Form(...),  # "approve" or "modify"
    feedback: Optional[str] = Form(None),
    # Categorization: "visual", "general", or "both" (default "visual" for
    # backwards compatibility with any older client).
    feedback_type: Optional[str] = Form("visual"),
    # Procedural / Gemini image controls. Optional: when absent we keep the
    # values currently stored in the job state.
    grid_size: Optional[int] = Form(None),
    cell_px: Optional[int] = Form(None),
    rembg_enabled: Optional[bool] = Form(None),
):
    """Permite al usuario validar la imagen legolizada o pedir modificaciones antes de continuar.

    ``feedback_type`` controls where the comment is routed:
      - ``visual``  → appended to ``job['visual_feedbacks']`` and the image is regenerated.
      - ``general`` → appended to ``job['general_feedbacks']`` which enriches the
        master prompt used by Fase 2 (image regen) **and** Fase 3 (design brief).
        No image regeneration happens.
      - ``both``    → appended to both lists; image is regenerated.
    """
    job = ACTIVE_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")

    if job.get("status") != "waiting_validation":
        raise HTTPException(status_code=400, detail="El trabajo no está esperando validación actualmente.")

    if action == "approve":
        job["approved"] = True
        job["status"] = "running"
        job["validation_event"].set()
        return JSONResponse({"status": "approved", "message": "Imagen validada. Continuando con la generación..."})
    elif action == "modify":
        ftype = (feedback_type or "visual").strip().lower()
        if ftype not in ("visual", "general", "both"):
            raise HTTPException(status_code=400, detail="feedback_type debe ser 'visual', 'general' o 'both'.")

        # Validate slider ranges (allow None → keep current).
        allowed_grid = {16, 32, 48, 96, 192, 240}
        allowed_cell = {4, 8, 16, 32}
        if grid_size is not None and grid_size not in allowed_grid:
            raise HTTPException(status_code=400, detail=f"grid_size debe estar en {sorted(allowed_grid)}")
        if cell_px is not None and cell_px not in allowed_cell:
            raise HTTPException(status_code=400, detail=f"cell_px debe estar en {sorted(allowed_cell)}")
        if grid_size is not None and cell_px is not None and grid_size * cell_px > 4096:
            raise HTTPException(status_code=400, detail="Resolución combinada demasiado alta (grid_size*cell_px > 4096).")

        fb = (feedback or "").strip()
        appended_general = False
        appended_visual = False
        if fb:
            if ftype in ("general", "both"):
                job["general_feedbacks"].append(fb)
                appended_general = True
            if ftype in ("visual", "both"):
                job["visual_feedbacks"].append(fb)
                appended_visual = True

        if grid_size is not None:
            job["grid_size"] = grid_size
        if cell_px is not None:
            job["cell_px"] = cell_px
        if rembg_enabled is not None:
            job["rembg_enabled"] = bool(rembg_enabled)

        # Decide whether to regenerate the image this round. A pure "general"
        # comment with no slider/toggle change just updates the master prompt.
        sliders_changed = grid_size is not None or cell_px is not None or rembg_enabled is not None
        job["regenerate_image"] = (ftype in ("visual", "both")) or sliders_changed

        # Keep legacy field populated for any code still reading it.
        job["feedback_prompt"] = fb
        job["approved"] = False
        job["status"] = "running"
        job["validation_event"].set()

        return JSONResponse({
            "status": "regenerating" if job["regenerate_image"] else "prompt_enriched",
            "feedback_type": ftype,
            "appended_general": appended_general,
            "appended_visual": appended_visual,
            "general_feedbacks": list(job["general_feedbacks"]),
            "visual_feedbacks": list(job["visual_feedbacks"]),
            "grid_size": job["grid_size"],
            "cell_px": job["cell_px"],
            "rembg_enabled": job["rembg_enabled"],
            "message": (
                "Comentario general añadido al prompt maestro. La imagen se mantiene."
                if not job["regenerate_image"]
                else "Regenerando imagen legolizada con los comentarios..."
            ),
        })
    else:
        raise HTTPException(status_code=400, detail="Acción no válida. Use 'approve' o 'modify'.")


@app.post("/api/cancel/{job_id}")
async def cancel_job(job_id: str):
    """Aborta un job en curso.

    - Marca ``status = "cancelled"``.
    - Hace ``set()`` del ``validation_event`` para desbloquear la Fase 2 si
      el pipeline está esperando validación.
    - El pipeline chequea el flag tras la espera y lanza
      ``JobCancelledException`` para terminar limpiamente sin disparar la
      rama genérica de error.
    - El bucle SSE sale cuando detecta ``cancelled``.
    """
    job = ACTIVE_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")

    if job.get("status") in ("completed", "failed", "cancelled"):
        return JSONResponse({
            "status": job["status"],
            "message": "El trabajo ya había finalizado; no se requiere cancelación."
        })

    job["status"] = "cancelled"
    # Desbloquear la Fase 2 si el pipeline está en await validation_event.wait()
    ev = job.get("validation_event")
    if ev is not None:
        ev.set()

    return JSONResponse({
        "status": "cancelled",
        "message": "Pipeline cancelado. Los componentes de UX se reinicializarán."
    })


@app.get("/api/status/{job_id}")
async def get_job_status(job_id: str):
    job = ACTIVE_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")

    return JSONResponse({
        "id": job["id"],
        "slug": job["slug"],
        "status": job["status"],
        "phase": job["phase"],
        "progress": job["progress"],
        "logs": job["logs"],
        "artifacts": job["artifacts"],
        "error": job["error"]
    })


@app.get("/api/stream/{job_id}")
async def stream_job_events(job_id: str):
    """Server-Sent Events (SSE) streaming for real-time iteration loop feedback."""
    job = ACTIVE_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")

    async def event_generator():
        # First send all historical logs
        for log_entry in job["logs"]:
            yield f"data: {json.dumps(log_entry)}\n\n"
        # Si el job ya terminó (incluyendo cancelado) antes de conectarse,
        # cerrar el stream para que el cliente libere el EventSource.
        if job["status"] in ("completed", "failed", "cancelled"):
            return

        queue: asyncio.Queue = job["events_queue"]
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=25.0)
                yield f"data: {json.dumps(event)}\n\n"
                if job["status"] in ("completed", "failed", "cancelled"):
                    break
            except asyncio.TimeoutError:
                # Keep-alive ping
                yield ": keep-alive\n\n"
                if job["status"] in ("completed", "failed", "cancelled"):
                    break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/designs")
async def list_designs():
    """Lists existing design outputs."""
    designs = []
    if not OUTPUT_ROOT.exists():
        return JSONResponse({"designs": []})

    for item in sorted(OUTPUT_ROOT.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if item.is_dir() and not item.name.startswith("."):
            slug = item.name
            render_home = item / "renders" / "home.png"
            mpd_file = item / f"{slug}.mpd"
            meta_file = item / "metadata.json"

            metadata = {}
            if meta_file.exists():
                try:
                    metadata = json.loads(meta_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

            designs.append({
                "slug": slug,
                "title": metadata.get("title", slug),
                "created_at": item.stat().st_mtime,
                "has_render": render_home.exists(),
                "render_url": f"/output/{slug}/renders/home.png" if render_home.exists() else None,
                "has_mpd": mpd_file.exists(),
                "mpd_url": f"/output/{slug}/{slug}.mpd" if mpd_file.exists() else None,
            })



@app.get("/api/iterations/{slug}")
async def get_iterations(slug: str):
    """Fetch iteration data for a given design slug."""
    design_dir = OUTPUT_ROOT / slug
    if not design_dir.exists():
        raise HTTPException(status_code=404, detail=f"Design {slug} not found")
    
    try:
        from ldraw_tools.loop_state_manager import LoopStateManager
        manager = LoopStateManager(design_dir)
        loop_data = manager.load_state() or {}
        
        iterations = []
        
        # Load each iteration's data from loop_state
        for iter_info in loop_data.get('iterations', []):
            iter_num = iter_info.get('iter_num', 0)
            
            # Load GT images (shared across iterations)
            gt_dir = design_dir / "gt"
            gt_images = {}
            if gt_dir.exists():
                for view in ["cenital", "frontal", "lateral_izq", "lateral_der"]:
                    img_path = gt_dir / f"gt_{view}.png"
                    if img_path.exists():
                        gt_images[view] = f"/output/{slug}/gt/gt_{view}.png"
            
            # Load render images (shared across iterations)
            renders_dir = design_dir / "renders"
            render_images = {}
            if renders_dir.exists():
                for view in ["home", "front", "right", "top"]:
                    img_path = renders_dir / f"{view}.png"
                    if img_path.exists():
                        render_images[view] = f"/output/{slug}/renders/{view}.png"
            
            # Load judge score from diff_report (real path or iter-specific)
            judge_score = 0
            per_axis_scores = {}
            diffs = []
            
            # Try iter-specific first, then global
            diff_report_paths = [
                design_dir / f"iter_{iter_num}" / "diff_report.json",
                design_dir / "diff_report.json"
            ]
            
            for diff_report_path in diff_report_paths:
                if diff_report_path.exists():
                    try:
                        diff_data = json.loads(diff_report_path.read_text())
                        judge_score = diff_data.get("global_score", 0)
                        per_axis_scores = diff_data.get("per_axis_scores", {})
                        diffs = diff_data.get("diffs", [])
                        break
                    except Exception:
                        pass
            
            iterations.append({
                "iteration": iter_num,
                "gt_images": gt_images,
                "render_images": render_images,
                "judge_score": judge_score,
                "per_axis_scores": per_axis_scores,
                "diffs": diffs,
            })
        
        return JSONResponse({
            "slug": slug,
            "iterations": iterations,
            "total_iterations": len(iterations),
            "kpis": {
                "summary": {
                    "best_score": loop_data.get("best_score", 0),
                    "score_threshold": loop_data.get("config", {}).get("score_threshold", 85),
                    "max_iterations": loop_data.get("config", {}).get("max_iterations", 4),
                    "iterations_used": loop_data.get("current_iteration", 0) + 1,
                    "converged": loop_data.get("converged", False),
                    "stop_reason": loop_data.get("stop_reason", "running"),
                    "total_elapsed_sec": loop_data.get("telemetry", {}).get("total_elapsed_sec", 0),
                },
                "telemetry": loop_data.get("telemetry", {}),
                "diffs": {
                    "high_count": 0,
                    "medium_count": 0,
                    "low_count": 0,
                }
            }
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "slug": slug,
            "iterations": [],
            "error": str(e),
        })

    return JSONResponse({"designs": designs})
