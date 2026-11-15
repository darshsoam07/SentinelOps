from sentinelops_common.security import verify
from .config import settings


def read_subject(token: str) -> str:
    return verify(token, settings.sentinelops_public_key_file, settings.sentinelops_operator)
