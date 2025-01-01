

from pydantic import BaseModel

class RegisterUserSchema(BaseModel):
    username: str
    email: str
    password: str


class LoginUserSchema(BaseModel):
    email: str
    password: str