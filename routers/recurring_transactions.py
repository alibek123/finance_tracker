from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from dependencies import get_db
from models.schemas import RecurringTransaction, RecurringTransactionCreate, RecurringTransactionUpdate
from utils.enums import TransactionType
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

router = APIRouter(
    prefix="/recurring-transactions",
    tags=["Recurring Transactions"]
)


@router.get("/", response_model=List[Dict[str, Any]])
def get_recurring_transactions(
        active_only: bool = True,
        db: Session = Depends(get_db)
):
    query = """
        SELECT
            rt.*,
            c.name as category_name,
            af.name as account_from_name,
            at.name as account_to_name
        FROM recurring_transactions rt
        LEFT JOIN categories c ON rt.category_id = c.id
        LEFT JOIN accounts af ON rt.account_from_id = af.id
        LEFT JOIN accounts at ON rt.account_to_id = at.id
        WHERE 1=1
    """

    if active_only:
        query += " AND rt.is_active = true"

    query += " ORDER BY rt.created_at DESC"

    result = db.execute(text(query))
    return [dict(row._asdict()) for row in result]


@router.post("/", response_model=RecurringTransaction)
def create_recurring_transaction(
        transaction: RecurringTransactionCreate,
        db: Session = Depends(get_db)
):
    query = """
        INSERT INTO recurring_transactions (
            name, type, amount, account_from_id, account_to_id,
            category_id, frequency, start_date, end_date, is_active
        ) VALUES (
            :name, :transaction_type, :amount, :account_from_id, :account_to_id,
            :category_id, :frequency, :start_date, :end_date, :is_active
        ) RETURNING *
    """
    params = transaction.model_dump()
    params['transaction_type'] = params.pop('type', None)

    result = db.execute(text(query), params)
    db.commit()

    return dict(result.fetchone()._asdict())


@router.post("/{id}/process")
def process_recurring_transaction(
        id: int,
        db: Session = Depends(get_db)
):
    """Создает транзакции для повторяющейся транзакции"""
    trans = db.begin()
    try:
        # Получаем повторяющуюся транзакцию
        rt = db.execute(
            text("SELECT * FROM recurring_transactions WHERE id = :id AND is_active = true FOR UPDATE"),
            {"id": id}
        ).fetchone()

        if not rt:
            raise HTTPException(status_code=404, detail="Повторяющаяся транзакция не найдена или неактивна")

        # Определяем даты для создания транзакций
        last_date = rt['last_created_date'] or rt['start_date']
        current_date = date.today()
        created_count = 0

        # Start from the day after last processed date
        if last_date >= current_date:
            trans.rollback()
            return {"created": 0, "message": "Все транзакции уже созданы"}

        next_date = last_date

        while created_count < 100:  # Limit to prevent infinite loops
            # Calculate next date based on frequency
            if rt['frequency'] == 'daily':
                next_date = next_date + timedelta(days=1)
            elif rt['frequency'] == 'weekly':
                next_date = next_date + timedelta(weeks=1)
            elif rt['frequency'] == 'monthly':
                # Use relativedelta for proper month handling
                next_date = next_date + relativedelta(months=1)
            elif rt['frequency'] == 'quarterly':
                next_date = next_date + relativedelta(months=3)
            elif rt['frequency'] == 'yearly':
                next_date = next_date + relativedelta(years=1)
            else:
                raise ValueError(f"Неизвестная частота: {rt['frequency']}")

            # Check if we've reached the current date
            if next_date > current_date:
                break

            # Check if we've exceeded end_date
            if rt['end_date'] and next_date > rt['end_date']:
                break

            # Create transaction
            transaction_params = {
                "date": next_date,
                "type": rt['type'],
                "amount": rt['amount'],
                "account_from_id": rt['account_from_id'],
                "account_to_id": rt['account_to_id'],
                "category_id": rt['category_id'],
                "description": f"{rt['name']} (автоматически)",
                "is_planned": False
            }

            db.execute(text("""
                INSERT INTO transactions (
                    date, type, amount, account_from_id, account_to_id,
                    category_id, description, is_planned
                ) VALUES (
                    :date, :type, :amount, :account_from_id, :account_to_id,
                    :category_id, :description, :is_planned
                )
            """), transaction_params)

            # Update account balances
            if rt['account_from_id']:
                db.execute(
                    text("UPDATE accounts SET current_balance = current_balance - :amount WHERE id = :id"),
                    {"amount": rt['amount'], "id": rt['account_from_id']}
                )
            if rt['account_to_id']:
                db.execute(
                    text("UPDATE accounts SET current_balance = current_balance + :amount WHERE id = :id"),
                    {"amount": rt['amount'], "id": rt['account_to_id']}
                )

            created_count += 1
            last_date = next_date

        # Update last_created_date
        if created_count > 0:
            db.execute(
                text("UPDATE recurring_transactions SET last_created_date = :date WHERE id = :id"),
                {"date": last_date, "id": id}
            )

        trans.commit()
        return {"created": created_count, "last_processed_date": last_date.isoformat()}

    except Exception as e:
        trans.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке: {str(e)}")


@router.delete("/{id}")
def delete_recurring_transaction(id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("DELETE FROM recurring_transactions WHERE id = :id RETURNING id"),
        {"id": id}
    )
    deleted = result.fetchone()
    if not deleted:
        raise HTTPException(status_code=404, detail="Повторяющаяся транзакция не найдена")
    db.commit()
    return {"message": "Повторяющаяся транзакция удалена"}


@router.put("/{id}", response_model=RecurringTransaction)
def update_recurring_transaction(
        id: int,
        recurring_update: RecurringTransactionUpdate,
        db: Session = Depends(get_db)
):
    update_data = recurring_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    # Special handling for 'type' field
    if 'type' in update_data:
        update_data['transaction_type'] = update_data.pop('type')

    update_fields = []
    params = {"id": id}

    for field, value in update_data.items():
        update_fields.append(f"{field} = :{field}")
        params[field] = value

    query = f"""
        UPDATE recurring_transactions
        SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
        WHERE id = :id
        RETURNING *
    """

    result = db.execute(text(query), params)
    db.commit()

    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Повторяющаяся транзакция не найдена")

    return dict(row._asdict())
