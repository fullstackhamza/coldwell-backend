from pydantic import EmailStr, Field

from .common import CamelModel


class UserCreate(CamelModel):
    full_name: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class UserLogin(CamelModel):
    email: EmailStr
    password: str


class UserPublic(CamelModel):
    id: str
    full_name: str
    email: EmailStr
    role: str = "customer"


class Token(CamelModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic
