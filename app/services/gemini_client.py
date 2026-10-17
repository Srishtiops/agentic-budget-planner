import json
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

CATEGORIES = [
    "Food",
    "Groceries",
    "Travel",
    "Shopping",
    "Bills",
    "Entertainment",
    "Healthcare",
    "Education",
    "Housing",
    "Other",
]


def _model():
    if not settings.gemini_api_key:
        return None
    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        return genai.GenerativeModel(settings.gemini_model)
    except Exception as exc:  # pragma: no cover - optional dependency path
        logger.warning("Gemini unavailable: %s", exc)
        return None


def generate_text(prompt: str) -> str | None:
    model = _model()
    if model is None:
        return None
    try:
        response = model.generate_content(prompt)
        return (response.text or "").strip()
    except Exception as exc:
        logger.warning("Gemini generation failed: %s", exc)
        return None


def generate_json(prompt: str) -> Any | None:
    text = generate_text(prompt + "\nReturn valid JSON only.")
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Gemini returned non-JSON output")
        return None
