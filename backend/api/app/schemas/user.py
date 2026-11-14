from typing import Literal
from pydantic import BaseModel


class User(BaseModel):
    username: str


class AccessToken(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
