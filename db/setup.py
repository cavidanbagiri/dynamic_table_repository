
import os

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

class Base(DeclarativeBase):
    pass


connection_string = os.getenv('DEV_DATABASE_URL')

engine = create_async_engine(connection_string, echo=True)

SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def get_db():
    async with engine.connect() as conn:
        yield conn