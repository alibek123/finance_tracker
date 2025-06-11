# from database import Base
# from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Numeric, ForeignKey
# from sqlalchemy.orm import relationship
# from utils.enums import TransactionType, AccountType, BudgetPeriod

# If you were to define ORM models, they'd go here, e.g.:
# class Category(Base):
#     __tablename__ = "categories"
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String, unique=True, index=True)
#     parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
#     type = Column(String) # Will be mapped to Enum later
#     # ... other columns