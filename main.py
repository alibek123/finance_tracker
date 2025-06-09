# main.py
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
import os
from pathlib import Path

# Загрузка переменных окружения
from dotenv import load_dotenv

load_dotenv()

# Настройки базы данных
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost/finance_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(title="Personal Finance Tracker", version="1.0.0")

# CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Pydantic модели для валидации данных
class CategoryBase(BaseModel):
    name: str
    parent_id: Optional[int] = None
    type: str = Field(..., pattern="^(expense|income|transfer)$", alias="category_type")
    icon: Optional[str] = None
    color: Optional[str] = None
    is_active: bool = True

    class Config:
        populate_by_name = True


class CategoryCreate(CategoryBase):
    pass


class Category(CategoryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class AccountBase(BaseModel):
    name: str
    type: str = Field(..., pattern="^(cash|debit_card|credit_card|savings|investment)$", alias="account_type")
    initial_balance: Decimal = 0
    credit_limit: Optional[Decimal] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    is_active: bool = True

    class Config:
        populate_by_name = True


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
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
    type: str = Field(..., pattern="^(expense|income|transfer)$", alias="transaction_type")
    amount: Decimal = Field(..., gt=0)
    account_from_id: Optional[int] = None
    account_to_id: Optional[int] = None
    category_id: Optional[int] = None
    subcategory_id: Optional[int] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    is_planned: bool = False

    class Config:
        populate_by_name = True


class TransactionCreate(TransactionBase):
    tag_ids: Optional[List[int]] = []


class Transaction(TransactionBase):
    id: int
    time: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BudgetBase(BaseModel):
    name: str
    category_id: int
    amount: Decimal = Field(..., gt=0)
    period: str = Field(..., pattern="^(daily|weekly|monthly|quarterly|yearly)$")
    start_date: date
    end_date: Optional[date] = None
    is_active: bool = True


class BudgetCreate(BudgetBase):
    pass


class BudgetUpdate(BaseModel):
    name: Optional[str] = None
    amount: Optional[Decimal] = None
    is_active: Optional[bool] = None


class Budget(BudgetBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class TagBase(BaseModel):
    name: str
    color: Optional[str] = None


class TagCreate(TagBase):
    pass


class Tag(TagBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class SavingsGoalBase(BaseModel):
    name: str
    target_amount: Decimal = Field(..., gt=0)
    target_date: Optional[date] = None
    account_id: Optional[int] = None
    notes: Optional[str] = None


class SavingsGoalCreate(SavingsGoalBase):
    pass


class SavingsGoal(SavingsGoalBase):
    id: int
    current_amount: Decimal
    is_achieved: bool
    created_at: datetime
    achieved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# API Endpoints

# Категории
@app.get("/api/categories", response_model=List[Dict[str, Any]])
def get_categories(
        category_type: Optional[str] = Query(None, pattern="^(expense|income|transfer)$"),
        include_inactive: bool = False,
        db: Session = Depends(get_db)
):
    query = """
        WITH RECURSIVE category_tree AS (
            SELECT 
                c.id, c.name, c.parent_id, c.type, c.icon, c.color, c.is_active,
                c.name::text as path,
                0 as level
            FROM finance.categories c
            WHERE c.parent_id IS NULL

            UNION ALL

            SELECT 
                c.id, c.name, c.parent_id, c.type, c.icon, c.color, c.is_active,
                (ct.path || ' > ' || c.name)::text as path,
                ct.level + 1 as level
            FROM finance.categories c
            JOIN category_tree ct ON c.parent_id = ct.id
        )
        SELECT * FROM category_tree
        WHERE 1=1
    """
    params = {}

    if category_type:
        query += " AND type = :type"
        params["type"] = category_type

    if not include_inactive:
        query += " AND is_active = true"

    query += " ORDER BY type, level, name"

    result = db.execute(text(query), params)
    return [dict(row._asdict()) for row in result]


@app.post("/api/categories", response_model=Dict[str, Any])
def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    query = """
        INSERT INTO finance.categories (name, parent_id, type, icon, color, is_active)
        VALUES (:name, :parent_id, :category_type, :icon, :color, :is_active)
        RETURNING *
    """
    params = category.model_dump()
    params['category_type'] = params.pop('type', None)
    result = db.execute(text(query), params)
    db.commit()
    return dict(result.fetchone()._asdict())


@app.put("/api/categories/{category_id}")
def update_category(
        category_id: int,
        updates: Dict[str, Any],
        db: Session = Depends(get_db)
):
    allowed_fields = ['name', 'icon', 'color', 'is_active']
    update_fields = []
    params = {"id": category_id}

    for field, value in updates.items():
        if field in allowed_fields and value is not None:
            update_fields.append(f"{field} = :{field}")
            params[field] = value

    if not update_fields:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    query = f"""
        UPDATE finance.categories 
        SET {', '.join(update_fields)}
        WHERE id = :id
        RETURNING *
    """

    result = db.execute(text(query), params)
    db.commit()

    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Category not found")

    return dict(row._asdict())


# Счета
@app.get("/api/accounts", response_model=List[Dict[str, Any]])
def get_accounts(
        include_inactive: bool = False,
        db: Session = Depends(get_db)
):
    query = """
        SELECT 
            a.*,
            COUNT(DISTINCT t.id) as transaction_count,
            MAX(t.date) as last_transaction_date
        FROM finance.accounts a
        LEFT JOIN finance.transactions t ON (a.id = t.account_from_id OR a.id = t.account_to_id)
        WHERE 1=1
    """

    if not include_inactive:
        query += " AND a.is_active = true"

    query += " GROUP BY a.id ORDER BY a.created_at"

    result = db.execute(text(query))
    return [dict(row._asdict()) for row in result]


@app.post("/api/accounts", response_model=Dict[str, Any])
def create_account(account: AccountCreate, db: Session = Depends(get_db)):
    query = """
        INSERT INTO finance.accounts (name, type, initial_balance, current_balance, credit_limit, color, icon, is_active)
        VALUES (:name, :account_type, :initial_balance, :initial_balance, :credit_limit, :color, :icon, :is_active)
        RETURNING *
    """
    params = account.model_dump()
    params['account_type'] = params.pop('type', None)
    result = db.execute(text(query), params)
    db.commit()
    return dict(result.fetchone()._asdict())


@app.put("/api/accounts/{account_id}")
def update_account(
        account_id: int,
        account_update: AccountUpdate,
        db: Session = Depends(get_db)
):
    update_data = account_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_fields = []
    params = {"id": account_id}

    for field, value in update_data.items():
        update_fields.append(f"{field} = :{field}")
        params[field] = value

    query = f"""
        UPDATE finance.accounts 
        SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
        WHERE id = :id
        RETURNING *
    """

    result = db.execute(text(query), params)
    db.commit()

    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Account not found")

    return dict(row._asdict())


# Транзакции
@app.get("/api/transactions")
def get_transactions(
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        transaction_type: Optional[str] = Query(None, pattern="^(expense|income|transfer)$"),
        category_id: Optional[int] = None,
        account_id: Optional[int] = None,
        limit: int = Query(default=100, le=1000),
        offset: int = 0,
        db: Session = Depends(get_db)
):
    try:
        query = """
            SELECT 
                t.*,
                c.name as category_name,
                c.icon as category_icon,
                c.color as category_color,
                sc.name as subcategory_name,
                af.name as account_from_name,
                at.name as account_to_name,
                array_agg(DISTINCT tg.name) FILTER (WHERE tg.name IS NOT NULL) as tags
            FROM finance.transactions t
            LEFT JOIN finance.categories c ON t.category_id = c.id
            LEFT JOIN finance.categories sc ON t.subcategory_id = sc.id
            LEFT JOIN finance.accounts af ON t.account_from_id = af.id
            LEFT JOIN finance.accounts at ON t.account_to_id = at.id
            LEFT JOIN finance.transaction_tags tt ON t.id = tt.transaction_id
            LEFT JOIN finance.tags tg ON tt.tag_id = tg.id
            WHERE 1=1
        """
        params = {"limit": limit, "offset": offset}

        if start_date:
            query += " AND t.date >= :start_date"
            params["start_date"] = start_date

        if end_date:
            query += " AND t.date <= :end_date"
            params["end_date"] = end_date

        if transaction_type:
            query += " AND t.type = :type"
            params["type"] = transaction_type

        if category_id:
            query += " AND (t.category_id = :category_id OR t.subcategory_id = :category_id)"
            params["category_id"] = category_id

        if account_id:
            query += " AND (t.account_from_id = :account_id OR t.account_to_id = :account_id)"
            params["account_id"] = account_id

        query += " GROUP BY t.id, c.name, c.icon, c.color, sc.name, af.name, at.name"
        query += " ORDER BY t.date DESC, t.time DESC LIMIT :limit OFFSET :offset"

        result = db.execute(text(query), params)
        return [dict(row._asdict()) for row in result]
    except Exception as e:
        print(e)
        return 0


@app.post("/api/transactions")
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)):
    trans = db.begin()
    try:
        query = """
            INSERT INTO finance.transactions (
                date, type, amount, account_from_id, account_to_id,
                category_id, subcategory_id, description, notes, is_planned
            ) VALUES (
                :date, :transaction_type, :amount, :account_from_id, :account_to_id,
                :category_id, :subcategory_id, :description, :notes, :is_planned
            ) RETURNING id
        """
        params = transaction.model_dump(exclude={'tag_ids'})
        params['transaction_type'] = params.pop('type', None)
        result = db.execute(text(query), params)
        transaction_id = result.fetchone()[0]

        if transaction.tag_ids:
            for tag_id in transaction.tag_ids:
                db.execute(
                    text("INSERT INTO finance.transaction_tags (transaction_id, tag_id) VALUES (:tid, :tag_id)"),
                    {"tid": transaction_id, "tag_id": tag_id}
                )

        trans.commit()
        return {"id": transaction_id, "message": "Transaction created successfully"}
    except Exception as e:
        trans.rollback()
        print("Error:", str(e))
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("DELETE FROM finance.transactions WHERE id = :id RETURNING id"),
        {"id": transaction_id}
    )
    deleted = result.fetchone()
    if not deleted:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.commit()
    return {"message": "Transaction deleted successfully"}


