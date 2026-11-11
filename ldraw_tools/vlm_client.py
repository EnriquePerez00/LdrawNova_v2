"""VLM Client — Unified interface to Gemini 2.5 Flash via proxy LiteLLM."""
import base64
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _b64_data_uri(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """Encode image bytes as base64 data URI."""
    return f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"


def vlm_chat(
    model: str,
    prompt: str,
    image_paths: Optional[List[Path]] = None,
    llm_config: Optional[Dict[str, Any]] = None,
    timeout: int = 120,
) -> str:
    """
    Call a VLM via proxy LiteLLM (OpenAI-compatible endpoint).
    
    Args:
        model: Model ID (e.g., "gemini-2.5-flash")
        prompt: Text prompt
        image_paths: List of Path objects to images (optional; multi-image OK)
        llm_config: Dict with keys: base_url, secret, fallback_model, fallback_base_url
        timeout: Request timeout in seconds
    
    Returns:
        Assistant text response
    
    Raises:
        RuntimeError: If all backends fail
    """
    import requests
    
    # Normalize config
    llm_config = llm_config or {}
    base_url = (llm_config.get("base_url") or "http://localhost:6655/litellm").rstrip("/")
    secret = llm_config.get("secret", "")
    fallback_model = llm_config.get("fallback_model", "llama3.2-vision:11b")
    fallback_base_url = llm_config.get("fallback_base_url", "http://127.0.0.1:11434")
    
    # Build content with multi-image support
    content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
    
    if image_paths:
        for img_path in image_paths:
            img_path = Path(img_path)
            if not img_path.exists():
                logger.warning(f"Image not found: {img_path}")
                continue
            
            img_bytes = img_path.read_bytes()
            mime_type = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }.get(img_path.suffix.lower(), "image/jpeg")
            
            content.append({
                "type": "image_url",
                "image_url": {"url": _b64_data_uri(img_bytes, mime_type)}
            })
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.3,
    }
    
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    
    # Try primary backend (proxy LiteLLM)
    url = f"{base_url}/v1/chat/completions"
    primary_err = None
    try:
        logger.debug(f"[VLM] Primary: {url} model={model}")
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("VLM response has no 'choices'")
        
        message = choices[0].get("message", {})
        text = (message.get("content") or "").strip()
        logger.info(f"[VLM] {model} OK ({len(text)} chars)")
        return text
    
    except Exception as e:
        primary_err = e
        logger.warning(f"[VLM] Primary failed: {e}")
    
    # Fallback to local VLM (Ollama)
    if fallback_model and fallback_base_url:
        logger.info(f"[VLM] Trying fallback: {fallback_model}@{fallback_base_url}")
        
        fallback_url = f"{fallback_base_url}/v1/chat/completions"
        fallback_headers = {"Content-Type": "application/json"}
        fallback_payload = {
            "model": fallback_model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.3,
        }
        
        try:
            resp = requests.post(fallback_url, headers=fallback_headers, json=fallback_payload, timeout=timeout)
            resp.raise_for_status()
            
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("Fallback response has no 'choices'")
            
            message = choices[0].get("message", {})
            text = (message.get("content") or "").strip()
            logger.info(f"[VLM] Fallback OK ({len(text)} chars)")
            return text
        
        except Exception as fallback_err:
            logger.warning(f"[VLM] Fallback also failed: {fallback_err}")
    
    raise RuntimeError(f"All VLM backends failed. Primary: {primary_err}")
