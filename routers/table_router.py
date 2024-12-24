
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form

from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession

from db.setup import get_db
from repositories.table_repository import CreateTableRepository

router = APIRouter()

@router.post("/create")
async def create_table(file: UploadFile = File(...), company_name: str = Form(...), table_name: str = Form(...), db:AsyncSession = Depends(get_db)):

    repository = CreateTableRepository(db)
    try:
        data = await repository.create_table(file, company_name, table_name)
        return data
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})