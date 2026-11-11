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

    # Assemble LLM provider configuration (Google AI Studio vs. local LiteLLM proxy)
    llm_config = {
        "provider": (provider or "gemini").strip().lower(),
        "api_key": api_key.strip() if api_key else None,
        "base_url": llm_base_url.strip() if llm_base_url else None,
        "secret": llm_secret.strip() if llm_secret else None,
        "plan_model": plan_model.strip() if plan_model else None,
        "act_model": act_model.strip() if act_model else None,
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
    feedback: Optional[str] = Form(None)
):
    """Permite al usuario validar la imagen legolizada o pedir modificaciones antes de continuar."""
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
        job["approved"] = False
        job["feedback_prompt"] = (feedback or "").strip()
        job["status"] = "running"
        job["validation_event"].set()
        return JSONResponse({"status": "regenerating", "feedback": job["feedback_prompt"], "message": "Regenerando imagen legolizada con los comentarios..."})
    else:
        raise HTTPException(status_code=400, detail="Acción no válida. Use 'approve' o 'modify'.")


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

        queue: asyncio.Queue = job["events_queue"]
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=25.0)
                yield f"data: {json.dumps(event)}\n\n"
                if job["status"] in ["completed", "failed"]:
                    break
            except asyncio.TimeoutError:
                # Keep-alive ping
                yield ": keep-alive\n\n"
                if job["status"] in ["completed", "failed"]:
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

    return JSONResponse({"designs": designs})
