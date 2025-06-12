from enum import Enum

class TransactionType(str, Enum):
    expense = "expense"
    income = "income"
    transfer = "transfer"
    correction = "correction"

class AccountType(str, Enum):
    cash = "cash"
    debit_card = "debit_card"
    credit_card = "credit_card"
    savings = "savings"
    investment = "investment"

class BudgetPeriod(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"