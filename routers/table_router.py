
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form

from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Union

from db.setup import get_db
from dependecies.authorization import TokenVerifyMiddleware
from repositories.table_repository import CreateTableRepository, FetchTableRepository, ExecuteQueryRepository, \
    FetchPublicTablesRepository, FavoriteTableRepository

router = APIRouter()

# Checked - Fetch all public tables
@router.get("/fetchpublictables", status_code=200)
async def fetch_public_tables(user_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):

    repository = FetchPublicTablesRepository(db)
    data = await repository.fetch_public_tables(user_id=user_id)
    return data


# Checked - Fetch all Favorite tables
@router.get("/fetchfavoritetables", status_code=200)
async def fetch_favorite_tables(db: AsyncSession = Depends(get_db), user_info = Depends(TokenVerifyMiddleware.verify_access_token)):
    repository = FavoriteTableRepository(db)
    if user_info:
        try:
            data = await repository.fetch_favorite_tables(user_info.get('id'))
            return data
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    else:
        return JSONResponse(status_code=401, content={"detail": 'Please login before creating a table'})

# Checked - Add table to favorites
@router.post("/addtofavorites/{table_id}", status_code=201)
async def add_to_favorites(table_id: int, db: AsyncSession = Depends(get_db), user_info = Depends(TokenVerifyMiddleware.verify_access_token)):
    repository = FavoriteTableRepository(db)
    if user_info:
        try:
            data = await repository.add_favorite_table(table_id, user_info.get('id'))
            return data
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    else:
        return JSONResponse(status_code=401, content={"detail": 'Please login before creating a table'})

# Checked - Delete table from favorites
@router.post("/deletefromfavorites/{table_id}", status_code=201)
async def delete_from_favorites(table_id: int, db: AsyncSession = Depends(get_db), user_info = Depends(TokenVerifyMiddleware.verify_access_token)):
    repository = FavoriteTableRepository(db)
    if user_info:
        try:
            data = await repository.delete_favorite_table(table_id, user_info.get('id'))
            return data
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    else:
        return JSONResponse(status_code=401, content={"detail": 'Please login before creating a table'})





# Checked for file, but create from manual, doesnt ready
@router.post("/createtable", status_code=201)
async def create_table(file: UploadFile = File(...), table_status: str = Form(...), table_description: str = Form(...), table_name: str = Form(...), db:AsyncSession = Depends(get_db),
                       user_info = Depends(TokenVerifyMiddleware.verify_access_token)):
    if user_info :
        repository = CreateTableRepository(db)
        try:
            data = await repository.create_table(user_info.get('id'), file, table_status, table_description, table_name)
            return data
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    else:
        return JSONResponse(status_code=401, content={"detail": 'Please login before creating a table'})



@router.get("/fetch/{table_name}")
async def fetch_table(table_name: str, db: AsyncSession = Depends(get_db), user_info = Depends(TokenVerifyMiddleware.verify_access_token)):
    repository = FetchTableRepository(db)
    if user_info:
        try:
            data = await repository.fetch_table(user_id=user_info.get('id'), table_name=table_name)
            return data
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    else:
        return JSONResponse(status_code=401, content={"detail": 'Please login before creating a table'})


@router.get("/query/{table_name}")
async def sql_query(
        table_name: str,
        sql_query: str,  # Ensure this is a string type
        db: AsyncSession = Depends(get_db),
        user_info=Depends(TokenVerifyMiddleware.verify_access_token)
):
    repository = ExecuteQueryRepository(db)

    if user_info:
        try:
            data = await repository.execute_query(sql_query)
            return data
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        except Exception as e:
            return JSONResponse(status_code=500, content={"detail": f"An error occurred: {str(e)}"})
    else:
        return JSONResponse(status_code=401, content={"detail": 'Please login before creating a table'})