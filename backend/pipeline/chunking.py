from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

def semantic_chunk(text: str, metadata: dict, chunk_size: int = 512, overlap: int = 64) -> list[dict]:
    """
    Découpe en deux passes :
    1. Par headers Markdown (respecte la structure du document Docling)
    2. RecursiveCharacterTextSplitter pour les sections trop grandes
    """
    headers_to_split_on = [("#", "h1"), ("##", "h2"), ("###", "h3")]
    md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    header_splits = md_splitter.split_text(text)

    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ".", " "]
    )

    chunks = []
    for i, split in enumerate(char_splitter.split_documents(header_splits)):
        chunks.append({
            "text": split.page_content,
            "metadata": {
                **metadata,
                **split.metadata,  # headers Markdown hérités
                "chunk_index": i
            }
        })
    return chunks
