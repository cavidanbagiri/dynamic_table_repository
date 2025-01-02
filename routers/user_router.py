from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession

from db.setup import get_db

from dependecies.authorization import TokenVerifyMiddleware
from repositories.user_repository import UserRegisterRepository, UserLoginRepository
from schemas.main_model_schemas import RegisterUserSchema, LoginUserSchema

router = APIRouter()

@router.post("/register", status_code=201)
async def register_user(user: RegisterUserSchema, db: AsyncSession = Depends(get_db)):

    repository = UserRegisterRepository(db)
    try:
        user = await repository.register_user(user)
        data = {
            "user": user,
            "message": "User registered successfully"
        }
        return data
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"message": e.detail})

# Checked
@router.post("/login", status_code=200)
async def login_user(user: LoginUserSchema, db: AsyncSession = Depends(get_db)):
    repository = UserLoginRepository(db)
    try:
        user = await repository.login(user.email, user.password)
        return user
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"message": e.detail})


@router.get('/refresh', status_code=200)
async def refresh(request: Request, user_info = Depends(TokenVerifyMiddleware.verify_access_token)):
    if user_info:
        return JSONResponse(status_code=200, content={'user': user_info})
    else:
        return None