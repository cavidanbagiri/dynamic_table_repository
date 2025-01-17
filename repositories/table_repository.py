import time
import asyncio
import re
import pandas as pd

from typing import Optional, List

import sqlparse
from fastapi import UploadFile, HTTPException
from pandas.io.sql import execute

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import text
from sqlalchemy import select, and_, or_, MetaData, Table
from sqlalchemy.orm import joinedload, aliased, selectinload

from db.setup import SessionLocal

from models.main_models import UserTable, TableDefinition, FavoriteTables


# Fetch all public tables
class FetchPublicTablesRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def fetch_public_tables(self, user_id: Optional[int] = None):
        async with SessionLocal() as session:

            if user_id:
                FavoriteTablesAlias = aliased(FavoriteTables)

                # Execute the query
                data = await session.execute(
                    select(TableDefinition)
                    .options(
                        joinedload(TableDefinition.user_tables).joinedload(UserTable.user),
                        joinedload(TableDefinition.favorite_tables.of_type(FavoriteTablesAlias))
                    )
                    .where(
                        and_(
                            TableDefinition.table_status == "public",
                            or_(
                                FavoriteTablesAlias.user_id != user_id,
                                FavoriteTablesAlias.user_id == None
                            )
                        )
                    )
                )

                result = data.unique().scalars().all()
                processed_result = []
                for table in result:
                    table_info = {
                        "id": table.id,
                        "table_name": table.table_name.replace('_', ' ').title(),
                        "original_table_name": table.table_name,
                        "table_status": table.table_status,
                        "table_description": table.table_description,
                        "username": table.user_tables[0].user.username,
                        "email": table.user_tables[0].user.email,
                        "created_at": table.created_at
                    }
                    processed_result.append(table_info)
                return processed_result

            else:
                data = await session.execute(
                    select(TableDefinition)
                    .options(joinedload(TableDefinition.user_tables).joinedload(UserTable.user))
                    .where(TableDefinition.table_status == "public")
                )
                result = data.unique().scalars().all()
                processed_result = []
                for table in result:
                    table_info = {
                        "id": table.id,
                        "table_name": table.table_name.replace('_', ' ').title(),
                        "original_table_name": table.table_name,
                        "table_status": table.table_status,
                        "table_description": table.table_description,
                        "username": table.user_tables[0].user.username,
                        "email": table.user_tables[0].user.email,
                        "created_at": table.created_at
                    }
                    processed_result.append(table_info)
                return processed_result


# Fetch All My tables
class FetchMyTablesRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # async def fetch_my_tables(self, user_id: int):
    #     async with SessionLocal() as session:
    #
    #         data = await session.execute(
    #             select(TableDefinition.table_name, TableDefinition.id, TableDefinition.table_status)
    #             .options(joinedload(TableDefinition.user_tables).joinedload(UserTable.user))
    #             .where(UserTable.user_id == user_id)
    #         )
    #         print('data is........................................................................................................................', data)
    #
    #         result = data.unique().scalars().all()
    #         print(f'result is............ {result}')
    #         return result

    async def fetch_my_tables(self, user_id: int):
        async with SessionLocal() as session:

            query = (
                select(TableDefinition.id, TableDefinition.table_name, TableDefinition.table_status)
                .where(UserTable.user_id == user_id)
            )

            data = await session.execute(query)
            result = data.unique().mappings().all()

            result_list = []
            for i in result:
                result_list.append(
                    {
                        "id": i["id"],
                        "table_name": i["table_name"].replace('_', ' ').title(),
                        "original_table_name": i["table_name"],
                        "table_status": i["table_status"]
                    }
                )

            return result_list


