
import time
import re
from datetime import datetime

import pandas as pd

from typing import Optional, List

import sqlparse
from fastapi import UploadFile, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError
from sqlalchemy.sql import text
from sqlalchemy.orm import joinedload, aliased
from sqlalchemy import Table, Column, Integer, String, MetaData, select, and_, or_, Float, Date, delete, Boolean
from sqlalchemy.sql.ddl import CreateTable

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
                UserTableAlias = aliased(UserTable)

                # Execute the query
                data = await session.execute(
                    select(TableDefinition)
                    .options(
                        joinedload(TableDefinition.user_tables.of_type(UserTableAlias)).joinedload(UserTableAlias.user),
                        joinedload(TableDefinition.favorite_tables.of_type(FavoriteTablesAlias))
                    )
                    .where(
                        and_(
                            TableDefinition.table_status == "public",
                            or_(
                                and_(
                                    FavoriteTablesAlias.user_id != user_id,
                                    FavoriteTablesAlias.user_id == None
                                ),
                                UserTableAlias.user_id != user_id
                            )

                        )
                    )
                )

                result = data.unique().scalars().all()


                processed_result = []
                for table in result:
                    if not table.user_tables:
                        continue
                    table_info = {
                        "id": table.id,
                        "table_name": table.table_name.replace('_', ' ').title(),
                        "original_table_name": table.table_name,
                        "table_status": table.table_status,
                        "table_description": table.table_description,
                        "table_category": table.category,
                        "username": table.user_tables[0].user.username,
                        "email": table.user_tables[0].user.email,
                        "created_at": table.created_at
                    }
                    # Get column size
                    column_size_result = await session.execute(text(
                        f"SELECT COUNT(*) FROM information_schema.columns WHERE table_name = '{table_info['original_table_name']}'"))
                    table_info["column_size"] = column_size_result.scalar()  # Extract the scalar value

                    # Get row size
                    row_size_result = await session.execute(
                        text(f"SELECT COUNT(*) FROM {table_info['original_table_name']}"))
                    table_info["row_size"] = row_size_result.scalar()  # Extract the scalar value
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

                    if not table.user_tables:
                        continue

                    table_info = {
                        "id": table.id,
                        "table_name": table.table_name.replace('_', ' ').title(),
                        "original_table_name": table.table_name,
                        "table_status": table.table_status,
                        "table_description": table.table_description,
                        "table_category": table.category,
                        "username": table.user_tables[0].user.username,
                        "email": table.user_tables[0].user.email,
                        "created_at": table.created_at
                    }
                    # Get column size
                    column_size_result = await session.execute(text(
                        f"SELECT COUNT(*) FROM information_schema.columns WHERE table_name = '{table_info['original_table_name']}'"))
                    table_info["column_size"] = column_size_result.scalar()  # Extract the scalar value

                    # Get row size
                    row_size_result = await session.execute(
                        text(f"SELECT COUNT(*) FROM {table_info['original_table_name']}"))
                    table_info["row_size"] = row_size_result.scalar()  # Extract the scalar value

                    processed_result.append(table_info)
                return processed_result


