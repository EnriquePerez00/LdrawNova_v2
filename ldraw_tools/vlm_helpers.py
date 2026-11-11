"""VLM response parsing and validation helpers."""
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def parse_json_block(text: str, default: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Extract JSON object from text (handles markdown code blocks, etc.).
    
    Args:
        text: Text containing JSON
        default: Default dict if no JSON found
    
    Returns:
        Parsed JSON dict or default
    """
    from typing import Optional
    default = default or {}
    
    # Try markdown code block first
    match = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try raw JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try extracting {...} blocks
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    
    logger.warning(f"[VLM] Could not extract JSON from: {text[:200]}")
    return default


def validate_against_schema(data: Dict, schema_path: Path) -> Tuple[bool, List[str]]:
    """
    Validate a dict against a JSON schema file.
    
    Returns:
        (is_valid, error_messages)
    """
    try:
        import jsonschema
    except ImportError:
        logger.warning("jsonschema not installed; skipping validation")
        return True, []
    
    if not schema_path.exists():
        logger.warning(f"Schema not found: {schema_path}")
        return True, []
    
    try:
        schema = json.loads(schema_path.read_text())
        jsonschema.validate(data, schema)
        return True, []
    except jsonschema.ValidationError as e:
        return False, [str(e)]
    except Exception as e:
        logger.warning(f"Schema validation error: {e}")
        return True, []
