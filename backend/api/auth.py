from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from auth import is_auth_disabled, verify_token, _extract_bearer

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    token: str


class AuthStatus(BaseModel):
    authenticated: bool
    auth_required: bool


@router.get("/status", response_model=AuthStatus)
def auth_status(authorization: str | None = Header(None)):
    """Indique au front si l'auth est active et si le token courant est valide.

    Utile au chargement de l'app : permet d'éviter d'afficher le formulaire de login
    quand admin_token n'est pas configuré (mode dev).
    """
    if is_auth_disabled():
        return AuthStatus(authenticated=True, auth_required=False)
    token = _extract_bearer(authorization)
    return AuthStatus(authenticated=verify_token(token), auth_required=True)


@router.post("/login", response_model=AuthStatus)
def login(payload: LoginRequest):
    """Vérifie le token et le renvoie sous forme de statut. Le front est responsable
    de stocker le token (localStorage) pour les requêtes suivantes."""
    if is_auth_disabled():
        return AuthStatus(authenticated=True, auth_required=False)
    if not verify_token(payload.token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton administrateur invalide",
        )
    return AuthStatus(authenticated=True, auth_required=True)
