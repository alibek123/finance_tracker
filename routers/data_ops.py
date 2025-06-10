from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from dependencies import get_db
from models.schemas import TransactionType
from datetime import date, datetime
from decimal import Decimal
import io
import csv
import json

router = APIRouter(
    prefix="/data",
    tags=["Data Operations"]
)


@router.get("/search/transactions")
def search_transactions(
        q: Optional[str] = Query(None, description="Поисковый запрос"),
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        min_amount: Optional[Decimal] = None,
        max_amount: Optional[Decimal] = None,
        account_ids: Optional[List[int]] = Query(None),
        category_ids: Optional[List[int]] = Query(None),
        tag_ids: Optional[List[int]] = Query(None),
        transaction_types: Optional[List[TransactionType]] = Query(None),
        limit: int = Query(default=50, le=500),
        offset: int = 0,
        db: Session = Depends(get_db)
):
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
    if account_ids:
        query += " AND (t.account_from_id = ANY(:account_ids) OR t.account_to_id = ANY(:account_ids))"
        params["account_ids"] = account_ids

    # Фильтры по категориям
    if category_ids:
        query += " AND (t.category_id = ANY(:category_ids) OR t.subcategory_id = ANY(:category_ids))"
        params["category_ids"] = category_ids

    # Фильтры по типам
    if transaction_types:
        # Convert list of Enums to list of strings
        transaction_type_values = [ttype.value for ttype in transaction_types]
        query += " AND t.type = ANY(:transaction_types)"
        params["transaction_types"] = transaction_type_values

    # Фильтры по тегам
    if tag_ids:
        query += " AND EXISTS (SELECT 1 FROM transaction_tags tt2 WHERE tt2.transaction_id = t.id AND tt2.tag_id = ANY(:tag_ids))"
        params["tag_ids"] = tag_ids

    query += """
        GROUP BY t.id, c.name, c.icon, c.color, sc.name, af.name, at.name
        ORDER BY t.date DESC, t.time DESC
        LIMIT :limit OFFSET :offset
    """

    result = db.execute(text(query), params)

    # Получаем общее количество
    # To get total count, remove LIMIT, OFFSET, and GROUP BY from the main query.
    # A more robust way would be to create a separate count query or use SQLAlchemy ORM's count.
    count_query_base = """
        SELECT COUNT(DISTINCT t.id)
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts af ON t.account_from_id = af.id
        LEFT JOIN accounts at ON t.account_to_id = at.id
        LEFT JOIN transaction_tags tt ON t.id = tt.transaction_id
        LEFT JOIN tags tg ON tt.tag_id = tg.id
        WHERE 1=1
    """
    # Re-apply filters for the count query
    count_query = count_query_base
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
    if account_ids:
        count_query += " AND (t.account_from_id = ANY(:account_ids) OR t.account_to_id = ANY(:account_ids))"
    if category_ids:
        count_query += " AND (t.category_id = ANY(:category_ids) OR t.subcategory_id = ANY(:category_ids))"
    if transaction_types:
        count_query += " AND t.type = ANY(:transaction_types)"
    if tag_ids:
        count_query += " AND EXISTS (SELECT 1 FROM transaction_tags tt2 WHERE tt2.transaction_id = t.id AND tt2.tag_id = ANY(:tag_ids))"

    total_count = db.execute(text(count_query), count_params).scalar()

    transactions = [dict(row._asdict()) for row in result]

    return {
        "transactions": transactions,
        "total": total_count,
        "limit": limit,
        "offset": offset
    }


@router.get("/export/{format}")
def export_data(
        format: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        db: Session = Depends(get_db)
):
    if format not in ["csv", "json"]:
        raise HTTPException(status_code=400, detail="Формат должен быть csv или json")

    # Получаем транзакции
    query = """
        SELECT
            t.date,
            t.type,
            t.amount,
            t.description,
            t.notes,
            c.name as category,
            af.name as account_from,
            at.name as account_to,
            array_agg(DISTINCT tg.name) FILTER (WHERE tg.name IS NOT NULL) as tags
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts af ON t.account_from_id = af.id
        LEFT JOIN accounts at ON t.account_to_id = at.id
        LEFT JOIN transaction_tags tt ON t.id = tt.transaction_id
        LEFT JOIN tags tg ON tt.tag_id = tg.id
        WHERE 1=1
    """
    params = {}

    if start_date:
        query += " AND t.date >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND t.date <= :end_date"
        params["end_date"] = end_date

    query += " GROUP BY t.id, t.date, t.type, t.amount, t.description, t.notes, c.name, af.name, at.name"
    query += " ORDER BY t.date DESC"

    result = db.execute(text(query), params)
    transactions = [dict(row._asdict()) for row in result]

    if format == "csv":
        output = io.StringIO()
        fieldnames = [
            "date", "type", "amount", "description", "notes",
            "category", "account_from", "account_to", "tags"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()

        for t in transactions:
            t['tags'] = ', '.join(t['tags']) if t['tags'] else ''
            writer.writerow(t)

        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=transactions_{datetime.now().strftime('%Y%m%d')}.csv"}
        )

    else:  # json
        return StreamingResponse(
            io.BytesIO(json.dumps(transactions, default=str, ensure_ascii=False).encode('utf-8')),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=transactions_{datetime.now().strftime('%Y%m%d')}.json"}
        )


