

from pydantic import BaseModel

class RegisterUserSchema(BaseModel):
    name: str
    email: str
    password: str


class LoginUserSchema(BaseModel):
    email: str
    password: str