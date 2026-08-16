"""Versioned aviation terminology normalizer.

The normalizer maps ASR output to a normalized transcript while **never overwriting the raw
ASR text** (GOAL.md principle C). Rules are grouped into versioned rulesets so historical
normalizations can be traced to the exact ruleset that produced them
(`docs/speech-production.md` §4).

Design rules:
- High-confidence rules (exact aliases, hyphen/typed variants, phrase homophones) are
  applied and recorded as auditable mappings.
- Ambiguous candidates are **not** silently rewritten; they produce a warning so the case
  is routed for human review (docs/speech-production.md §6). Plain English/numbers are
  never rewritten into aviation abbreviations without high confidence.
"""

from __future__ import annotations

import re
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
    ruleset_version: str


@dataclass(frozen=True)
class _Ruleset:
    high_confidence: tuple[tuple[str, str, str], ...]
    spaced_abbreviations: tuple[str, ...]
    low_confidence: dict[str, tuple[str, ...]]


# Every change to a ruleset must bump its version so history stays traceable.
NORMALIZER_RULESET_VERSION = "builtin-v4"


RULESETS: dict[str, _Ruleset] = {
    "builtin-v1": _Ruleset(
        high_confidence=(
            ("B七三七NG", "B737NG", "LAYER_1_EXACT_ALIAS"),
            ("M P D", "MPD", "LAYER_1_EXACT_ALIAS"),
            ("维修放心", "维修放行", "LAYER_2_CONTEXT_ALIAS"),
        ),
        spaced_abbreviations=(),
        low_confidence={"L": ("fault", "保留故障", "MEL", "CDL")},
    ),
    "builtin-v2": _Ruleset(
        high_confidence=(
            # builtin-v1 rules preserved verbatim
            ("B七三七NG", "B737NG", "LAYER_1_EXACT_ALIAS"),
            ("M P D", "MPD", "LAYER_1_EXACT_ALIAS"),
            ("维修放心", "维修放行", "LAYER_2_CONTEXT_ALIAS"),
            # builtin-v2: hyphen / typed-variant / phrase homophone corrections (high confidence)
            ("B-737NG", "B737NG", "V2_SPACING_HYPHEN"),
            ("B七三七负八百", "B737-800", "V2_TYPED_VARIANT"),
            ("CFM56七字节", "CFM56-7B", "V2_TYPED_VARIANT"),
            ("试航指令", "适航指令", "V2_HOMOPHONE_PHRASE"),
            ("对低设备清单", "最低设备清单", "V2_HOMOPHONE_PHRASE"),
        ),
        spaced_abbreviations=("MEL", "AMM", "FIM", "CDL", "TSM", "IPC", "MPD", "EO", "ETOPS", "APU"),
        low_confidence={
            "L": ("fault", "保留故障", "MEL", "CDL"),
            "四百五十": ("CDL", "MEL", "最低设备清单", "故障", "保留", "项目"),
            "NPD": ("MPD", "维修项目", "检查项目"),
            "E U": ("EO", "工程指令", "维修记录", "签署", "维修"),
            "Swiflam": ("CFM56", "发动机"),
            "gaslyfm": ("CFM56", "发动机"),
            "ML": ("MEL", "故障保留"),
        },
    ),
    "builtin-v3": _Ruleset(
        high_confidence=(
            # builtin-v2 rules preserved verbatim
            ("B七三七NG", "B737NG", "LAYER_1_EXACT_ALIAS"),
            ("M P D", "MPD", "LAYER_1_EXACT_ALIAS"),
            ("维修放心", "维修放行", "LAYER_2_CONTEXT_ALIAS"),
            ("B-737NG", "B737NG", "V2_SPACING_HYPHEN"),
            ("B七三七负八百", "B737-800", "V2_TYPED_VARIANT"),
            ("CFM56七字节", "CFM56-7B", "V2_TYPED_VARIANT"),
            ("试航指令", "适航指令", "V2_HOMOPHONE_PHRASE"),
            ("对低设备清单", "最低设备清单", "V2_HOMOPHONE_PHRASE"),
            # builtin-v3 (from S01 real-human corpus, run 2026-08-16-s1b-s01-qual-v1):
            # phrase-level homophones of the standard term 适航指令 and a hyphen variant of
            # the model designation. High confidence because these strings are not standard
            # aviation terms and appear in clear maintenance context.
            ("失航指令", "适航指令", "V3_HOMOPHONE_PHRASE"),
            ("释行指令", "适航指令", "V3_HOMOPHONE_PHRASE"),
            ("B-737-800", "B737-800", "V3_SPACING_HYPHEN"),
        ),
        spaced_abbreviations=("MEL", "AMM", "FIM", "CDL", "TSM", "IPC", "MPD", "EO", "ETOPS", "APU"),
        low_confidence={
            "L": ("fault", "保留故障", "MEL", "CDL"),
            "四百五十": ("CDL", "MEL", "最低设备清单", "故障", "保留", "项目"),
            "NPD": ("MPD", "维修项目", "检查项目"),
            "E U": ("EO", "工程指令", "维修记录", "签署", "维修"),
            "Swiflam": ("CFM56", "发动机"),
            "gaslyfm": ("CFM56", "发动机"),
            "ML": ("MEL", "故障保留"),
            # builtin-v3: single-letter / near-homophone confusions observed on real human
            # speech — review-only candidates, never silently rewritten.
            "MER": ("MEL", "故障保留", "最低设备清单", "故障", "维修"),
            "SIM": ("FIM", "故障", "排除", "无法"),
            "MTD": ("MPD", "维修项目", "检查项目", "维修"),
            "故障法流": ("故障保留", "放行", "保留", "维修", "故障"),
            "CF56-7B": ("CFM56-7B", "发动机", "型号"),
        },
    ),
    # builtin-v4 is the SAFE ruleset grounded in the versioned Golden corpus + safe
    # deterministic rules (docs/qualification/SPEECH_QUALIFICATION.md §Governance). S01
    # real-human speech may DISCOVER issues but cannot alone prove a fuzzy rule safe, so
    # S01-only homophone auto-replacements (失航/释行指令) are demoted to review-only
    # candidates below.
    "builtin-v4": _Ruleset(
        high_confidence=(
            # builtin-v2 rules preserved (TTS Golden-corpus grounded or safe deterministic)
            ("B七三七NG", "B737NG", "LAYER_1_EXACT_ALIAS"),
            ("M P D", "MPD", "LAYER_1_EXACT_ALIAS"),
            ("维修放心", "维修放行", "LAYER_2_CONTEXT_ALIAS"),
            ("B-737NG", "B737NG", "V2_SPACING_HYPHEN"),
            ("B七三七负八百", "B737-800", "V2_TYPED_VARIANT"),
            ("CFM56七字节", "CFM56-7B", "V2_TYPED_VARIANT"),
            ("试航指令", "适航指令", "V2_HOMOPHONE_PHRASE"),
            ("对低设备清单", "最低设备清单", "V2_HOMOPHONE_PHRASE"),
            # safe deterministic hyphen / compact model encodings (render profile pair)
            ("B-737-800", "B737-800", "V4_SPACING_HYPHEN"),
            ("B737800", "B737-800", "V4_COMPACT_MODEL"),
            ("CFM567B", "CFM56-7B", "V4_COMPACT_MODEL"),
        ),
        spaced_abbreviations=(
            "MEL", "AMM", "FIM", "CDL", "TSM", "IPC", "MPD", "EO", "ETOPS", "APU", "AD", "SB",
            "B737NG", "A330", "CFM56", "B737800", "CFM567B",
        ),
        low_confidence={
            "L": ("fault", "保留故障", "MEL", "CDL"),
            "四百五十": ("CDL", "MEL", "最低设备清单", "故障", "保留", "项目"),
            "NPD": ("MPD", "维修项目", "检查项目"),
            "E U": ("EO", "工程指令", "维修记录", "签署", "维修"),
            "Swiflam": ("CFM56", "发动机"),
            "gaslyfm": ("CFM56", "发动机"),
            "ML": ("MEL", "故障保留"),
            "MER": ("MEL", "故障保留", "最低设备清单", "故障", "维修"),
            "SIM": ("FIM", "故障", "排除", "无法"),
            "MTD": ("MPD", "维修项目", "检查项目", "维修"),
            "故障法流": ("故障保留", "放行", "保留", "维修", "故障"),
            "CF56-7B": ("CFM56-7B", "发动机", "型号"),
            # Demoted from builtin-v3: observed on S01 only; review-only until independently
            # validated (S01 is discovery, not a mapping source).
            "失航指令": ("适航指令", "AD", "指令"),
            "释行指令": ("适航指令", "AD", "指令"),
        },
    ),
}


