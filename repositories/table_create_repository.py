
import logging
import re

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.ddl import CreateTable
from sqlalchemy import Table, Column, Integer, String, MetaData, text, Boolean, Date, Float

from models.main_models import UserTable, TableDefinition


table_logger = logging.getLogger("table_logger")
table_logger.setLevel(logging.DEBUG)
table_handler = logging.FileHandler("logs/tablelog.log")
table_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s'))
table_logger.addHandler(table_handler)


class TableValidationRepository:

    RESERVED_NAMES = {
        "information_schema",
        "pg_catalog",
        "pg_toast",
        "pg_temp",
        "pg_toast_temp",
        "public",
        "admin",
        "guest",
        "user",
    }
    RESERVED_KEYWORDS = {
        "select", "insert", "update", "delete", "create", "drop", "alter", "table", "where", "join", "from", "order", "by", "asc", "desc", "limit", "offset", "group", "having", "union", "intersect", "except", "all", "exists", "true", "false", "null", "case", "when", "then", "else", "end", "is", "not", "and", "or", "between", "in", "like", "isnull", "isnotnull", "isdistinctfrom", "isnotdistinctfrom", "isunknown", "isnotunknown", "istrue", "isnottrue", "isfalse", "isnotfalse", "isunknown", "isnotunknown", "isdistinctfrom", "isnotdistinctfrom", "isunknown", "isnotunknown", "istrue", "isnottrue", "isfalse", "isnotfalse"
    }

    @staticmethod
    def is_reserved_name(name: str) -> bool:
        """Check if the table name is reserved."""
        return name.lower() in TableValidationRepository.RESERVED_NAMES

    @staticmethod
    def is_reserved_keyword(name: str) -> bool:
        """Check if the table name is a reserved SQL keyword."""
        return name.upper() in TableValidationRepository.RESERVED_KEYWORDS


    @staticmethod
    def is_valid_name(name: str):

        """Validate the table name."""
        if TableValidationRepository.is_reserved_name(name):
            table_logger.error(f"The table name '{name}' is reserved and cannot be used.")
            raise HTTPException(
                status_code=400,
                detail=f"The table name '{name}' is reserved and cannot be used.",
            )
        if TableValidationRepository.is_reserved_keyword(name):
            table_logger.error(f"The table name '{name}' is a reserved SQL keyword and cannot be used.")
            raise HTTPException(
                status_code=400,
                detail=f"The table name '{name}' is a reserved SQL keyword and cannot be used.",
            )

        if not re.match(r'^[A-Za-z0-9_çÇğĞıİöÖşŞüÜа-яА-ЯёЁ]+$', name):
            table_logger.error(f"Table name must be alphanumeric and can include underscores: {name}")
            raise HTTPException(status_code=400, detail="Table name must be alphanumeric and can include underscores.")

    @staticmethod
    def validate_column_names(columns):
        # reserved_keywords = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'FROM', 'WHERE', 'JOIN', 'CREATE', 'DROP', 'ALTER', 'TABLE'}
        for column in columns:
            if not re.match(r'^[A-Za-z0-9_çÇğĞıİöÖşŞüÜа-яА-ЯёЁ]+$', column):
                raise HTTPException(status_code=400, detail=f"Invalid column name: '{column}'. Column names must be alphanumeric and can include underscores.")
            if column[0].isdigit():
                raise HTTPException(status_code=400, detail=f"Invalid column name: '{column}'. Column names cannot start with a number.")
            if column.lower() in  TableValidationRepository.RESERVED_KEYWORDS:
                raise HTTPException(status_code=400, detail=f"Invalid column name: '{column}'. Column names cannot be SQL reserved keywords.")

    @staticmethod
    def validate_table_data(table_data):
        if not table_data.tableName:
            raise HTTPException(status_code=400, detail="Table name is required")
        TableValidationRepository.is_valid_name(table_data.tableName)
        if not table_data.columns:
            raise HTTPException(status_code=400, detail="At least one column is required")
        cols = [column.name for column in table_data.columns]
        TableValidationRepository.validate_column_names(cols)




class CheckTableNameAvailabilityRepository:
    @staticmethod
    async def check_table_already_exists(table_name: str, session: AsyncSession):
        query = text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :table_name)")
        result = await session.execute(query, {"table_name": table_name})
        if result.scalar():
            table_logger.error(f"Table already exists: {table_name}")
            raise HTTPException(status_code=400, detail="Table already exists.")

class CreateTableDefinitionRepository:
    @staticmethod
    async def create_table_definition(table_status: str, table_description: str, table_name: str, table_category: str, session: AsyncSession) -> int:
        table_definition = TableDefinition(
            table_name=table_name,
            table_status=table_status,
            table_description=table_description,
            category=table_category
        )
        session.add(table_definition)
        await session.commit()
        await session.refresh(table_definition)
        return table_definition.id

class CreateUserRepository:
    @staticmethod
    async def create_user_tables(user_id: int, table_id: int, session: AsyncSession):
        user_table = UserTable(user_id=user_id, table_id=table_id)
        session.add(user_table)
        table_logger.debug(f"UserTable created for user {user_id} and table {table_id}.")

class CreateTableFromReadyComponentsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_table_from_components(self, table_data, user_id: int):
        try:
            table_data.tableName = table_data.tableName.strip().lower().replace(' ', '_')
            TableValidationRepository.validate_table_data(table_data)
            await CheckTableNameAvailabilityRepository.check_table_already_exists(table_data.tableName, self.db)
            table_id = await CreateTableDefinitionRepository.create_table_definition(
                table_data.tableStatus, table_data.description, table_data.tableName, table_data.category, self.db
            )
            await self._create_table_columns(table_data)
            await CreateUserRepository.create_user_tables(user_id, table_id, self.db)
            await self.db.commit()
            table_logger.info(f"Table '{table_data.tableName}' created by user {user_id}.")
            return {"message": f"Table '{table_data.tableName}' created successfully"}
        except SQLAlchemyError as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

    async def _create_table_columns(self, table_data):
        type_mapping = {
            "string": String,
            "integer": Integer,
            "boolean": Boolean,
            "date": Date,
            "float": Float
        }
        columns = [Column("id", Integer, primary_key=True, autoincrement=True)]
        for col in table_data.columns:
            if col.type not in type_mapping:
                raise HTTPException(status_code=400, detail=f"Invalid column type: {col.type}")
            columns.append(Column(col.name, type_mapping[col.type]))
        metadata = MetaData()
        table = Table(table_data.tableName, metadata, *columns)
        await self.db.execute(CreateTable(table))






