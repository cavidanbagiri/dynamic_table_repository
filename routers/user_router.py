from fastapi import APIRouter, Depends, HTTPException

from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession

from db.setup import get_db
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
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})

@router.post("/login", status_code=201)
async def login_user(user: LoginUserSchema, db: AsyncSession = Depends(get_db)):

    repository = UserLoginRepository(db)
    try:
        user = await repository.login(user.email, user.password)
        return user
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})