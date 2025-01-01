
from db.setup import Base
from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String, nullable=False, )
    image_url = Column(String, nullable=True)

    user_tables = relationship("UserTable", back_populates="user")

    def __repr__(self):
        return f"User(name={self.username}, email={self.email})"


class UserTable(Base):
    __tablename__ = "user_tables"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    table_id = Column(Integer, ForeignKey("table_definitions.id"))

    user = relationship("User", back_populates="user_tables")
    table_definition = relationship("TableDefinition", back_populates="user_tables")


class TableDefinition(Base):
    __tablename__ = "table_definitions"

    id = Column(Integer, primary_key=True, index=True)
    table_name = Column(String, unique=True, index=True)
    table_status = Column(String, index=True)
    table_description = Column(Text)

    user_tables = relationship("UserTable", back_populates="table_definition")

    def __repr__(self):
        return f"TableDefinition(table_name={self.table_name}, table_status={self.table_status})"