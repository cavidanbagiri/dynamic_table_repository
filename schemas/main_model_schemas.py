from typing import Optional

from pydantic import BaseModel

class RegisterUserSchema(BaseModel):
    name: str
    middle_name: Optional[str] = None
    surname: str
    username: str
    email: str
    password: str


class LoginUserSchema(BaseModel):
    email: str
    password: str