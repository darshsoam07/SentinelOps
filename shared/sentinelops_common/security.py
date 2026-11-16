import jwt
from fastapi import HTTPException


def signing_key(secret):
    if not secret or len(secret.get_secret_value().encode()) < 32:
        raise HTTPException(503, "Configure operator authentication")
    return secret.get_secret_value()


def verify(token: str, secret, operator: str) -> str:
    try:
        claims = jwt.decode(
            token,
            signing_key(secret),
            algorithms=["HS256"],
            issuer="sentinelops",
            audience="sentinelops-workspace",
            options={"require": ["exp", "iat", "sub"]},
        )
        if claims["sub"] != operator:
            raise jwt.InvalidTokenError()
        return claims["sub"]
    except jwt.InvalidTokenError:
        raise HTTPException(
            401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"}
        )
