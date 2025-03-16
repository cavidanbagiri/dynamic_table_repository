
import os
import logging

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from fastapi import Request

import jwt
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession


user_logger = logging.getLogger("user_logger")
user_logger.setLevel(logging.INFO)
user_handler = logging.FileHandler("logs/userlog.log")
# user_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s'))
user_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s - [File: %(filename)s] - %(message)s'))
user_logger.addHandler(user_handler)

from models.main_models import TokenModel



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
            to_encode.update({"exp": datetime.now(timezone.utc) + timedelta(minutes=15)})
            secret_key = os.getenv('JWT_SECRET_KEY')
            algorithm = os.getenv('JWT_ALGORITHM')
            if not secret_key or not algorithm:
                user_logger.error("JWT secret key or algorithm not set.")
                raise ValueError("JWT secret key or algorithm not set.")
            return jwt.encode(to_encode, secret_key, algorithm=algorithm)
        except Exception as e:
            user_logger.error(f"Error creating access token: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create access token.")

    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """
        Creates a refresh token with the provided data.

        :param data: Data to encode in the token.
        :return: JWT refresh token.
        """
        try:
            to_encode = data.copy()  # Ensure data is not modified
            to_encode.update({"exp": datetime.now(timezone.utc) + timedelta(days=30)})
            secret_key = os.getenv('JWT_REFRESH_SECRET_KEY')
            algorithm = os.getenv('JWT_ALGORITHM')
            if not secret_key or not algorithm:
                user_logger.error("JWT refresh secret key or algorithm not set.")
                raise ValueError("JWT refresh secret key or algorithm not set.")
            return jwt.encode(to_encode, secret_key, algorithm=algorithm)
        except Exception as e:
            user_logger.error(f"Error creating refresh token: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create refresh token.")


class TokenVerifyMiddleware:

    # Verify Access Token
    @staticmethod
    def verify_access_token(request: Request):
        headers = dict(request.headers)
        if headers.get('token'):
            try:
                token = headers.get('token').split(" ")[1]
                payload = jwt.decode(token, os.getenv('JWT_SECRET_KEY'), algorithms=os.getenv('JWT_ALGORITHM'))
                return payload
            except jwt.ExpiredSignatureError:
                raise HTTPException(status_code=401, detail="Invalid token")
            except jwt.DecodeError:
                raise HTTPException(status_code=401, detail="Invalid token")
        else:
            raise HTTPException(status_code=401, detail="Invalid token")


class VerifyRefreshTokenMiddleware:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_refresh_token(self, request: Request):
        """
        Validates a refresh token and returns new access and refresh tokens.

        :param request: Incoming request.
        :return: Dictionary containing new access and refresh tokens.
        """
        # headers = dict(request.headers)
        # refresh_token = headers.get('refresh_token')
        refresh_token = request.cookies.get('refresh_token')

        if not refresh_token:
            user_logger.warning("Please login before executing")
            raise HTTPException(status_code=400, detail="Please login before executing")

        try:
            # Decode the refresh token
            payload = jwt.decode(
                refresh_token,
                os.getenv('JWT_REFRESH_SECRET_KEY'),
                algorithms=[os.getenv('JWT_ALGORITHM')]
            )

            # Check if the new refresh token already exists in the database
            user_id = await SearchRefreshTokenRepository(self.db).search_refresh_token(refresh_token)

            if user_id is None:
                raise HTTPException(status_code=401, detail="Invalid or revoked refresh token")

            # Generate new tokens
            access_token = TokenRepository.create_access_token(payload)
            new_refresh_token = TokenRepository.create_refresh_token(payload)

            await UpdateRefreshTokenRepository(self.db).update_refresh_token(payload['id'], new_refresh_token)

            # Log successful token refresh
            user_logger.info(f"New tokens issued for user: {user_id}")

            # Save the new refresh token
            # await SaveRefreshTokenRepository(self.db).save_refresh_token(payload['id'], new_refresh_token)

            return {
                'access_token': access_token,
                'refresh_token': new_refresh_token,
                'user': payload
            }


        except jwt.ExpiredSignatureError:
            user_logger.warning("Expired refresh token")
            raise HTTPException(status_code=401, detail="Expired refresh token")

        except jwt.InvalidTokenError as e:
            user_logger.warning(f"Invalid refresh token: {str(e)}")
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        except Exception as e:
            user_logger.error(f"Unexpected error validating refresh token: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="An error occurred while validating the refresh token")


class SaveRefreshTokenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_refresh_token(self, user_id: int, refresh_token: str):
        """
        Saves a refresh token for a user.

        :param user_id: ID of the user.
        :param refresh_token: Refresh token to save.
        """
        try:
            refresh_token_data = {
                "user_id": user_id,
                "refresh_token": refresh_token
            }
            refresh_token_model = TokenModel(
                user_id=user_id,
                token=refresh_token
            )
            self.db.add(refresh_token_model)
            await self.db.commit()
            await self.db.refresh(refresh_token_model)
            user_logger.info(f"Refresh token saved for user: {user_id}")
        except Exception as e:
            user_logger.error(f"Error saving refresh token: {str(e)}")
            raise


class UpdateRefreshTokenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_refresh_token(self, user_id: int, refresh_token: str):
        """
        Updates a refresh token for a user.

        :param user_id: ID of the user.
        :param refresh_token: Refresh token to update.
        """
        try:
            await self.db.execute(
                update(TokenModel).where(TokenModel.user_id == user_id).values(token=refresh_token)
            )
            await self.db.commit()
        except Exception as e:
            user_logger.error(f"Error updating refresh token: {str(e)}")



class DeleteRefreshTokenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def delete_refresh_token(self, user_id: int) -> None:
        """
        Deletes a refresh token for a user.

        :param user_id: ID of the user.
        """
        try:
            await self.db.execute(
                delete(TokenModel).where(TokenModel.user_id == user_id)
            )
            await self.db.commit()
            user_logger.info(f"Refresh token deleted for user {user_id}.")
        except Exception as e:
            user_logger.error(f"Error deleting refresh token for user {user_id}: {str(e)}")
            raise


class SearchRefreshTokenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_refresh_token(self, refresh_token: str):
        """
        Searches for a refresh token in the database.

        :param refresh_token: Refresh token to search for.
        :return: User ID if found, None otherwise.
        """
        try:
            token = await self.db.execute(
                select(TokenModel).where(TokenModel.token == refresh_token)
            )

            token = token.scalar()
            if token:
                return token.user_id
            else:
                return None

        except Exception as e:
            user_logger.error(f"Error searching refresh token: {str(e)}")
            raise