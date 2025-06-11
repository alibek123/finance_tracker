from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from dependencies import get_db
from models.schemas import Tag, TagCreate, TagBase

router = APIRouter(
    prefix="/tags",
    tags=["Tags"]
)


@router.get("/", response_model=List[Tag])
def get_tags(db: Session = Depends(get_db)):
    query = "SELECT * FROM tags ORDER BY name"
    result = db.execute(text(query))
    return [dict(row._asdict()) for row in result]


@router.post("/", response_model=Tag)
def create_tag(tag: TagCreate, db: Session = Depends(get_db)):
    # Check if tag already exists (case-insensitive)
    existing_tag = db.execute(
        text("SELECT id FROM tags WHERE lower(name) = lower(:name)"),
        {"name": tag.name}
    ).scalar()
    if existing_tag:
        raise HTTPException(status_code=409, detail="Тег с таким именем уже существует")

    query = """
        INSERT INTO tags (name, color)
        VALUES (:name, :color)
        RETURNING *
    """
    params = tag.model_dump()
    result = db.execute(text(query), params)
    db.commit()
    return dict(result.fetchone()._asdict())


@router.put("/{tag_id}", response_model=Tag)
def update_tag(
        tag_id: int,
        tag_update: TagBase,  # Using TagBase as it contains updatable fields
        db: Session = Depends(get_db)
):
    update_data = tag_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    update_fields = []
    params = {"id": tag_id}

    for field, value in update_data.items():
        update_fields.append(f"{field} = :{field}")
        params[field] = value

    query = f"""
        UPDATE tags
        SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
        WHERE id = :id
        RETURNING *
    """

    result = db.execute(text(query), params)
    db.commit()

    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Тег не найден")

    return dict(row._asdict())


@router.delete("/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    # Check if any transactions are associated with this tag
    count = db.execute(
        text("SELECT COUNT(*) FROM transaction_tags WHERE tag_id = :id"),
        {"id": tag_id}
    ).scalar()

    if count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Невозможно удалить тег. Существует {count} транзакций, связанных с этим тегом."
        )

    result = db.execute(
        text("DELETE FROM tags WHERE id = :id RETURNING id"),
        {"id": tag_id}
    )
    deleted = result.fetchone()
    if not deleted:
        raise HTTPException(status_code=404, detail="Тег не найден")
    db.commit()
    return {"message": "Тег удален"}
