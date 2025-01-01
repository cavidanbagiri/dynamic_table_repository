
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.setup import SessionLocal
from models.main_models import User as UserModel

from passlib.context import CryptContext


from datetime import datetime, timedelta, timezone

import jwt
import os

class UserRegisterRepository:

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def __init__(self, db: AsyncSession):
        self.db= db

    async def register_user(self, user: UserModel):
        async with SessionLocal() as session:
            user = UserModel(
                username=user.username,
                email=user.email,
                password=self._hash_password(user.password),
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            user_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email
            }
            return user_data

    def _hash_password(self, password: str):
        return self.pwd_context.hash(password)


class TokenRepository:

    # Create Access Token
    @staticmethod
    def create_access_token( data):
        to_encode = data
        to_encode.update({"exp": datetime.now(timezone.utc) + timedelta(hours=12) })
        return jwt.encode(to_encode, os.getenv('JWT_SECRET_KEY'), algorithm=os.getenv('JWT_ALGORITHM'))


class UserLoginRepository:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def __init__(self, db: AsyncSession):
        self.db = db

    async def login(self, email:str, password:str):
        async with SessionLocal() as session:
            finded_user = await session.execute(text("SELECT * FROM users WHERE email = :email"), {"email": email})
            user = finded_user.mappings().first()
            if not user:
                return False
            if not self.__verify_password(password, user.password):
                return False

            user_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email
            }
            token_data = {
                "id": user.id,
                "username": user.username,
            }
            new_data = {'access_token': TokenRepository.create_access_token(token_data), 'user': user_data}
            return new_data




    def __verify_password(self, password, hashed_password):
        return self.pwd_context.verify(password, hashed_password)

