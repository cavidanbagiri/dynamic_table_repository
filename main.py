
from fastapi import FastAPI

# Import .env
from dotenv import load_dotenv
load_dotenv()

# Import routers
from routers import table_router

app = FastAPI()

app.include_router(table_router.router, prefix="/api/table")
