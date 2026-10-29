"""PDF, DOCX and images through Docling, with Tesseract for OCR (ADR 0015).

Docling is imported when the first document is parsed: it loads PyTorch, which takes
seconds and is not needed by anything else.
"""

import shutil
import subprocess
import threading
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path, PurePath
from typing import TYPE_CHECKING

import pypdfium2 as pdfium

from assistant.adapters.model_loading import MODEL_LOADING
from assistant.adapters.pinned_models import DOCLING_MODELS, ModelsNotReady, verify_models
from assistant.domain.documents import Block, ParsedDocument
from assistant.domain.errors import DocumentUnreadable

if TYPE_CHECKING:
    from docling.document_converter import DocumentConverter
    from docling_core.types.doc.document import DoclingDocument

__all__ = ["DoclingDocumentParser", "ModelsNotReady"]

MAX_PAGES = 500
OCR_LANGUAGES = ("eng", "pol")


class DoclingDocumentParser:
    def __init__(
        self, models_dir: Path, max_pages: int = MAX_PAGES, tesseract: str = "tesseract"
    ) -> None:
        self._artifacts = models_dir / "docling"
        self._max_pages = max_pages
        self._tesseract = tesseract
        self._converter: DocumentConverter | None = None
        self._lock = threading.Lock()

    @staticmethod
    def ensure_ready(models_dir: Path, tesseract: str = "tesseract") -> None:
        """Raise `ModelsNotReady` unless the pinned models and Tesseract with eng and pol exist."""
        verify_models(models_dir, DOCLING_MODELS)

        executable = shutil.which(tesseract)
        if executable is None:
            raise ModelsNotReady(
                f"OCR needs {tesseract}, which is not installed: `brew install tesseract "
                "tesseract-lang` or `apt install tesseract-ocr tesseract-ocr-pol`."
            )
        listed_languages = subprocess.run(  # noqa: S603 (fixed arguments, resolved executable)
            [executable, "--list-langs"], capture_output=True, text=True, check=False
        ).stdout.split()
        absent = [language for language in OCR_LANGUAGES if language not in listed_languages]
        if absent:
            raise ModelsNotReady(
                f"tesseract has no language data for {', '.join(absent)}: "
                "`brew install tesseract-lang` or `apt install tesseract-ocr-pol`."
            )

    def parse(self, filename: str, content: bytes) -> ParsedDocument:
        if PurePath(filename).suffix.lower() == ".pdf":
            self._check_pdf(content)

        from docling.datamodel.base_models import ConversionStatus, DocumentStream

        result = self._get_converter().convert(
            DocumentStream(name=filename, stream=BytesIO(content)),
            raises_on_error=False,
            max_num_pages=self._max_pages,
        )
        if result.status not in {ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS}:
            raise DocumentUnreadable("The document could not be read.")
        document = result.document
        return ParsedDocument(
            page_count=len(document.pages) or None, blocks=tuple(_blocks(document))
        )

    def _check_pdf(self, content: bytes) -> None:
        """Reasons Docling would only report as a generic failure."""
        try:
            pdf = pdfium.PdfDocument(content)
        except pdfium.PdfiumError as error:
            if "password" in str(error).lower():
                raise DocumentUnreadable("The PDF is password-protected.") from error
            raise DocumentUnreadable("The file is not a readable PDF.") from error
        try:
            pages = len(pdf)
        finally:
            pdf.close()
        if pages > self._max_pages:
            raise DocumentUnreadable(
                f"The document has {pages} pages; at most {self._max_pages} pages are supported."
            )

    def _get_converter(self) -> "DocumentConverter":
        with self._lock:
            if self._converter is None:
                self._converter = self._build_converter()
            return self._converter

    def _build_converter(self) -> "DocumentConverter":
        from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            PdfPipelineOptions,
            TesseractCliOcrOptions,
        )
        from docling.document_converter import (
            DocumentConverter,
            ImageFormatOption,
            PdfFormatOption,
        )

        options = PdfPipelineOptions(
            artifacts_path=self._artifacts,
            enable_remote_services=False,
            do_ocr=True,
            ocr_options=TesseractCliOcrOptions(
                lang=list(OCR_LANGUAGES), tesseract_cmd=self._tesseract
            ),
            do_table_structure=True,
        )
        converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF, InputFormat.DOCX, InputFormat.IMAGE],
            format_options={
                # Docling's own PDF text backend garbles some Polish letters in EUR-Lex PDFs;
                # pdfium reads them correctly.
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=options, backend=PyPdfiumDocumentBackend
                ),
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=options),
            },
        )
        # Docling would load its models halfway through the first document; load them now,
        # one model at a time with the other adapters.
        with MODEL_LOADING:
            converter.initialize_pipeline(InputFormat.PDF)
        return converter


def _blocks(document: "DoclingDocument") -> Iterator[Block]:
    """Body items in reading order; page headers and footers are not part of the body."""
    from docling_core.types.doc.items.node import DocItem
    from docling_core.types.doc.items.table.table import TableItem
    from docling_core.types.doc.items.text import ListItem, SectionHeaderItem, TextItem, TitleItem

    for item, _ in document.iterate_items(with_groups=False):
        if not isinstance(item, DocItem):
            continue
        page = item.prov[0].page_no if item.prov else None
        if isinstance(item, TableItem):
            yield Block(kind="table", text=item.export_to_markdown(doc=document), page=page)
        elif isinstance(item, SectionHeaderItem):
            yield Block(kind="heading", text=item.text, page=page, level=item.level)
        elif isinstance(item, TitleItem):
            yield Block(kind="heading", text=item.text, page=page, level=1)
        elif isinstance(item, ListItem):
            yield _list_item(item.marker, item.text, page)
        elif isinstance(item, TextItem):
            # Paragraphs, captions, footnotes; pictures carry no text.
            yield Block(kind="paragraph", text=item.text, page=page)


def _list_item(marker: str, text: str, page: int | None) -> Block:
    """Docling keeps a list marker apart from the text; numbered paragraphs of legal texts
    arrive this way too, and the chunker needs the number in the text."""
    marker = marker.strip()
    if marker and not text.startswith(marker):
        text = f"{marker} {text}"
    return Block(kind="list_item", text=text, page=page)
