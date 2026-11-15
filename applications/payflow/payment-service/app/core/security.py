from sentinelops_common.security import verify
from .config import settings


def read_subject(token: str) -> str:
    return verify(token, settings.sentinelops_jwt_secret, settings.sentinelops_operator)
