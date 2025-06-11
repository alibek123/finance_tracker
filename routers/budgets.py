from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from dependencies import get_db
from models.schemas import Budget, BudgetCreate, BudgetUpdate
from utils.enums import BudgetPeriod
from datetime import date, datetime, timedelta
from decimal import Decimal

router = APIRouter(
    prefix="/budgets",
    tags=["Budgets"]
)


def calculate_budget_period_dates(budget_period: str, start_date: date) -> tuple[date, date]:
    """Calculate the current period dates based on budget period type."""
    today = date.today()

    if budget_period == 'daily':
        return today, today
    elif budget_period == 'weekly':
        # Find the start of the current week
        days_since_start = (today - start_date).days
        weeks_passed = days_since_start // 7
        current_week_start = start_date + timedelta(weeks=weeks_passed)
        current_week_end = current_week_start + timedelta(days=6)
        return current_week_start, min(current_week_end, today)
    elif budget_period == 'monthly':
        # Current month
        period_start = date(today.year, today.month, 1)
        # Last day of current month
        if today.month == 12:
            period_end = date(today.year, 12, 31)
        else:
            period_end = date(today.year, today.month + 1, 1) - timedelta(days=1)
        return period_start, period_end
    elif budget_period == 'quarterly':
        # Current quarter
        quarter = (today.month - 1) // 3
        quarter_start_month = quarter * 3 + 1
        period_start = date(today.year, quarter_start_month, 1)
        # End of quarter
        quarter_end_month = quarter_start_month + 2
        if quarter_end_month > 12:
            period_end = date(today.year, 12, 31)
        else:
            period_end = date(today.year, quarter_end_month + 1, 1) - timedelta(days=1)
        return period_start, period_end
    elif budget_period == 'yearly':
        # Current year
        return date(today.year, 1, 1), date(today.year, 12, 31)
    else:
        # Default to monthly
        return date(today.year, today.month, 1), today


@router.get("/", response_model=List[Dict[str, Any]])
def get_budgets(
        include_inactive: bool = False,
        db: Session = Depends(get_db)
):
    query = """
        SELECT
            b.*,
            c.name as category_name,
            c.icon as category_icon,
            c.color as category_color
        FROM budgets b
        LEFT JOIN categories c ON b.category_id = c.id
        WHERE 1=1
    """
    params = {}
    if not include_inactive:
        query += " AND b.is_active = true"
    query += " ORDER BY b.start_date DESC"

    result = db.execute(text(query), params)
    budgets = [dict(row._asdict()) for row in result]

    # Calculate spent amount for each budget
    for budget in budgets:
        period_start, period_end = calculate_budget_period_dates(budget['period'], budget['start_date'])

        spent_query = """
            SELECT COALESCE(SUM(amount), 0) as spent
            FROM transactions
            WHERE category_id = :category_id
              AND type = 'expense'
              AND date >= :start_date
              AND date <= :end_date
        """

        spent_result = db.execute(text(spent_query), {
            'category_id': budget['category_id'],
            'start_date': period_start,
            'end_date': period_end
        }).fetchone()

        budget['spent_amount'] = float(spent_result.spent) if spent_result else 0
        budget['usage_percentage'] = round((budget['spent_amount'] / float(budget['amount']) * 100), 1) if budget[
                                                                                                               'amount'] > 0 else 0
        budget['period_start'] = period_start
        budget['period_end'] = period_end

    return budgets


@router.post("/", response_model=Budget)
def create_budget(budget: BudgetCreate, db: Session = Depends(get_db)):
    # Set start_date to current date if not provided
    if not hasattr(budget, 'start_date') or not budget.start_date:
        budget.start_date = date.today()

    query = """
        INSERT INTO budgets (name, category_id, amount, period, start_date, end_date, is_active)
        VALUES (:name, :category_id, :amount, :period, :start_date, :end_date, :is_active)
        RETURNING *
    """
    params = budget.model_dump()
    result = db.execute(text(query), params)
    db.commit()
    return dict(result.fetchone()._asdict())


@router.put("/{budget_id}", response_model=Budget)
def update_budget(
        budget_id: int,
        budget_update: BudgetUpdate,
        db: Session = Depends(get_db)
):
    update_data = budget_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    update_fields = []
    params = {"id": budget_id}

    for field, value in update_data.items():
        update_fields.append(f"{field} = :{field}")
        params[field] = value

    query = f"""
        UPDATE budgets
        SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
        WHERE id = :id
        RETURNING *
    """

    result = db.execute(text(query), params)
    db.commit()

    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Бюджет не найден")

    return dict(row._asdict())


@router.delete("/{budget_id}")
def delete_budget(budget_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("DELETE FROM budgets WHERE id = :id RETURNING id"),
        {"id": budget_id}
    )
    deleted = result.fetchone()
    if not deleted:
        raise HTTPException(status_code=404, detail="Бюджет не найден")
    db.commit()
    return {"message": "Бюджет удален"}


@router.get("/{budget_id}/summary")
def get_budget_summary(budget_id: int, db: Session = Depends(get_db)):
    budget = db.execute(
        text("SELECT * FROM budgets WHERE id = :id"),
        {"id": budget_id}
    ).fetchone()

    if not budget:
        raise HTTPException(status_code=404, detail="Бюджет не найден")

    budget_dict = dict(budget._asdict())

    # Calculate current period dates
    period_start, period_end = calculate_budget_period_dates(budget.period, budget.start_date)

    # Calculate expenses for the budget period and category
    expenses_query = """
        SELECT COALESCE(SUM(amount), 0) as total_spent
        FROM transactions
        WHERE category_id = :category_id
          AND type = 'expense'
          AND date >= :start_date
          AND date <= :end_date
    """

    result = db.execute(
        text(expenses_query),
        {
            "category_id": budget.category_id,
            "start_date": period_start,
            "end_date": period_end
        }
    )

    total_spent = float(result.scalar() or 0)

    # Get category info
    category = db.execute(
        text("SELECT name, icon, color FROM categories WHERE id = :id"),
        {"id": budget.category_id}
    ).fetchone()

    return {
        "budget": budget_dict,
        "category": dict(category._asdict()) if category else None,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "total_spent": total_spent,
        "remaining": float(budget.amount) - total_spent,
        "usage_percentage": round((total_spent / float(budget.amount) * 100), 1) if budget.amount > 0 else 0,
        "is_over_budget": total_spent > float(budget.amount)
    }
