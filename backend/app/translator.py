import logging
import os
from typing import Dict

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

logger = logging.getLogger(__name__)

_TRANSLATION_CACHE: Dict[str, str] = {}
_MODEL_NAME = "gemini-1.5-flash"
_MODEL_DISABLED = False
_MODEL_DISABLE_REASON = ""


def translate_text(text: str, target_lang: str) -> str:
    global _MODEL_DISABLED, _MODEL_DISABLE_REASON

    original = str(text or "").strip()
    if not original:
        return ""

    if target_lang == "uz":
        return original

    cache_key = f"{target_lang}::{original}"
    cached = _TRANSLATION_CACHE.get(cache_key)
    if cached is not None:
        return cached

    if _MODEL_DISABLED:
        _TRANSLATION_CACHE[cache_key] = original
        return original

    prompt = (
        f"Translate the following text to {target_lang}. Keep meaning accurate:\n"
        f"{original}"
    )

    try:
        model = genai.GenerativeModel(_MODEL_NAME)
        response = model.generate_content(prompt)
        translated = str(getattr(response, "text", "") or "").strip()
        if translated:
            _TRANSLATION_CACHE[cache_key] = translated
            return translated
    except Exception:  # noqa: BLE001
        _MODEL_DISABLED = True
        _MODEL_DISABLE_REASON = f"{_MODEL_NAME} is unavailable in current API setup"
        logger.warning("Translation disabled: %s", _MODEL_DISABLE_REASON)

    # Fallback: never crash, keep original Uzbek/source text.
    _TRANSLATION_CACHE[cache_key] = original
    return original
