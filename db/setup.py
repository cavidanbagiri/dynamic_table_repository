
import os

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

class Base(DeclarativeBase):
    pass


# connection_string = f"postgresql+asyncpg://{os.getenv('DEV_DATABASE_USER')}:{os.getenv('DEV_DATABASE_PASSWORD')}@{os.getenv('DEV_DATABASE_HOST')}:5432/{os.getenv('DEV_DATABASE_NAME')}"

connection_string = "postgresql+asyncpg://postgres:Initial_123@localhost/dynamic_db"

engine = create_async_engine(connection_string, echo=True)

SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def get_db():
    async with engine.connect() as conn:
        yield conn