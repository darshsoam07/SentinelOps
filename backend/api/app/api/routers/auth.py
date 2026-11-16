from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from app.api.dependencies import current_user
from app.core.config import settings
from app.core.security import issue_token
from app.schemas import AccessToken, User

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()
hasher = PasswordHash.recommended()


@router.post("/auth/login", tags=["Authentication"])
@limiter.limit("10/minute")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends()) -> AccessToken:
    digest = settings.sentinelops_password_hash
    if not digest:
        raise HTTPException(503, "Configure operator authentication")
    valid = hasher.verify(form.password, digest.get_secret_value())
    if not valid or form.username != settings.sentinelops_operator:
        raise HTTPException(
            401,
            "Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AccessToken(access_token=issue_token(form.username))


@router.get("/users/me", tags=["Users"])
async def me(username: str = Depends(current_user)) -> User:
    return User(username=username)
