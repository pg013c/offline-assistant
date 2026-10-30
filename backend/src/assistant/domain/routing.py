"""Which questions the agent's tools are for (F-07, spec decision 6).

One search answers most questions well and fast. The tools pay off when a question names a
provision, which search finds by meaning rather than by number, or compares two of them.
"""

import re

# "Article 83", "articles 5 and 6", "art. 17", "Art 17", "Artykuł 26", followed by a number.
# Annexes are left out: no tool reads an annex yet (F-07 review #4).
_PROVISION = re.compile(r"\b(?:articles?|art\.?|artyku\w*)\s*\d+", re.IGNORECASE)
# "Compare", "differ", "difference between", "versus", "porównaj", "różnica", but not the
# adjective "different".
_COMPARISON = re.compile(
    r"\b(?:compar\w*|differ(?:s|ence|ences)?|versus|vs\.?|porówna\w*|różni\w*)\b",
    re.IGNORECASE,
)


def needs_tools(question: str) -> bool:
    """True for a question about a numbered article, or one asking to compare."""
    return bool(_PROVISION.search(question) or _COMPARISON.search(question))
