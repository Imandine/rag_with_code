"""Chunking sémantique structuré utilisant le HybridChunker de Docling.

Avantages vs RecursiveCharacterTextSplitter sur le markdown :
- Respecte les frontières structurelles natives du DoclingDocument (sections, paragraphes,
  tableaux, listes, légendes), pas un découpage caractère par caractère.
- Token-aware : utilise le tokenizer du modèle d'embedding pour garantir que chaque chunk
  rentre dans la fenêtre 512 tokens du MiniLM, sans tronquer une phrase ou un tableau.
- Fusionne les petits chunks adjacents partageant le même contexte (`merge_peers=True`).
- Réinjecte les en-têtes de section dans chaque chunk : un chunk "perdu" garde la
  hiérarchie « Titre § Sous-titre — texte » utile pour la pertinence et l'affichage.
- Repropage l'en-tête d'un tableau qui déborde sur plusieurs chunks (`repeat_table_header`).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from docling.chunking import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer

from config import settings

if TYPE_CHECKING:
    from docling_core.types.doc import DoclingDocument

# Marge sous la limite réelle (512) : tokens supplémentaires consommés par les en-têtes
# de section que HybridChunker contextualise dans chaque chunk.
MAX_TOKENS = 480

_chunker: HybridChunker | None = None


def get_chunker() -> HybridChunker:
    global _chunker
    if _chunker is None:
        hf_tok = AutoTokenizer.from_pretrained(settings.embedding_model)
        tokenizer = HuggingFaceTokenizer(tokenizer=hf_tok, max_tokens=MAX_TOKENS)
        _chunker = HybridChunker(
            tokenizer=tokenizer,
            merge_peers=True,
        )
    return _chunker


def chunk_docling_document(
    document: "DoclingDocument",
    base_metadata: dict,
    chunk_index_offset: int = 0,
) -> list[dict]:
    """Produit des chunks structuraux à partir d'un DoclingDocument.

    Le format de sortie est strictement identique à `semantic_chunk` (markdown) pour
    rester drop-in : `{ "text": str, "metadata": dict }`.
    """
    chunker = get_chunker()
    chunks: list[dict] = []
    for i, raw in enumerate(chunker.chunk(dl_doc=document)):
        # `serialize` produit le texte enrichi (en-têtes inclus) que verra l'embedding.
        text = chunker.contextualize(chunk=raw)
        if not text or not text.strip():
            continue

        meta_extra: dict = {}
        # Hiérarchie de titres si dispo (ex. ["Chapitre 1", "Article 4"])
        headings = getattr(raw.meta, "headings", None) or []
        if headings:
            meta_extra["headings"] = headings
            # Compatibilité avec l'ancien format h1/h2/h3 utilisé par le générateur
            for level, h in enumerate(headings[:3], start=1):
                meta_extra[f"h{level}"] = h

        # Pages de provenance du chunk : utile pour citer "p. 42-43"
        pages: set[int] = set()
        for it in (getattr(raw.meta, "doc_items", None) or []):
            for prov in (getattr(it, "prov", None) or []):
                page_no = getattr(prov, "page_no", None)
                if page_no is not None:
                    pages.add(page_no)
        if pages:
            meta_extra["chunk_pages"] = sorted(pages)

        chunks.append({
            "text": text,
            "metadata": {
                **base_metadata,
                **meta_extra,
                "chunk_index": chunk_index_offset + len(chunks),
            },
        })
    return chunks
