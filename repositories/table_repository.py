import asyncio
import re
import pandas as pd

from fastapi import UploadFile, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import text
from sqlalchemy import select

from db.setup import SessionLocal

from models.main_models import UserTable, TableDefinition

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
            try:
                # 1 - Check if table exists and get table id with table name
                table = await session.execute(
                    select(TableDefinition.id).where(TableDefinition.table_name == table_name))
                table_id = table.scalar()
                if not table_id:
                    raise HTTPException(status_code=404, detail="Table not found")

                # 2 - Check if user is associated with the table
                query = text("SELECT * FROM user_tables WHERE user_id = :user_id AND table_id = :table_id")
                result = await session.execute(query, {"user_id": user_id, "table_id": table_id})
                user_table = result.fetchone()
                if not user_table:
                    raise HTTPException(status_code=404, detail="User is not associated with this table")

                # 3 - Fetch data from the specified table
                query = text(f"SELECT * FROM {table_name}")
                result = await session.execute(query)
                data = result.mappings().fetchall()
                return data
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error fetching data: {str(e)}")