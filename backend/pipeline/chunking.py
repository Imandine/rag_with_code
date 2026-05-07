from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

_HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3")]


def semantic_chunk(
    text: str,
    metadata: dict,
    chunk_size: int = 512,
    overlap: int = 64,
    chunk_index_offset: int = 0,
) -> list[dict]:
    """
    Découpe en deux passes :
    1. Par headers Markdown (respecte la structure du document Docling)
    2. RecursiveCharacterTextSplitter pour les sections trop grandes

    `chunk_index_offset` permet de continuer la numérotation entre lots successifs.
    """
    if not text or not text.strip():
        return []

    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=_HEADERS)
    header_splits = md_splitter.split_text(text)

    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ".", " "],
    )

    chunks = []
    for i, split in enumerate(char_splitter.split_documents(header_splits)):
        chunks.append({
            "text": split.page_content,
            "metadata": {
                **metadata,
                **split.metadata,
                "chunk_index": chunk_index_offset + i,
            },
        })
    return chunks
