"""Auth simple par jeton partagé pour les endpoints admin.

Modèle :
- Un seul jeton (`settings.admin_token`) donne accès aux opérations administratives
  (upload, suppression, réindexation, gestion des documents).
- Le jeton est transmis via `Authorization: Bearer <token>`.
- Si `settings.admin_token` est vide ou non défini, l'authentification est désactivée :
  utile en dev, mais à éviter en production.

Le chat (`/query`) reste public — c'est explicitement le seul endpoint accessible sans auth.
"""
from fastapi import Header, HTTPException, status

from config import settings


def is_auth_disabled() -> bool:
    return not bool(settings.admin_token)


def verify_token(token: str | None) -> bool:
    if is_auth_disabled():
        return True
    if not token:
        return False
    return token == settings.admin_token


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def require_admin(authorization: str | None = Header(None)) -> None:
    """Dépendance FastAPI : exige un token admin valide dans l'en-tête Authorization.

    Lève 401 si le token est manquant ou invalide. Si l'auth est désactivée
    (admin_token non configuré), passe sans vérifier.
    """
    if is_auth_disabled():
        return
    token = _extract_bearer(authorization)
    if not verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification administrateur requise",
            headers={"WWW-Authenticate": "Bearer"},
        )
