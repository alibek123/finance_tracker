from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from utils.enums import TransactionType, AccountType, BudgetPeriod


# Pydantic models (Request/Response)

class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[int] = None
    type: TransactionType = Field(..., alias="category_type")
    icon: Optional[str] = Field(None, max_length=10)
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    is_active: bool = True

    class Config:
        populate_by_name = True
        use_enum_values = True


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    icon: Optional[str] = Field(None, max_length=10)
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    is_active: Optional[bool] = None


class Category(CategoryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class AccountBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: AccountType = Field(..., alias="account_type")
    initial_balance: Decimal = Field(default=0, ge=0)
    credit_limit: Optional[Decimal] = Field(None, ge=0)
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = Field(None, max_length=10)
    is_active: bool = True
    currency: str = Field(default="KZT", max_length=3)

    class Config:
        populate_by_name = True
        use_enum_values = True


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = Field(None, max_length=10)
    is_active: Optional[bool] = None


class Account(AccountBase):
    id: int
    current_balance: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TransactionBase(BaseModel):
    date: date
    type: TransactionType = Field(..., alias="transaction_type")
    amount: Decimal = Field(..., gt=0)
    account_from_id: Optional[int] = None
    account_to_id: Optional[int] = None
    category_id: Optional[int] = None
    subcategory_id: Optional[int] = None
    description: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None
    is_planned: bool = False

    class Config:
        populate_by_name = True
        use_enum_values = True


class TransactionCreate(TransactionBase):
    tag_ids: Optional[List[int]] = []


class TransactionUpdate(BaseModel):
    description: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = None
    tag_ids: Optional[List[int]] = None


class Transaction(TransactionBase):
    id: int
    date: date
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BudgetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category_id: int
    amount: Decimal = Field(..., gt=0)
    period: BudgetPeriod
    start_date: date
    end_date: Optional[date] = None
    is_active: bool = True

    class Config:
        use_enum_values = True


class BudgetCreate(BudgetBase):
    pass


class BudgetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    amount: Optional[Decimal] = Field(None, gt=0)
    is_active: Optional[bool] = None


class Budget(BudgetBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class TagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")


class TagCreate(TagBase):
    pass


class Tag(TagBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class SavingsGoalBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    target_amount: Decimal = Field(..., gt=0)
    target_date: Optional[date] = None
    account_id: Optional[int] = None
    notes: Optional[str] = None


class SavingsGoalCreate(SavingsGoalBase):
    pass


class SavingsGoalUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    target_amount: Optional[Decimal] = Field(None, gt=0)
    target_date: Optional[date] = None
    notes: Optional[str] = None


class SavingsGoal(SavingsGoalBase):
    id: int
    current_amount: Decimal
    is_achieved: bool
    created_at: datetime
    achieved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Новые модели для повторяющихся транзакций
class RecurringTransactionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: TransactionType = Field(..., alias="transaction_type")
    amount: Decimal = Field(..., gt=0)
    account_from_id: Optional[int] = None
    account_to_id: Optional[int] = None
    category_id: Optional[int] = None
    frequency: str = Field(..., pattern="^(daily|weekly|monthly|quarterly|yearly)$")
    start_date: date
    end_date: Optional[date] = None
    is_active: bool = True

    class Config:
        populate_by_name = True
        use_enum_values = True


class RecurringTransactionCreate(RecurringTransactionBase):
    pass


class RecurringTransactionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    type: Optional[TransactionType] = Field(None, alias="transaction_type")
    amount: Optional[Decimal] = Field(None, gt=0)
    account_from_id: Optional[int] = None
    account_to_id: Optional[int] = None
    category_id: Optional[int] = None
    frequency: Optional[str] = Field(None, pattern="^(daily|weekly|monthly|quarterly|yearly)$")
    end_date: Optional[date] = None
    is_active: Optional[bool] = None

    class Config:
        populate_by_name = True
        use_enum_values = True


class RecurringTransaction(RecurringTransactionBase):
    id: int
    last_created_date: Optional[date] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DailyExpenseItem(BaseModel):
    date: date
    amount: float


class CategoryBreakdownItem(BaseModel):
    category_name: str
    amount: float
    color: Optional[str]
    icon: Optional[str]


class DashboardStats(BaseModel):
    total_income: float
    total_expense: float
    net_balance: float
    total_balance: Optional[float] = None
    net_savings: Optional[float] = None
    daily_expenses: List[DailyExpenseItem]
    category_breakdown: List[CategoryBreakdownItem]


class TrendData(BaseModel):
    period: str  # Например, 'YYYY-MM-DD', 'YYYY-IW', 'YYYY-MM'
    income: float
    expenses: float
    transaction_count: int


class CategoryBreakdownItem(BaseModel):
    category_name: str
    amount: float
    color: str


class ForecastData(BaseModel):
    month: str
    income: float
    expense: float
    net: float
