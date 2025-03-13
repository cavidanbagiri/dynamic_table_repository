
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator

# Request schema for user registration
class RequestRegisterUserSchema(BaseModel):
    name: Optional[str] = Field(default=None, description="User's first name")
    middle_name: Optional[str] = Field(default=None, description="User's middle name")
    surname: Optional[str] = Field(default=None, description="User's last name")
    username: str = Field(..., description="User's unique username")
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password (min 8 characters)")


# Response schema for registered user details
class ResponseRegisterUserSchema(BaseModel):
    id: int = Field(..., description="User's unique ID")
    username: str = Field(..., description="User's username")
    email: str = Field(..., description="User's email address")

# Response schema for registration endpoint
class RegisterResponseSchema(BaseModel):
    message: str = Field(..., description="Response message")
    user: ResponseRegisterUserSchema = Field(..., description="Registered user details")

# Request schema for user login
class LoginUserSchema(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


# from typing import Optional
#
# from pydantic import BaseModel
#
# class RequestRegisterUserSchema(BaseModel):
#     name: Optional[str] = None
#     middle_name: Optional[str] = None
#     surname: Optional[str] = None
#     username: str
#     email: str
#     password: str
#
# class ResponseRegisterUserSchema(BaseModel):
#     id: int
#     username: str
#     email: str
#
# class RegisterResponseSchema(BaseModel):
#     message: str
#     user: ResponseRegisterUserSchema
#
#
# class LoginUserSchema(BaseModel):
#     email: str
#     password: str