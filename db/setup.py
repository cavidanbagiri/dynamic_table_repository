
import os
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

class Base(DeclarativeBase):
    pass

# Ensure the environment variable is set
connection_string = os.getenv('DEV_DATABASE_URL')
if not connection_string:
    raise ValueError("DEV_DATABASE_URL environment variable is not set")

# Create the async engine with connection pooling
engine = create_async_engine(
    connection_string,
    echo=True,  # Disable in production
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
)

# Create the async session factory
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get a database session
async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()



# import os
#
# from sqlalchemy.orm import DeclarativeBase
# from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
#
#
# class Base(DeclarativeBase):
#     pass
#
#
# connection_string = os.getenv('DEV_DATABASE_URL')
#
# engine = create_async_engine(connection_string, echo=True)
#
# SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
#
# async def get_db():
#     async with SessionLocal() as session:  # Create an AsyncSession
#         yield session  # Yield the session