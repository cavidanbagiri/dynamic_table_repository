
import re

import pandas as pd

import time

from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.sql import text

from db.setup import SessionLocal


class CreateTableRepository:

    def __init__(self, db):
        self.db = db

    async def create_table(self, file: UploadFile, company_name: str, table_name: str = None):

        async with SessionLocal() as session:

            company_name, table_name = company_name.strip(), table_name.strip()

            # 1 - Check Table Name and create
            if not table_name and not company_name:
                raise HTTPException(status_code=400, detail="Company and Table name are required.")
                # Validate that names are alphanumeric and can include underscores
            if not self._is_valid_name(company_name) or not self._is_valid_name(table_name):
                raise HTTPException(status_code=400,
                                    detail="Company and Table name must be alphanumeric and can include underscores.")

            combine_table_name = f"{company_name.strip()}_{table_name.strip()}"

            # Check if table already exists
            query = f"SELECT * FROM information_schema.tables WHERE table_name = '{combine_table_name}'"
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
                else:  # Assuming it's an Excel file
                    df = pd.read_excel(file.file)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")

            # 4 - Get All Columns
            df.columns = df.columns.str.replace(r'[ ./\\-]', '_', regex=True)
            # df.columns = df.columns.str.replace("'", "''")  # Escape single quotes
            # columns = df.columns.tolist()

            columns = [column.strip() for column in df.columns]
            # 5 - Validate Column Names
            self._validate_column_names(columns)

            # 6 - Create Table
            try:
                await self._create_table_and_columns(session, combine_table_name, columns)
                await session.commit()  # Commit after creating the table
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error creating table: {str(e)}")

            # 7 - Insert Table
            try:
                await self._insert_to_table(session, combine_table_name, df)
                # await session.commit()  # Commit after inserting data
            except Exception as e:
                print(f'..............>>>>>>>>>>>>>>>>>>{str(e)}')
                raise HTTPException(status_code=500, detail=f"Error inserting data: {str(e)}")
            await session.commit()
            return {'message': 'Table created successfully'}

    async def _create_table_and_columns(self, session: AsyncSession, table_name: str, columns: list):
        query = f"CREATE TABLE {table_name} (id SERIAL PRIMARY KEY, "
        query += ", ".join([f"{column} VARCHAR(255) NULL" for column in columns]) + ")"
        await session.execute(text(query))

    async def _insert_to_table(self, session, table_name, data):

        start_time = time.time()  # Record the start time

        query = f"INSERT INTO {table_name} ("
        for column in data.columns:
            query += f"{column}, "
        query = query[:-2] + ") VALUES "
        for index, row in data.iterrows():
            if index <= 2500:
                continue
            elif index >= 2695 and index <= 2695:
                query += "("
                for column in data.columns:
                    query += f"'{str(row[column]).replace("'", "''").strip()}', "
                query = query[:-2] + "), "
        query = query[:-2]
        print(f'query is : \n{query}\n')
        await session.execute(text(query))
        end_time = time.time()  # Record the end time
        duration = end_time - start_time  # Calculate the duration
        print(f"Insertion operation took {duration:.4f} seconds")  # Print the duration


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