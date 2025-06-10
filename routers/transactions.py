from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional

from dependencies import get_db
from models.schemas import Transaction, TransactionCreate, TransactionUpdate

router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"]
)


# You will need to implement GET, POST, PUT, DELETE for transactions here.
# The original search endpoint is moved to data_ops.py.

@router.get("/", response_model=List[Transaction])
def get_all_transactions(
        limit: int = Query(default=50, le=500),
        offset: int = 0,
        db: Session = Depends(get_db)
):
    query = """
        SELECT
            t.*, -- Now t.date will be returned
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
        GROUP BY t.id, c.name, c.icon, c.color, sc.name, af.name, at.name
        ORDER BY t.date DESC -- Only order by date now
        LIMIT :limit OFFSET :offset
    """
    result = db.execute(text(query), {"limit": limit, "offset": offset})
    return [dict(row._asdict()) for row in result]


@router.post("/", response_model=Transaction)
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)):
    trans = db.begin()
    try:
        # Insert transaction
        query = """
            INSERT INTO transactions (
                date, type, amount, account_from_id, account_to_id,
                category_id, subcategory_id, description, notes, is_planned
            ) VALUES (
                :date, :transaction_type, :amount, :account_from_id, :account_to_id,
                :category_id, :subcategory_id, :description, :notes, :is_planned
            ) RETURNING id, date, type, amount, account_from_id, account_to_id, category_id, subcategory_id, description, notes, is_planned,  created_at, updated_at
        """
        params = transaction.model_dump(exclude={"tag_ids"})
        params['transaction_type'] = params.pop('type', None)  # Renaming 'type' for SQL
        result = db.execute(text(query), params)
        new_transaction = result.fetchone()

        if not new_transaction:
            raise HTTPException(status_code=500, detail="Failed to create transaction")

        transaction_id = new_transaction.id

        # Handle tags
        if transaction.tag_ids:
            tag_insert_values = [
                {"transaction_id": transaction_id, "tag_id": tag_id}
                for tag_id in transaction.tag_ids
            ]
            db.execute(text("""
                INSERT INTO transaction_tags (transaction_id, tag_id)
                VALUES (:transaction_id, :tag_id)
            """), tag_insert_values)

        # Update account balances
        if transaction.account_from_id:
            db.execute(
                text(
                    "UPDATE accounts SET current_balance = current_balance - :amount, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                {"amount": transaction.amount, "id": transaction.account_from_id}
            )
        if transaction.account_to_id:
            db.execute(
                text(
                    "UPDATE accounts SET current_balance = current_balance + :amount, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                {"amount": transaction.amount, "id": transaction.account_to_id}
            )

        trans.commit()
        return dict(new_transaction._asdict())

    except Exception as e:
        trans.rollback()
        print(e)
        raise HTTPException(status_code=500, detail=f"Failed to create transaction: {str(e)}")


@router.get("/{transaction_id}", response_model=Transaction)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
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
        WHERE t.id = :id
        GROUP BY t.id, c.name, c.icon, c.color, sc.name, af.name, at.name
    """
    result = db.execute(text(query), {"id": transaction_id}).fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Транзакция не найдена")
    return dict(result._asdict())


@router.put("/{transaction_id}", response_model=Transaction)
def update_transaction(
        transaction_id: int,
        transaction_update: TransactionUpdate,
        db: Session = Depends(get_db)
):
    trans = db.begin()
    try:
        # Get current transaction data to reverse old balance changes
        old_transaction = db.execute(
            text("SELECT * FROM transactions WHERE id = :id FOR UPDATE"),
            {"id": transaction_id}
        ).fetchone()

        if not old_transaction:
            raise HTTPException(status_code=404, detail="Транзакция не найдена")

        # Revert old balance changes
        if old_transaction.account_from_id:
            db.execute(
                text("UPDATE accounts SET current_balance = current_balance + :amount WHERE id = :id"),
                {"amount": old_transaction.amount, "id": old_transaction.account_from_id}
            )
        if old_transaction.account_to_id:
            db.execute(
                text("UPDATE accounts SET current_balance = current_balance - :amount WHERE id = :id"),
                {"amount": old_transaction.amount, "id": old_transaction.account_to_id}
            )

        update_data = transaction_update.model_dump(exclude_unset=True)
        if not update_data and not transaction_update.tag_ids:
            raise HTTPException(status_code=400, detail="Нет данных для обновления")

        # Update transaction details (excluding tags for now)
        transaction_fields_to_update = {k: v for k, v in update_data.items() if k != "tag_ids"}
        if transaction_fields_to_update:
            update_fields = []
            params = {"id": transaction_id}
            for field, value in transaction_fields_to_update.items():
                update_fields.append(f"{field} = :{field}")
                params[field] = value
            query = f"""
                UPDATE transactions
                SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                RETURNING *
            """
            result = db.execute(text(query), params)
            updated_transaction = result.fetchone()
        else:
            updated_transaction = old_transaction  # If only tags are updated

        # Handle tag updates: delete old tags and insert new ones
        if transaction_update.tag_ids is not None:  # If tag_ids is explicitly provided
            db.execute(
                text("DELETE FROM transaction_tags WHERE transaction_id = :transaction_id"),
                {"transaction_id": transaction_id}
            )
            if transaction_update.tag_ids:
                tag_insert_values = [
                    {"transaction_id": transaction_id, "tag_id": tag_id}
                    for tag_id in transaction_update.tag_ids
                ]
                db.execute(text("""
                    INSERT INTO transaction_tags (transaction_id, tag_id)
                    VALUES (:transaction_id, :tag_id)
                """), tag_insert_values)

        # Apply new balance changes based on the updated transaction
        current_transaction_data = db.execute(
            text("SELECT * FROM transactions WHERE id = :id"),
            {"id": transaction_id}
        ).fetchone()

        if current_transaction_data.account_from_id:
            db.execute(
                text(
                    "UPDATE accounts SET current_balance = current_balance - :amount, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                {"amount": current_transaction_data.amount, "id": current_transaction_data.account_from_id}
            )
        if current_transaction_data.account_to_id:
            db.execute(
                text(
                    "UPDATE accounts SET current_balance = current_balance + :amount, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                {"amount": current_transaction_data.amount, "id": current_transaction_data.account_to_id}
            )

        trans.commit()
        return dict(current_transaction_data._asdict())

    except Exception as e:
        trans.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update transaction: {str(e)}")


@router.delete("/{transaction_id}")
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    trans = db.begin()
    try:
        # Get transaction details to revert balance changes
        transaction_to_delete = db.execute(
            text("SELECT * FROM transactions WHERE id = :id FOR UPDATE"),
            {"id": transaction_id}
        ).fetchone()

        if not transaction_to_delete:
            raise HTTPException(status_code=404, detail="Транзакция не найдена")

        # Revert balance changes
        if transaction_to_delete.account_from_id:
            db.execute(
                text("UPDATE accounts SET current_balance = current_balance + :amount WHERE id = :id"),
                {"amount": transaction_to_delete.amount, "id": transaction_to_delete.account_from_id}
            )
        if transaction_to_delete.account_to_id:
            db.execute(
                text("UPDATE accounts SET current_balance = current_balance - :amount WHERE id = :id"),
                {"amount": transaction_to_delete.amount, "id": transaction_to_delete.account_to_id}
            )

        # Delete associated tags first
        db.execute(
            text("DELETE FROM transaction_tags WHERE transaction_id = :id"),
            {"id": transaction_id}
        )

        # Delete the transaction
        result = db.execute(
            text("DELETE FROM transactions WHERE id = :id RETURNING id"),
            {"id": transaction_id}
        )
        deleted = result.fetchone()
        if not deleted:
            # This case should ideally not be reached if transaction_to_delete was found
            raise HTTPException(status_code=404, detail="Транзакция не найдена после попытки удаления")

        trans.commit()
        return {"message": "Транзакция удалена и балансы счетов скорректированы"}

    except Exception as e:
        trans.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении транзакции: {str(e)}")


@router.get("/search/transactions")
def search_transactions(
        q: Optional[str] = Query(None, description="Поисковый запрос"),
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        min_amount: Optional[Decimal] = None,
        max_amount: Optional[Decimal] = None,
        account_ids: Optional[str] = Query(None),  # Changed to str to handle comma-separated values
        category_ids: Optional[str] = Query(None),  # Changed to str
        tag_ids: Optional[str] = Query(None),  # Changed to str
        transaction_types: Optional[str] = Query(None),  # Changed to str
        limit: int = Query(default=50, le=500),
        offset: int = 0,
        db: Session = Depends(get_db)
):
    # Parse comma-separated IDs
    account_ids_list = [int(x) for x in account_ids.split(',')] if account_ids else None
    category_ids_list = [int(x) for x in category_ids.split(',')] if category_ids else None
    tag_ids_list = [int(x) for x in tag_ids.split(',')] if tag_ids else None
    transaction_types_list = transaction_types.split(',') if transaction_types else None

    query = """
        SELECT DISTINCT
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

    # Текстовый поиск
    if q:
        query += """
            AND (
                t.description ILIKE :search_query
                OR t.notes ILIKE :search_query
                OR c.name ILIKE :search_query
                OR af.name ILIKE :search_query
                OR at.name ILIKE :search_query
            )
        """
        params["search_query"] = f"%{q}%"

    # Фильтры по датам
    if start_date:
        query += " AND t.date >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND t.date <= :end_date"
        params["end_date"] = end_date

    # Фильтры по суммам
    if min_amount is not None:
        query += " AND t.amount >= :min_amount"
        params["min_amount"] = min_amount

    if max_amount is not None:
        query += " AND t.amount <= :max_amount"
        params["max_amount"] = max_amount

    # Фильтры по счетам
    if account_ids_list:
        query += " AND (t.account_from_id = ANY(:account_ids) OR t.account_to_id = ANY(:account_ids))"
        params["account_ids"] = account_ids_list

    # Фильтры по категориям
    if category_ids_list:
        query += " AND (t.category_id = ANY(:category_ids) OR t.subcategory_id = ANY(:category_ids))"
        params["category_ids"] = category_ids_list

    # Фильтры по типам
    if transaction_types_list:
        query += " AND t.type = ANY(:transaction_types)"
        params["transaction_types"] = transaction_types_list

    # Фильтры по тегам
    if tag_ids_list:
        query += " AND EXISTS (SELECT 1 FROM transaction_tags tt2 WHERE tt2.transaction_id = t.id AND tt2.tag_id = ANY(:tag_ids))"
        params["tag_ids"] = tag_ids_list

    query += """
        GROUP BY t.id, c.name, c.icon, c.color, sc.name, af.name, at.name
        ORDER BY t.date DESC
        LIMIT :limit OFFSET :offset
    """

    result = db.execute(text(query), params)

    # Получаем общее количество
    count_query = """
        SELECT COUNT(DISTINCT t.id)
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts af ON t.account_from_id = af.id
        LEFT JOIN accounts at ON t.account_to_id = at.id
        LEFT JOIN transaction_tags tt ON t.id = tt.transaction_id
        WHERE 1=1
    """

    # Re-apply filters for the count query
    count_params = {k: v for k, v in params.items() if k not in ['limit', 'offset']}

    if q:
        count_query += """
            AND (
                t.description ILIKE :search_query
                OR t.notes ILIKE :search_query
                OR c.name ILIKE :search_query
                OR af.name ILIKE :search_query
                OR at.name ILIKE :search_query
            )
        """
    if start_date:
        count_query += " AND t.date >= :start_date"
    if end_date:
        count_query += " AND t.date <= :end_date"
    if min_amount is not None:
        count_query += " AND t.amount >= :min_amount"
    if max_amount is not None:
        count_query += " AND t.amount <= :max_amount"
    if account_ids_list:
        count_query += " AND (t.account_from_id = ANY(:account_ids) OR t.account_to_id = ANY(:account_ids))"
    if category_ids_list:
        count_query += " AND (t.category_id = ANY(:category_ids) OR t.subcategory_id = ANY(:category_ids))"
    if transaction_types_list:
        count_query += " AND t.type = ANY(:transaction_types)"
    if tag_ids_list:
        count_query += " AND EXISTS (SELECT 1 FROM transaction_tags tt2 WHERE tt2.transaction_id = t.id AND tt2.tag_id = ANY(:tag_ids))"

    total_count = db.execute(text(count_query), count_params).scalar()

    transactions = [dict(row._asdict()) for row in result]

    return {
        "transactions": transactions,
        "total": total_count,
        "limit": limit,
        "offset": offset
    }
