from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from app.core.security import read_subject

scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def current_user(token: str = Depends(scheme)) -> str:
    return read_subject(token)
