
from db.setup import Base
from sqlalchemy import func
from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    middle_name = Column(String, nullable=True)
    surname = Column(String, nullable=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False, )
    image_url = Column(String, nullable=True)

    user_tables = relationship("UserTable", back_populates="user")
    favorite_tables = relationship("FavoriteTables", back_populates="user")

    created_at = Column(DateTime, nullable=True, server_default=func.now())

    def __repr__(self):
        return f"User(name={self.username}, email={self.email})"



class TokenModel(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, nullable=False)

    def __repr__(self):
        return f"TokenModel(user_id={self.user_id}, token={self.token})"


class UserTable(Base):
    __tablename__ = "user_tables"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    table_id = Column(Integer, ForeignKey("table_definitions.id"), nullable=False)

    user = relationship("User", back_populates="user_tables")

    table_definition = relationship("TableDefinition", back_populates="user_tables")
    created_at = Column(DateTime, nullable=True, server_default=func.now())


    def __repr__(self):
        return f"UserTable(user_id={self.user_id}, table_id={self.table_id}, table_definition={self.table_definition})"


class TableDefinition(Base):
    __tablename__ = "table_definitions"

    id = Column(Integer, primary_key=True, index=True, nullable=False)
    table_name = Column(String, unique=True, index=True, nullable=False)
    table_status = Column(String, index=True, nullable=False)
    table_description = Column(Text, nullable=True)
    category = Column(String, nullable=True)

    user_tables = relationship("UserTable", back_populates="table_definition")
    favorite_tables = relationship("FavoriteTables", back_populates="table")
    created_at = Column(DateTime, nullable=True, server_default=func.now())

    def __repr__(self):
        return f"TableDefinition(table_name={self.table_name}, table_status={self.table_status}), created_at={self.created_at})"


class FavoriteTables(Base):
    __tablename__ = "favorite_tables"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    table_id = Column(Integer, ForeignKey("table_definitions.id"))
    created_at = Column(DateTime, nullable=True, server_default=func.now())

    user = relationship("User", back_populates="favorite_tables")
    table = relationship("TableDefinition", back_populates="favorite_tables")