# Бюджеты
@app.get("/api/budgets")
def get_budgets(
        active_only: bool = True,
        db: Session = Depends(get_db)
):
    query = """
        SELECT 
            b.*,
            c.name as category_name,
            c.icon as category_icon,
            c.color as category_color,
            COALESCE(SUM(t.amount), 0) as spent_amount,
            b.amount - COALESCE(SUM(t.amount), 0) as remaining_amount,
            CASE 
                WHEN b.amount > 0 THEN 
                    ROUND((COALESCE(SUM(t.amount), 0) / b.amount) * 100, 2)
                ELSE 0 
            END as usage_percentage,
            EXTRACT(DAY FROM CURRENT_DATE - DATE_TRUNC('month', CURRENT_DATE))::int as days_passed,
            EXTRACT(DAY FROM DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month') - DATE_TRUNC('month', CURRENT_DATE))::int as days_in_period
        FROM finance.budgets b
        LEFT JOIN finance.categories c ON b.category_id = c.id
        LEFT JOIN finance.transactions t ON t.category_id = b.category_id
            AND t.type = 'expense'
            AND t.date >= b.start_date
            AND (b.end_date IS NULL OR t.date <= b.end_date)
        WHERE 1=1
    """

    if active_only:
        query += " AND b.is_active = true"

    query += " GROUP BY b.id, c.name, c.icon, c.color ORDER BY b.created_at DESC"

    result = db.execute(text(query))
    return [dict(row._asdict()) for row in result]


