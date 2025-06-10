from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from dependencies import get_db
from models.schemas import SavingsGoal, SavingsGoalCreate, SavingsGoalUpdate
from datetime import date, datetime
from decimal import Decimal

router = APIRouter(
    prefix="/savings-goals",
    tags=["Savings Goals"]
)


@router.get("/", response_model=List[SavingsGoal])
def get_savings_goals(
        include_achieved: bool = False,
        db: Session = Depends(get_db)
):
    query = """
        SELECT sg.*, a.name as account_name
        FROM savings_goals sg
        LEFT JOIN accounts a ON sg.account_id = a.id
        WHERE 1=1
    """
    params = {}
    if not include_achieved:
        query += " AND sg.is_achieved = false"
    query += " ORDER BY sg.target_date NULLS LAST, sg.created_at DESC"
    result = db.execute(text(query), params)
    return [dict(row._asdict()) for row in result]


@router.post("/", response_model=SavingsGoal)
def create_savings_goal(goal: SavingsGoalCreate, db: Session = Depends(get_db)):
    query = """
        INSERT INTO savings_goals (name, target_amount, current_amount, target_date, account_id, notes, is_achieved)
        VALUES (:name, :target_amount, 0, :target_date, :account_id, :notes, false)
        RETURNING *
    """
    params = goal.model_dump()
    result = db.execute(text(query), params)
    db.commit()
    return dict(result.fetchone()._asdict())


@router.put("/{goal_id}", response_model=SavingsGoal)
def update_savings_goal(
        goal_id: int,
        goal_update: SavingsGoalUpdate,
        db: Session = Depends(get_db)
):
    update_data = goal_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")

    update_fields = []
    params = {"id": goal_id}

    for field, value in update_data.items():
        update_fields.append(f"{field} = :{field}")
        params[field] = value

    query = f"""
        UPDATE savings_goals
        SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
        WHERE id = :id
        RETURNING *
    """

    result = db.execute(text(query), params)
    db.commit()

    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Цель накопления не найдена")

    return dict(row._asdict())


@router.post("/{goal_id}/deposit")
def deposit_to_savings_goal(
        goal_id: int,
        amount: Decimal = Query(..., gt=0),
        transaction_id: Optional[int] = None,  # Optional: link to a transaction
        db: Session = Depends(get_db)
):
    trans = db.begin()
    try:
        goal = db.execute(
            text("SELECT * FROM savings_goals WHERE id = :id FOR UPDATE"),
            {"id": goal_id}
        ).fetchone()

        if not goal:
            raise HTTPException(status_code=404, detail="Цель накопления не найдена")

        if goal.is_achieved:
            raise HTTPException(status_code=400, detail="Цель уже достигнута.")

        new_current_amount = goal.current_amount + amount
        is_achieved = new_current_amount >= goal.target_amount
        achieved_at = datetime.now() if is_achieved else None

        db.execute(
            text("""
                UPDATE savings_goals
                SET current_amount = :new_current_amount,
                    is_achieved = :is_achieved,
                    achieved_at = :achieved_at,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
            """),
            {
                "new_current_amount": new_current_amount,
                "is_achieved": is_achieved,
                "achieved_at": achieved_at,
                "id": goal_id
            }
        )

        # Optionally, create a transaction for this deposit if not linked
        if not transaction_id and goal.account_id:
            category_id = db.execute(
                text("SELECT id FROM categories WHERE name = 'Пополнение цели' AND type = 'transfer'")
            ).scalar()
            if not category_id:
                new_cat = db.execute(
                    text("""
                        INSERT INTO categories (name, type, icon, color)
                        VALUES ('Пополнение цели', 'transfer', '🎯', '#007bff')
                        RETURNING id
                    """)
                ).fetchone()
                category_id = new_cat[0]

            db.execute(text("""
                INSERT INTO transactions (date, type, amount, account_from_id, account_to_id, category_id, description, is_planned)
                VALUES (CURRENT_DATE, 'expense', :amount, :account_id, NULL, :category_id, :description, false)
            """), {
                "amount": amount,
                "account_id": goal.account_id,
                "category_id": category_id,
                "description": f"Пополнение цели накопления '{goal.name}'",
            })
            # This creates an expense from the account to the goal (virtual transfer)
            # You might need a more complex system to represent this as a transfer within accounts if the goal is a "virtual account".

        trans.commit()
        return {"message": "Цель накопления пополнена", "current_amount": new_current_amount,
                "is_achieved": is_achieved}
    except Exception as e:
        trans.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при пополнении цели накопления: {str(e)}")


@router.delete("/{goal_id}")
def delete_savings_goal(goal_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text("DELETE FROM savings_goals WHERE id = :id RETURNING id"),
        {"id": goal_id}
    )
    deleted = result.fetchone()
    if not deleted:
        raise HTTPException(status_code=404, detail="Цель накопления не найдена")
    db.commit()
    return {"message": "Цель накопления удалена"}
