"""
DeepL translation helper.

Translates missing language fields on an Event object.
Translation only happens when the target language field is empty
AND the target language differs from the original language.

Supported languages: ja (Japanese), zh (Traditional Chinese), en (English)
"""

import logging
import os
from typing import Optional

import deepl

logger = logging.getLogger(__name__)

# DeepL language codes
LANG_MAP = {
    "ja": "JA",
    "zh": "ZH-HANT",   # Traditional Chinese
    "en": "EN-US",
}

_client: Optional[deepl.Translator] = None


def _get_client() -> deepl.Translator:
    global _client
    if _client is None:
        api_key = os.environ.get("DEEPL_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPL_API_KEY environment variable is not set.")
        _client = deepl.Translator(api_key)
    return _client


def _translate(text: Optional[str], source_lang: str, target_lang: str) -> Optional[str]:
    """Translate text from source_lang to target_lang. Returns None on failure."""
    if not text:
        return None
    if source_lang == target_lang:
        return text
    try:
        client = _get_client()
        result = client.translate_text(
            text,
            source_lang=LANG_MAP[source_lang],
            target_lang=LANG_MAP[target_lang],
        )
        return result.text
    except Exception as exc:
        logger.error(
            "DeepL translation failed (%s → %s): %s", source_lang, target_lang, exc
        )
        return None


def fill_translations(event) -> None:
    """
    Mutates the Event in-place: translates any missing name/description fields.

    Strategy:
      - Use the original_language field to determine the source language.
      - For each target language that is different from original and has no value, translate.
    """
    orig = event.original_language  # "ja" | "zh" | "en"
    all_langs = ["ja", "zh", "en"]

    for lang in all_langs:
        if lang == orig:
            continue  # Skip original language

        # Determine the source text for this field
        source_name = getattr(event, f"name_{orig}")
        source_desc = getattr(event, f"description_{orig}")

        # Only translate if the target field is empty
        if not getattr(event, f"name_{lang}"):
            translated_name = _translate(source_name, orig, lang)
            if translated_name:
                setattr(event, f"name_{lang}", translated_name)

        if not getattr(event, f"description_{lang}"):
            translated_desc = _translate(source_desc, orig, lang)
            if translated_desc:
                setattr(event, f"description_{lang}", translated_desc)