@app.post("/api/budgets", response_model=Dict[str, Any])
def create_budget(budget: BudgetCreate, db: Session = Depends(get_db)):
    query = """
        INSERT INTO finance.budgets (name, category_id, amount, period, start_date, end_date, is_active)
        VALUES (:name, :category_id, :amount, :period, :start_date, :end_date, :is_active)
        RETURNING *
    """
    result = db.execute(text(query), budget.model_dump())
    db.commit()
    return dict(result.fetchone()._asdict())


@app.put("/api/budgets/{budget_id}")
def update_budget(
        budget_id: int,
        budget_update: BudgetUpdate,
        db: Session = Depends(get_db)
):
    update_data = budget_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_fields = []
    params = {"id": budget_id}

    for field, value in update_data.items():
        update_fields.append(f"{field} = :{field}")
        params[field] = value

    query = f"""
        UPDATE finance.budgets 
        SET {', '.join(update_fields)}
        WHERE id = :id
        RETURNING *
    """

    result = db.execute(text(query), params)
    db.commit()

    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Budget not found")

    return dict(row._asdict())


@app.delete("/api/budgets/{budget_id}")
def delete_budget(budget_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("UPDATE finance.budgets SET is_active = false WHERE id = :id RETURNING id"),
        {"id": budget_id}
    )
    updated = result.fetchone()
    if not updated:
        raise HTTPException(status_code=404, detail="Budget not found")
    db.commit()
    return {"message": "Budget deactivated successfully"}