# Add table to favorites
class FavoriteTableRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_favorite_table(self, table_id: int, user_id: int):
        async with SessionLocal() as session:
            # 1 - Check table already added or not
            already_added = await session.execute(
                select(FavoriteTables).where(
                    and_(
                        FavoriteTables.table_id == table_id,
                        FavoriteTables.user_id == user_id
                    )
                )
            )

            temp = already_added.scalars().all()

            if temp:
                raise HTTPException(status_code=400, detail="Table is already added to favorites.")

            favorite_table = FavoriteTables(table_id=table_id, user_id=user_id)
            session.add(favorite_table)
            await session.commit()

            # 2 - Get the table info
            data = await session.execute(
                select(TableDefinition)
                .options(joinedload(TableDefinition.user_tables).joinedload(UserTable.user))
                .where(TableDefinition.id == table_id)
            )
            result = data.unique().scalars().first()

            table_info = {
                "id": result.id,
                "table_name": result.table_name.replace('_', ' ').title(),
                "original_table_name": result.table_name,
                "table_status": result.table_status,
                "table_description": result.table_description,
                "username": result.user_tables[0].user.username,
                "email": result.user_tables[0].user.email,
            }

            return {
                "message": "Table added to favorites successfully",
                "data": table_info
            }

    async def delete_favorite_table(self, table_id: int, user_id: int):
        async with SessionLocal() as session:  # Assuming SessionLocal is an async session
            # 1 - Check if the table is already added or not
            result = await session.execute(
                select(FavoriteTables).where(
                    FavoriteTables.table_id == table_id,
                    FavoriteTables.user_id == user_id
                )
            )
            favorite_table = result.scalars().first()  # Get the first result

            if not favorite_table:
                raise HTTPException(status_code=400, detail="Table is not added to favorites.")

            await session.delete(favorite_table)  # Delete the favorite table
            await session.commit()  # Commit the transaction

            return {
                "message": "Table deleted from favorites successfully",
                "id": table_id
            }

    async def fetch_favorite_tables(self, user_id: int):

        async with SessionLocal() as session:

            data = await session.execute(
                select(TableDefinition)
                .options(joinedload(TableDefinition.user_tables).joinedload(UserTable.user))
                .join(FavoriteTables, FavoriteTables.table_id == TableDefinition.id)
                .where(FavoriteTables.user_id == user_id)
            )
            result = data.unique().scalars().all()

            processed_result = []
            for table in result:
                table_info = {
                    "id": table.id,
                    "table_name": table.table_name.replace('_', ' ').title(),
                    "original_table_name": table.table_name,
                    "table_status": table.table_status,
                    "table_description": table.table_description,
                    "username": table.user_tables[0].user.username,
                    "email": table.user_tables[0].user.email,
                }
                processed_result.append(table_info)
            return processed_result


