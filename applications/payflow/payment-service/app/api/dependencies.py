from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import read_subject

scheme = HTTPBearer(auto_error=False)


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(scheme),
) -> str:
    if not credentials:
        raise HTTPException(
            401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"}
        )
    return read_subject(credentials.credentials)