# Теги
@app.get("/api/tags", response_model=List[Dict[str, Any]])
def get_tags(db: Session = Depends(get_db)):
    query = """
        SELECT 
            t.*,
            COUNT(DISTINCT tt.transaction_id) as usage_count
        FROM finance.tags t
        LEFT JOIN finance.transaction_tags tt ON t.id = tt.tag_id
        GROUP BY t.id
        ORDER BY usage_count DESC, t.name
    """
    result = db.execute(text(query))
    return [dict(row._asdict()) for row in result]


@app.post("/api/tags", response_model=Dict[str, Any])
def create_tag(tag: TagCreate, db: Session = Depends(get_db)):
    query = """
        INSERT INTO finance.tags (name, color)
        VALUES (:name, :color)
        RETURNING *
    """
    result = db.execute(text(query), tag.model_dump())
    db.commit()
    return dict(result.fetchone()._asdict())


# Цели накопления
@app.get("/api/savings-goals")
def get_savings_goals(
        include_achieved: bool = False,
        db: Session = Depends(get_db)
):
    query = """
        SELECT 
            sg.*,
            a.name as account_name,
            a.icon as account_icon
        FROM finance.savings_goals sg
        LEFT JOIN accounts a ON sg.account_id = a.id
        WHERE 1=1
    """

    if not include_achieved:
        query += " AND sg.is_achieved = false"

    query += " ORDER BY sg.target_date, sg.created_at"

    result = db.execute(text(query))
    return [dict(row._asdict()) for row in result]


@app.post("/api/savings-goals", response_model=Dict[str, Any])
def create_savings_goal(goal: SavingsGoalCreate, db: Session = Depends(get_db)):
    query = """
        INSERT INTO finance.savings_goals (name, target_amount, target_date, account_id, notes)
        VALUES (:name, :target_amount, :target_date, :account_id, :notes)
        RETURNING *
    """
    result = db.execute(text(query), goal.model_dump())
    db.commit()
    return dict(result.fetchone()._asdict())


@app.post("/api/savings-goals/{goal_id}/contribute")
def add_savings_contribution(
        goal_id: int,
        amount: Decimal,
        transaction_id: Optional[int] = None,
        notes: Optional[str] = None,
        db: Session = Depends(get_db)
):
    trans = db.begin()
    try:
        # Добавляем взнос
        db.execute(text("""
            INSERT INTO finance.savings_contributions (goal_id, transaction_id, amount, date, notes)
            VALUES (:goal_id, :transaction_id, :amount, CURRENT_DATE, :notes)
        """), {
            "goal_id": goal_id,
            "transaction_id": transaction_id,
            "amount": amount,
            "notes": notes
        })

        # Обновляем текущую сумму
        db.execute(text("""
            UPDATE finance.savings_goals 
            SET current_amount = current_amount + :amount
            WHERE id = :goal_id
        """), {
            "goal_id": goal_id,
            "amount": amount
        })

        # Проверяем, достигнута ли цель
        result = db.execute(text("""
            UPDATE finance.savings_goals 
            SET is_achieved = true, achieved_at = CURRENT_TIMESTAMP
            WHERE id = :goal_id 
                AND current_amount >= target_amount 
                AND is_achieved = false
            RETURNING id
        """), {"goal_id": goal_id})

        achieved = result.fetchone()

        trans.commit()

        return {
            "message": "Contribution added successfully",
            "goal_achieved": achieved is not None
        }
    except Exception as e:
        trans.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# Аналитика
