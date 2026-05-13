import gc
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.base_models import DocumentStream
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TesseractOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption


PDF_BATCH_PAGES = 10  # taille d'un sous-document PDF envoyé à Docling (réduit pour limiter la mémoire)

# Langues OCR Tesseract — `fra` pour le corpus douanier français, `eng` pour les
# documents bilingues fréquents (réglementations UEMOA/CEDEAO).
OCR_LANGUAGES = ["fra", "eng"]

# Formats que LibreOffice convertit en PDF (meilleure qualité).
# Si LibreOffice est absent, certains peuvent être traités directement par Docling (voir ci-dessous).
LIBREOFFICE_FORMATS = {
    ".doc", ".docx", ".odt", ".rtf",
    ".ppt", ".pptx", ".odp",
    ".xls", ".xlsx", ".ods", ".csv",
    ".html", ".htm",
}

# Parmi les LIBREOFFICE_FORMATS, ceux que Docling supporte nativement en fallback
# (si LibreOffice est absent, on passe directement à Docling plutôt que d'échouer).
DOCLING_NATIVE_FALLBACK = {".docx", ".pptx", ".xlsx", ".csv", ".html", ".htm"}

# Formats qui nécessitent LibreOffice obligatoirement — Docling ne les reconnaît pas.
# Si LibreOffice est absent, l'ingestion renvoie une erreur claire.
LIBREOFFICE_REQUIRED = LIBREOFFICE_FORMATS - DOCLING_NATIVE_FALLBACK

# Formats texte bruts traités directement, sans passer par Docling
PLAIN_TEXT_FORMATS = {".txt", ".md", ".markdown", ".log"}

# Formats laissés à Docling tels quels (PDF de secours, etc.)
DOCLING_DIRECT_FORMATS = {".pdf"}


def _page_has_text(page: pdfium.PdfPage) -> bool:
    """True si la page contient du texte sélectionnable (donc pas besoin d'OCR)."""
    text_page = page.get_textpage()
    try:
        return bool(text_page.get_text_range().strip())
    finally:
        text_page.close()


