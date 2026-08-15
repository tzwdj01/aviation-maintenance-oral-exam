from __future__ import annotations

from dataclasses import dataclass

from app.normalization.vocabulary import VocabularySnapshot


@dataclass(frozen=True)
class Mapping:
    raw_fragment: str
    normalized_fragment: str
    start_char: int
    end_char: int
    confidence: float
    normalization_rule: str


@dataclass(frozen=True)
class NormalizationResult:
    normalized_text: str
    mappings: tuple[Mapping, ...]
    warnings: tuple[str, ...]
    vocabulary_version: str


LAYER_ONE = {"B七三七NG": "B737NG", "M P D": "MPD"}
LAYER_TWO = {"维修放心": "维修放行"}
LOW_CONFIDENCE = {"L": ("fault", "保留故障", "MEL", "CDL")}


def normalize(text: str, vocabulary: VocabularySnapshot) -> NormalizationResult:
    result, mappings, warnings = text, [], []
    for raw, replacement in LAYER_ONE.items():
        start = result.find(raw)
        if start >= 0:
            result = result.replace(raw, replacement)
            mappings.append(Mapping(raw, replacement, start, start + len(raw), 1.0, "LAYER_1_EXACT_ALIAS"))
    for raw, replacement in LAYER_TWO.items():
        start = result.find(raw)
        if start >= 0 and any(hint in result for hint in ("维修", "记录", "放行", "工作单")):
            result = result.replace(raw, replacement)
            mappings.append(Mapping(raw, replacement, start, start + len(raw), 0.98, "LAYER_2_CONTEXT_ALIAS"))
    for fragment, hints in LOW_CONFIDENCE.items():
        if fragment in text and any(hint.lower() in text.lower() for hint in hints):
            warnings.append(f"Low-confidence candidate '{fragment}' retained without replacement")
    # Published vocabulary can extend, but not rewrite, the deterministic layers above.
    for term in vocabulary.terms:
        for alias in term.aliases:
            start = result.find(alias)
            if start >= 0 and alias != term.canonical:
                result = result.replace(alias, term.canonical)
                mappings.append(Mapping(alias, term.canonical, start, start + len(alias), term.confidence, "VOCABULARY_ALIAS"))
    return NormalizationResult(result, tuple(mappings), tuple(warnings), vocabulary.version)
