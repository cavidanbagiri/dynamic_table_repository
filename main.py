
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


import logging

# Set up logging
logging.basicConfig(level=logging.WARNING,
                    datefmt='%Y-%m-%d %H:%M:%S',
                    format='----------[%(asctime)s.%(msecs)03d] - %(module)20s:%(lineno)d - %(levelname)s - %(message)s'
                    )


# Import .env
from dotenv import load_dotenv
load_dotenv()


# Import routers
from routers import table_router, user_router

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
