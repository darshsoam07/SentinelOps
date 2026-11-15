from pathlib import Path

import jwt
from fastapi import HTTPException


def key_bytes(path):
    try:
        return Path(path).read_bytes()
    except (TypeError, OSError) as exc:
        raise HTTPException(503, "Configure operator authentication") from exc


def verify(token: str, public_key_file, operator: str) -> str:
    try:
        claims = jwt.decode(
            token,
            key_bytes(public_key_file),
            algorithms=["EdDSA"],
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
