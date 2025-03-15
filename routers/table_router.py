
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Request

from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from db.setup import get_db
from dependecies.authorization import TokenVerifyMiddleware
from repositories.table_repository import CreateTableRepository, FetchTableRepository, ExecuteQueryRepository, \
    FetchPublicTablesRepository, FavoriteTableRepository, FetchTableWithHeaderFilterRepository, FetchMyTablesRepository, \
    DeleteTableRepository, SearchPublicTableRepository, CreateTableFromReadyComponentsRepository, GetQueryTypeRepository

from schemas.table_schemas import QueryRequest, TableCreateRequest

router = APIRouter()



# Checked - Fetch all my tables
@router.get("/fetchmytables", status_code=200)
async def fetch_my_tables(db: AsyncSession = Depends(get_db), user_info = Depends(TokenVerifyMiddleware.verify_access_token)):
    repository = FetchMyTablesRepository(db)
    if user_info:
        try:
            data = await repository.fetch_my_tables(user_info.get('id'))
            return data
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    else:
        return JSONResponse(status_code=401, content={"detail": 'Please login before creating a table'})






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



# Checked
@router.post("/createtable", status_code=201)
async def create_table(file: UploadFile = File(...), table_status: str = Form(...), table_description: str = Form(...), table_name: str = Form(...),
                       table_category: str = Form(...), db:AsyncSession = Depends(get_db),
                       user_info = Depends(TokenVerifyMiddleware.verify_access_token)):
    if user_info :
        repository = CreateTableRepository(db)
        try:
            data = await repository.create_table(user_info.get('id'), file, table_status, table_description, table_name, table_category)
            return data
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    else:
        return JSONResponse(status_code=401, content={"detail": 'Please login before creating a table'})



# Checked
@router.delete("/deletetable/{table_name}")
async def delete_table(table_name: str, db: AsyncSession = Depends(get_db), user_info = Depends(TokenVerifyMiddleware.verify_access_token)):
    repository = DeleteTableRepository(db)
    if user_info:
        try:
            data = await repository.delete_table(table_name, user_info.get('id'))
            return data
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    else:
        return JSONResponse(status_code=401, content={"detail": 'Please login before creating a table'})



# Checked
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


# Checked
@router.get("/filter/{table_name}", status_code=200)
async def filter_table_by_headers(table_name: str, request: Request, db: AsyncSession = Depends(get_db), user_info = Depends(TokenVerifyMiddleware.verify_access_token)):
    repository = FetchTableWithHeaderFilterRepository(db)
    if user_info:
        try:
            query_params = request.query_params
            query_dict = dict(query_params)
            data = await repository.fetch_table_with_header(user_id=user_info.get('id'), table_name=table_name, params=query_dict)
            return data
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    else:
        return JSONResponse(status_code=401, content={"detail": 'Please login before creating a table'})



# Checked
@router.get("/searchpublictable")
async def search_public_table(search_keyword: str, db: AsyncSession = Depends(get_db), user_info = Depends(TokenVerifyMiddleware.verify_access_token)):
    repository = SearchPublicTableRepository(db)
    if user_info:
        try:
            data = await repository.search_public_table(search_keyword, user_id = user_info.get('id'))
            return data
        except HTTPException as e:
            print(f'Error searching public table: {str(e)}')
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    else:
        return JSONResponse(status_code=401, content={"detail": 'Please login before creating a table'})


# Checked
@router.post("/createtablefromcomponents")
async def create_table_from_components(table_data : TableCreateRequest, db: AsyncSession = Depends(get_db), user_info = Depends(TokenVerifyMiddleware.verify_access_token)):
    repository = CreateTableFromReadyComponentsRepository(db)
    if user_info:
        try:
            data = await repository.create_table_from_components(table_data, user_id=user_info.get('id'))
            return data
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    else:
        return JSONResponse(status_code=401, content={"detail": 'Please login before creating a table'})




# Checked
@router.post("/query")
async def sql_query(
    query_request: QueryRequest,  # Use the Pydantic model here
    db: AsyncSession = Depends(get_db),
    user_info=Depends(TokenVerifyMiddleware.verify_access_token)
):
    sql_query = query_request.sql_query  # Access the sql_query from the request body

    repository = ExecuteQueryRepository(db)
    if user_info:
        print(f'11111111111111')
        try:
            # get Query type for returning status code
            query_type = GetQueryTypeRepository.get_query_type(sql_query)

            data = await repository.execute_query(sql_query, user_info)

            if query_type == 'SELECT':
                return JSONResponse(status_code=200, content=data)
            elif query_type in ['INSERT', 'UPDATE', 'DELETE']:
                return JSONResponse(status_code=201, content=data)
            elif query_type == 'CREATE':
                return JSONResponse(status_code=201, content=data)
            else:
                return JSONResponse(status_code=400, content={"detail": "Invalid query type"})

            # return data
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"message": e.detail})
        except Exception as e:
            return JSONResponse(status_code=500, content={"message": f"An error occurred: {str(e)}"})
    else:
        return JSONResponse(status_code=401, content={"message": 'Please login before creating a table'})