@router.post("/import")
async def import_data(
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    if not file.filename.endswith(('.csv', '.json')):
        raise HTTPException(status_code=400, detail="Файл должен быть в формате CSV или JSON")

    content = await file.read()
    trans = db.begin()  # Start transaction for import

    try:
        if file.filename.endswith('.csv'):
            # Парсим CSV
            text_content = content.decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(text_content))
            transactions_data = list(reader)
        else:
            # Парсим JSON
            transactions_data = json.loads(content)

        imported_count = 0
        errors = []

        for idx, t in enumerate(transactions_data):
            try:
                # Basic validation and type conversion
                transaction_date = date.fromisoformat(t['date'])
                transaction_type = TransactionType(t['type'])  # Ensures enum is valid
                amount = Decimal(t['amount'])
                if amount <= 0:
                    raise ValueError("Amount must be positive.")

                # Находим или создаем категорию
                category_id = None
                if t.get('category'):
                    cat_result = db.execute(
                        text("SELECT id FROM categories WHERE name = :name LIMIT 1"),
                        {"name": t['category']}
                    ).fetchone()

                    if cat_result:
                        category_id = cat_result[0]
                    else:
                        # Создаем новую категорию
                        new_cat = db.execute(
                            text("""
                                INSERT INTO categories (name, type, icon, color)
                                VALUES (:name, :type, '📁', '#5e72e4')
                                RETURNING id
                            """),
                            {"name": t['category'], "type": transaction_type.value}  # Use .value for enum
                        ).fetchone()
                        category_id = new_cat[0]

                # Находим счета
                account_from_id = None
                account_to_id = None

                if t.get('account_from'):
                    acc_result = db.execute(
                        text("SELECT id FROM accounts WHERE name = :name LIMIT 1"),
                        {"name": t['account_from']}
                    ).fetchone()
                    if acc_result:
                        account_from_id = acc_result[0]
                    else:
                        errors.append(f"Строка {idx + 1}: Счет 'account_from' '{t['account_from']}' не найден.")
                        continue  # Skip this transaction

                if t.get('account_to'):
                    acc_result = db.execute(
                        text("SELECT id FROM accounts WHERE name = :name LIMIT 1"),
                        {"name": t['account_to']}
                    ).fetchone()
                    if acc_result:
                        account_to_id = acc_result[0]
                    else:
                        errors.append(f"Строка {idx + 1}: Счет 'account_to' '{t['account_to']}' не найден.")
                        continue  # Skip this transaction

                # Validate account presence based on transaction type
                if transaction_type == TransactionType.expense and not account_from_id:
                    raise ValueError("Для расхода требуется 'account_from'.")
                if transaction_type == TransactionType.income and not account_to_id:
                    raise ValueError("Для дохода требуется 'account_to'.")
                if transaction_type == TransactionType.transfer and (not account_from_id or not account_to_id):
                    raise ValueError("Для перевода требуются 'account_from' и 'account_to'.")

                # Создаем транзакцию
                insert_result = db.execute(text("""
                    INSERT INTO transactions (
                        date, type, amount, account_from_id, account_to_id,
                        category_id, description, notes
                    ) VALUES (
                        :date, :type, :amount, :account_from_id, :account_to_id,
                        :category_id, :description, :notes
                    ) RETURNING id
                """), {
                    "date": transaction_date,
                    "type": transaction_type.value,
                    "amount": amount,
                    "account_from_id": account_from_id,
                    "account_to_id": account_to_id,
                    "category_id": category_id,
                    "description": t.get('description'),
                    "notes": t.get('notes')
                })
                new_transaction_id = insert_result.fetchone()[0]

                # Handle tags for imported transaction
                if t.get('tags'):
                    tag_names = [tag.strip() for tag in t['tags'].split(',')]
                    for tag_name in tag_names:
                        tag_id = db.execute(
                            text("SELECT id FROM tags WHERE name = :name LIMIT 1"),
                            {"name": tag_name}
                        ).scalar()
                        if not tag_id:
                            # Create new tag if it doesn't exist
                            new_tag = db.execute(
                                text("INSERT INTO tags (name) VALUES (:name) RETURNING id"),
                                {"name": tag_name}
                            ).fetchone()
                            tag_id = new_tag[0]
                        db.execute(
                            text(
                                "INSERT INTO transaction_tags (transaction_id, tag_id) VALUES (:transaction_id, :tag_id) ON CONFLICT DO NOTHING"),
                            {"transaction_id": new_transaction_id, "tag_id": tag_id}
                        )

                # Update account balances
                if account_from_id:
                    db.execute(
                        text(
                            "UPDATE accounts SET current_balance = current_balance - :amount, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                        {"amount": amount, "id": account_from_id}
                    )
                if account_to_id:
                    db.execute(
                        text(
                            "UPDATE accounts SET current_balance = current_balance + :amount, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                        {"amount": amount, "id": account_to_id}
                    )

                imported_count += 1

            except Exception as e:
                errors.append(f"Строка {idx + 1} (данные: {t}): {str(e)}")

        trans.commit()  # Commit all changes if no unhandled exceptions
        return {
            "imported": imported_count,
            "total": len(transactions_data),
            "errors": errors
        }

    except json.JSONDecodeError:
        trans.rollback()
        raise HTTPException(status_code=400, detail="Неверный формат JSON файла.")
    except Exception as e:
        trans.rollback()
        raise HTTPException(status_code=400, detail=f"Ошибка при импорте: {str(e)}")
