from datetime import UTC, datetime, timedelta
import jwt
from sentinelops_common.security import key_bytes
from sentinelops_common.security import verify
from .config import settings


def read_subject(token: str) -> str:
    return verify(token, settings.sentinelops_public_key_file, settings.sentinelops_operator)


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
        key_bytes(settings.sentinelops_private_key_file),
        algorithm="EdDSA",
    )