def _has_text_layer(pdf: pdfium.PdfDocument, sample_size: int = 4) -> bool:
    """Retourne True si AU MOINS une page échantillon embarque du texte.

    Sert seulement à décider du moteur OCR (do_ocr global). La granularité page-par-page
    est gérée plus finement par `_strip_decorative_images` qui inspecte chaque page.
    """
    n = len(pdf)
    if n == 0:
        return False
    indices = list({0, n // 2, n - 1})[:sample_size]
    for idx in indices:
        page = pdf[idx]
        try:
            if _page_has_text(page):
                return True
        finally:
            page.close()
    return False


def _strip_decorative_images(pdf: pdfium.PdfDocument) -> dict:
    """Retire les images décoratives des pages qui ont déjà une couche texte.

    Stratégie :
    - Page avec texte sélectionnable → image = logo/diagramme décoratif → on la retire
      (gain : pas d'OCR sur la page, moins de mémoire, pas de bruit OCR dans le markdown).
    - Page sans texte (scannée) → l'image EST le contenu → on la garde intacte pour OCR.

    Modifie le document en place. Retourne des stats {pages_stripped, images_removed,
    pages_kept_for_ocr} utiles pour le statut affiché dans le back-office.
    """
    pages_stripped = 0
    images_removed = 0
    pages_kept_for_ocr = 0

    for i in range(len(pdf)):
        page = pdf[i]
        try:
            if not _page_has_text(page):
                pages_kept_for_ocr += 1
                continue

            # Page avec couche texte : on retire ses images via l'API pypdfium2.raw
            count = pdfium_c.FPDFPage_CountObjects(page.raw)
            removed_on_page = 0
            # Parcours à l'envers : remove invalide les indices supérieurs
            for j in range(count - 1, -1, -1):
                obj = pdfium_c.FPDFPage_GetObject(page.raw, j)
                if pdfium_c.FPDFPageObj_GetType(obj) == pdfium_c.FPDF_PAGEOBJ_IMAGE:
                    pdfium_c.FPDFPage_RemoveObject(page.raw, obj)
                    removed_on_page += 1
            if removed_on_page:
                pdfium_c.FPDFPage_GenerateContent(page.raw)
                pages_stripped += 1
                images_removed += removed_on_page
        finally:
            page.close()

    return {
        "pages_stripped": pages_stripped,
        "images_removed": images_removed,
        "pages_kept_for_ocr": pages_kept_for_ocr,
    }


def _preprocess_pdf(pdf_path: str) -> str:
    """Stripe les images décoratives et retourne le chemin d'un PDF nettoyé.

    Si rien n'a été retiré (PDF entièrement scanné), retourne le chemin d'origine pour
    éviter une copie inutile.
    """
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        stats = _strip_decorative_images(pdf)
        if stats["images_removed"] == 0:
            return pdf_path
        out_path = pdf_path + ".stripped.pdf"
        pdf.save(out_path)
        return out_path
    finally:
        pdf.close()


def _is_tesseract_available() -> bool:
    """Détecte si tesseract est installé (binaire dans le PATH ou défini par env)."""
    env = os.environ.get("TESSERACT_BIN") or os.environ.get("TESSERACT_CMD")
    if env and Path(env).exists():
        return True
    return shutil.which("tesseract") is not None


def _build_converter(do_ocr: bool) -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = do_ocr
    pipeline_options.do_table_structure = True
    pipeline_options.document_timeout = 600.0  # garde-fou par sous-document
    # Traitement séquentiel page-à-page pour éviter les std::bad_alloc
    pipeline_options.layout_batch_size = 1
    pipeline_options.ocr_batch_size = 1
    pipeline_options.table_batch_size = 1
    # Pas de rendu d'images dans l'output Docling (économise mémoire et I/O)
    pipeline_options.generate_page_images = False
    pipeline_options.generate_picture_images = False
    # Résolution réduite : limite la mémoire des images intermédiaires (OCR float64 = 8x la taille)
    pipeline_options.images_scale = 1.0
    pipeline_options.accelerator_options = AcceleratorOptions(num_threads=2, device="cpu")

    # OCR : Tesseract avec français+anglais si disponible (qualité supérieure sur le
    # corpus français accentué). Sinon on laisse Docling utiliser son moteur par défaut
    # (RapidOCR) pour ne pas casser les environnements de dev sans tesseract installé.
    if do_ocr and _is_tesseract_available():
        pipeline_options.ocr_options = TesseractOcrOptions(lang=OCR_LANGUAGES)

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
    # 1) Prétraitement : on retire les images décoratives des pages avec couche texte.
    #    Les pages 100% scannées sont préservées pour l'OCR. Renvoie un nouveau chemin
    #    si un PDF nettoyé a été produit, sinon le chemin d'origine.
    stripped_path = _preprocess_pdf(file_path)
    used_stripped = stripped_path != file_path

    pdf = pdfium.PdfDocument(stripped_path)
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
        if used_stripped:
            try:
                os.unlink(stripped_path)
            except OSError:
                pass


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
      - autres (images, binaires)     → erreur explicite
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

        # LibreOffice indisponible
        if suffix in LIBREOFFICE_REQUIRED:
            # Docling ne reconnaît pas ces formats (.doc, .odt, .rtf, .ppt, .xls, .ods…)
            raise RuntimeError(
                f"Le format '{suffix}' nécessite LibreOffice pour être converti. "
                "Installez LibreOffice et assurez-vous que 'soffice' est dans le PATH "
                "(puis définissez LIBREOFFICE_BIN dans le .env)."
            )
        # Formats que Docling gère nativement (.docx, .pptx, .xlsx, .html…)
        yield from _iter_docling_direct(file_path)
        return

    if suffix in DOCLING_DIRECT_FORMATS:
        yield from _iter_docling_direct(file_path)
        return

    # Format non supporté (images, fichiers binaires, etc.)
    raise RuntimeError(
        f"Le format '{suffix}' n'est pas pris en charge. "
        "Formats acceptés : PDF, Word, PowerPoint, Excel, OpenDocument, HTML, CSV, Markdown, texte."
    )
