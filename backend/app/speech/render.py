"""Versioned Aviation Speech Rendering Layer.

Produces a **derived** TTS render text from the canonical question text. The canonical /
display text is never modified (GOAL.md / ADR-0001); only the text handed to TTS synthesis
is rendered. The render profile is versioned so every historical TTS call is traceable to
the exact rendering ruleset that produced its input.

Safety: rendering is a deterministic, invertible encoding — abbreviations and model /
engine designators are spelled out (e.g. ``MEL`` -> ``M E L``, ``B737-800`` ->
``B 7 3 7 8 0 0``) and the safe normalizer ruleset (``builtin-v4``) merges those spaced
forms back to canonical. No fuzzy per-speaker rules live here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SpeechRenderProfile:
    version: str
    spaced_terms: tuple[str, ...]


_ABBREVIATIONS = (
    "MEL", "AMM", "CDL", "FIM", "TSM", "IPC", "MPD", "EO", "ETOPS", "APU", "AD", "SB",
)
_MODELS_NO_HYPHEN = ("B737NG", "A330", "CFM56")
# Models with a hyphen are rendered without the hyphen; the safe normalizer compact rules
# recover the canonical hyphenated form (B737800 -> B737-800, CFM567B -> CFM56-7B).
_HYPHEN_MODELS = {
    "B737-800": "B 7 3 7 8 0 0",
    "CFM56-7B": "C F M 5 6 7 B",
}

RENDER_PROFILE_V1 = SpeechRenderProfile(
    version="render-v1",
    spaced_terms=_ABBREVIATIONS + _MODELS_NO_HYPHEN,
)


def render_for_tts(text: str, profile: SpeechRenderProfile = RENDER_PROFILE_V1) -> str:
    """Derive the TTS input text by spelling out aviation terms (canonical untouched)."""
    result = text
    # Hyphenated models first so they are not partially matched by their prefix terms.
    for canonical, spaced in _HYPHEN_MODELS.items():
        pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(canonical) + r"(?![A-Za-z0-9])")
        result = pattern.sub(spaced, result)
    for term in profile.spaced_terms:
        pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])")
        result = pattern.sub(" ".join(term), result)
    return result