def _apply_spaced_abbreviations(
    text: str, abbreviations: tuple[str, ...]
) -> tuple[str, list[Mapping]]:
    mappings: list[Mapping] = []
    for abbreviation in abbreviations:
        pattern = re.compile(
            r"(?<![A-Za-z0-9])" + r"\s*".join(re.escape(ch) for ch in abbreviation) + r"(?![A-Za-z0-9])"
        )
        match = pattern.search(text)
        if not match:
            continue
        new_text = pattern.sub(abbreviation, text)
        if new_text != text:
            mappings.append(
                Mapping(
                    raw_fragment=match.group(0),
                    normalized_fragment=abbreviation,
                    start_char=match.start(),
                    end_char=match.end(),
                    confidence=0.99,
                    normalization_rule="V2_SPACED_ABBREVIATION",
                )
            )
            text = new_text
    return text, mappings


def _apply_high_confidence(
    text: str, rules: tuple[tuple[str, str, str], ...]
) -> tuple[str, list[Mapping]]:
    mappings: list[Mapping] = []
    for raw, replacement, rule in rules:
        start = text.find(raw)
        if start < 0:
            continue
        text = text.replace(raw, replacement)
        mappings.append(Mapping(raw, replacement, start, start + len(raw), 1.0, rule))
    return text, mappings


