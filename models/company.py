

from sqlalchemy import ForeignKey, DateTime, func, null, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.setup import Base

class CompanyModel(Base):
    __tablename__ = 'company'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    users: Mapped[list['UserModel']] = relationship(back_populates='company')
