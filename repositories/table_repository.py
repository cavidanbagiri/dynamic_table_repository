
import time
import re
import sys
from abc import abstractmethod

import pandas as pd

from typing import Optional, Dict

import sqlparse
from fastapi import UploadFile, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError
from sqlalchemy.sql import text
from sqlalchemy.orm import joinedload, aliased
from sqlalchemy import Table, Column, Integer, String, MetaData, select, and_, or_, Float, Date, delete, Boolean, \
    exists
from sqlalchemy.sql.ddl import CreateTable
from typing import List, Tuple

from db.setup import SessionLocal

from models.main_models import UserTable, TableDefinition, FavoriteTables

import logging


# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Log to terminal
    ]
)


# For simplifying SQL error messages
class SimplifyErrorMessageRepository:

    @staticmethod
    def simplify_sql_error_message(error_message: str) -> str:
        """
        Simplify SQL error messages by extracting the relevant parts.
        Returns a formatted error message in the format: <error_description> [SQL: <sql_query>]
        """
        # Extract the error description (between the first colon and "[SQL:")
        if ": " in error_message and "[SQL:" in error_message:
            error_description = error_message.split(": ")[1].split("[SQL:")[0].strip()
            sql_query = error_message.split("[SQL:")[1].split("]")[0].strip()
            return f"{error_description} [SQL: {sql_query}]"

        # Fallback: Return the original error message if parsing fails
        return error_message



# Fetch Public Tables - Checked + Optimized
class FetchPublicTablesRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def fetch_public_tables(self, user_id: Optional[int] = None):
        try:
            data = await self._get_data(user_id)
            result = await self._return_data(data)
            logging.info(f"Fetched public tables successfully.")
            return result
        except Exception as e:
            logging.error(f"Error fetching public tables: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch public tables.")

    async def _get_data(self, user_id: Optional[int] = None):
        try:
            FavoriteTablesAlias = aliased(FavoriteTables)
            UserTableAlias = aliased(UserTable)

            query = (
                select(TableDefinition)
                .options(
                    joinedload(TableDefinition.user_tables.of_type(UserTableAlias)).joinedload(UserTableAlias.user),
                    joinedload(TableDefinition.favorite_tables.of_type(FavoriteTablesAlias))
                )
                .where(TableDefinition.table_status == "public")
            )

            if user_id:
                query = query.where(
                    or_(
                        and_(
                            FavoriteTablesAlias.user_id != user_id,
                            FavoriteTablesAlias.user_id == None
                        ),
                        UserTableAlias.user_id != user_id
                    )
                )

            data = await self.db.execute(query)
            result = data.unique().scalars().all()
            logging.info(f"Retrieved {len(result)} public tables from database.")
            return result
        except Exception as e:
            logging.error(f"Error retrieving public tables data: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to retrieve public tables data.")

    async def _return_data(self, result):
        try:
            processed_result = []
            for table in result:
                if not table.user_tables:
                    logging.warning(f"Skipping table {table.id} due to missing user_tables.")
                    continue

                try:
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

                    table_info_func = await self._fetch_table_info(table_info["original_table_name"])
                    table_info["column_size"] = table_info_func["column_size"]
                    table_info["row_size"] = table_info_func["row_size"]

                    processed_result.append(table_info)
                except IndexError:
                    logging.warning(f"Skipping table {table.id} due to missing user_tables.")
                except Exception as e:
                    logging.error(f"Error processing table {table.id}: {str(e)}")

            logging.info(f"Processed {len(processed_result)} tables for return.")
            return processed_result
        except Exception as e:
            logging.error(f"Error processing tables for return: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to process tables for return.")

    async def _fetch_table_info(self, table_name: str) -> dict:
        try:
            logging.info(f"Fetching metadata for table: {table_name}")

            # Validate the table name
            if not re.match(r'^[a-zA-Z0-9_]+$', table_name):
                raise HTTPException(status_code=400, detail="Invalid table name.")

            # Check if the table exists in the database
            table_exists_query = text("""
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_name = :table_name
                )
            """)
            table_exists_result = await self.db.execute(table_exists_query, {"table_name": table_name})
            if not table_exists_result.scalar():
                raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found.")

            # Fetch column size (parameterized query)
            column_query = text("""
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_name = :table_name
            """)
            column_size_result = await self.db.execute(column_query, {"table_name": table_name})

            # Fetch row size (safe dynamic query with validated table name)
            row_query = text(f"SELECT COUNT(*) FROM {table_name}")
            row_size_result = await self.db.execute(row_query)

            logging.info(f"Fetched metadata for table {table_name} successfully.")
            return {
                "column_size": column_size_result.scalar(),
                "row_size": row_size_result.scalar()
            }
        except HTTPException:
            raise  # Re-raise HTTPException
        except ProgrammingError as e:
            logging.error(f"Database error fetching table metadata: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        except Exception as e:
            logging.error(f"Error fetching table metadata: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error fetching table metadata: {str(e)}")



# Fetch My Tables - Checked + Optimized
class FetchMyTablesRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def fetch_my_tables(self, user_id: int) -> List[Dict]:
        try:
            # Validate input
            if not isinstance(user_id, int):
                raise ValueError("user_id must be an integer")

            logging.info(f"Fetching tables for user_id: {user_id}")

            # Execute the query
            data = await self.db.execute(
                select(UserTable)
                .options(joinedload(UserTable.table_definition))
                .where(UserTable.user_id == user_id)
                .order_by(UserTable.created_at.desc())  # Optional: Sort by creation date
            )

            # Process the result
            result = data.unique().mappings().all()
            result_list = []

            for row in result:
                if not row["UserTable"].table_definition:
                    logging.warning(f"Missing table definition for user_id: {user_id}")
                    continue

                table_name = row["UserTable"].table_definition.table_name
                result_list.append(
                    {
                        "table_name": table_name.replace('_', ' ').title(),
                        "original_table_name": table_name,
                    }
                )

            return result_list
        except Exception as e:
            logging.error(f"Error fetching tables for user_id {user_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")



# Work With favorite tables - Checked + Optimized
class FavoriteTableRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_favorite_table(self, table_id: int, user_id: int) -> Dict:
        try:
            # Validate input
            if not isinstance(table_id, int) or not isinstance(user_id, int):
                raise ValueError("table_id and user_id must be integers")

            logging.info(f"Adding table_id {table_id} to favorites for user_id {user_id}")

            # Check if the table is already added
            already_added = await self.db.execute(
                select(exists().where(
                    FavoriteTables.table_id == table_id,
                    FavoriteTables.user_id == user_id
                ))
            )
            if already_added.scalar():
                raise HTTPException(status_code=400, detail="Table is already added to favorites.")

            # Add the favorite table
            favorite_table = FavoriteTables(table_id=table_id, user_id=user_id)
            self.db.add(favorite_table)
            await self.db.commit()

            # Get the table info
            data = await self.db.execute(
                select(TableDefinition)
                .options(joinedload(TableDefinition.user_tables).joinedload(UserTable.user))
                .where(TableDefinition.id == table_id)
            )
            result = data.unique().scalars().first()

            if not result or not result.user_tables or not result.user_tables[0].user:
                logging.warning(f"Missing table or user information for table_id: {table_id}")
                raise HTTPException(status_code=404, detail="Table not found.")

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
        except Exception as e:
            logging.error(f"Error adding table to favorites: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def delete_favorite_table(self, table_id: int, user_id: int) -> Dict:
        try:
            # Validate input
            if not isinstance(table_id, int) or not isinstance(user_id, int):
                raise ValueError("table_id and user_id must be integers")

            logging.info(f"Deleting table_id {table_id} from favorites for user_id {user_id}")

            # Check if the table is already added
            result = await self.db.execute(
                select(FavoriteTables).where(
                    FavoriteTables.table_id == table_id,
                    FavoriteTables.user_id == user_id
                )
            )
            favorite_table = result.scalars().first()

            if not favorite_table:
                raise HTTPException(status_code=400, detail="Table is not added to favorites.")

            # Delete the favorite table
            await self.db.delete(favorite_table)
            await self.db.commit()

            return {
                "message": "Table deleted from favorites successfully",
                "id": table_id
            }
        except Exception as e:
            logging.error(f"Error deleting table from favorites: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def fetch_favorite_tables(self, user_id: int) -> List[Dict]:
        try:
            # Validate input
            if not isinstance(user_id, int):
                raise ValueError("user_id must be an integer")

            logging.info(f"Fetching favorite tables for user_id {user_id}")

            # Execute the query
            data = await self.db.execute(
                select(TableDefinition)
                .options(joinedload(TableDefinition.user_tables).joinedload(UserTable.user))
                .join(FavoriteTables, FavoriteTables.table_id == TableDefinition.id)
                .where(FavoriteTables.user_id == user_id)
                .order_by(TableDefinition.created_at.desc())  # Optional: Sort by creation date
            )

            # Ensure uniqueness of results
            result = data.unique().scalars().all()

            # Process the result
            processed_result = [
                {
                    "id": row.id,
                    "table_name": row.table_name.replace('_', ' ').title(),
                    "original_table_name": row.table_name,
                    "table_status": row.table_status,
                    "table_description": row.table_description,
                    "username": row.user_tables[0].user.username if row.user_tables and row.user_tables[
                        0].user else None,
                    "email": row.user_tables[0].user.email if row.user_tables and row.user_tables[0].user else None,
                }
                for row in result
                if row.user_tables and row.user_tables[0].user
            ]

            return processed_result
        except Exception as e:
            logging.error(f"Error fetching favorite tables: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")



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


# Delete table from database - Checked + Optimized
class DeleteTableRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def delete_table(self, table_name: str, user_id: int):
        try:
            # Validate table name
            if not self.is_valid_table_name(table_name):
                raise HTTPException(status_code=400, detail="Invalid table name.")

            table_name = table_name.strip().lower()

            # 1 - Check if table exists and get table id with table name
            table = await self.db.scalar(select(TableDefinition).where(TableDefinition.table_name == table_name))
            if not table:
                raise HTTPException(status_code=404, detail="Table not found.")

            # 2 - Check if the user has permission to delete the table
            user_table = await self.db.scalar(
                select(UserTable).where(
                    UserTable.user_id == user_id,
                    UserTable.table_id == table.id
                )
            )
            if not user_table:
                raise HTTPException(status_code=403, detail="You do not have permission to delete this table.")

            # 3 - Delete the table and associated records
            await self.db.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))  # Fixed here
            await self.db.execute(delete(UserTable).where(UserTable.table_id == table.id))
            await self.db.execute(delete(TableDefinition).where(TableDefinition.id == table.id))
            await self.db.execute(delete(FavoriteTables).where(FavoriteTables.table_id == table.id))
            await self.db.commit()
            return {"message": "Table deleted successfully"}

        except HTTPException:
            raise  # Re-raise HTTPException as is
        except SQLAlchemyError as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    def is_valid_table_name(self, table_name: str) -> bool:
        # Validate table name (alphanumeric and underscores only)
        return bool(re.match(r'^[A-Za-z0-9_]+$', table_name))



# Delete table from database - Checked + Optimized
class FetchTableRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def fetch_table(self, user_id: int, table_name: str):
        start_time = time.time()
        try:
            # 1 - Check if table exists and get table id with table name
            table = await self.db.execute(
                select(TableDefinition).where(TableDefinition.table_name == table_name))
            founded_table = table.scalars().first()

            # 2 - Check if table not available, raise error
            if not founded_table:
                raise HTTPException(status_code=404, detail="Table not found")

            # 3 - Check if table is public
            if founded_table.table_status == 'public':
                data, row_size, column_size, table_size, headers = await self.fetch_table_data(table_name)
            else:
                # 4 - Check if user is associated with the table
                query = text("SELECT * FROM user_tables WHERE user_id = :user_id AND table_id = :table_id")
                result = await self.db.execute(query, {"user_id": user_id, "table_id": founded_table.id})
                user_table = result.fetchone()
                if not user_table:
                    raise HTTPException(status_code=404, detail="User is not associated with this table")

                # 5 - Fetch data from the specified table
                data, row_size, column_size, table_size, headers = await self.fetch_table_data(table_name)

            execution_time = time.time() - start_time
            return {
                "data": data,
                "total_rows": row_size,
                "total_columns": column_size,
                "table_size": table_size,
                "original_table_name": table_name,
                "execution_time": execution_time.__round__(4),
                "headers": headers
            }

        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    async def fetch_table_data(self, table_name: str):
        """Helper method to fetch table data and metadata."""
        query = text(f"SELECT * FROM {table_name} LIMIT 100")
        result = await self.db.execute(query)
        data = result.mappings().fetchall()

        row_size = await self.db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        column_size = await self.db.execute(text(f"SELECT COUNT(*) FROM information_schema.columns WHERE table_name = '{table_name}'"))
        table_size = await self.db.execute(text(f"SELECT pg_size_pretty(pg_total_relation_size('{table_name}'))"))

        headers = await self.fetch_columns(table_name)
        return data, row_size.scalar(), column_size.scalar(), table_size.scalar(), headers

    async def fetch_columns(self, table_name: str, schema: str = 'public') -> List[str]:
        """Fetch column names for a given table."""
        query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name AND table_schema = :schema;
        """
        result = await self.db.execute(text(query), {"table_name": table_name, "schema": schema})
        return [row.column_name for row in result.fetchall()]



# Fetch data from table with header query - Checked + Optimized
class BaseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

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
        return [row.column_name for row in result.fetchall()]
class FetchTableWithHeaderFilterRepository(BaseRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(db)  # Initialize the BaseRepository with the db instance

    async def fetch_table_with_header(self, user_id: int, table_name: str, params: dict):
        start_time = time.time()

        try:
            # Fetch allowed columns and validate params
            allowed_columns = await self.fetch_columns(table_name)
            for key in params.keys():
                if key not in allowed_columns:
                    raise HTTPException(status_code=400, detail=f"Invalid column name: {key}")

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

        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")



# Search public table with keyword - Checked + Optimized
class SearchPublicTableRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_public_table(self, search_keyword: str, user_id: int):
        try:
            # Validate search keyword
            # if not search_keyword or not search_keyword.strip():
            #     raise HTTPException(status_code=400, detail="Search keyword cannot be empty")

            # Parameterized query to prevent SQL injection
            query = text("""
                SELECT * 
                FROM table_definitions
                LEFT JOIN user_tables ON table_definitions.id = user_tables.table_id
                LEFT JOIN users ON users.id = user_tables.user_id
                WHERE (table_name LIKE :search_keyword 
                       OR table_description LIKE :search_keyword 
                       OR category LIKE :search_keyword)
                AND table_status = 'public'
                AND user_tables.user_id != :user_id
            """)
            result = await self.db.execute(query, {"search_keyword": f"%{search_keyword}%", "user_id": user_id})
            data = result.mappings().all()

            # Process data and return
            return [
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

        except SQLAlchemyError as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


class GetQueryTypeRepository:

    @staticmethod
    def get_query_type(query: str) -> str:
        """
        Determines the type of SQL query (SELECT, INSERT, UPDATE, DELETE).
        """
        parsed = sqlparse.parse(query)
        if not parsed:
            raise HTTPException(status_code=400, detail="Invalid SQL query")

        # Get the first statement (in case of multiple statements)
        first_statement = parsed[0]

        # Iterate through the tokens to find the first keyword
        for token in first_statement.tokens:
            if token.is_keyword and token.value.upper() in {"SELECT", "INSERT", "UPDATE", "DELETE", "CREATE"}:
                return token.value.upper()

        # If no valid keyword is found, raise an error
        raise HTTPException(status_code=400, detail="Unsupported query type")


class QueryValidationRepository:

    @staticmethod
    def is_valid_sql(query: str) -> bool:
        """
        Validate the SQL query using sqlparse.
        """
        try:
            parsed = sqlparse.parse(query)
            return len(parsed) > 0
        except Exception:
            return False

    @staticmethod
    def contains_sql_injection(query: str) -> bool:
        """
        Check if the query contains potential SQL injection patterns.
        """
        # Common SQL injection patterns
        injection_patterns = [
            r"'.*--",  # SQL comment
            r"'.*;",   # Multiple queries
            r"'.*\/\*.*\*\/",  # Block comments
            r"'.*union.*select",  # UNION SELECT
            r"'.*drop\s+table",  # DROP TABLE
            r"'.*delete\s+from",  # DELETE FROM
            r"'.*insert\s+into",  # INSERT INTO
            r"'.*update\s+.+\s+set",  # UPDATE ... SET
        ]

        # Check for patterns in the query
        for pattern in injection_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def contains_restricted_tables(query: str) -> dict:
        """
        Check if the query contains references to restricted tables.
        """
        restricted_tables = {"user_tables", "alembic_version", "table_definitions", "users", "favorite_tables"}  # Add all restricted table names here

        # Parse the query
        parsed = sqlparse.parse(query)
        table_name = None
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
                            return {
                                "table_name": table_name,
                                "status": True
                            }
                        break  # Exit after processing the first non-whitespace token

        return {
            "table_name": table_name,
            "status": False
        }


class SelectQueryRepository:

    def __init__(self, db: AsyncSession, table_name: str):
        self.db = db
        self.table_name = table_name

    async def execute_select_query(self, query: str) -> dict:
        """
        Execute a SELECT query and return the results.
        """
        start_time = time.time()
        result = await self.db.execute(text(query))

        # Check if the result has any rows
        if result.rowcount == 0:
            return await self.zero_rows()

        # Convert RowMapping objects to dictionaries
        rows = result.mappings().all()
        data = [dict(row) for row in rows]  # Convert each RowMapping to a dictionary

        # Extract headers (column names)
        headers = list(data[0].keys()) if data else []

        execution_time = time.time() - start_time
        return {
            "data": data[:100],  # Limit to 100 results
            "total_rows": len(data),  # Total rows fetched
            "execution_time": execution_time.__round__(4),
            "original_table_name": self.table_name,
            "headers": headers
        }

        # If nothing is return, need to send to frontend all headers

    async def zero_rows(self):
        start_time = time.time()
        headers = []
        if self.table_name:
            # Query the information schema to get column names
            column_query = text("""
                                              SELECT column_name
                                              FROM information_schema.columns
                                              WHERE table_name = :table_name
                                              ORDER BY ordinal_position;
                                          """)
            column_result = await self.db.execute(column_query, {"table_name": self.table_name})
            headers = [row[0] for row in column_result]
        return {
            "data": [],
            "total_rows": 0,
            "execution_time": time.time() - start_time,
            "original_table_name": self.table_name,
            "headers": headers
        }


class CheckTableOwnershipRepository:

    def __init__(self, db: AsyncSession):
        self.db = db


    async def check_table_ownership(self, table_name: str, user_id: int) -> bool:
        """
        Check if the user owns the table.
        """
        # Combine the queries using a join
        query = (
            select(TableDefinition)
            .join(UserTable, TableDefinition.id == UserTable.table_id)
            .where(TableDefinition.table_name == table_name, UserTable.user_id == user_id)
        )

        result = await self.db.execute(query)
        table_definition = result.scalars().first()
        if not table_definition:
            raise HTTPException(status_code=403,
                                detail="You are not authorized to perform this operation or the table does not exist")

        return True


class InsertUpdateDeleteQueryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_write_query(self, query: str, query_type: str, user_info: dict, table_name: str) -> dict:
        """
        Execute INSERT, UPDATE, or DELETE queries and return the number of affected rows.
        """
        # Validate query type

        if query_type.upper() not in {"INSERT", "UPDATE", "DELETE"}:
            raise HTTPException(status_code=400, detail="Invalid query type")

        # Log the operation
        self.log_operation(query, query_type, user_info)

        # Check table ownership
        check_table_ownership = CheckTableOwnershipRepository(self.db)
        await check_table_ownership.check_table_ownership(table_name, user_info.get('id'))

        # Execute the query
        start_time = time.time()
        try:
            result = await self.db.execute(text(query))
            await self.db.commit()  # Commit the transaction for write operations
        except Exception as e:
            await self.db.rollback()  # Rollback in case of error
            raise HTTPException(status_code=500, detail=f"Error executing query: {str(e)}")

        execution_time = time.time() - start_time
        return {
            "message": f"{query_type} operation successful",
            "affected_rows": result.rowcount,
            "execution_time": execution_time.__round__(4),
        }

    def log_operation(self, query: str, query_type: str, user_info: dict):
        """
        Log the operation for auditing purposes.
        """
        logging.info(f"User {user_info.get('id')} performed {query_type} operation: {query}")


class ExecuteQueryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.table_name = None

    async def execute_query(self, query: str, user_info: dict) -> object:
        try:
            # 1 - Validate the SQL query
            if not QueryValidationRepository.is_valid_sql(query):
                raise HTTPException(status_code=400, detail="Invalid SQL query")

            # 2 - Check for SQL injection
            if QueryValidationRepository.contains_sql_injection(query):
                raise HTTPException(status_code=400, detail="Potential SQL injection detected")

            # 3 - Check if the query attempts to access restricted tables
            restricted_table_status = QueryValidationRepository.contains_restricted_tables(query)
            if restricted_table_status["status"]:
                raise HTTPException(status_code=403, detail="Access to restricted tables is not allowed")
            else:
                self.table_name = restricted_table_status["table_name"]

            # 4 - Check query type
            query_type = GetQueryTypeRepository.get_query_type(query)
            if query_type == 'SELECT':
                select_query_repository = SelectQueryRepository(self.db, self.table_name)
                return await select_query_repository.execute_select_query(query)

            elif query_type in ['UPDATE', 'DELETE', 'INSERT']:
                insert_update_delete_query_repository = InsertUpdateDeleteQueryRepository(self.db,)
                return await insert_update_delete_query_repository.execute_write_query(query, query_type, user_info, self.table_name)

            elif query_type == 'CREATE':
                create_table_query_repository = CreateTableQueryRepository(self.db)
                return await create_table_query_repository.execute_create_table_query(query, user_info)

        except ProgrammingError as e:
            # Log the error for debugging
            logging.error(f"Database error: {str(e)}")

            # Simplify the error message
            error_message = str(e.orig) if hasattr(e, 'orig') else str(e)
            simplified_error = SimplifyErrorMessageRepository.simplify_sql_error_message(error_message)

            # Raise the simplified error message
            raise HTTPException(status_code=500, detail=simplified_error)

        except HTTPException as e:
            # Re-raise HTTP exceptions (e.g., validation errors)
            raise e

        except Exception as e:
            # Handle any other unexpected errors
            logging.error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


# Create table by query
class CreateTableQueryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_create_table_query(self, query: str, user_info: dict) -> dict:
        """
        Execute a CREATE TABLE query and return the result.
        """
        # Validate the query type
        query_type = GetQueryTypeRepository.get_query_type(query)
        if query_type != "CREATE":
            raise HTTPException(status_code=400, detail="Invalid query type for table creation")

        # Log the operation
        self.log_operation(query, query_type, user_info)

        # Execute the query
        start_time = time.time()
        try:
            result = await self.db.execute(text(query))
            await self.db.commit()  # Commit the transaction for table creation
        except Exception as e:
            await self.db.rollback()  # Rollback in case of error

            # Simplify the error message
            error_message = str(e)
            simplified_error = SimplifyErrorMessageRepository.simplify_sql_error_message(error_message)

            raise HTTPException(status_code=500, detail=simplified_error)

        execution_time = time.time() - start_time
        return {
            "message": "CREATE TABLE operation successful",
            "execution_time": execution_time.__round__(4),
        }

    def log_operation(self, query: str, query_type: str, user_info: dict):
        """
        Log the operation for auditing purposes.
        """
        logging.info(f"User {user_info.get('id')} performed {query_type} operation: {query}")

# Create table by components - Checked + Optimized
class CreateTableFromReadyComponentsRepository(TableValidationRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_table_from_components(self, table_data, user_id: int):
        try:
            table_data.tableName = table_data.tableName.lower().replace(' ', '_')
            # 1 - Validate table data
            self._validate_table_data(table_data)

            # 2 - Check if the table already exists
            table = await self.db.scalar(select(TableDefinition).where(TableDefinition.table_name == table_data.tableName))
            if table:
                raise HTTPException(status_code=400, detail="Table with the same name already exists.")

            # 3 - Create the table definition
            table_definition = await self._create_table_definition(table_data)
            self.db.add(table_definition)
            await self.db.commit()
            await self.db.refresh(table_definition)
            table_id = table_definition.id

            # 4 - Create the table columns
            await self._create_table_columns(table_data)

            # 5 - Create the user table
            user_table = UserTable(
                table_id=table_id,
                user_id=user_id
            )
            self.db.add(user_table)
            await self.db.commit()

            return {"message": f"Table '{table_data.tableName}' created successfully"}

        except SQLAlchemyError as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    def _validate_table_data(self, table_data):
        """Validate table data."""
        if not table_data.tableName:
            raise HTTPException(status_code=400, detail="Table name is required")
        if not TableValidationRepository.is_valid_name(table_data.tableName):
            raise HTTPException(status_code=400, detail="Table name must be alphanumeric and can include underscores.")
        if not table_data.columns:
            raise HTTPException(status_code=400, detail="At least one column is required")
        cols = [column.name for column in table_data.columns]
        TableValidationRepository.validate_column_names(cols)

    async def _create_table_definition(self, table_data):
        """Create and return the table definition."""
        return TableDefinition(
            table_name=table_data.tableName,
            table_description=table_data.description,
            table_status=table_data.tableStatus,
            category=table_data.category,
        )

    async def _create_table_columns(self, table_data):
        """Create the table columns dynamically."""
        type_mapping = {
            "string": String,
            "integer": Integer,
            "boolean": Boolean,
            "date": Date,
            "float": Float
        }

        columns = [
            Column("id", Integer, primary_key=True, autoincrement=True)
        ]
        for col in table_data.columns:
            if col.type not in type_mapping:
                raise HTTPException(status_code=400, detail=f"Invalid column type: {col.type}")
            columns.append(Column(col.name, type_mapping[col.type]))

        metadata = MetaData()
        table = Table(table_data.tableName, metadata, *columns)
        await self.db.execute(CreateTable(table))


# Create new table by excel, csv - Checked + Optimized
class CreateTableRepository(TableValidationRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_table(self, user_id: int, file: UploadFile, table_status: str, table_description: str, table_name: str = None, table_category: str = None):
        async with SessionLocal() as session:
            try:
                logging.info(f"Starting table creation for user {user_id}. Table name: {table_name}")

                # Validate inputs
                self._validate_inputs(table_name, table_category, file)
                logging.debug("Inputs validated successfully.")

                # Define table name and category
                define_table_name = table_name.strip().lower()
                table_category = table_category.strip().lower()
                logging.debug(f"Table name: {define_table_name}, Category: {table_category}")

                # Check if table already exists
                await self._check_table_already_exists(define_table_name, session)
                logging.debug("Table does not already exist.")

                # Read the file into a DataFrame
                df = self._read_the_file(file)
                logging.debug(f"File read successfully. Rows: {len(df)}, Columns: {len(df.columns)}")

                # Create columns based on DataFrame dtypes
                columns_alchemy, columns_names = self._create_columns_according_to_datatypes(df)
                logging.debug(f"Columns created: {columns_names}")

                # Validate column names
                TableValidationRepository.validate_column_names(columns_names)
                logging.debug("Column names validated successfully.")

                # Create TableDefinition
                table_id = await self._create_table_definition(table_status, table_description, define_table_name, table_category, session)
                logging.info(f"TableDefinition created with ID: {table_id}")

                # Create the table and insert data
                await self._create_table_and_columns(session, define_table_name, columns_alchemy)
                logging.debug("Table and columns created in the database.")

                await self._insert_data(session, define_table_name, df)
                logging.debug("Data inserted into the table.")

                await self._create_user_tables(user_id, table_id, session)
                logging.debug(f"UserTable created for user {user_id} and table {table_id}.")

                await session.commit()
                logging.info(f"Table '{define_table_name}' created successfully for user {user_id}.")
                return {'message': 'Table created successfully'}

            except HTTPException as e:
                logging.error(f"HTTPException: {e.detail}")
                raise  # Re-raise HTTPException
            except Exception as e:
                await session.rollback()
                logging.error(f"Error creating table: {str(e)}", exc_info=True)
                if 'table_id' in locals():
                    await self._delete_table_definition(table_id)
                    logging.warning(f"Deleted TableDefinition with ID: {table_id} due to error.")
                raise HTTPException(status_code=500, detail=f"Error creating table: {str(e)}")

    def _validate_inputs(self, table_name: str, table_category: str, file: UploadFile):
        """Validate user inputs."""
        if not table_name:
            logging.error("Table name is required.")
            raise HTTPException(status_code=400, detail="Table name is required.")
        if not TableValidationRepository.is_valid_name(table_name):
            logging.error(f"Invalid table name: {table_name}")
            raise HTTPException(status_code=400, detail="Table name must be alphanumeric and can include underscores.")
        if not file.filename.endswith(('.csv', '.xlsx')):
            logging.error(f"Invalid file type: {file.filename}")
            raise HTTPException(status_code=400, detail="Invalid file type. Only .csv and .xlsx files are accepted.")

    async def _check_table_already_exists(self, table_name: str, session: AsyncSession):
        """Check if the table already exists in the database."""
        query = text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :table_name)")
        result = await session.execute(query, {"table_name": table_name})
        if result.scalar():
            logging.error(f"Table already exists: {table_name}")
            raise HTTPException(status_code=400, detail="Table already exists.")

    def _read_the_file(self, file: UploadFile) -> pd.DataFrame:
        """Read the uploaded file into a DataFrame."""
        try:
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file.file)
            else:
                df = pd.read_excel(file.file)
            logging.debug(f"File read successfully: {file.filename}")
            return df
        except Exception as e:
            logging.error(f"Error reading file: {str(e)}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")

    async def _create_table_definition(self, table_status: str, table_description: str, table_name: str, table_category: str, session: AsyncSession) -> int:
        """Create a TableDefinition record in the database."""
        table_definition = TableDefinition(
            table_name=table_name,
            table_status=table_status,
            table_description=table_description,
            category=table_category
        )
        session.add(table_definition)
        await session.commit()
        await session.refresh(table_definition)
        logging.debug(f"TableDefinition created: {table_definition.id}")
        return table_definition.id

    async def _delete_table_definition(self, table_id: int):
        """Delete a TableDefinition record from the database."""
        async with SessionLocal() as session:
            table_definition = await session.execute(select(TableDefinition).where(TableDefinition.id == table_id))
            table_definition = table_definition.scalars().first()
            await session.delete(table_definition)
            await session.commit()
            logging.debug(f"TableDefinition deleted: {table_id}")

    async def _create_table_and_columns(self, session: AsyncSession, table_name: str, columns_alchemy: List[Column]):
        """Create the table and its columns in the database."""
        metadata = MetaData()
        table = Table(
            table_name, metadata,
            Column('id', Integer, primary_key=True),
            *columns_alchemy
        )
        await session.execute(CreateTable(table))
        logging.debug(f"Table created: {table_name}")

    async def _insert_data(self, session: AsyncSession, table_name: str, data: pd.DataFrame):
        """Insert data into the table."""
        sanitized_data = self._sanitize_data(data)
        columns = ', '.join(sanitized_data[0].keys())
        placeholders = ', '.join([f":{key}" for key in sanitized_data[0].keys()])
        query = text(f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})")

        try:
            await session.execute(query, sanitized_data)
            logging.debug(f"Data inserted into table: {table_name}")
        except SQLAlchemyError as e:
            logging.error(f"Error inserting data: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error inserting data: {str(e)}")

    def _sanitize_data(self, data: pd.DataFrame) -> List[dict]:
        """Sanitize column names and convert values to the appropriate data type."""
        sanitized_data = []
        for _, row in data.iterrows():
            row_data = {}
            for column_name, value in row.items():
                sanitized_column_name = re.sub(r'[^a-zA-Z0-9_]', '_', column_name.strip())
                if pd.isna(value):
                    row_data[sanitized_column_name] = None
                elif pd.api.types.is_integer_dtype(data[column_name].dtype):
                    row_data[sanitized_column_name] = int(value)
                elif pd.api.types.is_float_dtype(data[column_name].dtype):
                    row_data[sanitized_column_name] = float(value)
                elif pd.api.types.is_datetime64_any_dtype(data[column_name].dtype):
                    row_data[sanitized_column_name] = pd.to_datetime(value).to_pydatetime()
                else:
                    row_data[sanitized_column_name] = str(value)
            sanitized_data.append(row_data)
        logging.debug("Data sanitized successfully.")
        return sanitized_data

    async def _create_user_tables(self, user_id: int, table_id: int, session: AsyncSession):
        """Create a UserTable record in the database."""
        user_table = UserTable(user_id=user_id, table_id=table_id)
        session.add(user_table)
        logging.debug(f"UserTable created for user {user_id} and table {table_id}.")

    def _create_columns_according_to_datatypes(self, df: pd.DataFrame) -> Tuple[List[Column], List[str]]:
        """Create SQLAlchemy columns based on DataFrame dtypes."""
        inner_columns = []
        column_names = []
        for column_name, dtype in df.dtypes.items():
            sanitized_column_name = self._sanitize_column_name(column_name)
            if pd.api.types.is_integer_dtype(dtype):
                inner_columns.append(Column(sanitized_column_name, Integer))
            elif pd.api.types.is_float_dtype(dtype):
                inner_columns.append(Column(sanitized_column_name, Float))
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                inner_columns.append(Column(sanitized_column_name, Date))
            else:
                inner_columns.append(Column(sanitized_column_name, String))
            column_names.append(sanitized_column_name)
        logging.debug(f"Columns created: {column_names}")
        return inner_columns, column_names

    def _sanitize_column_name(self, column_name: str) -> str:
        """Sanitize a column name."""
        sanitized_name = column_name.strip().replace(' ', '_').replace('.', '_').replace('/', '_').replace('\\', '_').replace('-', '_')
        if not self.is_valid_name(sanitized_name):
            logging.error(f"Invalid column name: {column_name}")
            raise HTTPException(status_code=400, detail=f"Invalid column name: '{column_name}'.")
        return sanitized_name.lower()

