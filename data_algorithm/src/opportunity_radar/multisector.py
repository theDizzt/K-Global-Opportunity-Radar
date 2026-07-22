from __future__ import annotations

from .taxonomy_v2 import SECTORS


def classify_sectors(text: str) -> list[tuple[str, float, int]]:
    """Return all matching sectors as (code, confidence, keyword_hits)."""
    lowered = (text or "").casefold()
    hits = {
        code: sum(1 for term in cfg["terms"] if term.casefold() in lowered)
        for code, cfg in SECTORS.items()
    }
    maximum = max(hits.values(), default=0)
    if maximum == 0:
        return []
    ranked: list[tuple[str, float, int]] = []
    for code, count in hits.items():
        if count == 0:
            continue
        confidence = min(0.99, 0.55 + 0.10 * count + (0.05 if count == maximum else 0.0))
        ranked.append((code, confidence, count))
    order = {code: index for index, code in enumerate(SECTORS)}
    return sorted(ranked, key=lambda row: (-row[2], order[row[0]]))
