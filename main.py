
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app.include_router(user_router.router, prefix="/api/user")
app.include_router(table_router.router, prefix="/api/table")
app.include_router(profile_router.router, prefix="/api/profile")