def _collect_warnings(text: str, low_confidence: dict[str, tuple[str, ...]]) -> list[str]:
    warnings: list[str] = []
    for fragment, hints in low_confidence.items():
        if fragment in text and any(hint.lower() in text.lower() for hint in hints):
            warnings.append(
                f"Low-confidence candidate '{fragment}' retained without replacement "
                "(possible aviation term; review required)"
            )
    return warnings


def normalize(
    text: str,
    vocabulary: VocabularySnapshot,
    *,
    ruleset_version: str = NORMALIZER_RULESET_VERSION,
) -> NormalizationResult:
    ruleset = RULESETS.get(ruleset_version, RULESETS[NORMALIZER_RULESET_VERSION])
    result, mappings = text, []

    if ruleset.spaced_abbreviations:
        result, spaced_mappings = _apply_spaced_abbreviations(result, ruleset.spaced_abbreviations)
        mappings.extend(spaced_mappings)

    result, high_mappings = _apply_high_confidence(result, ruleset.high_confidence)
    mappings.extend(high_mappings)
    warnings = _collect_warnings(text, ruleset.low_confidence)

    # Published vocabulary can extend, but not rewrite, the deterministic layers above.
    for term in vocabulary.terms:
        for alias in term.aliases:
            start = result.find(alias)
            if start >= 0 and alias != term.canonical:
                result = result.replace(alias, term.canonical)
                mappings.append(
                    Mapping(alias, term.canonical, start, start + len(alias), term.confidence, "VOCABULARY_ALIAS")
                )

    return NormalizationResult(
        result,
        tuple(mappings),
        tuple(warnings),
        vocabulary.version,
        ruleset_version,
    )
