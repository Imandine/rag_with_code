import gc
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator

import pypdfium2 as pdfium
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.base_models import DocumentStream
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption


PDF_BATCH_PAGES = 10  # taille d'un sous-document PDF envoyé à Docling (réduit pour limiter la mémoire)

# Formats convertibles en PDF par LibreOffice (rendu fidèle, puis pipeline PDF)
LIBREOFFICE_FORMATS = {
    ".doc", ".docx", ".odt", ".rtf",
    ".ppt", ".pptx", ".odp",
    ".xls", ".xlsx", ".ods", ".csv",
    ".html", ".htm",
}

# Formats texte bruts traités directement, sans passer par Docling
PLAIN_TEXT_FORMATS = {".txt", ".md", ".markdown", ".log"}

# Formats laissés à Docling tels quels (images, PDF de secours, etc.)
DOCLING_DIRECT_FORMATS = {
    ".pdf",
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp",
}


def _has_text_layer(pdf: pdfium.PdfDocument, sample_size: int = 4) -> bool:
    """Retourne True si le PDF embarque déjà du texte (donc pas besoin d'OCR)."""
    n = len(pdf)
    if n == 0:
        return False
    indices = list({0, n // 2, n - 1})[:sample_size]
    for idx in indices:
        page = pdf[idx]
        try:
            text_page = page.get_textpage()
            try:
                if text_page.get_text_range().strip():
                    return True
            finally:
                text_page.close()
        finally:
            page.close()
    return False


def _build_converter(do_ocr: bool) -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = do_ocr
    pipeline_options.do_table_structure = True
    pipeline_options.document_timeout = 600.0  # garde-fou par sous-document
    # Traitement séquentiel page-à-page pour éviter les std::bad_alloc
    pipeline_options.layout_batch_size = 1
    pipeline_options.ocr_batch_size = 1
    pipeline_options.table_batch_size = 1
    # Résolution réduite : limite la mémoire des images intermédiaires (OCR float64 = 8x la taille)
    pipeline_options.images_scale = 1.0
    pipeline_options.accelerator_options = AcceleratorOptions(num_threads=2, device="cpu")
    return DocumentConverter(
        format_options={"pdf": PdfFormatOption(pipeline_options=pipeline_options)}
    )


def _convert_stream(converter: DocumentConverter, name: str, data: bytes):
    """Convertit un flux et renvoie (markdown, DoclingDocument).

    Le DoclingDocument est conservé pour permettre le chunking structurel par HybridChunker.
    Il est libéré explicitement par l'appelant après usage (gc.collect après le yield).
    """
    stream = DocumentStream(name=name, stream=io.BytesIO(data))
    result = converter.convert(stream)
    document = result.document
    md = document.export_to_markdown()
    # On garde une référence sur le document seul, on libère l'enveloppe ConversionResult
    return md, document


def _find_libreoffice() -> str | None:
    """Cherche un binaire LibreOffice exploitable (Linux/macOS/Windows)."""
    env = os.environ.get("LIBREOFFICE_BIN")
    if env and Path(env).exists():
        return env
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def _convert_to_pdf_via_libreoffice(file_path: str) -> str | None:
    """Convertit un fichier bureautique en PDF via LibreOffice headless. Retourne le chemin PDF, ou None si échec."""
    binary = _find_libreoffice()
    if not binary:
        return None
    out_dir = tempfile.mkdtemp(prefix="lo_pdf_")
    try:
        proc = subprocess.run(
            [
                binary, "--headless", "--norestore", "--nologo",
                "--convert-to", "pdf",
                "--outdir", out_dir,
                file_path,
            ],
            capture_output=True,
            timeout=600,
        )
        if proc.returncode != 0:
            return None
        out_pdf = Path(out_dir) / (Path(file_path).stem + ".pdf")
        return str(out_pdf) if out_pdf.exists() else None
    except (subprocess.TimeoutExpired, OSError):
        return None


def _iter_pdf_batches(file_path: str, batch_pages: int, source_format: str) -> Iterator[dict]:
    pdf = pdfium.PdfDocument(file_path)
    total = len(pdf)
    do_ocr = not _has_text_layer(pdf)

    converter = _build_converter(do_ocr=do_ocr)
    name = Path(file_path).stem

    try:
        if total == 0:
            yield {
                "markdown": "",
                "document": None,
                "page_start": 0,
                "page_end": 0,
                "total_pages": 0,
                "format": source_format,
                "ocr_used": False,
            }
            return
        for start in range(0, total, batch_pages):
            end = min(start + batch_pages, total)
            sub = pdfium.PdfDocument.new()
            try:
                sub.import_pages(pdf, pages=list(range(start, end)))
                buf = io.BytesIO()
                sub.save(buf)
                data = buf.getvalue()
            finally:
                sub.close()

            md, document = _convert_stream(converter, f"{name}_p{start + 1}-{end}.pdf", data)
            del data
            yield {
                "markdown": md,
                "document": document,
                "page_start": start + 1,
                "page_end": end,
                "total_pages": total,
                "format": source_format,
                "ocr_used": do_ocr,
            }
            del document
            gc.collect()  # libère la RAM accumulée par les modèles Docling avant le lot suivant
    finally:
        pdf.close()


def _iter_plain_text(file_path: str) -> Iterator[dict]:
    suffix = Path(file_path).suffix.lower()
    text = Path(file_path).read_text(encoding="utf-8", errors="replace")
    yield {
        "markdown": text,
        "document": None,
        "page_start": 1,
        "page_end": 1,
        "total_pages": 1,
        "format": suffix,
        "ocr_used": False,
    }


def _iter_docling_direct(file_path: str) -> Iterator[dict]:
    converter = _build_converter(do_ocr=True)  # images : OCR nécessaire ; PDF : Docling l'auto-gère via OcrAuto
    result = converter.convert(file_path)
    document = result.document
    md = document.export_to_markdown()
    pages = getattr(document, "pages", None)
    try:
        total = len(pages) if pages is not None else 1
    except TypeError:
        total = 1
    yield {
        "markdown": md,
        "document": document,
        "page_start": 1,
        "page_end": total,
        "total_pages": total,
        "format": Path(file_path).suffix.lower(),
        "ocr_used": True,
    }


def iter_document_batches(file_path: str, batch_pages: int = PDF_BATCH_PAGES) -> Iterator[dict]:
    """
    Itère sur le document en lots pour permettre un traitement en flux.

    Stratégie selon le format :
      - .pdf                          → split par tranches de pages, Docling sur chaque tranche
      - .docx/.pptx/.xlsx/.html/...   → conversion en PDF via LibreOffice puis pipeline PDF
      - .txt/.md/.csv                 → texte brut, pas de Docling
      - images                        → Docling direct (OCR auto)
    """
    suffix = Path(file_path).suffix.lower()

    if suffix == ".pdf":
        yield from _iter_pdf_batches(file_path, batch_pages, suffix)
        return

    if suffix in PLAIN_TEXT_FORMATS:
        yield from _iter_plain_text(file_path)
        return

    if suffix in LIBREOFFICE_FORMATS:
        pdf_path = _convert_to_pdf_via_libreoffice(file_path)
        if pdf_path:
            try:
                for batch in _iter_pdf_batches(pdf_path, batch_pages, source_format=suffix):
                    yield batch
            finally:
                try:
                    os.unlink(pdf_path)
                    os.rmdir(Path(pdf_path).parent)
                except OSError:
                    pass
            return
        # LibreOffice indisponible → fallback Docling natif
        yield from _iter_docling_direct(file_path)
        return

    if suffix in DOCLING_DIRECT_FORMATS:
        yield from _iter_docling_direct(file_path)
        return

    # Format inconnu : on tente Docling, qui lèvera une erreur explicite si non géré
    yield from _iter_docling_direct(file_path)