@app.get("/api/analytics/dashboard")
def get_dashboard_stats(
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        db: Session = Depends(get_db)
):
    if not start_date:
        start_date = date.today().replace(day=1)
    if not end_date:
        end_date = date.today()

    query = """
        WITH period_stats AS (
            SELECT 
                SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as total_income,
                SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as total_expenses,
                COUNT(*) as transaction_count,
                AVG(CASE WHEN type = 'expense' THEN amount ELSE NULL END) as avg_expense
            FROM finance.transactions
            WHERE date BETWEEN :start_date AND :end_date
        ),
        account_balances AS (
            SELECT SUM(current_balance) as total_balance
            FROM finance.accounts
            WHERE is_active = true
        ),
        daily_expenses AS (
            SELECT 
                date,
                SUM(amount) as amount
            FROM finance.transactions
            WHERE type = 'expense' 
                AND date BETWEEN :start_date AND :end_date
            GROUP BY date
        )
        SELECT 
            ps.*,
            ab.total_balance,
            ps.total_income - ps.total_expenses as net_savings,
            (
                SELECT json_agg(json_build_object('date', date, 'amount', amount) ORDER BY date)
                FROM daily_expenses
            ) as daily_expenses
        FROM period_stats ps, account_balances ab
    """

    result = db.execute(text(query), {"start_date": start_date, "end_date": end_date})
    return dict(result.fetchone()._asdict())


@app.get("/api/analytics/categories")
def get_category_analytics(
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        transaction_type: str = "expense",
        db: Session = Depends(get_db)
):
    if not start_date:
        start_date = date.today().replace(day=1)
    if not end_date:
        end_date = date.today()

    query = """
        SELECT 
            c.id,
            c.name,
            c.icon,
            c.color,
            COUNT(t.id) as transaction_count,
            SUM(t.amount) as total_amount,
            AVG(t.amount) as avg_amount,
            ROUND(
                SUM(t.amount) * 100.0 / NULLIF(
                    (SELECT SUM(amount) FROM finance.transactions 
                     WHERE type = :type 
                     AND date BETWEEN :start_date AND :end_date), 0
                ), 2
            ) as percentage
        FROM finance.categories c
        JOIN finance.transactions t ON t.category_id = c.id
        WHERE t.type = :type
            AND t.date BETWEEN :start_date AND :end_date
        GROUP BY c.id, c.name, c.icon, c.color
        ORDER BY total_amount DESC
    """

    result = db.execute(text(query), {
        "start_date": start_date,
        "end_date": end_date,
        "type": transaction_type
    })
    return [dict(row._asdict()) for row in result]


@app.get("/api/analytics/trends")
def get_trends(
        period: str = "monthly",
        months: int = 6,
        db: Session = Depends(get_db)
):
    date_format = {
        "daily": "YYYY-MM-DD",
        "weekly": "YYYY-IW",
        "monthly": "YYYY-MM"
    }.get(period, "YYYY-MM")

    query = f"""
        SELECT 
            TO_CHAR(date, :date_format) as period,
            SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expenses,
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
            COUNT(*) as transaction_count
        FROM finance.transactions
        WHERE date >= CURRENT_DATE - INTERVAL '{months} months'
        GROUP BY TO_CHAR(date, :date_format)
        ORDER BY period
    """

    result = db.execute(text(query), {"date_format": date_format})
    return [dict(row._asdict()) for row in result]


# Serve static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


    @app.get("/", response_class=HTMLResponse)
    def read_root():
        index_file = static_dir / "index.html"
        if index_file.exists():
            return index_file.read_text(encoding="utf-8")
        else:
            return """<h1>Personal Finance Tracker</h1><p>Please create static/index.html file</p>"""

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
