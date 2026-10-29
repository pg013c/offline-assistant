"""Print the OpenAPI schema of the API: `python -m assistant.openapi` (ADR 0005).

Lives next to the composition root rather than in `api/`, because it builds the whole app.
"""

import json
import sys
from pathlib import Path

from assistant.app import create_app
from assistant.settings import Settings


def openapi_json() -> str:
    """The OpenAPI schema as stable, pretty-printed JSON."""
    # The schema does not depend on settings: the data directory is never touched, and the
    # text parser needs no models.
    app = create_app(Settings(data_dir=Path(), document_parser="text-only"))
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    sys.stdout.write(openapi_json())
