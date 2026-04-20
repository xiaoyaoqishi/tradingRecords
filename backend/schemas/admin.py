from typing import Optional

from pydantic import BaseModel


class UserCreateBody(BaseModel):
    username: str
    password: str


class UserResetPasswordBody(BaseModel):
    password: str


class UserUpdateBody(BaseModel):
    role: Optional[str] = None
    password: Optional[str] = None
