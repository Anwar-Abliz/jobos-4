"""Document content extraction from PDF, DOCX, TXT, MD, CSV."""
from __future__ import annotations

import logging
from pathlib import PurePosixPath

from jobos.adapters.extraction.url_extractor import ExtractedContent

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv"}


def extract_from_bytes(content: bytes, filename: str) -> ExtractedContent:
    """Route by extension to the appropriate extractor."""
    ext = PurePosixPath(filename).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if ext == ".pdf":
        return _extract_pdf(content, filename)
    elif ext == ".docx":
        return _extract_docx(content, filename)
    else:
        return _extract_text(content, filename, ext)


def _extract_pdf(content: bytes, filename: str) -> ExtractedContent:
    """Extract text from PDF using pymupdf."""
    import pymupdf

    doc = pymupdf.open(stream=content, filetype="pdf")
    pages: list[str] = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()

    text = "\n\n".join(pages)
    return ExtractedContent(
        text=text,
        title=filename,
        source=f"upload:{filename}",
        metadata={"pages": str(len(pages)), "type": "pdf"},
    )


def _extract_docx(content: bytes, filename: str) -> ExtractedContent:
    """Extract text from DOCX using python-docx."""
    import io

    from docx import Document

    doc = Document(io.BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n\n".join(paragraphs)

    return ExtractedContent(
        text=text,
        title=filename,
        source=f"upload:{filename}",
        metadata={"paragraphs": str(len(paragraphs)), "type": "docx"},
    )


def _extract_text(content: bytes, filename: str, ext: str) -> ExtractedContent:
    """Extract text from plain text files (.txt, .md, .csv)."""
    try:
        import chardet

        detected = chardet.detect(content)
        encoding = detected.get("encoding", "utf-8") or "utf-8"
    except ImportError:
        encoding = "utf-8"

    text = content.decode(encoding, errors="replace")
    return ExtractedContent(
        text=text,
        title=filename,
        source=f"upload:{filename}",
        metadata={"encoding": encoding, "type": ext.lstrip(".")},
    )
