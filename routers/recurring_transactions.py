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


# Функция для добавления столбца last_created_date если его нет
def ensure_last_created_date_column(db: Session):
    """Проверяет и добавляет столбец last_created_date если его нет"""
    try:
        # Проверяем, существует ли столбец
        check_column = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'recurring_transactions' 
            AND column_name = 'last_created_date'
            AND table_schema = 'finance';
        """
        result = db.execute(text(check_column)).fetchone()

        if not result:
            # Добавляем столбец если его нет
            add_column = """
                ALTER TABLE recurring_transactions 
                ADD COLUMN last_created_date DATE;
            """
            db.execute(text(add_column))
            db.commit()
            print("Added last_created_date column to recurring_transactions table")
    except Exception as e:
        print(f"Column might already exist or error: {e}")
        db.rollback()


@router.get("/", response_model=List[Dict[str, Any]])
def get_recurring_transactions(
        active_only: bool = True,
        db: Session = Depends(get_db)
):
    # Убеждаемся что столбец существует
    ensure_last_created_date_column(db)

    query = """
        SELECT
            rt.*,
            c.name as category_name,
            c.icon as category_icon,
            c.color as category_color,
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
    ensure_last_created_date_column(db)

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
    """Создает транзакции для повторяющейся транзакции с улучшенной логикой"""
    ensure_last_created_date_column(db)

    trans = db.begin()
    try:
        # Получаем повторяющуюся транзакцию
        rt = db.execute(
            text("SELECT * FROM recurring_transactions WHERE id = :id AND is_active = true FOR UPDATE"),
            {"id": id}
        ).fetchone()

        if not rt:
            raise HTTPException(status_code=404, detail="Повторяющаяся транзакция не найдена или неактивна")

        # Определяем начальную дату для создания транзакций
        last_date = rt.last_created_date or rt.start_date
        current_date = date.today()
        created_count = 0

        # Если уже все транзакции созданы на сегодня
        if last_date >= current_date:
            trans.rollback()
            return {"created": 0, "message": "Все транзакции уже созданы на сегодня"}

        # Начинаем с последней обработанной даты
        next_date = last_date
        actual_last_date = last_date

        # Создаем транзакции до текущей даты
        while created_count < 100:  # Ограничение для предотвращения бесконечного цикла
            # Вычисляем следующую дату в зависимости от частоты
            if rt.frequency == 'daily':
                next_date = next_date + timedelta(days=1)
            elif rt.frequency == 'weekly':
                next_date = next_date + timedelta(weeks=1)
            elif rt.frequency == 'monthly':
                next_date = next_date + relativedelta(months=1)
            elif rt.frequency == 'quarterly':
                next_date = next_date + relativedelta(months=3)
            elif rt.frequency == 'yearly':
                next_date = next_date + relativedelta(years=1)
            else:
                raise ValueError(f"Неизвестная частота: {rt.frequency}")

            # Проверяем, не превысили ли текущую дату
            if next_date > current_date:
                break

            # Проверяем, не превысили ли конечную дату
            if rt.end_date and next_date > rt.end_date:
                break

            # Создаем транзакцию
            transaction_params = {
                "date": next_date,
                "type": rt.type,
                "amount": rt.amount,
                "account_from_id": rt.account_from_id,
                "account_to_id": rt.account_to_id,
                "category_id": rt.category_id,
                "description": f"{rt.name} (автоматически)",
                "is_planned": False,
                "is_recurring": True,
                "recurring_id": rt.id
            }

            # Создаем транзакцию
            db.execute(text("""
                INSERT INTO transactions (
                    date, type, amount, account_from_id, account_to_id,
                    category_id, description, is_planned, is_recurring, recurring_id
                ) VALUES (
                    :date, :type, :amount, :account_from_id, :account_to_id,
                    :category_id, :description, :is_planned, :is_recurring, :recurring_id
                )
            """), transaction_params)

            # Обновляем балансы счетов
            if rt.account_from_id:
                db.execute(
                    text("UPDATE accounts SET current_balance = current_balance - :amount WHERE id = :id"),
                    {"amount": rt.amount, "id": rt.account_from_id}
                )
            if rt.account_to_id:
                db.execute(
                    text("UPDATE accounts SET current_balance = current_balance + :amount WHERE id = :id"),
                    {"amount": rt.amount, "id": rt.account_to_id}
                )

            created_count += 1
            actual_last_date = next_date

        # Обновляем last_created_date только если создали транзакции
        if created_count > 0:
            db.execute(
                text("UPDATE recurring_transactions SET last_created_date = :date WHERE id = :id"),
                {"date": actual_last_date, "id": id}
            )

        trans.commit()
        return {
            "created": created_count,
            "last_processed_date": actual_last_date.isoformat(),
            "message": f"Создано {created_count} транзакций"
        }

    except Exception as e:
        trans.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке: {str(e)}")


