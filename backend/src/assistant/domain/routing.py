"""Which questions the agent's tools are for (F-07, spec decision 6).

One search answers most questions well and fast. The tools pay off when a question names a
provision, which search finds by meaning rather than by number, or compares two of them.
"""

import re

# "Article 83", "art. 17", "Artykuł 26", "Annex III", "załącznik III", with a number after it.
_PROVISION = re.compile(
    r"\b(?:article|art\.|artyku\w*|annex|za[łl][ąa]cznik\w*)\s*(?:\d+|[IVXLC]+\b)",
    re.IGNORECASE,
)
_COMPARISON = re.compile(
    r"\b(?:compar\w*|differ\w*|versus|vs\.?|porówna\w*|różni\w*)\b",
    re.IGNORECASE,
)


def needs_tools(question: str) -> bool:
    """True for a question about a numbered article or annex, or one asking to compare."""
    return bool(_PROVISION.search(question) or _COMPARISON.search(question))
