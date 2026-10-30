"""The tools the agent may call: search, one article, two articles side by side (F-07).

Every result reaches the model as data: numbered passage blocks, or a sentence it can act on.
A mistake in the arguments is a result too, so the model can correct it (AI-21).
"""

import re
from collections.abc import Sequence

from assistant.domain.documents import Chunk, Document, indexed_text
from assistant.domain.tools import (
    CompareArguments,
    GetArticleArguments,
    PassageLedger,
    SearchDocumentsArguments,
    ToolCall,
    ToolSpec,
    neutralised,
)
from assistant.ports.document_store import DocumentStore
from assistant.services.questions import CANDIDATES, RERANK_CANDIDATES, QuestionService

# Passages a tool returns at most: a search, one article, each article of a comparison.
SEARCH_CAP = 5
ARTICLE_CAP = 12
COMPARE_CAP = 6

TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="search_documents",
        description=(
            "Search the uploaded documents for passages relevant to a query. Optionally keep "
            "to one document, named by its title."
        ),
        arguments=SearchDocumentsArguments,
    ),
    ToolSpec(
        name="get_article",
        description="The full text of one article of a document, e.g. GDPR (EN), article 17.",
        arguments=GetArticleArguments,
    ),
    ToolSpec(
        name="compare",
        description="Two articles side by side, from the same or different documents.",
        arguments=CompareArguments,
    ),
)

_ARTICLE_NUMBER = re.compile(r"\d+[a-z]?", re.IGNORECASE)


class _ToolError(Exception):
    """The arguments name something that does not exist; the message goes to the model."""


class DocumentTools:
    """Runs the agent's tool calls against the stored and indexed documents."""

    def __init__(self, questions: QuestionService, store: DocumentStore) -> None:
        self._questions = questions
        self._store = store

    async def run(self, call: ToolCall, ledger: PassageLedger) -> str:
        """The tool's result as the model reads it; passages are numbered in `ledger`."""
        try:
            match call.arguments:
                case SearchDocumentsArguments() as arguments:
                    return await self._search(arguments, ledger)
                case GetArticleArguments() as arguments:
                    return self._article(arguments.document, arguments.number, ARTICLE_CAP, ledger)
                case CompareArguments(a=a, b=b):
                    return "\n\n".join(
                        self._article(ref.document, ref.number, COMPARE_CAP, ledger)
                        for ref in (a, b)
                    )
                case _:
                    return f"Error: there is no tool {call.name}."
        except _ToolError as error:
            return f"Error: {error}"

    async def _search(self, arguments: SearchDocumentsArguments, ledger: PassageLedger) -> str:
        document = self._document(arguments.document) if arguments.document else None
        # Keeping to one document filters the candidates, so more of them are fetched.
        found = await self._questions.search(
            arguments.query, RERANK_CANDIDATES if document else CANDIDATES
        )
        relevant = [
            passage
            for passage in found
            if passage.similarity >= self._questions.min_similarity
            and (document is None or passage.chunk.document_id == document.id)
        ][:SEARCH_CAP]
        if not relevant:
            return f'No passage above the relevance threshold was found for "{arguments.query}".'
        return "\n\n".join(
            _block(ledger.number(passage.chunk), passage.chunk, passage.document_title)
            for passage in relevant
        )

    def _article(self, name: str, number: str, cap: int, ledger: PassageLedger) -> str:
        document = self._document(name)
        label = _ARTICLE_NUMBER.search(number)
        wanted = label.group().lower() if label else number
        chunks = sorted(
            (
                chunk
                for chunk in self._store.load_chunks(document.id)
                if (chunk.location.article or "").lower() == wanted
            ),
            key=lambda chunk: chunk.position,
        )
        if not chunks:
            raise _ToolError(f"{document.title} has no article {number}.")
        blocks = [_block(ledger.number(chunk), chunk, document.title) for chunk in chunks[:cap]]
        if len(chunks) > cap:
            blocks.append(f"({len(chunks) - cap} more passages of this article are not shown.)")
        return "\n\n".join(blocks)

    def _document(self, name: str) -> Document:
        documents = self._store.list_documents()
        wanted = name.strip().lower()
        for document in documents:
            if wanted in (document.id.lower(), document.title.lower()):
                return document
        titles = ", ".join(f'"{document.title}"' for document in _by_title(documents))
        raise _ToolError(f'there is no document "{name}". The documents are: {titles}.')


def _by_title(documents: Sequence[Document]) -> list[Document]:
    return sorted(documents, key=lambda document: document.title)


def _block(number: int, chunk: Chunk, title: str) -> str:
    article = f' article="{chunk.location.article}"' if chunk.location.article else ""
    attributes = f'number="{number}" document="{title.replace('"', "'")}"{article}'
    return f"<passage {attributes}>\n{neutralised(indexed_text(chunk))}\n</passage>"
