from datetime import UTC, datetime, timedelta
import jwt
from fastapi import HTTPException
from .config import settings


def signing_key():
    secret = settings.sentinelops_jwt_secret
    if not secret or len(secret.get_secret_value().encode()) < 32:
        raise HTTPException(503, "Configure operator authentication")
    return secret.get_secret_value()


def read_subject(token: str) -> str:
    try:
        claims = jwt.decode(
            token,
            signing_key(),
            algorithms=["HS256"],
            issuer="sentinelops",
            audience="sentinelops-workspace",
            options={"require": ["exp", "iat", "sub"]},
        )
        if claims["sub"] != settings.sentinelops_operator:
            raise jwt.InvalidTokenError()
        return claims["sub"]
    except jwt.InvalidTokenError:
        raise HTTPException(
            401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"}
        )
