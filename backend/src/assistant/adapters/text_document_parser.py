"""Plain text and Markdown, read without any model."""

import re

from assistant.domain.documents import Block, ParsedDocument
from assistant.domain.errors import DocumentUnreadable

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


class TextDocumentParser:
    """Markdown `#` lines are headings; lines between blank lines are a paragraph."""

    def parse(self, filename: str, content: bytes) -> ParsedDocument:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise DocumentUnreadable(f"{filename} is not valid UTF-8 text") from error

        blocks: list[Block] = []
        lines: list[str] = []

        def end_paragraph() -> None:
            if lines:
                blocks.append(Block(kind="paragraph", text="\n".join(lines)))
                lines.clear()

        for line in text.splitlines():
            heading = _HEADING.match(line)
            if heading:
                end_paragraph()
                blocks.append(
                    Block(kind="heading", text=heading.group(2), level=len(heading.group(1)))
                )
            elif line.strip():
                lines.append(line.strip())
            else:
                end_paragraph()
        end_paragraph()
        # Plain text has no pages.
        return ParsedDocument(page_count=None, blocks=tuple(blocks))
