from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions
from pathlib import Path


def _safe_num_pages(document) -> int | None:
    pages = getattr(document, "pages", None)
    try:
        n = len(pages) if pages is not None else 0
        return n if n > 0 else None
    except TypeError:
        return None


def convert_document_to_markdown(file_path: str) -> dict:
    """
    Utilise Docling pour convertir tout type de document en Markdown structuré.
    Docling préserve la structure : titres, tableaux, listes, figures.
    """
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True            # OCR pour les PDFs scannés
    pipeline_options.do_table_structure = True # Extraction des tableaux

    converter = DocumentConverter()
    result = converter.convert(file_path)

    markdown_text = result.document.export_to_markdown()

    num_pages = _safe_num_pages(result.document)
    return {
        "text": markdown_text,
        "metadata": {
            "source": Path(file_path).name,
            "num_pages": num_pages if num_pages else None,
            "num_words": len(markdown_text.split()),
            "format": Path(file_path).suffix.lower(),
        }
    }
