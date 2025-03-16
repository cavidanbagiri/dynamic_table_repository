
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


# Ensure the logs directory exists
os.makedirs("logs", exist_ok=True)

# Import .env
from dotenv import load_dotenv
load_dotenv()


# Import routers
from routers import table_router, user_router, profile_router

app = FastAPI()


origins = [
    'http://localhost:5173'
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router.router, prefix="/api/user", tags=["Users"])
app.include_router(table_router.router, prefix="/api/table", tags=["Tables"])
app.include_router(profile_router.router, prefix="/api/profile", tags=["Profiles"])

