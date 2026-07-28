"""Upload handling and text extraction from documents."""

import shutil
import uuid
from pathlib import Path

import fitz
from docx import Document as DocxDocument
from fastapi import UploadFile

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


def validate_upload(file: UploadFile) -> str:
    if not file.filename:
        raise ValueError("Filename is required")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Supported formats: PDF, DOCX, TXT")
    return suffix


async def save_upload(
    *,
    file: UploadFile,
    upload_root: Path,
    knowledge_base_id: int,
) -> tuple[str, Path]:
    validate_upload(file)
    safe_name = Path(file.filename or "upload").name
    doc_dir = upload_root / str(knowledge_base_id) / uuid.uuid4().hex
    doc_dir.mkdir(parents=True, exist_ok=True)
    dest = doc_dir / safe_name

    size = 0
    with dest.open("wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                shutil.rmtree(doc_dir, ignore_errors=True)
                raise ValueError("File exceeds 20 MB upload limit")
            out.write(chunk)

    return safe_name, dest


def extract_text(*, file_path: Path, filename: str) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(file_path)
    if suffix == ".docx":
        return _extract_docx(file_path)
    if suffix == ".txt":
        return _extract_txt(file_path)
    raise ValueError(f"Unsupported file type: {filename}")


def _extract_pdf(file_path: Path) -> str:
    pages: list[str] = []
    with fitz.open(file_path) as doc:
        for page in doc:
            text = page.get_text("text").strip()
            if text:
                pages.append(text)
    return "\n\n".join(pages)


def _extract_docx(file_path: Path) -> str:
    """Extract paragraphs and table cells in document order."""
    from docx.document import Document as DocxDocumentType
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = DocxDocument(str(file_path))
    parts: list[str] = []

    def walk(container: DocxDocumentType) -> None:
        for child in container.element.body:
            if child.tag == qn("w:p"):
                paragraph = Paragraph(child, container)
                text = paragraph.text.strip()
                if text:
                    parts.append(text)
            elif child.tag == qn("w:tbl"):
                table = Table(child, container)
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if cells:
                        parts.append(" | ".join(cells))

    walk(doc)
    return "\n\n".join(parts)


def _extract_txt(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8", errors="replace").strip()
