import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pandas.io.clipboard import clipboard_get

from sqlalchemy.ext.asyncio import AsyncSession

from db.setup import get_db


from fastapi.responses import Response

import logging

logger = logging.getLogger(__name__)

from dependecies.authorization import TokenVerifyMiddleware, VerifyRefreshTokenMiddleware
from repositories.user_repository import UserRegisterRepository, UserLoginRepository, TokenRepository, \
    UserLogoutRepository
from schemas.main_model_schemas import RequestRegisterUserSchema, RegisterResponseSchema, LoginUserSchema

router = APIRouter()



@router.post("/register", status_code=201, response_model=RegisterResponseSchema)
async def register_user(
    user: RequestRegisterUserSchema,
    db: AsyncSession = Depends(get_db)
):
    repository = UserRegisterRepository(db)
    try:
        user_data = await repository.register_user(user)
        return {
            "message": "User registered successfully",
            "user": user_data,
        }
    except HTTPException as e:
        raise  # Re-raise the HTTPException to let FastAPI handle it
    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")




@router.post("/login", status_code=200)
async def login_user(response: Response, user: LoginUserSchema, db: AsyncSession = Depends(get_db)):
    repository = UserLoginRepository(db)
    try:
        user = await repository.login(user.email, user.password)
        response.set_cookie(
            key="refresh_token",
            value=user.get("refresh_token"),
            httponly=True,
            secure=True,
            samesite="none",
            # max_age=30 * 60 * 60 * 24
        )
        return user
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"message": e.detail})



