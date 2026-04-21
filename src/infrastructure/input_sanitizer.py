"""Minimal input sanitation for user text that flows into LLM prompts.

Prompt injection cannot be fully prevented, but we raise the bar by:
  * stripping C0/C1 control characters (except the usual whitespace),
  * capping the input length,
  * rejecting obvious instruction-override markers when a strict check is
    requested (used at the equipment-model extraction boundary; the main
    conversation still passes free text through with only normalisation).

The goal is to keep responses deterministic and logs clean — not to act as
a full policy engine.
"""

from __future__ import annotations

import re
import unicodedata

# Allow ordinary whitespace (\t, \n, \r) but drop other control chars.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Heuristic markers that usually indicate an override attempt. We do *not*
# use these to reject conversation turns — they only gate the narrow path
# where a user-typed slug becomes a filesystem read. Anything richer would
# belong in a dedicated guardrail layer.
_OVERRIDE_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "disregard previous",
    "system:",
    "<|system|>",
    "<|im_start|>",
)

DEFAULT_MAX_LEN = 8_000


def normalise_user_text(text: str, max_len: int = DEFAULT_MAX_LEN) -> str:
    """Return a sanitised copy of ``text`` safe to forward to an LLM.

    Normalisation is conservative: it preserves meaning while removing
    characters that tend to break logging, JSON serialisation, or prompt
    structure. Non-string inputs return an empty string.
    """
    if not isinstance(text, str) or not text:
        return ""
    cleaned = unicodedata.normalize("NFKC", text)
    cleaned = _CONTROL_CHARS_RE.sub("", cleaned)
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
    return cleaned


def looks_like_prompt_override(text: str) -> bool:
    """Return True if ``text`` contains obvious instruction-override markers."""
    if not isinstance(text, str):
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in _OVERRIDE_MARKERS)
