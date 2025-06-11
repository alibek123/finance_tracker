from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from dependencies import get_db
from models.schemas import Category, CategoryCreate, CategoryUpdate
from utils.enums import TransactionType

router = APIRouter(
    prefix="/categories",
    tags=["Categories"]
)


@router.get("/", response_model=List[Dict[str, Any]])
def get_categories(
        category_type: Optional[TransactionType] = None,
        include_inactive: bool = False,
        db: Session = Depends(get_db)
):
    query = """
        WITH RECURSIVE category_tree AS (
            SELECT
                c.id, c.name, c.parent_id, c.type, c.icon, c.color, c.is_active,
                c.name::text as path,
                0 as level,
                c.created_at
            FROM categories c
            WHERE c.parent_id IS NULL

            UNION ALL

            SELECT
                c.id, c.name, c.parent_id, c.type, c.icon, c.color, c.is_active,
                (ct.path || ' > ' || c.name)::text as path,
                ct.level + 1 as level,
                c.created_at
            FROM categories c
            JOIN category_tree ct ON c.parent_id = ct.id
        )
        SELECT * FROM category_tree
        WHERE 1=1
    """
    params = {}

    if category_type:
        query += " AND type = :type"
        params["type"] = category_type.value  # Use .value for Enum to string conversion

    if not include_inactive:
        query += " AND is_active = true"

    query += " ORDER BY type, level, name"

    result = db.execute(text(query), params)
    return [dict(row._asdict()) for row in result]


@router.post("/", response_model=Category)
def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    query = """
        INSERT INTO categories (name, parent_id, type, icon, color, is_active)
        VALUES (:name, :parent_id, :category_type, :icon, :color, :is_active)
        RETURNING *
    """
    params = category.model_dump()
    params['category_type'] = params.pop('type', None)  # Renaming 'type' to 'category_type' for SQL
    result = db.execute(text(query), params)
    db.commit()
    return dict(result.fetchone()._asdict())


@router.put("/{category_id}", response_model=Category)
def update_category(
        category_id: int,
        category_update: CategoryUpdate,
        db: Session = Depends(get_db)
):
    update_data = category_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    update_fields = []
    params = {"id": category_id}

    for field, value in update_data.items():
        update_fields.append(f"{field} = :{field}")
        params[field] = value

    query = f"""
        UPDATE categories
        SET {', '.join(update_fields)}
        WHERE id = :id
        RETURNING *
    """

    result = db.execute(text(query), params)
    db.commit()

    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Категория не найдена")

    return dict(row._asdict())


@router.delete("/{category_id}")
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
