from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict
import calendar

from dependencies import get_db
from sqlalchemy import text

from models.schemas import TrendData, ForecastData, CategoryBreakdownItem, DashboardStats

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"]
)


# Улучшенный дашборд - фокус на 4-5 ключевых метриках
@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_data(db: Session = Depends(get_db)):
    # Более точный расчет текущего месяца
    today = date.today()
    month_start = today.replace(day=1)

    # Основные метрики
    balance_query = """
        SELECT COALESCE(SUM(current_balance), 0) AS total_balance
        FROM accounts WHERE is_active = true;
    """
    balance_result = db.execute(text(balance_query)).fetchone()
    total_balance = float(balance_result.total_balance)

    # Доходы и расходы за текущий месяц
    monthly_query = """
        SELECT
        COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) AS total_income,
        COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) AS total_expense
        FROM transactions
        WHERE date >= :month_start AND date <= :today
    """

    stats_result = db.execute(text(monthly_query), {
        "month_start": month_start,
        "today": today
    }).fetchone()

    total_income = float(stats_result.total_income)
    total_expense = float(stats_result.total_expense)
    net_savings = total_income - total_expense

    # Среднедневные расходы (для прогноза на конец месяца)
    days_passed = today.day
    avg_daily_expense = total_expense / days_passed if days_passed > 0 else 0
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    projected_monthly_expense = avg_daily_expense * days_in_month

    # Топ-3 категории расходов
    top_categories_query = """
        SELECT c.name, c.color, c.icon, SUM(t.amount) AS amount
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.type = 'expense' AND t.date >= :month_start AND t.date <= :today
        GROUP BY c.id, c.name, c.color, c.icon
        ORDER BY amount DESC
        LIMIT 3;
    """

    categories_result = db.execute(text(top_categories_query), {
        "month_start": month_start,
        "today": today
    }).fetchall()

    category_breakdown = [
        {
            "category_name": row.name,
            "amount": float(row.amount),
            "color": row.color,
            "icon": row.icon
        }
        for row in categories_result
    ]

    # Последние 7 дней расходов (мини-тренд)
    week_expenses_query = """
        SELECT date, SUM(amount) AS amount
        FROM transactions
        WHERE type = 'expense' AND date >= :week_start AND date <= :today
        GROUP BY date
        ORDER BY date ASC;
    """

    week_start = today - timedelta(days=6)
    week_result = db.execute(text(week_expenses_query), {
        "week_start": week_start,
        "today": today
    }).fetchall()

    daily_expenses = [{"date": str(row.date), "amount": float(row.amount)} for row in week_result]

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "net_balance": net_savings,
        "total_balance": total_balance,
        "net_savings": net_savings,
        "projected_monthly_expense": projected_monthly_expense,  # Новая метрика
        "daily_expenses": daily_expenses,
        "category_breakdown": category_breakdown
    }


