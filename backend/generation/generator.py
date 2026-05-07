from openai import OpenAI
from config import settings
from models.schemas import ChatMessage

# Nombre maximum de tours de conversation rappelés au modèle (1 tour = user + assistant)
MAX_HISTORY_TURNS = 6

# Combien de tours de l'historique on regarde pour réécrire la question (limiter les tokens)
REWRITE_HISTORY_TURNS = 3

REWRITE_SYSTEM_PROMPT = """Tu es chargé de réécrire une question de suivi en une question autonome.

Règles :
- Si la question dépend de l'historique (références implicites comme « et le prix ? », « celui-là », « ces deux pays », « cette directive »), réécris-la en intégrant le contexte explicite.
- Si la question est déjà autonome, renvoie-la telle quelle, sans la modifier.
- Conserve la langue originale (français, anglais, etc.).
- Ne réponds PAS à la question. Ne donne aucune explication. Renvoie UNIQUEMENT la question réécrite, en une seule phrase."""


SYSTEM_PROMPT = """Tu es un assistant expert qui répond aux questions en te basant UNIQUEMENT sur les documents fournis.
Règles :
- Cite uniquement les sources réellement utilisées pour formuler ta réponse (nom du document, section). Le nombre de citations doit refléter la pertinence : une seule si une seule source suffit, plusieurs si nécessaire — n'en ajoute pas pour faire du remplissage.
- Si la réponse n'est pas dans les documents, dis-le clairement
- Sois précis et concis
- Réponds dans la langue de la question
- Tiens compte de l'historique de la conversation : si l'utilisateur fait référence à un sujet déjà abordé (« et le prix ? », « celui-ci », « l'autre »), interprète sa question dans le contexte des échanges précédents."""


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


def rewrite_query(query: str, history: list[ChatMessage]) -> str:
    """Transforme une question de suivi en question autonome via le LLM.

    Pas d'appel si l'historique est vide (gain de latence). En cas d'erreur LLM, retombe
    silencieusement sur la question originale plutôt que de bloquer la recherche.
    """
    if not history:
        return query

    # On ne garde que les derniers tours pour limiter les tokens
    recent = history[-(REWRITE_HISTORY_TURNS * 2):]
    formatted = []
    for m in recent:
        formatted.append(f"{m.role.upper()}: {m.content[:600]}")
    formatted.append(f"USER: {query}")
    transcript = "\n".join(formatted)

    try:
        resp = client.chat.completions.create(
            model=settings.openrouter_model,
            max_tokens=120,
            temperature=0,
            messages=[
                {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Historique de la conversation :\n\n{transcript}\n\nRéécris la dernière question de l'utilisateur en une question autonome :"},
            ],
        )
        rewritten = (resp.choices[0].message.content or "").strip()
        # Garde-fous : on ne remplace que si le résultat semble exploitable
        if not rewritten or len(rewritten) > 500:
            return query
        # Nettoyage : certains modèles ajoutent des guillemets ou un préfixe
        rewritten = rewritten.strip('"\'« »').strip()
        if rewritten.lower().startswith("question :"):
            rewritten = rewritten.split(":", 1)[1].strip()
        return rewritten or query
    except Exception:
        return query


def _trim_history(history: list[ChatMessage]) -> list[ChatMessage]:
    """Conserve les `MAX_HISTORY_TURNS` derniers tours et garantit l'alternance user/assistant."""
    if not history:
        return []
    max_msgs = MAX_HISTORY_TURNS * 2
    trimmed = history[-max_msgs:]
    # Le premier message conservé doit être 'user' pour respecter l'alternance attendue
    while trimmed and trimmed[0].role != "user":
        trimmed = trimmed[1:]
    return trimmed


def generate_answer(query: str, chunks: list[dict], history: list[ChatMessage] | None = None):
    """Génération streamée via OpenRouter (API OpenAI-compatible)."""
    context = build_context(chunks)
    history = _trim_history(history or [])

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({
        "role": "user",
        "content": f"Documents de référence :\n\n{context}\n\nQuestion : {query}",
    })

    stream = client.chat.completions.create(
        model=settings.openrouter_model,
        max_tokens=2048,
        stream=True,
        messages=messages,
    )
    for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            yield content