# Create a new table
class CreateTableRepository:

    def __init__(self, db):
        self.db = db

    async def create_table(self, user_id: int, file: UploadFile, table_status: str, table_description: str, table_name: str = None):

        async with SessionLocal() as session:

            # 0 - Check Table Name and company
            if not table_name:
                raise HTTPException(status_code=400, detail="Table name are required.")
            if not self._is_valid_name(table_name):
                raise HTTPException(status_code=400,
                                    detail="Table name must be alphanumeric and can include underscores.")

            define_table_name = f"{table_name.strip().lower()}"

            # 1 - Check if table already exists
            query = f"SELECT * FROM information_schema.tables WHERE table_name = '{define_table_name}'"
            result = await session.execute(text(query))
            table_exists = result.fetchone()
            if table_exists:
                raise HTTPException(status_code=400, detail="Table already exists.")

            # 2 - Check Table is csv or xlsx
            if not file.filename.endswith(('.csv', '.xlsx')):
                raise HTTPException(status_code=400, detail="Invalid file type. Only .csv and .xlsx files are accepted.")

            # 3 - Read the file into a DataFrame
            try:
                if file.filename.endswith('.csv'):
                    df = pd.read_csv(file.file)
                else:
                    df = pd.read_excel(file.file)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")

            # 4 - Get All Columns
            df.columns = df.columns.str.strip().str.replace(r'[ ./\\-]', '_', regex=True)
            columns = [column.strip() for column in df.columns]

            # 5 - Validate Column Names
            self._validate_column_names(columns)

            # 6 - Create TableDefinition and Table
            # 6.0 - Create TableDefinition
            try:
                table_id = await self._create_table_definition(table_status, table_description, define_table_name, session)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error creating table definition: {str(e)}")

            # 6.1 - Create Table
            try:
                await self._create_table_and_columns(session, define_table_name, columns)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error creating table: {str(e)}")

            # 7 - Insert Table
            try:
                await self.insert_row_by_row(session, define_table_name, df)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error inserting data: {str(e)}")

            # 8 - Create User Table
            try:
                await self._create_user_tables(user_id=user_id, table_id=table_id, session=session)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error creating user table: {str(e)}")


            await session.commit()
            return {'message': 'Table created successfully'}

    async def _create_table_and_columns(self, session: AsyncSession, table_name: str, columns: list):
        query = f"CREATE TABLE {table_name} (id SERIAL PRIMARY KEY, "
        query += ", ".join([f"{column} TEXT NULL" for column in columns]) + ")"
        await session.execute(text(query))

    async def _create_table_definition(self, table_status, table_description, table_name, session: AsyncSession):
        table_definition = TableDefinition(table_name=table_name, table_status=table_status, table_description=table_description)
        session.add(table_definition)
        await session.commit()
        await session.refresh(table_definition)
        return table_definition.id

    async def insert_row_by_row(self, session, table_name, data):

        for index, row in data.iterrows():

            # Convert the row to a dictionary
            row_data = row.to_dict()

            # Convert all values to strings
            row_data = {key: str(value) for key, value in row_data.items()}

            # Create an insert query
            columns = ', '.join(row_data.keys())
            placeholders = ', '.join([f":{key}" for key in row_data.keys()])
            query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

            # Execute the insert query
            try:
                await session.execute(text(query), row_data)
            except SQLAlchemyError as e:
                print(f"Error inserting row {index + 1}: {str(e)}")

    async def _create_user_tables(self, user_id, table_id: int, session: AsyncSession):
        data = UserTable(user_id=user_id, table_id=table_id)
        session.add(data)

    def _validate_column_names(self, columns):
        reserved_keywords = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'FROM', 'WHERE', 'JOIN', 'CREATE', 'DROP', 'ALTER',
                             'TABLE'}

        for column in columns:
            # Check if the column name is alphanumeric or contains underscores
            if not re.match(r'^[A-Za-z0-9_çÇğĞıİöÖşŞüÜа-яА-ЯёЁ]+$', column):
                raise HTTPException(status_code=400,
                                    detail=f"Invalid column name: '{column}'. Column names must be alphanumeric and can include underscores.")

            # Check for reserved keywords
            if column.upper() in reserved_keywords:
                raise HTTPException(status_code=400,
                                    detail=f"Invalid column name: '{column}'. Column names cannot be SQL reserved keywords.")

    def _is_valid_name(self, name: str) -> bool:
        # Regular expression to check if the name is alphanumeric and can include underscores
        return bool(re.match(r'^[A-Za-z0-9_]+$', name))