# Анализ паттернов трат (новая функция)
@router.get("/spending-patterns")
async def get_spending_patterns(
        days_back: int = Query(default=30, ge=7, le=90),
        db: Session = Depends(get_db)
):
    """Анализирует паттерны трат для выявления аномалий и привычек"""
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    # Анализ по дням недели
    weekday_query = """
        SELECT 
            EXTRACT(DOW FROM date) as weekday,
            AVG(amount) as avg_amount,
            COUNT(*) as transaction_count,
            SUM(amount) as total_amount
        FROM transactions
        WHERE type = 'expense' AND date >= :start_date AND date <= :end_date
        GROUP BY EXTRACT(DOW FROM date)
        ORDER BY weekday;
    """

    weekday_result = db.execute(text(weekday_query), {
        "start_date": start_date,
        "end_date": end_date
    }).fetchall()

    weekday_names = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб']
    weekday_patterns = []

    for row in weekday_result:
        weekday_patterns.append({
            "day": weekday_names[int(row.weekday)],
            "avg_amount": float(row.avg_amount),
            "transaction_count": row.transaction_count,
            "total_amount": float(row.total_amount)
        })

    # Анализ по времени (утро, день, вечер)
    time_pattern_query = """
        SELECT 
            CASE 
                WHEN EXTRACT(HOUR FROM time) BETWEEN 6 AND 11 THEN 'morning'
                WHEN EXTRACT(HOUR FROM time) BETWEEN 12 AND 17 THEN 'afternoon'
                WHEN EXTRACT(HOUR FROM time) BETWEEN 18 AND 23 THEN 'evening'
                ELSE 'night'
            END as period,
            COUNT(*) as transaction_count,
            AVG(amount) as avg_amount,
            SUM(amount) as total_amount
        FROM transactions
        WHERE type = 'expense' AND date >= :start_date AND date <= :end_date
        GROUP BY period
        ORDER BY total_amount DESC;
    """

    time_result = db.execute(text(time_pattern_query), {
        "start_date": start_date,
        "end_date": end_date
    }).fetchall()

    time_patterns = []
    period_names = {
        'morning': 'Утром (6-11)',
        'afternoon': 'Днем (12-17)',
        'evening': 'Вечером (18-23)',
        'night': 'Ночью (0-5)'
    }

    for row in time_result:
        time_patterns.append({
            "period": period_names.get(row.period, row.period),
            "transaction_count": row.transaction_count,
            "avg_amount": float(row.avg_amount),
            "total_amount": float(row.total_amount)
        })

    # Выявление аномальных трат (больше среднего + 2 стандартных отклонения)
    anomaly_query = """
        WITH expense_stats AS (
            SELECT 
                AVG(amount) as avg_expense,
                STDDEV(amount) as stddev_expense
            FROM transactions 
            WHERE type = 'expense' AND date >= :start_date AND date <= :end_date
        )
        SELECT 
            t.date, t.amount, t.description,
            c.name as category_name, c.icon, c.color,
            a.name as account_name
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts a ON t.account_from_id = a.id
        CROSS JOIN expense_stats es
        WHERE t.type = 'expense' 
        AND t.date >= :start_date AND t.date <= :end_date
        AND t.amount > (es.avg_expense + 2 * es.stddev_expense)
        ORDER BY t.amount DESC
        LIMIT 5;
    """

    anomaly_result = db.execute(text(anomaly_query), {
        "start_date": start_date,
        "end_date": end_date
    }).fetchall()

    anomalies = []
    for row in anomaly_result:
        anomalies.append({
            "date": str(row.date),
            "amount": float(row.amount),
            "description": row.description,
            "category": {
                "name": row.category_name,
                "icon": row.icon,
                "color": row.color
            },
            "account": row.account_name
        })

    return {
        "weekday_patterns": weekday_patterns,
        "time_patterns": time_patterns,
        "unusual_expenses": anomalies,
        "analysis_period": {"start": str(start_date), "end": str(end_date)}
    }


# Отслеживание подписок (новая функция)
@router.get("/subscriptions")
async def get_subscriptions(db: Session = Depends(get_db)):
    """Выявляет регулярные платежи, которые могут быть подписками"""

    # Ищем транзакции с одинаковыми суммами, которые повторяются регулярно
    subscription_query = """
        WITH transactions_with_lag AS (
        SELECT 
            t.description,
            t.amount,
            c.name AS category_name,
            c.icon,
            c.color,
            a.name AS account_name,
            t.date,
            LAG(t.date) OVER (
                PARTITION BY t.description, t.amount 
                ORDER BY t.date
            ) AS previous_date
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts a ON t.account_from_id = a.id
        WHERE t.type = 'expense' 
          AND t.date >= CURRENT_DATE - INTERVAL '6 months'
    ),
    recurring_payments AS (
        SELECT 
            description,
            amount,
            category_name,
            icon,
            color,
            account_name,
            COUNT(*) AS payment_count,
            MIN(date) AS first_payment,
            MAX(date) AS last_payment,
            AVG(EXTRACT(EPOCH FROM date::timestamp - previous_date::timestamp) / 86400.0) AS avg_days_between
        FROM transactions_with_lag
        WHERE previous_date IS NOT NULL
        GROUP BY description, amount, category_name, icon, color, account_name
        HAVING COUNT(*) >= 3
    )
    SELECT 
        *,
        ROUND(amount * 12) AS estimated_yearly_cost,
        CASE 
            WHEN avg_days_between BETWEEN 28 AND 32 THEN 'monthly'
            WHEN avg_days_between BETWEEN 85 AND 95 THEN 'quarterly'
            WHEN avg_days_between BETWEEN 7 AND 10 THEN 'weekly'
            WHEN avg_days_between BETWEEN 360 AND 370 THEN 'yearly'
            ELSE 'irregular'
        END AS frequency_type
    FROM recurring_payments
    WHERE avg_days_between IS NOT NULL
    ORDER BY amount DESC;

    """

    result = db.execute(text(subscription_query)).fetchall()

    subscriptions = []
    for row in result:
        subscriptions.append({
            "description": row.description,
            "amount": float(row.amount),
            "payment_count": row.payment_count,
            "first_payment": str(row.first_payment),
            "last_payment": str(row.last_payment),
            "avg_days_between": float(row.avg_days_between) if row.avg_days_between else None,
            "frequency_type": row.frequency_type,
            "estimated_yearly_cost": float(row.estimated_yearly_cost),
            "category": {
                "name": row.category_name,
                "icon": row.icon,
                "color": row.color
            },
            "account": row.account_name
        })

    # Подсчитаем общую стоимость подписок
    total_monthly = sum(s["amount"] for s in subscriptions if s["frequency_type"] == "monthly")
    total_yearly = sum(s["estimated_yearly_cost"] for s in subscriptions)

    return {
        "subscriptions": subscriptions,
        "summary": {
            "total_subscriptions": len(subscriptions),
            "estimated_monthly_cost": total_monthly,
            "estimated_yearly_cost": total_yearly
        }
    }