# Fetch All My tables
class FetchMyTablesRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def fetch_my_tables(self, user_id: int):
        async with SessionLocal() as session:

            data = await session.execute(select(UserTable)
                .options(joinedload(UserTable.table_definition))
                .where(UserTable.user_id == user_id))


            result = data.mappings().all()

            result_list = []
            for i in result:
                table_name = i["UserTable"].table_definition.table_name
                result_list.append(
                    {
                        "table_name": table_name.replace('_', ' ').title(),
                        "original_table_name": table_name,
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


# Table Validation
class TableValidationRepository:

    @staticmethod
    def is_valid_name(name: str) -> bool:
        # Regular expression to check if the name is alphanumeric and can include underscores
        return bool(re.match(r'^[A-Za-z0-9_]+$', name))

    @staticmethod
    def validate_column_names(columns):
        reserved_keywords = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'FROM', 'WHERE', 'JOIN', 'CREATE', 'DROP', 'ALTER',
                             'TABLE'}

        for column in columns:
            # Check if the column name is alphanumeric or contains underscores
            if not re.match(r'^[A-Za-z0-9_çÇğĞıİöÖşŞüÜа-яА-ЯёЁ]+$', column):
                raise HTTPException(status_code=400,
                                    detail=f"Invalid column name: '{column}'. Column names must be alphanumeric and can include underscores.")

            # If the column name start with number, raise error
            if column[0].isdigit():
                raise HTTPException(status_code=400,
                                    detail=f"Invalid column name: '{column}'. Column names cannot start with a number.")

            # Check for reserved keywords
            if column.upper() in reserved_keywords:
                raise HTTPException(status_code=400,
                                    detail=f"Invalid column name: '{column}'. Column names cannot be SQL reserved keywords.")


# Create a new table
class CreateTableRepository (TableValidationRepository):

    def __init__(self, db):
        self.db = db

    async def create_table(self, user_id: int, file: UploadFile, table_status: str, table_description: str, table_name: str = None, table_category: str = None):

        async with SessionLocal() as session:

            # 0 - Check Table Name and company
            if not table_name:
                raise HTTPException(status_code=400, detail="Table name are required.")
            if not TableValidationRepository.is_valid_name(table_name):
                raise HTTPException(status_code=400, detail="Table name must be alphanumeric and can include underscores.")

            define_table_name = f"{table_name.strip().lower()}"
            table_category = f"{table_category.strip().lower()}"

            # 1 - Check if table already exists
            await self._check_table_already_exists(define_table_name, session)

            # 2 - Check Table is csv or xlsx
            if not file.filename.endswith(('.csv', '.xlsx')):
                raise HTTPException(status_code=400, detail="Invalid file type. Only .csv and .xlsx files are accepted.")

            # 3 - Read the file into a DataFrame
            df = self._read_the_file(file)

            # 4 - Get All Columns

            columns_alchemy = self._create_columns_according_to_datatypes(df)[0]
            columns_names = self._create_columns_according_to_datatypes(df)[1]

            # 5 - Validate Column Names
            TableValidationRepository.validate_column_names(columns_names)

            # 6 - Create TableDefinition and Table
            # 6.0 - Create TableDefinition
            try:
                table_id = await self._create_table_definition(table_status, table_description, define_table_name, table_category, session = session)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error creating table definition: {str(e)}")

            # 6.1 - Create Table
            try:
                await self._create_table_and_columns(session, define_table_name, columns_alchemy) # create table and columns
                await self.insert_row_by_row(session, define_table_name, df)
                await self._create_user_tables(user_id=user_id, table_id=table_id, session=session)
                await session.commit()
                return {'message': 'Table created successfully'}
            except Exception as e:
                await session.rollback()
                await self._delete_table_definition(table_id)
                raise HTTPException(status_code=500, detail=f"Error creating table: {str(e)}")


    async def _check_table_already_exists(self, define_table_name, session):

        query = f"SELECT * FROM information_schema.tables WHERE table_name = '{define_table_name}'"
        result = await session.execute(text(query))
        table_exists = result.fetchone()
        if table_exists:
            raise HTTPException(status_code=400, detail="Table already exists.")

    def _read_the_file(self, file):
        try:
            if file.filename.endswith('.csv'):
                with file.file as f:
                    df = pd.read_csv(f)
            else:
                with file.file as f:
                    df = pd.read_excel(f)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
        return df

    async def _create_table_definition(self, table_status, table_description, table_name, table_category, session: AsyncSession):
        table_definition = TableDefinition(table_name=table_name, table_status=table_status, table_description=table_description, category=table_category)
        session.add(table_definition)
        await session.commit()
        await session.refresh(table_definition)
        return table_definition.id

    async def _delete_table_definition(self, table_id):
        async with SessionLocal() as session:
            table_definition = await session.execute(select(TableDefinition).where(TableDefinition.id == table_id))
            table_definition = table_definition.scalars().first()
            await session.delete(table_definition)
            await session.commit()

    async def _create_table_and_columns(self, session: AsyncSession, table_name: str, columns_alchemy: list):
        metadata = MetaData()
        table = Table(
            table_name, metadata,
            Column('id', Integer, primary_key=True),
            *columns_alchemy
        )
        await session.execute(CreateTable(table))

    async def insert_row_by_row(self, session, table_name, data):

        for index, row in data.iterrows():
            row_data = row.to_dict()

            # Sanitize column names and convert values to the appropriate data type
            sanitized_row_data = {}
            for column_name, value in row_data.items():
                # Sanitize column name: replace special characters with underscores
                sanitized_column_name = re.sub(r'[^a-zA-Z0-9_]', '_', column_name.strip())

                if pd.isna(value):
                    sanitized_row_data[sanitized_column_name] = None  # Handle NULL values
                else:
                    # Determine the column type from the DataFrame's dtypes
                    dtype = data[column_name].dtype
                    if pd.api.types.is_integer_dtype(dtype):
                        sanitized_row_data[sanitized_column_name] = int(value)
                    elif pd.api.types.is_float_dtype(dtype):
                        sanitized_row_data[sanitized_column_name] = float(value)
                    elif pd.api.types.is_datetime64_any_dtype(dtype):
                        sanitized_row_data[sanitized_column_name] = pd.to_datetime(value).to_pydatetime()
                    else:
                        sanitized_row_data[sanitized_column_name] = str(value)  # Default to string

            # Create the insert query
            columns = ', '.join(sanitized_row_data.keys())
            placeholders = ', '.join([f":{key}" for key in sanitized_row_data.keys()])
            query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

            # Execute the insert query
            try:
                await session.execute(text(query), sanitized_row_data)
            except SQLAlchemyError as e:
                raise HTTPException(status_code=500, detail=f"Error inserting row {index + 1}: {str(e)}")

    async def _create_user_tables(self, user_id, table_id: int, session: AsyncSession):
        data = UserTable(user_id=user_id, table_id=table_id)
        session.add(data)

    def _create_columns_according_to_datatypes(self, df):
        inner_columns = []
        column_names = []

        for column_name, dtype in df.dtypes.items():
            # Clean the column name
            temp_name = column_name
            column_name = column_name.strip().replace(' ', '_').replace('.', '_').replace('/', '_').replace('\\','_').replace('-', '_')

            if not self.is_valid_name(column_name):
                raise HTTPException(status_code=400,
                                    detail=f"Invalid column name: '{temp_name}->{column_name}'. Column names must be alphanumeric and can include underscores.")
            column_name = column_name.lower()
            if pd.api.types.is_integer_dtype(dtype):
                inner_columns.append(Column(column_name, Integer))
            elif pd.api.types.is_float_dtype(dtype):
                inner_columns.append(Column(column_name, Float))
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                inner_columns.append(Column(column_name, Date))
            else:
                inner_columns.append(Column(column_name, String))  # Default to String

            column_names.append(column_name)
        return [inner_columns, column_names]


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

        # Start building the base query
        base_query = f"""
        SELECT *, COUNT(*) OVER() AS total_rows
        FROM {table_name}
        WHERE 1=1
        """
        filters = []
        filter_values = {}

        # Build the filter conditions
        for key, value in params.items():
            filters.append(f"{key}::text ILIKE :{key}")  # Cast to text and use ILIKE
            filter_values[key] = f"%{value}%"  # Add value to filter_values

        # Add filters to the query if any
        if filters:
            base_query += " AND " + " AND ".join(filters)

        # Add LIMIT to the query
        base_query += " LIMIT 100;"


        # Execute the query with parameters
        result = await self.db.execute(text(base_query), filter_values)
        data = result.mappings().fetchall()

        # Fetch column names
        headers = await self.fetch_columns(table_name)

        # Calculate execution time
        execution_time = time.time() - start_time

        # Extract total_rows from the first row (if data exists)
        total_rows = data[0]["total_rows"] if data else 0

        # Return the results
        return {
            "data": data,  # Limited to 100 results by the query
            "total_rows": total_rows,  # Total rows matching the query
            "execution_time": round(execution_time, 4),  # Execution time rounded to 4 decimal places
            "headers": headers  # Column headers
        }

    async def fetch_columns(self, table_name: str, schema: str = 'public') -> List[str]:
        """
        Fetch column names for a given table.
        """
        query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name AND table_schema = :schema;
        """
        result = await self.db.execute(text(query), {"table_name": table_name, "schema": schema})
        columns = [row[0] for row in result.fetchall()]  # Fetch all column names
        return columns


# Delete table from database
class DeleteTableRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def delete_table(self, table_name: str, user_id: int):
        async with SessionLocal() as session:
            try:
                # Validate table name
                if not self.is_valid_table_name(table_name):
                    raise HTTPException(status_code=400, detail="Invalid table name.")

                # 1 - Check if table exists and get table id with table name
                table = await session.scalar(select(TableDefinition).where(TableDefinition.table_name == table_name))
                if not table:
                    raise HTTPException(status_code=404, detail="Table not found.")

                # 2 - Check if the user has permission to delete the table
                user_table = await session.scalar(
                    select(UserTable).where(
                        UserTable.user_id == user_id,
                        UserTable.table_id == table.id
                    )
                )
                if not user_table:
                    raise HTTPException(status_code=403, detail="You do not have permission to delete this table.")

                # 3 - Delete the table and associated records
                await session.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
                await session.execute(delete(UserTable).where(UserTable.table_id == table.id))
                await session.execute(delete(TableDefinition).where(TableDefinition.id == table.id))
                await session.execute(delete(FavoriteTables).where(FavoriteTables.table_id == table.id))

                await session.commit()
                return {"message": "Table deleted successfully"}

            except HTTPException:
                raise HTTPException(status_code=403, detail="Can not delete table")

            except Exception as e:
                await session.rollback()
                raise HTTPException(status_code=500, detail=f"Error deleting table: {str(e)}")

    def is_valid_table_name(self, table_name: str) -> bool:
        # Validate table name (alphanumeric and underscores only)
        return bool(re.match(r'^[A-Za-z0-9_]+$', table_name))


# Search public table with keywords
class SearchPublicTableRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_public_table(self, search_keyword: str, user_id: int):
        try:
            # Parameterized query to prevent SQL injection
            query = text("""
                SELECT * FROM table_definitions
                LEFT JOIN user_tables ON table_definitions.id = user_tables.table_id
                LEFT JOIN users ON users.id = user_tables.user_id
                WHERE (table_name LIKE :search_keyword OR table_description LIKE :search_keyword OR category LIKE :search_keyword)
                AND table_status = 'public'
                AND user_tables.user_id != :user_id
            """)
            result = await self.db.execute(query, {"search_keyword": f"%{search_keyword}%", "user_id": user_id})
            data = result.mappings().all()

            # Process data using dictionary comprehension
            processed_data = [
                {
                    "id": item["id"],
                    "table_name": item["table_name"].replace('_', ' ').title(),
                    "original_table_name": item["table_name"],
                    "table_description": item["table_description"],
                    "table_status": item["table_status"],
                    "table_category": item["category"],
                    "created_at": item["created_at"],
                    "user_id": item["user_id"]
                }
                for item in data
            ]

            return processed_data

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error searching public table: {str(e)}")


# Create table from ready components
class CreateTableFromReadyComponentsRepository (TableValidationRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_table_from_components(self, table_data, user_id: int):

        async with SessionLocal() as session:

            try:

                # 1 - Validate table data
                if not table_data.tableName:
                    raise HTTPException(status_code=400, detail="Table name is required")
                # 1.1 - Validate table name
                if not TableValidationRepository.is_valid_name(table_data.tableName):
                    raise HTTPException(status_code=400, detail="Table name must be alphanumeric and can include underscores.")

                # 1.1 - Validate columns
                if not table_data.columns:
                    raise HTTPException(status_code=400, detail="At least one column is required")

                # 1.2 - Validate column names
                cols = []
                for column in table_data.columns:
                    cols.append(column.name)
                TableValidationRepository.validate_column_names(cols)

                # 2 - Check if the table already exists
                table = await session.scalar(select(TableDefinition).where(TableDefinition.table_name == table_data.tableName))
                if table:
                    raise HTTPException(status_code=400, detail="Table with the same name already exists.")



                # 3 - Create the table
                table_definition = TableDefinition(
                    table_name=table_data.tableName,
                    table_description=table_data.description,
                    table_status=table_data.tableStatus,
                    category=table_data.category,
                )
                session.add(table_definition)
                await session.commit()  # Commit to generate the ID
                await session.refresh(table_definition)
                table_id = table_definition.id

                # 4 - Create the table columns

                type_mapping = {
                    "string": String,
                    "integer": Integer,
                    "boolean": Boolean,
                    "date": Date,
                    "float": Float
                }

                # Create table columns dynamically
                columns = [
                    Column("id", Integer, primary_key=True, autoincrement=True)
                ]
                for col in table_data.columns:
                    if col.type not in type_mapping:
                        raise HTTPException(status_code=400, detail=f"Invalid column type: {col.type}")
                    columns.append(Column(col.name, type_mapping[col.type]))

                # Create the table
                metadata = MetaData()
                table = Table(table_data.tableName, metadata, *columns)
                await session.execute(CreateTable(table))

                # 5 - Create the user table
                user_table = UserTable(
                    table_id=table_id,
                    user_id=user_id
                )
                session.add(user_table)
                await session.commit()

                return {"message": f"Table '{table_data.tableName}' created successfully"}

            except Exception as e:
                await session.rollback()
                raise HTTPException(status_code=500, detail=f"Error creating table: {str(e)}")


# Execute SQL Query
class ExecuteQueryRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_query(self, query: str) -> object:
        try:
            # Validate the SQL query
            if not self.is_valid_sql(query):
                raise HTTPException(status_code=400, detail="Invalid SQL query")

            # Check if the query attempts to access restricted tables
            if self.contains_restricted_tables(query):
                raise HTTPException(status_code=403, detail="Access to restricted tables is not allowed")

            # Execute the query
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
        except ProgrammingError as e:
            error_message = str(e.orig).lower()
            if "does not exist" in error_message and "relation" in error_message:
                raise HTTPException(status_code=404, detail="Table not found: {}".format(str(e.orig)))
            elif "does not exist" in error_message and "column" in error_message:
                raise HTTPException(status_code=404, detail="Column not found: {}".format(str(e.orig)))
            else:
                raise HTTPException(status_code=500, detail=f"Error executing query: {str(e.orig)}")
        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error executing query: {str(e)}")

    def is_valid_sql(self, query: str) -> bool:
        try:
            parsed = sqlparse.parse(query)
            return len(parsed) > 0
        except Exception:
            return False

    def contains_restricted_tables(self, query: str) -> bool:
        """
        Check if the query contains references to restricted tables.
        """
        restricted_tables = {"user_tables", "alembic_version", "table_definitions", "users", "favorite_tables"}  # Add all restricted table names here

        # Parse the query
        parsed = sqlparse.parse(query)

        for statement in parsed:
            for i, token in enumerate(statement.tokens):
                # Check if the token is a keyword (e.g., FROM, JOIN, INTO, UPDATE)
                if token.is_keyword and token.value.upper() in {"FROM", "JOIN", "INTO", "UPDATE"}:
                    # Iterate through the next tokens to find the table name
                    j = i + 1
                    while j < len(statement.tokens):
                        next_token = statement.tokens[j]

                        # Skip whitespace and other irrelevant tokens
                        if next_token.is_whitespace or next_token.value in {',', '(', ')'}:
                            j += 1
                            continue

                        # Extract the table name from the token
                        table_name = next_token.value.strip().split()[0].strip("`\"'[]")  # Handle quoted table names

                        if table_name.lower() in restricted_tables:
                            return True
                        break  # Exit after processing the first non-whitespace token

        return False