# Fetch data from table
class FetchTableRepository:

    def __init__(self, db: AsyncSession):
        self.db = db


    async def fetch_table(self, user_id: int, table_name: str):
        async with SessionLocal() as session:  # Ensure SessionLocal is an async session
            start_time = time.time()
            try:
                # 1 - Check if table exists and get table id with table name
                table = await session.execute(
                    select(TableDefinition).where(TableDefinition.table_name == table_name))

                founded_table = table.scalars().first()

                # 2 - Check if table not available, raise error
                if not founded_table:
                    raise HTTPException(status_code=404, detail="Table not found")

                # 3 - Check if table is public
                if founded_table and founded_table.table_status == 'public':
                    query = text(f"SELECT * FROM {table_name}")
                    result = await session.execute(query)
                    data = result.mappings().fetchall()

                    row_size = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    column_size = await session.execute(text(f"SELECT COUNT(*) FROM information_schema.columns WHERE table_name = '{table_name}'"))
                    table_size = await session.execute(text(f"SELECT pg_size_pretty(pg_total_relation_size('{table_name}'))"))

                    # Fetching column names
                    headers = await self.fetch_columns(table_name)


                    execution_time = time.time() - start_time

                    return {
                        "data": data[:100],
                        "total_rows": row_size.scalar(),
                        "total_columns": column_size.scalar(),
                        "table_size": table_size.scalar(),
                        "original_table_name": table_name,
                        "execution_time": execution_time.__round__(4),
                        "headers": headers
                    }
                else:
                    # 4 - Check if user is associated with the table
                    query = text("SELECT * FROM user_tables WHERE user_id = :user_id AND table_id = :table_id")
                    result = await session.execute(query, {"user_id": user_id, "table_id": founded_table.id})
                    user_table = result.fetchone()
                    if not user_table:
                        raise HTTPException(status_code=404, detail="User is not associated with this table")

                    # 5 - Fetch data from the specified table
                    query = text(f"SELECT * FROM {table_name}")
                    result = await session.execute(query)
                    data = result.mappings().fetchall()
                    row_size = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                    column_size = await session.execute(text(f"SELECT COUNT(*) FROM information_schema.columns WHERE table_name = '{table_name}'"))
                    table_size = await session.execute(text(f"SELECT pg_size_pretty(pg_total_relation_size('{table_name}'))"))

                    # Fetching column names
                    headers = await self.fetch_columns(table_name)

                    execution_time = time.time() - start_time

                    return {
                        "data": data[:100],
                        "total_rows": row_size.scalar(),
                        "total_columns": column_size.scalar(),
                        "table_size": table_size.scalar(),
                        "original_table_name": table_name,
                        "execution_time": execution_time.__round__(4),
                        "headers": headers
                    }

            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error fetching data: {str(e)}")

    async def fetch_columns(self, table_name: str, schema: str = 'public') -> List[str]:
        query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name AND table_schema = :schema;
        """
        result = await self.db.execute(text(query), {"table_name": table_name, "schema": schema})
        columns = [row[0] for row in result.fetchall()]  # Fetch all column names
        return columns


# Fetch data from table with header query
class FetchTableWithHeaderFilterRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def fetch_table_with_header(self, user_id: int, table_name: str, params: dict):
        start_time = time.time()
        # Start building the query
        query = f"SELECT * FROM {table_name} WHERE 1=1"
        filters = []
        values = []

        # Build the filter conditions
        for key, value in params.items():
            filters.append(f"{key} ILIKE :{key}")
            values.append((key, f"%{value}%"))

        # Add filters to the query if any
        if filters:
            query += " AND " + " AND ".join(filters)

        # Execute the query with parameters
        data = await self.db.execute(text(query), dict(values))

        # Fetch the results
        temp = data.mappings().fetchall()

        # Fetching column names
        headers = await self.fetch_columns(table_name)


        execution_time = time.time() - start_time

        # Return the results
        return {
            "data": temp[:100],  # Limit to 100 results
            "total_rows": len(temp),  # Total rows fetched
            "execution_time": execution_time.__round__(4),  # Execution time
            "headers": headers
        }

    async def fetch_columns(self, table_name: str, schema: str = 'public') -> List[str]:
        query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name AND table_schema = :schema;
        """
        result = await self.db.execute(text(query), {"table_name": table_name, "schema": schema})
        columns = [row[0] for row in result.fetchall()]  # Fetch all column names
        return columns


# Execute SQL Query in database
class ExecuteQueryRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_query(self, query: str) -> object:
        try:

            if not self.is_valid_sql(query):
                raise HTTPException(status_code=400, detail="Invalid SQL query")

            start_time = time.time()
            result = await self.db.execute(text(query))

            # Check if the result has any rows
            if result.rowcount == 0:
                return []  # Return an empty list if no rows are found

            # Use mappings to get all columns
            temp = result.mappings().all()

            headers = []
            for key in temp[0].keys():
                headers.append(key)

            execution_time = time.time() - start_time
            return {
                "data": temp[:100],  # Limit to 100 results
                "total_rows": len(temp),  # Total rows fetched
                "execution_time": execution_time.__round__(4),
                "headers": headers
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error executing query: {str(e)}")

    def is_valid_sql(self, query: str) -> bool:
        try:
            parsed = sqlparse.parse(query)
            return len(parsed) > 0
        except HTTPException as e:
            return False