"""Print the OpenAPI schema of the API: `python -m assistant.openapi` (ADR 0005).

Lives next to the composition root rather than in `api/`, because it builds the whole app.
"""

import json
import sys
from pathlib import Path

from assistant.app import create_app, schema_adapters
from assistant.settings import Settings


def openapi_json() -> str:
    """The OpenAPI schema as stable, pretty-printed JSON."""
    # The schema depends on neither settings nor adapters; these need no models, Qdrant or disk.
    app = create_app(Settings(data_dir=Path(), models_dir=Path()), schema_adapters())
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    sys.stdout.write(openapi_json())
