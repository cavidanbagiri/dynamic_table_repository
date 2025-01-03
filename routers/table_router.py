
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form

from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession

from db.setup import get_db
from dependecies.authorization import TokenVerifyMiddleware
from repositories.table_repository import CreateTableRepository, FetchTableRepository, ExecuteQueryRepository, \
    FetchPublicTablesRepository

router = APIRouter()

# Checked
@router.get("/fetchpublictables", status_code=200)
async def fetch_public_tables(db: AsyncSession = Depends(get_db)):
    repository = FetchPublicTablesRepository(db)
    data = await repository.fetch_public_tables()
    return data


@router.post("/create")
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