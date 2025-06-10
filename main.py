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
import urllib.parse

# Загрузка переменных окружения
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# Настройки базы данных с правильной кодировкой
def get_database_url():
    # Получаем параметры подключения
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "finance_db")
    default_schema = os.getenv("DB_SCHEMA", "finance")

    # Экранируем пароль для URL
    db_password_encoded = urllib.parse.quote_plus(db_password)
    schema_encoded = urllib.parse.quote_plus(default_schema)

    # Формируем URL с параметрами кодировки
    return (
        f"postgresql://{db_user}:{db_password_encoded}@{db_host}:{db_port}/{db_name}"
        f"?client_encoding=utf8&options=-csearch_path%3D{schema_encoded}"
    )


DATABASE_URL = os.getenv("DATABASE_URL", get_database_url())

# Создаем engine с дополнительными параметрами для Windows
try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Проверка соединения перед использованием
        pool_size=5,
        max_overflow=10,
        connect_args={
            "client_encoding": "utf8",
            "connect_timeout": 10
        }
    )
    # Проверяем подключение
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        print("✅ Successfully connected to database")
except Exception as e:
    print(f"❌ Database connection error: {e}")
    print("Please check your database settings in .env file:")
    print("DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME")
    raise

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
            FROM categories c
            WHERE c.parent_id IS NULL

            UNION ALL

            SELECT 
                c.id, c.name, c.parent_id, c.type, c.icon, c.color, c.is_active,
                (ct.path || ' > ' || c.name)::text as path,
                ct.level + 1 as level
            FROM categories c
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
        INSERT INTO categories (name, parent_id, type, icon, color, is_active)
        VALUES (:name, :parent_id, :category_type, :icon, :color, :is_active)
        RETURNING *
    """
    params = category.model_dump()
    params['category_type'] = params.pop('type', None)
    result = db.execute(text(query), params)
    db.commit()
    return dict(result.fetchone()._asdict())


@app.delete("/api/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    # Проверяем, есть ли транзакции с этой категорией
    count = db.execute(
        text("SELECT COUNT(*) FROM transactions WHERE category_id = :id OR subcategory_id = :id"),
        {"id": category_id}
    ).scalar()

    if count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Невозможно удалить категорию. Существует {count} транзакций с этой категорией"
        )

    # Проверяем, есть ли подкатегории
    subcount = db.execute(
        text("SELECT COUNT(*) FROM categories WHERE parent_id = :id"),
        {"id": category_id}
    ).scalar()

    if subcount > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Невозможно удалить категорию. У неё есть {subcount} подкатегорий"
        )

    result = db.execute(
        text("DELETE FROM categories WHERE id = :id RETURNING id"),
        {"id": category_id}
    )
    deleted = result.fetchone()
    if not deleted:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    db.commit()
    return {"message": "Категория удалена"}


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
        FROM accounts a
        LEFT JOIN transactions t ON (a.id = t.account_from_id OR a.id = t.account_to_id)
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
        INSERT INTO accounts (name, type, initial_balance, current_balance, credit_limit, color, icon, is_active)
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
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    update_fields = []
    params = {"id": account_id}

    for field, value in update_data.items():
        update_fields.append(f"{field} = :{field}")
        params[field] = value

    query = f"""
        UPDATE accounts 
        SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
        WHERE id = :id
        RETURNING *
    """

    result = db.execute(text(query), params)
    db.commit()

    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Счет не найден")

    return dict(row._asdict())


@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db)):
    # Проверяем баланс
    balance = db.execute(
        text("SELECT current_balance FROM accounts WHERE id = :id"),
        {"id": account_id}
    ).scalar()

    if balance is None:
        raise HTTPException(status_code=404, detail="Счет не найден")

    if balance != 0:
        raise HTTPException(
            status_code=400,
            detail=f"Невозможно удалить счет с ненулевым балансом ({balance})"
        )

    # Проверяем транзакции
    count = db.execute(
        text("SELECT COUNT(*) FROM transactions WHERE account_from_id = :id OR account_to_id = :id"),
        {"id": account_id}
    ).scalar()

    if count > 0:
        # Деактивируем вместо удаления
        db.execute(
            text("UPDATE accounts SET is_active = false WHERE id = :id"),
            {"id": account_id}
        )
        db.commit()
        return {"message": f"Счет деактивирован (есть {count} транзакций)"}

    # Удаляем если нет транзакций
    db.execute(text("DELETE FROM accounts WHERE id = :id"), {"id": account_id})
    db.commit()
    return {"message": "Счет удален"}


# Корректировка баланса
@app.post("/api/accounts/{account_id}/adjust-balance")
def adjust_account_balance(
        account_id: int,
        new_balance: Decimal,
        description: Optional[str] = None,
        db: Session = Depends(get_db)
):
    trans = db.begin()
    try:
        # Получаем текущий баланс
        current = db.execute(
            text("SELECT current_balance FROM accounts WHERE id = :id"),
            {"id": account_id}
        ).scalar()

        if current is None:
            raise HTTPException(status_code=404, detail="Счет не найден")

        difference = new_balance - current

        if difference == 0:
            return {"message": "Баланс не изменился"}

        # Находим категорию "Корректировка"
        category_id = db.execute(
            text("SELECT id FROM categories WHERE name = 'Корректировка' AND type = 'transfer'")
        ).scalar()

        # Создаем транзакцию корректировки
        transaction_type = "income" if difference > 0 else "expense"
        account_field = "account_to_id" if difference > 0 else "account_from_id"

        db.execute(text(f"""
            INSERT INTO transactions (
                date, type, amount, {account_field}, category_id, 
                description, notes, is_planned
            ) VALUES (
                CURRENT_DATE, :type, :amount, :account_id, :category_id,
                :description, 'Корректировка баланса', false
            )
        """), {
            "type": transaction_type,
            "amount": abs(difference),
            "account_id": account_id,
            "category_id": category_id,
            "description": description or f"Корректировка баланса: {difference:+.2f}"
        })

        # Обновляем баланс
        db.execute(
            text("UPDATE accounts SET current_balance = :balance WHERE id = :id"),
            {"balance": new_balance, "id": account_id}
        )

        trans.commit()
        return {
            "message": "Баланс скорректирован",
            "difference": float(difference),
            "new_balance": float(new_balance)
        }
    except Exception as e:
        trans.rollback()
        raise HTTPException(status_code=400, detail=str(e))


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
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            LEFT JOIN categories sc ON t.subcategory_id = sc.id
            LEFT JOIN accounts af ON t.account_from_id = af.id
            LEFT JOIN accounts at ON t.account_to_id = at.id
            LEFT JOIN transaction_tags tt ON t.id = tt.transaction_id
            LEFT JOIN tags tg ON tt.tag_id = tg.id
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
            INSERT INTO transactions (
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
                    text("INSERT INTO transaction_tags (transaction_id, tag_id) VALUES (:tid, :tag_id)"),
                    {"tid": transaction_id, "tag_id": tag_id}
                )

        trans.commit()
        return {"id": transaction_id, "message": "Transaction created successfully"}
    except Exception as e:
        trans.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("DELETE FROM transactions WHERE id = :id RETURNING id"),
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
        FROM budgets b
        LEFT JOIN categories c ON b.category_id = c.id
        LEFT JOIN transactions t ON t.category_id = b.category_id
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
        INSERT INTO budgets (name, category_id, amount, period, start_date, end_date, is_active)
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
        UPDATE budgets 
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
        text("UPDATE budgets SET is_active = false WHERE id = :id RETURNING id"),
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
        FROM tags t
        LEFT JOIN transaction_tags tt ON t.id = tt.tag_id
        GROUP BY t.id
        ORDER BY usage_count DESC, t.name
    """
    result = db.execute(text(query))
    return [dict(row._asdict()) for row in result]


@app.post("/api/tags", response_model=Dict[str, Any])
def create_tag(tag: TagCreate, db: Session = Depends(get_db)):
    query = """
        INSERT INTO tags (name, color)
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
        FROM savings_goals sg
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
        INSERT INTO savings_goals (name, target_amount, target_date, account_id, notes)
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
            INSERT INTO savings_contributions (goal_id, transaction_id, amount, date, notes)
            VALUES (:goal_id, :transaction_id, :amount, CURRENT_DATE, :notes)
        """), {
            "goal_id": goal_id,
            "transaction_id": transaction_id,
            "amount": amount,
            "notes": notes
        })

        # Обновляем текущую сумму
        db.execute(text("""
            UPDATE savings_goals 
            SET current_amount = current_amount + :amount
            WHERE id = :goal_id
        """), {
            "goal_id": goal_id,
            "amount": amount
        })

        # Проверяем, достигнута ли цель
        result = db.execute(text("""
            UPDATE savings_goals 
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
            FROM transactions
            WHERE date BETWEEN :start_date AND :end_date
                AND category_id NOT IN (
                    SELECT id FROM categories WHERE name = 'Корректировка'
                )
        ),
        account_balances AS (
            SELECT SUM(current_balance) as total_balance
            FROM accounts
            WHERE is_active = true
        ),
        daily_expenses AS (
            SELECT 
                date,
                SUM(amount) as amount
            FROM transactions
            WHERE type = 'expense' 
                AND date BETWEEN :start_date AND :end_date
                AND category_id NOT IN (
                    SELECT id FROM categories WHERE name = 'Корректировка'
                )
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
                    (SELECT SUM(amount) FROM transactions 
                     WHERE type = :type 
                     AND date BETWEEN :start_date AND :end_date), 0
                ), 2
            ) as percentage
        FROM categories c
        JOIN transactions t ON t.category_id = c.id
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
        FROM transactions
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
