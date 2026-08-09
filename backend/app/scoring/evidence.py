from dataclasses import dataclass


@dataclass(frozen=True)
class ResolvedEvidence:
    quote: str
    status: str
    start_char: int | None = None
    end_char: int | None = None


def resolve_quote(transcript: str, quote: str) -> ResolvedEvidence:
    if not quote:
        return ResolvedEvidence(quote=quote, status="INVALID")
    offsets: list[int] = []
    cursor = transcript.find(quote)
    while cursor >= 0:
        offsets.append(cursor)
        cursor = transcript.find(quote, cursor + 1)
    if len(offsets) == 1:
        return ResolvedEvidence(quote=quote, status="VALID", start_char=offsets[0], end_char=offsets[0] + len(quote))
    return ResolvedEvidence(quote=quote, status="AMBIGUOUS" if offsets else "INVALID")
