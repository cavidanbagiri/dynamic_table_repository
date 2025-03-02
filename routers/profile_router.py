from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession

from db.setup import get_db

from dependecies.authorization import TokenVerifyMiddleware

from repositories.profile_repository import UserProfileImageRepository

router = APIRouter()

# Checking
@router.post('/uploadprofileimage', status_code=201)
async def upload_img(db: AsyncSession = Depends(get_db), user_info = Depends(TokenVerifyMiddleware.verify_access_token), file: UploadFile=File(...)):

    if user_info:
        repository = UserProfileImageRepository(db)
        try:
            url = await repository.upload_image(user_info, file)
            return JSONResponse(status_code=201, content={'message': 'image added successfully', 'url': url})
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    else :
        return JSONResponse(status_code=404, content={"message": "Please login before adding profile image"})