# Улучшенный прогноз (умный анализ)
@router.get("/smart-forecast")
async def get_smart_forecast(
        months_ahead: int = Query(default=3, ge=1, le=6),
        db: Session = Depends(get_db)
):
    """Улучшенный прогноз с учетом сезонности и трендов"""

    # Анализируем последние 6 месяцев для выявления трендов
    analysis_months = 6
    start_analysis = date.today() - timedelta(days=30 * analysis_months)

    # Получаем месячные данные
    monthly_data_query = """
        SELECT 
            DATE_TRUNC('month', date) as month,
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
            SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expense
        FROM transactions
        WHERE date >= :start_date
        GROUP BY DATE_TRUNC('month', date)
        ORDER BY month;
    """

    historical_data = db.execute(text(monthly_data_query), {
        "start_date": start_analysis
    }).fetchall()

    if len(historical_data) < 2:
        return {"error": "Недостаточно данных для прогноза"}

    # Простой линейный тренд
    months = list(range(len(historical_data)))
    expenses = [float(row.expense) for row in historical_data]
    incomes = [float(row.income) for row in historical_data]

    # Вычисляем среднее и тренд
    avg_expense = sum(expenses) / len(expenses)
    avg_income = sum(incomes) / len(incomes)

    # Простой расчет тренда (изменение за месяц)
    if len(expenses) > 1:
        expense_trend = (expenses[-1] - expenses[0]) / (len(expenses) - 1)
        income_trend = (incomes[-1] - incomes[0]) / (len(incomes) - 1)
    else:
        expense_trend = 0
        income_trend = 0

    # Прогноз на будущие месяцы
    forecast_data = []
    for month_offset in range(1, months_ahead + 1):
        projected_expense = avg_expense + (expense_trend * month_offset)
        projected_income = avg_income + (income_trend * month_offset)

        # Не допускаем отрицательные значения
        projected_expense = max(0, projected_expense)
        projected_income = max(0, projected_income)

        future_date = date.today() + timedelta(days=30 * month_offset)
        month_name = future_date.strftime("%Y-%m")

        forecast_data.append({
            "month": month_name,
            "projected_income": projected_income,
            "projected_expense": projected_expense,
            "projected_net": projected_income - projected_expense
        })

    # Анализ рисков
    risk_level = "low"
    if expense_trend > income_trend:
        risk_level = "high" if expense_trend > 1000 else "medium"

    # Рекомендации
    recommendations = []
    if expense_trend > 0:
        recommendations.append("Расходы растут - стоит пересмотреть бюджет")
    if avg_expense > avg_income * 0.8:
        recommendations.append("Низкий уровень сбережений - увеличьте доходы или сократите расходы")

    return {
        "forecast": forecast_data,
        "analysis": {
            "historical_months": len(historical_data),
            "avg_monthly_expense": avg_expense,
            "avg_monthly_income": avg_income,
            "expense_trend": expense_trend,
            "income_trend": income_trend,
            "risk_level": risk_level
        },
        "recommendations": recommendations
    }


# Недостающие эндпоинты из старой версии
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


# Оптимизация существующих эндпоинтов
@router.get("/trends", response_model=List[TrendData])
def get_trends(
        period: str = Query("monthly", pattern="^(daily|weekly|monthly)$"),
        months: int = Query(6, ge=1, le=12),
        db: Session = Depends(get_db)
):
    # Упрощенный и более быстрый запрос
    if period == "monthly":
        query = """
            SELECT
                TO_CHAR(date, 'YYYY-MM') as period,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses,
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                COUNT(*) as transaction_count
            FROM transactions
            WHERE date >= CURRENT_DATE - INTERVAL '{} months'
            GROUP BY TO_CHAR(date, 'YYYY-MM')
            ORDER BY period
        """.format(months)
    elif period == "weekly":
        query = """
            SELECT
                TO_CHAR(date, 'IYYY-IW') as period,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expenses,
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                COUNT(*) as transaction_count
            FROM transactions
            WHERE date >= CURRENT_DATE - INTERVAL '3 months'
            GROUP BY TO_CHAR(date, 'IYYY-IW')
            ORDER BY period
        """
    else:  # daily
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
