from dataclasses import dataclass, field


@dataclass(frozen=True)
class VocabularyEntry:
    canonical: str
    aliases: tuple[str, ...]
    context_hints: tuple[str, ...] = ()
    confidence: float = 1.0


@dataclass(frozen=True)
class VocabularySnapshot:
    version: str
    terms: tuple[VocabularyEntry, ...] = field(default_factory=tuple)
