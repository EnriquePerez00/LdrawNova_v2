"""
LiteLLM HTTP client for the Multi-Agent PDF -> .io Pipeline.

Communicates with the local LiteLLM proxy at LITELLM_BASE_URL (default:
http://localhost:8000) using the OpenAI-compatible /v1/chat/completions endpoint.
Auth is via Bearer token (LITELLM_API_KEY=sk-default); the proxy handles Google
Cloud ADC translation to Gemini on its end.

Usage:
    from src.agentic_pipeline.litellm_client import LiteLLMClient

    client = LiteLLMClient(model="gemini-2.5-flash")
    result = client.chat("Describe this image", images=[png_bytes])
    text   = client.chat_text("What is 2+2?")
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class LiteLLMClient:
    """
    Thin HTTP client wrapping the LiteLLM proxy at localhost:8000.

    The proxy handles credential translation (Google ADC -> Gemini API).
    All calls use requests.post to /v1/chat/completions with an OpenAI-compatible
    payload — the `litellm` Python package is NOT used.

    Parameters
    ----------
    model : str, optional
        Model name to pass to the proxy (e.g. 'gemini-2.5-flash',
        'gemini-2.5-pro').  Defaults to LITELLM_MODEL_GEMINI_FLASH_2_5 env var
        or 'gemini-2.5-flash'.
    """

    def __init__(self, model: Optional[str] = None) -> None:
        self.base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:8000").rstrip("/")
        self.api_key = os.getenv("LITELLM_API_KEY", "sk-default")
        self.model = model or os.getenv("LITELLM_MODEL_GEMINI_FLASH_2_5", "gemini-2.5-flash")
        self.timeout_sec = int(os.getenv("LITELLM_VLM_TIMEOUT_SEC", "15"))
        self.retry_attempts = int(os.getenv("LITELLM_VLM_RETRY_ATTEMPTS", "1"))
        cache_dir = os.getenv("LITELLM_VLM_CACHE_DIR", "data/litellm_cache")
        self._cache_dir = Path(cache_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(
        self,
        prompt: str,
        images: Optional[List[bytes]] = None,
        json_response: bool = True,
        cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Send a text prompt (with optional PNG image bytes) to the model.

        Returns the parsed JSON dict from the model response.  On any failure
        (network, parse, timeout) returns an empty dict ``{}`` — callers must
        treat that as "no signal" and fall back to deterministic logic.

        Parameters
        ----------
        prompt : str
            User-turn text prompt.
        images : list of bytes, optional
            PNG image bytes to include as base64 data URLs in the message.
        json_response : bool
            If True (default) parse the model output as JSON.  If False return
            ``{"text": <raw_string>}``.
        cache : bool
            Cache responses on disk by (model, prompt, image hashes) to avoid
            duplicate calls during training runs.
        """
        cache_key = self._cache_key(prompt, images)
        if cache:
            cached = self._load_cache(cache_key)
            if cached is not None:
                return cached

        content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        if images:
            for img_bytes in images:
                b64 = base64.b64encode(img_bytes).decode("ascii")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                })

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.0,
        }
        if json_response:
            payload["response_format"] = {"type": "json_object"}

        result = self._post_with_retry(payload)
        if not result:
            return {}

        raw_text = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not raw_text:
            return {}

        if not json_response:
            return {"text": raw_text}

        parsed = self._parse_json(raw_text)
        if cache and parsed:
            self._save_cache(cache_key, parsed)
        return parsed

    def vlm_compare(self, image_png_bytes: bytes, prompt: str) -> Dict[str, Any]:
        """
        Backward-compatible single-image VLM call.

        Equivalent to ``chat(prompt, images=[image_png_bytes])``.
        """
        return self.chat(prompt, images=[image_png_bytes])

    def chat_text(self, prompt: str, cache: bool = True) -> str:
        """
        Text-only call that returns the raw string response (no JSON parsing).
        """
        result = self.chat(prompt, images=None, json_response=False, cache=cache)
        return result.get("text", "")

    def is_available(self) -> bool:
        """Returns True if the LiteLLM proxy responds to /health within 3 s."""
        try:
            r = requests.get(f"{self.base_url}/health", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post_with_retry(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/v1/chat/completions"
        last_exc: Optional[Exception] = None
        for attempt in range(max(1, self.retry_attempts)):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout_sec,
                )
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_exc = exc
                if attempt < self.retry_attempts - 1:
                    time.sleep(1.0)
        logger.warning("LiteLLMClient call failed after %d attempts: %s", self.retry_attempts, last_exc)
        return None

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Parse JSON from model output, stripping markdown fences if present."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            # strip first and last fence lines
            inner = "\n".join(lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:])
            cleaned = inner.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find first JSON object in the text
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(cleaned[start:end])
                except json.JSONDecodeError:
                    pass
        logger.debug("LiteLLMClient: could not parse JSON from response: %r", text[:200])
        return {}

    def _cache_key(self, prompt: str, images: Optional[List[bytes]]) -> str:
        h = hashlib.sha256()
        h.update(self.model.encode())
        h.update(prompt.encode())
        for img in (images or []):
            h.update(img[:4096])  # hash first 4 KB of each image
        return h.hexdigest()

    def _cache_path(self, key: str) -> Path:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        return self._cache_dir / f"{key}.json"

    def _load_cache(self, key: str) -> Optional[Dict[str, Any]]:
        p = self._cache_path(key)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def _save_cache(self, key: str, data: Dict[str, Any]) -> None:
        try:
            with open(self._cache_path(key), "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass
