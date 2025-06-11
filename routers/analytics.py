from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import List, Dict, Any, Optional

from dependencies import get_db
from sqlalchemy import text

from models.schemas import TrendData, ForecastData, CategoryBreakdownItem, DashboardStats

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"]
)


# --- Эндпоинты аналитики ---

@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_data(db: Session = Depends(get_db)):
    # Get total balance from all active accounts
    balance_query = """
        SELECT COALESCE(SUM(current_balance), 0) AS total_balance
        FROM accounts
        WHERE is_active = true;
    """
    balance_result = db.execute(text(balance_query)).fetchone()
    total_balance = float(balance_result.total_balance)

    # Get current month income and expenses
    current_month_query = """
        SELECT
        COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) AS total_income,
        COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) AS total_expense
        FROM transactions
        WHERE date >= (date_trunc('month', CURRENT_DATE) - INTERVAL '1 month' + INTERVAL '26 days')
          AND date < (date_trunc('month', CURRENT_DATE) + INTERVAL '26 days');
    """

    stats_result = db.execute(text(current_month_query)).fetchone()
    total_income = float(stats_result.total_income)
    total_expense = float(stats_result.total_expense)
    net_balance = total_income - total_expense
    net_savings = total_income - total_expense

    # Get daily expenses for the chart
    daily_expenses_query = """
        SELECT
            date,
            SUM(amount) AS amount
        FROM transactions
        WHERE type = 'expense'
          AND date >= (date_trunc('month', CURRENT_DATE) - INTERVAL '1 month' + INTERVAL '26 days')
          AND date < (date_trunc('month', CURRENT_DATE) + INTERVAL '26 days')
        GROUP BY date
        ORDER BY date ASC;
    """

    daily_expenses_result = db.execute(text(daily_expenses_query)).fetchall()
    daily_expenses = [{"date": str(row.date), "amount": float(row.amount)} for row in daily_expenses_result]

    # Get category breakdown
    category_expenses_query = """
        SELECT
            c.name as category_name,
            c.color as color,
            c.icon as icon,
            SUM(t.amount) AS amount
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.type = 'expense'
          AND t.date >= (date_trunc('month', CURRENT_DATE) - INTERVAL '1 month' + INTERVAL '26 days')
          AND t.date < (date_trunc('month', CURRENT_DATE) + INTERVAL '26 days')
        GROUP BY c.id, c.name, c.color, c.icon
        ORDER BY amount DESC
        LIMIT 5;
    """

    category_expenses_result = db.execute(text(category_expenses_query)).fetchall()
    category_breakdown = [
        {"category_name": row.category_name, "amount": float(row.amount), "color": row.color, "icon": row.icon}
        for row in category_expenses_result
    ]

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "net_balance": net_balance,
        "total_balance": total_balance,
        "net_savings": net_savings,
        "daily_expenses": daily_expenses,
        "category_breakdown": category_breakdown
    }


@router.get("/trends", response_model=List[TrendData])
def get_trends(
        period: str = Query("monthly", pattern="^(daily|weekly|monthly)$"),
        months: int = Query(6, ge=1, le=12),
        db: Session = Depends(get_db)
):
    db_type = db.bind.name

    if db_type == "postgresql":
        if period == "daily":
            # For daily, show last 30 days
            query = """
                SELECT
                    TO_CHAR(date, 'YYYY-MM-DD') as period,
                    COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses,
                    COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                    COUNT(*) as transaction_count
                FROM transactions
                WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY date
                ORDER BY date
            """
        elif period == "weekly":
            query = f"""
                SELECT
                    TO_CHAR(date, 'IYYY-IW') as period,
                    COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses,
                    COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                    COUNT(*) as transaction_count
                FROM transactions
                WHERE date >= CURRENT_DATE - INTERVAL '{months} months'
                GROUP BY TO_CHAR(date, 'IYYY-IW')
                ORDER BY period
            """
        else:  # monthly
            query = f"""
                SELECT
                    TO_CHAR(date, 'YYYY-MM') as period,
                    COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses,
                    COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                    COUNT(*) as transaction_count
                FROM transactions
                WHERE date >= CURRENT_DATE - INTERVAL '{months} months'
                GROUP BY TO_CHAR(date, 'YYYY-MM')
                ORDER BY period
            """
    else:  # sqlite
        if period == "daily":
            # For daily, show last 30 days
            query = """
                SELECT
                    strftime('%Y-%m-%d', date) as period,
                    COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses,
                    COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                    COUNT(*) as transaction_count
                FROM transactions
                WHERE date >= date('now', '-30 days')
                GROUP BY date
                ORDER BY date
            """
        elif period == "weekly":
            query = f"""
                SELECT
                    strftime('%Y-%W', date) as period,
                    COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses,
                    COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                    COUNT(*) as transaction_count
                FROM transactions
                WHERE date >= date('now', '-{months} months')
                GROUP BY strftime('%Y-%W', date)
                ORDER BY period
            """
        else:  # monthly
            query = f"""
                SELECT
                    strftime('%Y-%m', date) as period,
                    COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses,
                    COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                    COUNT(*) as transaction_count
                FROM transactions
                WHERE date >= date('now', '-{months} months')
                GROUP BY strftime('%Y-%m', date)
                ORDER BY period
            """

    result = db.execute(text(query)).fetchall()

    return [
        {
            "period": row.period,
            "expenses": float(row.expenses),
            "income": float(row.income),
            "transaction_count": row.transaction_count
        }
        for row in result
    ]


@router.get("/forecast", response_model=List[ForecastData])
async def get_forecast_data(
        months_ahead: int = Query(default=3, ge=1, le=12),
        db: Session = Depends(get_db)
):
    """
    Получает прогнозные данные на основе регулярных транзакций.
    """
    db_type = db.bind.name

    if db_type == "postgresql":
        forecast_query = """
            WITH RECURSIVE months AS (
                SELECT date_trunc('month', CURRENT_DATE) AS month
                UNION ALL
                SELECT month + interval '1 month'
                FROM months
                WHERE month < date_trunc('month', CURRENT_DATE) + interval :months_interval
            )
            SELECT
                TO_CHAR(m.month, 'YYYY-MM') AS month,
                COALESCE(SUM(CASE WHEN rt.type = 'income' THEN rt.amount ELSE 0 END), 0) AS income,
                COALESCE(SUM(CASE WHEN rt.type = 'expense' THEN rt.amount ELSE 0 END), 0) AS expense
            FROM months m
            LEFT JOIN recurring_transactions rt ON 
                rt.is_active = true AND
                rt.start_date <= m.month AND
                (rt.end_date IS NULL OR rt.end_date >= m.month)
            GROUP BY m.month
            ORDER BY m.month;
        """
        params = {"months_interval": f"{months_ahead} months"}
    else:  # sqlite
        # Simplified version for SQLite
        forecast_query = """
            SELECT
                strftime('%Y-%m', date('now', 'start of month', printf('+%d months', n))) AS month,
                0 AS income,
                0 AS expense
            FROM (
                SELECT 0 AS n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 
                UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7
                UNION SELECT 8 UNION SELECT 9 UNION SELECT 10 UNION SELECT 11
            ) months
            WHERE n < :months_ahead
            ORDER BY month;
        """
        params = {"months_ahead": months_ahead}

    result = db.execute(text(forecast_query), params).fetchall()

    forecast_data = []
    for row in result:
        income = float(row.income)
        expense = float(row.expense)
        forecast_data.append({
            "month": row.month,
            "income": income,
            "expense": expense,
            "net": income - expense
        })

    return forecast_data


@router.get("/category_breakdown", response_model=List[CategoryBreakdownItem])
async def get_category_breakdown(
        type: str = Query("expense", pattern="^(expense|income)$"),
        start_date: Optional[date] = Query(None),
        end_date: Optional[date] = Query(None),
        db: Session = Depends(get_db)
):
    """
    Получает распределение расходов или доходов по категориям за период.
    """
    query = """
        SELECT
            c.name as category_name,
            c.color as color,
            SUM(t.amount) AS amount
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.type = :type
    """
    params = {"type": type}

    if start_date:
        query += " AND t.date >= :start_date"
        params["start_date"] = start_date
    if end_date:
        query += " AND t.date <= :end_date"
        params["end_date"] = end_date

    query += """
        GROUP BY c.id, c.name, c.color
        ORDER BY amount DESC;
    """
    result = db.execute(text(query), params).fetchall()

    return [
        {"category_name": row.category_name, "amount": float(row.amount), "color": row.color}
        for row in result
    ]


@router.get("/categories")
async def get_category_analytics(
        transaction_type: str = Query("expense", pattern="^(expense|income)$"),
        db: Session = Depends(get_db)
):
    """
    Получает аналитику по категориям с процентами и количеством транзакций.
    """
    # Get total for percentage calculation
    total_query = """
        SELECT COALESCE(SUM(amount), 0) as total
        FROM transactions
        WHERE type = :type
          AND date >= date_trunc('month', CURRENT_DATE)
    """

    if db.bind.name == "sqlite":
        total_query = """
            SELECT COALESCE(SUM(amount), 0) as total
            FROM transactions
            WHERE type = :type
              AND date >= date('now', 'start of month')
        """

    total_result = db.execute(text(total_query), {"type": transaction_type}).fetchone()
    total_amount = float(total_result.total) if total_result.total > 0 else 1  # Avoid division by zero

    # Get category breakdown
    query = """
        SELECT
            c.id,
            c.name,
            c.color,
            c.icon,
            SUM(t.amount) AS total_amount,
            COUNT(t.id) AS transaction_count
        FROM categories c
        LEFT JOIN transactions t ON c.id = t.category_id 
            AND t.type = :type
            AND t.date >= date_trunc('month', CURRENT_DATE)
        WHERE c.type = :type
        GROUP BY c.id, c.name, c.color, c.icon
        HAVING SUM(t.amount) > 0
        ORDER BY total_amount DESC
    """

    if db.bind.name == "sqlite":
        query = """
            SELECT
                c.id,
                c.name,
                c.color,
                c.icon,
                SUM(t.amount) AS total_amount,
                COUNT(t.id) AS transaction_count
            FROM categories c
            LEFT JOIN transactions t ON c.id = t.category_id 
                AND t.type = :type
                AND t.date >= date('now', 'start of month')
            WHERE c.type = :type
            GROUP BY c.id, c.name, c.color, c.icon
            HAVING SUM(t.amount) > 0
            ORDER BY total_amount DESC
        """

    result = db.execute(text(query), {"type": transaction_type}).fetchall()

    return [
        {
            "id": row.id,
            "name": row.name,
            "color": row.color,
            "icon": row.icon,
            "total_amount": float(row.total_amount) if row.total_amount else 0,
            "transaction_count": row.transaction_count,
            "percentage": round((float(row.total_amount) / total_amount * 100), 1) if row.total_amount else 0
        }
        for row in result
    ]


@router.get("/account-balances")
async def get_account_balances(db: Session = Depends(get_db)):
    """
    Получает баланс по всем счетам с процентным распределением.
    """
    query = """
        SELECT
            a.id,
            a.name,
            a.type,
            a.current_balance,
            a.currency,
            a.icon,
            a.color,
            (SELECT COUNT(*) FROM transactions t 
             WHERE t.account_from_id = a.id OR t.account_to_id = a.id) as transaction_count
        FROM accounts a
        WHERE a.is_active = true
        ORDER BY a.current_balance DESC
    """

    result = db.execute(text(query)).fetchall()
    accounts = []
    total_balance = 0

    for row in result:
        balance = float(row.current_balance)
        total_balance += balance
        accounts.append({
            "id": row.id,
            "name": row.name,
            "type": row.type,
            "balance": balance,
            "currency": row.currency,
            "icon": row.icon,
            "color": row.color,
            "transaction_count": row.transaction_count
        })

    # Calculate percentages
    for acc in accounts:
        acc["percentage"] = round((acc["balance"] / total_balance * 100), 1) if total_balance > 0 else 0

    return {
        "total_balance": total_balance,
        "accounts": accounts
    }


@router.get("/monthly-comparison")
async def get_monthly_comparison(
        months_back: int = Query(default=3, ge=1, le=12),
        db: Session = Depends(get_db)
):
    """
    Сравнение доходов и расходов за последние месяцы.
    """
    db_type = db.bind.name

    if db_type == "postgresql":
        query = """
            WITH months AS (
                SELECT 
                    TO_CHAR(date_trunc('month', CURRENT_DATE - INTERVAL '1 month' * n), 'YYYY-MM') as month,
                    date_trunc('month', CURRENT_DATE - INTERVAL '1 month' * n) as month_start,
                    date_trunc('month', CURRENT_DATE - INTERVAL '1 month' * n) + INTERVAL '1 month' - INTERVAL '1 day' as month_end
                FROM generate_series(0, :months_back - 1) as n
            )
            SELECT
                m.month,
                COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as income,
                COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as expenses,
                COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE -t.amount END), 0) as net
            FROM months m
            LEFT JOIN transactions t ON t.date >= m.month_start AND t.date <= m.month_end AND t.type != 'transfer'
            GROUP BY m.month, m.month_start
            ORDER BY m.month DESC
        """
    else:  # sqlite
        # Create a simplified version for SQLite
        query = """
            SELECT
                strftime('%Y-%m', date) as month,
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses,
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END), 0) as net
            FROM transactions
            WHERE date >= date('now', 'start of month', printf('-%d months', :months_back))
              AND type != 'transfer'
            GROUP BY strftime('%Y-%m', date)
            ORDER BY month DESC
        """

    result = db.execute(text(query), {"months_back": months_back}).fetchall()

    comparison = []
    for row in result:
        income = float(row.income)
        expenses = float(row.expenses)
        net = float(row.net)
        comparison.append({
            "month": row.month,
            "income": income,
            "expenses": expenses,
            "net": net,
            "savings_rate": round((net / income * 100), 1) if income > 0 else 0
        })

    return comparison


@router.get("/expense-heatmap")
async def get_expense_heatmap(
        year: int = Query(default=None),
        month: int = Query(default=None),
        db: Session = Depends(get_db)
):
    """
    Получает тепловую карту расходов по дням.
    """
    if not year:
        year = datetime.now().year
    if not month:
        month = datetime.now().month

    query = """
        SELECT
            EXTRACT(DAY FROM date)::int as day,
            SUM(amount) as total
        FROM transactions
        WHERE type = 'expense'
          AND EXTRACT(YEAR FROM date) = :year
          AND EXTRACT(MONTH FROM date) = :month
        GROUP BY day
        ORDER BY day
    """

    if db.bind.name == "sqlite":
        query = """
            SELECT
                CAST(strftime('%d', date) AS INTEGER) as day,
                SUM(amount) as total
            FROM transactions
            WHERE type = 'expense'
              AND strftime('%Y', date) = printf('%04d', :year)
              AND strftime('%m', date) = printf('%02d', :month)
            GROUP BY day
            ORDER BY day
        """

    result = db.execute(text(query), {"year": year, "month": month}).fetchall()

    # Create heatmap data
    heatmap_data = []
    max_expense = 0

    for row in result:
        amount = float(row.total)
        max_expense = max(max_expense, amount)
        heatmap_data.append({
            "day": row.day,
            "amount": amount
        })

    # Calculate intensity levels
    for item in heatmap_data:
        item["intensity"] = round((item["amount"] / max_expense * 100), 0) if max_expense > 0 else 0

    return {
        "year": year,
        "month": month,
        "data": heatmap_data,
        "max_expense": max_expense
    }


@router.get("/top-expenses")
async def get_top_expenses(
        limit: int = Query(default=10, ge=1, le=50),
        days: int = Query(default=30, ge=1, le=365),
        db: Session = Depends(get_db)
):
    """
    Получает топ самых больших расходов за период.
    """
    query = """
        SELECT
            t.id,
            t.date,
            t.amount,
            t.description,
            c.name as category_name,
            c.icon as category_icon,
            c.color as category_color,
            a.name as account_name
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts a ON t.account_from_id = a.id
        WHERE t.type = 'expense'
          AND t.date >= CURRENT_DATE - INTERVAL :days_interval
        ORDER BY t.amount DESC
        LIMIT :limit
    """

    if db.bind.name == "sqlite":
        query = """
            SELECT
                t.id,
                t.date,
                t.amount,
                t.description,
                c.name as category_name,
                c.icon as category_icon,
                c.color as category_color,
                a.name as account_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            LEFT JOIN accounts a ON t.account_from_id = a.id
            WHERE t.type = 'expense'
              AND t.date >= date('now', printf('-%d days', :days))
            ORDER BY t.amount DESC
            LIMIT :limit
        """
        params = {"days": days, "limit": limit}
    else:
        params = {"days_interval": f"{days} days", "limit": limit}

    result = db.execute(text(query), params).fetchall()

    return [
        {
            "id": row.id,
            "date": row.date.isoformat(),
            "amount": float(row.amount),
            "description": row.description,
            "category": {
                "name": row.category_name,
                "icon": row.category_icon,
                "color": row.category_color
            },
            "account": row.account_name
        }
        for row in result
    ]
