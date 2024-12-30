
from db.setup import Base
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)


    users = relationship("User", back_populates="company")
    def __repr__(self):
        return f"Company(name={self.name})"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)

    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)

    company = relationship("Company", back_populates="users")
    user_tables = relationship("UserTable", back_populates="user")

    def __repr__(self):
        return f"User(name={self.name}, email={self.email})"


class UserTable(Base):
    __tablename__ = "user_tables"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    table_name = Column(String)

    user = relationship("User", back_populates="user_tables")

    def __repr__(self):
        return f"UserTable(user_id={self.user_id}, table_name={self.table_name})"