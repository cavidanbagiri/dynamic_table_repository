from fastapi import HTTPException
from sqlalchemy import text, select, column, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.main_models import User as UserModel

from passlib.context import CryptContext

from datetime import datetime, timedelta, timezone

import jwt
import os
import logging

logger = logging.getLogger(__name__)


class UserRegisterRepository:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_user(self, user: UserModel) -> dict:
        """
        Registers a new user.

        :param user: User model containing username, email, and password.
        :return: User data after successful registration.
        """
        try:

            # Validate input data
            if not user.username or not user.email or not user.password:
                raise HTTPException(status_code=400, detail="All fields are required.")

            await self._check_username_email_exists(user)


            new_user = UserModel(
                name = user.name,
                middle_name = user.middle_name,
                surname = user.surname,
                username=user.username,
                email=user.email,
                password=self._hash_password(user.password),
            )
            # print(f'new user is {new_user}')
            self.db.add(new_user)
            await self.db.commit()
            await self.db.refresh(new_user)
            user_data = {
                "id": new_user.id,
                "username": new_user.username,
                "email": new_user.email
            }
            logger.info(f"User {new_user.username} registered successfully.")
            return user_data
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error registering user: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to register user.")

    def _hash_password(self, password: str) -> str:
        """
        Hashes a password using bcrypt.

        :param password: Password to hash.
        :return: Hashed password.
        """
        return self.pwd_context.hash(password)

    async def _check_username_email_exists(self, user: UserModel) -> bool:

        existing_email = await self.db.execute(select(UserModel).where(UserModel.email == user.email))
        if existing_email.scalars().first():
            logger.info(f"Email {user.email} already in use.")
            print(f"Email {user.email} already in use.")
            raise HTTPException(status_code=400, detail="Email already in use.")

        existing_username = await self.db.execute(select(UserModel).where(UserModel.username == user.username))
        if existing_username.scalars().first():
            print(f"Username {user.username} already in use.")
            logger.info(f"Username {user.username} already in use.")
            raise HTTPException(status_code=400, detail="Username already in use.")




class TokenRepository:

    @staticmethod
    def create_access_token(data: dict) -> str:
        """
        Creates an access token with the provided data.

        :param data: Data to encode in the token.
        :return: JWT token.
        """
        try:
            to_encode = data.copy()  # Ensure data is not modified
            to_encode.update({"exp": datetime.now(timezone.utc) + timedelta(hours=12)})
            secret_key = os.getenv('JWT_SECRET_KEY')
            algorithm = os.getenv('JWT_ALGORITHM')
            if not secret_key or not algorithm:
                raise ValueError("JWT secret key or algorithm not set.")
            return jwt.encode(to_encode, secret_key, algorithm=algorithm)
        except Exception as e:
            logger.error(f"Error creating token: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create token.")


class UserLoginRepository:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def __init__(self, db: AsyncSession):
        self.db = db

    async def login(self, email: str, password: str) -> dict:
        """
        Logs in a user and returns an access token.

        :param email: User's email.
        :param password: User's password.
        :return: Access token and user data.
        """
        try:
            # Fetch user using ORM for consistency
            # user = await self.db.execute(select(UserModel).where(UserModel.email == email))
            user = await self.db.execute(
                select(
                    UserModel.id,
                    UserModel.username,
                    UserModel.email,
                    UserModel.password,
                    # Concatenate name, middle_name, and surname into a single common_name
                    func.concat(UserModel.name, ' ', UserModel.middle_name, ' ', UserModel.surname).label(
                        "fullname"),
                    UserModel.image_url
                ).where(UserModel.email == email)
            )

            user = user.first()

            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            if not self.__verify_password(password, user.password):
                raise HTTPException(status_code=401, detail="Incorrect password")


            user_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "fullname": user.fullname,
                "profile_image": user.image_url
            }
            token_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email
            }
            new_data = {
                'access_token': TokenRepository.create_access_token(token_data),
                'user': user_data
            }
            logger.info(f"User {user.username} logged in successfully.")
            return new_data
        except HTTPException as e:
            logger.error(f"Error logger in user: {str(e)}")
            raise HTTPException(status_code=500, detail=f"{str(e)}")

    def __verify_password(self, password: str, hashed_password: str) -> bool:
        """
        Verifies if a password matches the hashed password.

        :param password: Password to verify.
        :param hashed_password: Hashed password.
        :return: True if password matches, False otherwise.
        """
        return self.pwd_context.verify(password, hashed_password)