@router.post("/refreshtoken", status_code=200)
async def refresh_token(response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Refreshes an access token using a refresh token.

    :param user_info: Decoded token data from the refresh token.
    :return: New access and refresh tokens.
    """
    # Initialize the middleware with the database session
    print('-------------------------------------------------------------------------------- start refresh token')
    middleware = VerifyRefreshTokenMiddleware(db)
    try:
        # Validate the refresh token and get user info
        user_info = await middleware.validate_refresh_token(request)
        if not user_info:
            logger.warning("Invalid or expired refresh token")
            response.delete_cookie(key="refresh_token")
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

        # Set the new refresh token in an HTTP-only cookie
        response.set_cookie(
            key="refresh_token",
            value=user_info["refresh_token"],
            httponly=True,
            secure=True,  # Ensure this is True in production
            samesite="none",
        )

        # Return the new access token and user info
        return {
            "access_token": user_info["access_token"],
            "user": user_info,
        }

    except HTTPException as e:
        logger.error(f"Error refreshing token: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error refreshing token: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while refreshing the token")

@router.get('/logout', status_code=200)
async def logout(
    request: Request,
    response: Response,
    user_info: dict = Depends(TokenVerifyMiddleware.verify_access_token),
    db: AsyncSession = Depends(get_db)
):
    if not user_info:
        return JSONResponse(status_code=401, content={"message": "Please login before logging out"})

    user_logout_repository = UserLogoutRepository(db)
    try:
        result = await user_logout_repository.logout(user_info.get('id'))
        if not result:
            return JSONResponse(status_code=500, content={"message": "Error logging out user"})

        # Manually set the Set-Cookie header to delete the refresh token
        response.set_cookie(
            key="refresh_token",
            value="",  # Empty value
            max_age=0,  # Expire immediately
            expires=0,  # Expire immediately
            path="/",  # Ensure this matches the cookie's original path
            domain='localhost',
            httponly=True,
            secure=True,  # Ensure this is True in production
            samesite="none",  # Allow cross-site requests
        )

        return JSONResponse(status_code=200, content={"message": "Logout successful"})
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        return JSONResponse(status_code=500, content={"message": "An error occurred during logout"})


# @router.get('/refresh', status_code=200)
# async def refresh(request: Request, user_info = Depends(TokenVerifyMiddleware.verify_access_token)):
#     if user_info:
#         return JSONResponse(status_code=200, content={'user': user_info})
#     else:
#         return None
#
# @router.get('/logout', status_code=200)
# async def logout(
#     request: Request,
#     response: Response,
#     user_info: dict = Depends(TokenVerifyMiddleware.verify_access_token),
#     db: AsyncSession = Depends(get_db)
# ):
#     if not user_info:
#         return JSONResponse(status_code=401, content={"message": "Please login before logging out"})
#
#     user_logout_repository = UserLogoutRepository(db)
#     try:
#         result = await user_logout_repository.logout(user_info.get('id'))
#         if not result:
#             return JSONResponse(status_code=500, content={"message": "Error logging out user"})
#
#         # Manually set the Set-Cookie header to delete the refresh token
#         response.set_cookie(
#             key="refresh_token",
#             value="",  # Empty value
#             max_age=0,  # Expire immediately
#             expires=0,  # Expire immediately
#             path="/",  # Ensure this matches the cookie's original path
#             domain="localhost",  # Ensure this matches the cookie's original domain
#             httponly=True,
#             secure=True,  # Ensure this is True in production
#             samesite="none",  # Allow cross-site requests
#         )
#
#         print(f'-------------------------------------------------------------------------------- {response.headers}')
#         # return JSONResponse(status_code=200, content={"message": "Logout successful"})
#         return response
#     except Exception as e:
#         logger.error(f"Error during logout: {str(e)}")
#         return JSONResponse(status_code=500, content={"message": "An error occurred during logout"})
# @router.get('/logout', status_code=200)
# async def logout(
#     request: Request,
#     response: Response,
#     user_info: dict = Depends(TokenVerifyMiddleware.verify_access_token),
#     db: AsyncSession = Depends(get_db)
# ):
#     if not user_info:
#         return JSONResponse(status_code=401, content={"message": "Please login before logging out"})
#
#     user_logout_repository = UserLogoutRepository(db)
#     try:
#         result = await user_logout_repository.logout(user_info.get('id'))
#         if not result:
#             return JSONResponse(status_code=500, content={"message": "Error logging out user"})
#
#         # Manually set the Set-Cookie header to delete the refresh token
#         response.headers.append(
#             "Set-Cookie",
#             "refresh_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; Secure; SameSite=None"
#         )
#         print(f'-------------------------------------------------------------------------------- {response}')
#         print(f'-------------------------------------------------------------------------------- {response.headers}')
#         return JSONResponse(status_code=200, content={"message": "Logout successful"})
#     except Exception as e:
#         logger.error(f"Error during logout: {str(e)}")
#         return JSONResponse(status_code=500, content={"message": "An error occurred during logout"})

# @router.get('/logout', status_code=200)
# async def logout(
#     request: Request,
#     response: Response,
#     user_info: dict = Depends(TokenVerifyMiddleware.verify_access_token),
#     db: AsyncSession = Depends(get_db)
# ):
#     if not user_info:
#         return JSONResponse(status_code=401, content={"message": "Please login before logging out"})
#
#     user_logout_repository = UserLogoutRepository(db)
#     try:
#         result = await user_logout_repository.logout(user_info.get('id'))
#         if not result:
#             return JSONResponse(status_code=500, content={"message": "Error logging out user"})
#
#         # Delete the refresh token cookie
#
#         response.delete_cookie(
#             key="refresh_token",
#             httponly=True,
#             path="/",
#             secure=True,  # Ensure this is True in production
#             samesite="none",  # Allow cross-site requests
#         )
#
#         print(f'cookie deleted -> ', response)
#         print(f'cookie deleted -> ', response.headers)
#
#         return JSONResponse(status_code=200, content={"message": "Logout successful"})
#     except Exception as e:
#         logger.error(f"Error during logout: {str(e)}")
#         return JSONResponse(status_code=500, content={"message": "An error occurred during logout"})

# @router.get('/logout', status_code=200)
# async def logout(
#     request: Request,
#     response: Response,
#     user_info: dict = Depends(TokenVerifyMiddleware.verify_access_token),
#     db: AsyncSession = Depends(get_db)
# ):
#     print('-------------------------------------------------------------------------------- start logout')
#     if not user_info:
#         return JSONResponse(status_code=401, content={"message": "Please login before logging out"})
#
#     user_logout_repository = UserLogoutRepository(db)
#     try:
#         result = await user_logout_repository.logout(user_info.get('id'))
#         if not result:
#             return JSONResponse(status_code=500, content={"message": "Error logging out user"})
#
#         # Delete the refresh token cookie
#         response.delete_cookie(
#             key="refresh_token",
#             httponly=True,
#             secure=True,  # Ensure this is True in production
#             samesite="none",
#         )
#
#         return JSONResponse(status_code=200, content={"message": "Logout successful"})
#     except Exception as e:
#         logger.error(f"Error during logout: {str(e)}")
#         return JSONResponse(status_code=500, content={"message": "An error occurred during logout"})

# @router.get('/logout', status_code=200)
# async def logout(request: Request, response: Response, user_info = Depends(TokenVerifyMiddleware.verify_access_token), db: AsyncSession = Depends(get_db)):
#     if user_info:
#         user_logout_repository = UserLogoutRepository(db)
#         result = await user_logout_repository.logout(user_info.get('id'))
#         if not result:
#             return JSONResponse(status_code=500, content={"message": "Error logging out user"})
#         response.delete_cookie(key="refresh_token")
#         return JSONResponse(status_code=200, content={"message": "Logout successful"})
#     else:
#         return JSONResponse(status_code=401, content={"message": "Please login before logging out"})