from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from dependencies import get_db
from models.schemas import Account, AccountCreate, AccountUpdate
from utils.enums import AccountType
from decimal import Decimal

router = APIRouter(
    prefix="/accounts",
    tags=["Accounts"]
)


@router.get("/", response_model=List[Dict[str, Any]])
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


@router.post("/", response_model=Account)
def create_account(account: AccountCreate, db: Session = Depends(get_db)):
    query = """
        INSERT INTO accounts (name, type, initial_balance, current_balance, credit_limit, color, icon, is_active, currency)
        VALUES (:name, :account_type, :initial_balance, :initial_balance, :credit_limit, :color, :icon, :is_active, :currency)
        RETURNING *
    """
    params = account.model_dump()
    params['account_type'] = params.pop('type', None)  # Renaming 'type' to 'account_type' for SQL
    result = db.execute(text(query), params)
    db.commit()
    return dict(result.fetchone()._asdict())


@router.put("/{account_id}", response_model=Account)
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


@router.delete("/{account_id}")
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


@router.post("/{account_id}/adjust-balance")
def adjust_account_balance(
        account_id: int,
        new_balance: Decimal = Query(..., description="Новый баланс"),
        description: Optional[str] = None,
        db: Session = Depends(get_db)
):
    trans = db.begin()
    try:
        # Получаем текущий баланс
        current = db.execute(
            text("SELECT current_balance FROM accounts WHERE id = :id FOR UPDATE"),
            # FOR UPDATE to prevent race conditions
            {"id": account_id}
        ).scalar()

        if current is None:
            raise HTTPException(status_code=404, detail="Счет не найден")

        difference = new_balance - current

        if difference == 0:
            trans.rollback()
            return {"message": "Баланс не изменился"}

        # Находим категорию "Корректировка"
        category_id = db.execute(
            text("SELECT id FROM categories WHERE name = 'Корректировка' AND type = 'transfer'")
        ).scalar()

        if not category_id:
            # Create a default "Adjustment" category if it doesn't exist
            new_cat = db.execute(
                text("""
                    INSERT INTO categories (name, type, icon, color)
                    VALUES ('Корректировка', 'transfer', '🔄', '#8898aa')
                    RETURNING id
                """)
            ).fetchone()
            category_id = new_cat[0]

        # Создаем транзакцию корректировки
        transaction_type = "correction"
        # Determine which account field to use for the adjustment transaction
        account_from_id = account_id if difference < 0 else None
        account_to_id = account_id if difference > 0 else None

        db.execute(text(f"""
            INSERT INTO transactions (
                date, type, amount, account_from_id, account_to_id,
                category_id, description, notes, is_planned
            ) VALUES (
                CURRENT_DATE, :type, :amount, :account_from_id, :account_to_id,
                :category_id, :description, 'Корректировка баланса', false
            )
        """), {
            "type": transaction_type,
            "amount": abs(difference),  # Amount should be positive for transaction
            "account_from_id": account_from_id,
            "account_to_id": account_to_id,
            "category_id": category_id,
            "description": description or f"Корректировка баланса на {difference:+.2f} {current}",
        })

        # Update the account balance
        db.execute(
            text("UPDATE accounts SET current_balance = :new_balance, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
            {"new_balance": new_balance, "id": account_id}
        )

        trans.commit()
        return {"message": f"Баланс счета {account_id} скорректирован до {new_balance}", "old_balance": current,
                "new_balance": new_balance, "difference": difference}

    except HTTPException:
        trans.rollback()
        raise
    except Exception as e:
        trans.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при корректировке баланса: {str(e)}")