@router.post("/process-all")
def process_all_recurring_transactions(db: Session = Depends(get_db)):
    """Обрабатывает все активные повторяющиеся транзакции"""
    ensure_last_created_date_column(db)

    # Получаем все активные повторяющиеся транзакции
    active_recurring = db.execute(
        text("SELECT id FROM recurring_transactions WHERE is_active = true")
    ).fetchall()

    total_created = 0
    results = []

    for row in active_recurring:
        try:
            # Вызываем обработку для каждой транзакции
            result = process_recurring_transaction(row.id, db)
            total_created += result["created"]
            if result["created"] > 0:
                results.append(f"ID {row.id}: {result['created']} транзакций")
        except Exception as e:
            results.append(f"ID {row.id}: Ошибка - {str(e)}")

    return {
        "total_created": total_created,
        "processed_count": len(active_recurring),
        "details": results
    }


@router.get("/{id}/preview")
def preview_recurring_transactions(
        id: int,
        months_ahead: int = Query(default=3, ge=1, le=12),
        db: Session = Depends(get_db)
):
    """Предварительный просмотр будущих транзакций"""
    ensure_last_created_date_column(db)

    rt = db.execute(
        text("SELECT * FROM recurring_transactions WHERE id = :id"),
        {"id": id}
    ).fetchone()

    if not rt:
        raise HTTPException(status_code=404, detail="Повторяющаяся транзакция не найдена")

    # Генерируем предварительный список на N месяцев вперед
    start_date = rt.last_created_date or rt.start_date or date.today()
    end_preview = date.today() + relativedelta(months=months_ahead)

    preview_dates = []
    current_date = start_date

    while len(preview_dates) < 50 and current_date <= end_preview:
        if rt.frequency == 'daily':
            current_date = current_date + timedelta(days=1)
        elif rt.frequency == 'weekly':
            current_date = current_date + timedelta(weeks=1)
        elif rt.frequency == 'monthly':
            current_date = current_date + relativedelta(months=1)
        elif rt.frequency == 'quarterly':
            current_date = current_date + relativedelta(months=3)
        elif rt.frequency == 'yearly':
            current_date = current_date + relativedelta(years=1)

        # Проверяем конечную дату
        if rt.end_date and current_date > rt.end_date:
            break

        preview_dates.append({
            "date": current_date.isoformat(),
            "amount": float(rt.amount),
            "description": f"{rt.name} (автоматически)"
        })

    return {
        "recurring_transaction": {
            "id": rt.id,
            "name": rt.name,
            "amount": float(rt.amount),
            "frequency": rt.frequency,
            "type": rt.type
        },
        "preview_transactions": preview_dates,
        "preview_period": f"{months_ahead} месяцев",
        "total_amount": sum(t["amount"] for t in preview_dates)
    }


@router.put("/{id}/toggle")
def toggle_recurring_transaction(
        id: int,
        active: bool = Query(...),
        db: Session = Depends(get_db)
):
    """Активирует или деактивирует повторяющуюся транзакцию"""
    result = db.execute(
        text("UPDATE recurring_transactions SET is_active = :active WHERE id = :id RETURNING id, name, is_active"),
        {"id": id, "active": active}
    ).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Повторяющаяся транзакция не найдена")

    db.commit()

    status = "активирована" if active else "деактивирована"
    return {
        "id": result.id,
        "name": result.name,
        "is_active": result.is_active,
        "message": f"Повторяющаяся транзакция '{result.name}' {status}"
    }


@router.delete("/{id}")
def delete_recurring_transaction(id: int, db: Session = Depends(get_db)):
    # Проверяем, есть ли связанные транзакции
    linked_count = db.execute(
        text("SELECT COUNT(*) FROM transactions WHERE recurring_id = :id"),
        {"id": id}
    ).scalar()

    if linked_count > 0:
        # Вместо удаления, деактивируем
        result = db.execute(
            text("UPDATE recurring_transactions SET is_active = false WHERE id = :id RETURNING name"),
            {"id": id}
        ).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Повторяющаяся транзакция не найдена")

        db.commit()
        return {
            "message": f"Повторяющаяся транзакция '{result.name}' деактивирована (есть {linked_count} связанных транзакций)"
        }

    # Удаляем если нет связанных транзакций
    result = db.execute(
        text("DELETE FROM recurring_transactions WHERE id = :id RETURNING name"),
        {"id": id}
    ).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Повторяющаяся транзакция не найдена")

    db.commit()
    return {"message": f"Повторяющаяся транзакция '{result.name}' удалена"}


@router.put("/{id}", response_model=RecurringTransaction)
def update_recurring_transaction(
        id: int,
        recurring_update: RecurringTransactionUpdate,
        db: Session = Depends(get_db)
):
    ensure_last_created_date_column(db)

    update_data = recurring_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    # Специальная обработка поля 'type'
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
