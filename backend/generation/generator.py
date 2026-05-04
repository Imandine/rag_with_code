from openai import OpenAI
from config import settings

SYSTEM_PROMPT = """Tu es un assistant expert qui répond aux questions en te basant UNIQUEMENT sur les documents fournis.
Règles :
- Cite uniquement les sources réellement utilisées pour formuler ta réponse (nom du document, section). Le nombre de citations doit refléter la pertinence : une seule si une seule source suffit, plusieurs si nécessaire — n'en ajoute pas pour faire du remplissage.
- Si la réponse n'est pas dans les documents, dis-le clairement
- Sois précis et concis
- Réponds dans la langue de la question"""


def _build_client() -> OpenAI:
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY manquant dans .env")
    extra_headers = {}
    if settings.openrouter_referer:
        extra_headers["HTTP-Referer"] = settings.openrouter_referer
    if settings.openrouter_app_name:
        extra_headers["X-Title"] = settings.openrouter_app_name
    return OpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        default_headers=extra_headers or None,
    )


client = _build_client()


def build_context(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk["metadata"].get("source", "Document inconnu")
        section = chunk["metadata"].get("h1", chunk["metadata"].get("h2", ""))
        parts.append(f"[Source {i}: {source} — {section}]\n{chunk['text']}")
    return "\n\n---\n\n".join(parts)


def generate_answer(query: str, chunks: list[dict]):
    """Génération streamée via OpenRouter (API OpenAI-compatible)."""
    context = build_context(chunks)

    stream = client.chat.completions.create(
        model=settings.openrouter_model,
        max_tokens=2048,
        stream=True,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Documents de référence :\n\n{context}\n\nQuestion : {query}"},
        ],
    )
    for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            yield content
