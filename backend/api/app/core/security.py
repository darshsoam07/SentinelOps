from datetime import UTC, datetime, timedelta
import jwt
from sentinelops_common.security import signing_key
from sentinelops_common.security import verify
from .config import settings


def read_subject(token: str) -> str:
    return verify(token, settings.sentinelops_jwt_secret, settings.sentinelops_operator)


def issue_token(subject):
    now = datetime.now(UTC)
    return jwt.encode(
        dict(
            sub=subject,
            iat=now,
            exp=now + timedelta(minutes=15),
            iss="sentinelops",
            aud="sentinelops-workspace",
        ),
        signing_key(settings.sentinelops_jwt_secret),
        algorithm="HS256",
    )
