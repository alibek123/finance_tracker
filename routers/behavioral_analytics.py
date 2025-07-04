# routers/behavioral_analytics.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from dependencies import get_db
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
import numpy as np
from collections import defaultdict

router = APIRouter(
    prefix="/behavioral-analytics",
    tags=["Behavioral Analytics"]
)


@router.get("/dashboard-insights")
async def get_dashboard_insights(db: Session = Depends(get_db)):
    """
    Возвращает только 4-5 ключевых метрик с actionable insights
    вместо перегрузки информацией
    """
    # 1. Cash Flow Prediction (самая важная метрика)
    cash_flow = await predict_cash_flow(db)

    # 2. Spending Triggers Analysis
    triggers = await analyze_spending_triggers(db)

    # 3. Savings Momentum Score
    savings_score = await calculate_savings_momentum(db)

    # 4. Financial Health Score
    health_score = await calculate_financial_health_score(db)

    # 5. Next Best Action
    next_action = await get_next_best_action(db, cash_flow, triggers, savings_score)

    return {
        "cash_flow_prediction": cash_flow,
        "spending_triggers": triggers,
        "savings_momentum": savings_score,
        "financial_health": health_score,
        "next_best_action": next_action,
        "generated_at": datetime.now()
    }


async def predict_cash_flow(db: Session) -> Dict[str, Any]:
    """
    Прогнозирует cash flow на основе исторических данных
    с учетом сезонности и трендов
    """
    # Анализ за последние 3 месяца
    query = """
        WITH daily_flows AS (
            SELECT 
                date,
                SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
                SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expense
            FROM transactions
            WHERE date >= CURRENT_DATE - INTERVAL '90 days'
            GROUP BY date
        ),
        patterns AS (
            SELECT 
                EXTRACT(DOW FROM date) as day_of_week,
                AVG(expense) as avg_expense,
                STDDEV(expense) as stddev_expense,
                AVG(income) as avg_income
            FROM daily_flows
            GROUP BY EXTRACT(DOW FROM date)
        ),
        monthly_trend AS (
            SELECT 
                date_trunc('month', date) as month,
                SUM(expense) as total_expense,
                SUM(income) as total_income
            FROM daily_flows
            GROUP BY date_trunc('month', date)
            ORDER BY month
        )
        SELECT 
            (SELECT SUM(current_balance) FROM accounts WHERE is_active = true) as current_balance,
            (SELECT AVG(avg_expense) FROM patterns) as daily_avg_expense,
            (SELECT SUM(avg_expense) FROM patterns) as weekly_expense,
            (SELECT COALESCE(AVG(total_expense), 0) FROM monthly_trend) as monthly_avg_expense,
            (SELECT COALESCE(AVG(total_income), 0) FROM monthly_trend) as monthly_avg_income
    """

    result = db.execute(text(query)).fetchone()

    current_balance = float(result.current_balance or 0)
    daily_avg = float(result.daily_avg_expense or 0)
    monthly_expense = float(result.monthly_avg_expense or 0)
    monthly_income = float(result.monthly_avg_income or 0)

    # Прогноз критических дат
    days_until_critical = int(current_balance / daily_avg) if daily_avg > 0 else 999

    # Определение уровня риска
    risk_level = "low"
    if days_until_critical < 7:
        risk_level = "critical"
    elif days_until_critical < 14:
        risk_level = "high"
    elif days_until_critical < 30:
        risk_level = "medium"

    # Рекомендации based on behavioral economics
    recommendations = []
    if risk_level in ["critical", "high"]:
        recommendations.append({
            "type": "urgent",
            "message": f"Внимание! При текущем темпе трат денег хватит на {days_until_critical} дней",
            "action": "reduce_spending"
        })

    # Анализ предстоящих крупных трат
    upcoming_bills = await get_upcoming_bills(db)

    return {
        "current_balance": current_balance,
        "daily_burn_rate": daily_avg,
        "days_until_critical": days_until_critical,
        "risk_level": risk_level,
        "monthly_net": monthly_income - monthly_expense,
        "upcoming_bills": upcoming_bills,
        "recommendations": recommendations
    }


async def analyze_spending_triggers(db: Session) -> Dict[str, Any]:
    """
    Анализирует триггеры трат для behavioral insights
    """
    query = """
        WITH spending_patterns AS (
            SELECT 
                t.date,
                t.amount,
                t.category_id,
                c.name as category_name,
                EXTRACT(DOW FROM t.date) as day_of_week,
                EXTRACT(HOUR FROM t.created_at) as hour_of_day,
                LAG(t.date) OVER (ORDER BY t.date) as prev_transaction_date
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.type = 'expense' 
              AND t.date >= CURRENT_DATE - INTERVAL '30 days'
            ORDER BY t.date DESC
        ),
        trigger_analysis AS (
            SELECT 
                day_of_week,
                COUNT(*) as transaction_count,
                AVG(amount) as avg_amount,
                SUM(amount) as total_amount,
                -- Выходные vs будни
                CASE 
                    WHEN day_of_week IN (0, 6) THEN 'weekend'
                    ELSE 'weekday'
                END as day_type
            FROM spending_patterns
            GROUP BY day_of_week
        )
        SELECT 
            day_type,
            SUM(transaction_count) as transactions,
            AVG(avg_amount) as avg_transaction,
            SUM(total_amount) as total_spent
        FROM trigger_analysis
        GROUP BY day_type
    """

    patterns = db.execute(text(query)).fetchall()

    # Анализ импульсивных покупок
    impulse_query = """
        SELECT 
            COUNT(*) as impulse_count,
            SUM(amount) as impulse_total
        FROM transactions t
        WHERE type = 'expense'
          AND date >= CURRENT_DATE - INTERVAL '30 days'
          AND (
              -- Мелкие частые траты
              (amount < 500 AND category_id IN (
                  SELECT id FROM categories WHERE name IN ('Кафе', 'Фастфуд', 'Развлечения')
              ))
              OR
              -- Незапланированные крупные траты
              (amount > 5000 AND description ILIKE '%срочно%' OR description ILIKE '%акция%')
          )
    """

    impulse_result = db.execute(text(impulse_query)).fetchone()

    triggers = {
        "weekend_overspending": False,
        "stress_spending": False,
        "social_spending": False,
        "time_based_patterns": []
    }

    # Определяем паттерны
    weekend_spending = 0
    weekday_spending = 0

    for pattern in patterns:
        if pattern.day_type == 'weekend':
            weekend_spending = float(pattern.avg_transaction or 0)
        else:
            weekday_spending = float(pattern.avg_transaction or 0)

    if weekend_spending > weekday_spending * 1.5:
        triggers["weekend_overspending"] = True

    # Behavioral insights
    insights = []
    if triggers["weekend_overspending"]:
        insights.append({
            "type": "behavioral_trigger",
            "title": "Выходные = больше трат",
            "message": "Вы тратите на 50% больше по выходным",
            "suggestion": "Планируйте досуг заранее с фиксированным бюджетом"
        })

    if impulse_result and impulse_result.impulse_count > 10:
        insights.append({
            "type": "impulse_control",
            "title": "Частые импульсивные покупки",
            "message": f"{impulse_result.impulse_count} импульсивных покупок за месяц",
            "suggestion": "Используйте правило 24 часов перед покупкой"
        })

    return {
        "triggers_identified": triggers,
        "behavioral_insights": insights,
        "impulse_spending": {
            "count": impulse_result.impulse_count if impulse_result else 0,
            "total": float(impulse_result.impulse_total or 0) if impulse_result else 0
        }
    }


async def calculate_savings_momentum(db: Session) -> Dict[str, Any]:
    """
    Рассчитывает momentum сбережений с gamification элементами
    """
    query = """
        WITH monthly_savings AS (
            SELECT 
                date_trunc('month', date) as month,
                SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END) as net_savings
            FROM transactions
            WHERE date >= CURRENT_DATE - INTERVAL '6 months'
            GROUP BY date_trunc('month', date)
            ORDER BY month
        ),
        savings_trend AS (
            SELECT 
                month,
                net_savings,
                LAG(net_savings) OVER (ORDER BY month) as prev_month,
                AVG(net_savings) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as moving_avg
            FROM monthly_savings
        )
        SELECT 
            COALESCE(AVG(net_savings), 0) as avg_monthly_savings,
            COALESCE(STDDEV(net_savings), 0) as savings_volatility,
            COUNT(CASE WHEN net_savings > 0 THEN 1 END) as positive_months,
            COUNT(*) as total_months,
            MAX(net_savings) as best_month,
            MIN(net_savings) as worst_month
        FROM savings_trend
        WHERE month >= CURRENT_DATE - INTERVAL '3 months'
    """

    result = db.execute(text(query)).fetchone()

    avg_savings = float(result.avg_monthly_savings or 0)
    consistency = (result.positive_months / result.total_months * 100) if result.total_months > 0 else 0

    # Momentum score (0-100)
    momentum_score = 0
    if avg_savings > 0:
        momentum_score += 40
    if consistency > 80:
        momentum_score += 30
    if result.savings_volatility < avg_savings * 0.3:  # Low volatility is good
        momentum_score += 30

    # Streak calculation
    streak_query = """
        WITH daily_balance AS (
            SELECT 
                date,
                SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END) as daily_net
            FROM transactions
            WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY date
            ORDER BY date DESC
        )
        SELECT COUNT(*) as positive_days
        FROM daily_balance
        WHERE daily_net >= 0
    """

    streak_result = db.execute(text(streak_query)).fetchone()
    current_streak = streak_result.positive_days if streak_result else 0

    # Gamification elements
    level = "Новичок"
    if momentum_score >= 80:
        level = "Мастер сбережений"
    elif momentum_score >= 60:
        level = "Эксперт"
    elif momentum_score >= 40:
        level = "Продвинутый"

    return {
        "momentum_score": momentum_score,
        "level": level,
        "current_streak": current_streak,
        "avg_monthly_savings": avg_savings,
        "consistency_rate": consistency,
        "best_month_amount": float(result.best_month or 0),
        "motivation_message": get_motivation_message(momentum_score, current_streak)
    }


async def calculate_financial_health_score(db: Session) -> Dict[str, Any]:
    """
    Комплексная оценка финансового здоровья
    """
    # Ключевые метрики для оценки
    metrics_query = """
        WITH account_data AS (
            SELECT 
                SUM(current_balance) as total_balance,
                COUNT(*) as active_accounts
            FROM accounts 
            WHERE is_active = true
        ),
        monthly_data AS (
            SELECT 
                AVG(CASE WHEN type = 'income' THEN amount ELSE 0 END) as avg_income,
                AVG(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as avg_expense
            FROM transactions
            WHERE date >= CURRENT_DATE - INTERVAL '3 months'
        ),
        emergency_fund AS (
            SELECT 
                COALESCE(SUM(current_amount), 0) as emergency_savings
            FROM savings_goals
            WHERE name ILIKE '%резерв%' OR name ILIKE '%emergency%'
        )
        SELECT 
            a.total_balance,
            a.active_accounts,
            m.avg_income,
            m.avg_expense,
            e.emergency_savings,
            CASE 
                WHEN m.avg_expense > 0 THEN a.total_balance / m.avg_expense
                ELSE 999
            END as months_of_expenses
        FROM account_data a, monthly_data m, emergency_fund e
    """

    result = db.execute(text(metrics_query)).fetchone()

    # Расчет health score (0-100)
    health_score = 0

    # 1. Emergency fund (30 points)
    months_covered = result.months_of_expenses if result else 0
    if months_covered >= 6:
        health_score += 30
    elif months_covered >= 3:
        health_score += 20
    elif months_covered >= 1:
        health_score += 10

    # 2. Savings rate (30 points)
    if result and result.avg_income > 0:
        savings_rate = (result.avg_income - result.avg_expense) / result.avg_income * 100
        if savings_rate >= 20:
            health_score += 30
        elif savings_rate >= 10:
            health_score += 20
        elif savings_rate >= 5:
            health_score += 10

    # 3. Debt management (20 points) - simplified
    # В реальности нужно анализировать кредиты
    health_score += 15

    # 4. Diversification (20 points)
    if result and result.active_accounts >= 3:
        health_score += 20
    elif result and result.active_accounts >= 2:
        health_score += 10

    # Определение статуса
    status = "Требует внимания"
    if health_score >= 80:
        status = "Отличное"
    elif health_score >= 60:
        status = "Хорошее"
    elif health_score >= 40:
        status = "Удовлетворительное"

    return {
        "score": health_score,
        "status": status,
        "months_of_expenses_covered": months_covered,
        "key_metrics": {
            "emergency_fund": float(result.emergency_savings) if result else 0,
            "monthly_savings_rate": ((
                                             result.avg_income - result.avg_expense) / result.avg_income * 100) if result and result.avg_income > 0 else 0,
            "account_diversification": result.active_accounts if result else 0
        },
        "improvements_needed": get_health_improvements(health_score, months_covered)
    }


async def get_next_best_action(
        db: Session,
        cash_flow: Dict,
        triggers: Dict,
        savings_score: Dict
) -> Dict[str, Any]:
    """
    AI-powered персонализированная рекомендация следующего действия
    """
    actions = []

    # Приоритет 1: Критические проблемы с cash flow
    if cash_flow["risk_level"] in ["critical", "high"]:
        actions.append({
            "priority": 1,
            "type": "urgent",
            "title": "Сократите расходы немедленно",
            "description": f"У вас осталось денег на {cash_flow['days_until_critical']} дней",
            "action_button": "Посмотреть крупные траты",
            "action_link": "/analytics/top-expenses"
        })

    # Приоритет 2: Поведенческие триггеры
    if triggers["behavioral_insights"]:
        for insight in triggers["behavioral_insights"][:1]:  # Только самый важный
            actions.append({
                "priority": 2,
                "type": "behavioral",
                "title": insight["title"],
                "description": insight["suggestion"],
                "action_button": "Установить правило",
                "action_link": "/settings/rules"
            })

    # Приоритет 3: Улучшение сбережений
    if savings_score["momentum_score"] < 60:
        actions.append({
            "priority": 3,
            "type": "savings",
            "title": "Автоматизируйте сбережения",
            "description": "Настройте автоматический перевод 10% от дохода",
            "action_button": "Настроить",
            "action_link": "/recurring/new?type=savings"
        })

    # Выбираем самое важное действие
    if actions:
        actions.sort(key=lambda x: x["priority"])
        return actions[0]

    # Если все хорошо - мотивируем
    return {
        "type": "motivation",
        "title": "Отличная работа! 🎉",
        "description": f"Ваш уровень: {savings_score['level']}. Продолжайте в том же духе!",
        "action_button": "Посмотреть достижения",
        "action_link": "/achievements"
    }


async def get_upcoming_bills(db: Session) -> List[Dict[str, Any]]:
    """Получает предстоящие счета из повторяющихся транзакций"""
    query = """
        SELECT 
            name,
            amount,
            frequency,
            CASE 
                WHEN frequency = 'monthly' THEN 
                    date_trunc('month', CURRENT_DATE) + interval '1 month' - 
                    (date_trunc('month', CURRENT_DATE) - date_trunc('month', start_date))
                ELSE CURRENT_DATE + interval '7 days'
            END as next_due_date
        FROM recurring_transactions
        WHERE is_active = true 
          AND type = 'expense'
          AND (end_date IS NULL OR end_date > CURRENT_DATE)
        ORDER BY next_due_date
        LIMIT 5
    """

    results = db.execute(text(query)).fetchall()

    return [
        {
            "name": row.name,
            "amount": float(row.amount),
            "due_date": row.next_due_date.strftime('%Y-%m-%d') if row.next_due_date else None,
            "frequency": row.frequency
        }
        for row in results
    ]


def get_motivation_message(score: int, streak: int) -> str:
    """Генерирует мотивационное сообщение на основе прогресса"""
    if score >= 80:
        return f"Великолепно! {streak} дней положительного баланса подряд! 🚀"
    elif score >= 60:
        return f"Хороший прогресс! Еще немного и вы достигнете следующего уровня 💪"
    elif score >= 40:
        return "Вы на правильном пути! Каждый день имеет значение 📈"
    else:
        return "Начните с малого - сэкономьте 100₸ сегодня. Вы можете это! 💡"


def get_health_improvements(score: int, months_covered: float) -> List[str]:
    """Предлагает конкретные улучшения для финансового здоровья"""
    improvements = []

    if months_covered < 3:
        improvements.append("Создайте резервный фонд на 3 месяца расходов")

    if score < 60:
        improvements.append("Увеличьте норму сбережений до 10% от дохода")

    if len(improvements) == 0:
        improvements.append("Рассмотрите инвестиционные возможности")

    return improvements


# Micro-feedback notifications endpoint
@router.get("/spending-notifications")
async def get_spending_notifications(db: Session = Depends(get_db)):
    """
    Возвращает умные уведомления о тратах (не больше 3 в день)
    для создания micro-feedback loops
    """
    # Анализ трат за сегодня
    today_query = """
        WITH today_spending AS (
            SELECT 
                SUM(amount) as total_today,
                COUNT(*) as transaction_count,
                MAX(amount) as largest_transaction,
                array_agg(
                    json_build_object(
                        'amount', amount,
                        'category', c.name,
                        'time', t.created_at
                    ) ORDER BY amount DESC
                ) as transactions
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE t.type = 'expense' 
              AND t.date = CURRENT_DATE
        ),
        daily_average AS (
            SELECT AVG(daily_total) as avg_daily
            FROM (
                SELECT date, SUM(amount) as daily_total
                FROM transactions
                WHERE type = 'expense' 
                  AND date >= CURRENT_DATE - INTERVAL '30 days'
                  AND date < CURRENT_DATE
                GROUP BY date
            ) d
        ),
        category_limits AS (
            SELECT 
                b.category_id,
                c.name as category_name,
                b.amount / 30 as daily_limit
            FROM budgets b
            JOIN categories c ON b.category_id = c.id
            WHERE b.is_active = true 
              AND b.period = 'monthly'
        )
        SELECT 
            t.total_today,
            t.transaction_count,
            t.largest_transaction,
            t.transactions,
            d.avg_daily,
            (
                SELECT json_agg(
                    json_build_object(
                        'category', cl.category_name,
                        'daily_limit', cl.daily_limit,
                        'spent_today', COALESCE(
                            (SELECT SUM(amount) 
                             FROM transactions 
                             WHERE category_id = cl.category_id 
                               AND type = 'expense' 
                               AND date = CURRENT_DATE), 0
                        )
                    )
                )
                FROM category_limits cl
            ) as category_status
        FROM today_spending t, daily_average d
    """

    result = db.execute(text(today_query)).fetchone()

    notifications = []

    if result and result.total_today:
        total_today = float(result.total_today)
        avg_daily = float(result.avg_daily or 0)

        # Notification 1: Daily spending alert
        if total_today > avg_daily * 1.2:
            notifications.append({
                "type": "overspending",
                "title": "Повышенные траты сегодня",
                "message": f"Вы потратили {format_money(total_today)} - это на {int((total_today / avg_daily - 1) * 100)}% больше обычного",
                "severity": "warning",
                "action": "Посмотрите, на что ушли деньги"
            })

        # Notification 2: Category limit warnings
        if result.category_status:
            for cat_status in result.category_status:
                if cat_status['spent_today'] > cat_status['daily_limit'] * 1.5:
                    notifications.append({
                        "type": "category_limit",
                        "title": f"Лимит по категории '{cat_status['category']}'",
                        "message": f"Превышен дневной лимит в 1.5 раза",
                        "severity": "alert",
                        "action": "Пересмотреть бюджет"
                    })
                    break  # Only one category notification

        # Notification 3: Positive reinforcement
        if total_today < avg_daily * 0.8 and result.transaction_count > 0:
            notifications.append({
                "type": "achievement",
                "title": "Отличный контроль расходов! 👏",
                "message": f"Сегодня вы потратили на {int((1 - total_today / avg_daily) * 100)}% меньше обычного",
                "severity": "success",
                "action": None
            })

    # Limit to 3 notifications as per best practices
    return notifications[:3]


def format_money(amount: float) -> str:
    """Форматирование денег"""
    return f"{amount:,.0f}₸"


# Добавляем endpoint для peer comparison (анонимное сравнение)
@router.get("/peer-comparison")
async def get_peer_comparison(
        age_group: Optional[str] = Query(None, regex="^(18-25|26-35|36-45|46-55|56+)$"),
        db: Session = Depends(get_db)
):
    """
    Анонимное сравнение с похожими пользователями
    (в реальном приложении это было бы сравнение между пользователями)
    """
    # Для демо используем исторические данные с разными периодами
    comparison_query = """
        WITH user_metrics AS (
            SELECT 
                AVG(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as avg_expense,
                AVG(CASE WHEN type = 'income' THEN amount ELSE 0 END) as avg_income,
                COUNT(DISTINCT date_trunc('month', date)) as months
            FROM transactions
            WHERE date >= CURRENT_DATE - INTERVAL '3 months'
        ),
        -- Симулируем данные "других пользователей" используя исторические периоды
        peer_metrics AS (
            SELECT 
                AVG(CASE WHEN type = 'expense' THEN amount ELSE 0 END) * (0.8 + random() * 0.4) as avg_expense,
                AVG(CASE WHEN type = 'income' THEN amount ELSE 0 END) * (0.9 + random() * 0.2) as avg_income
            FROM transactions
            WHERE date >= CURRENT_DATE - INTERVAL '12 months'
              AND date < CURRENT_DATE - INTERVAL '3 months'
        )
        SELECT 
            u.avg_expense as your_expense,
            u.avg_income as your_income,
            p.avg_expense as peer_expense,
            p.avg_income as peer_income,
            CASE 
                WHEN u.avg_income > 0 THEN 
                    ((u.avg_income - u.avg_expense) / u.avg_income * 100)
                ELSE 0 
            END as your_savings_rate,
            CASE 
                WHEN p.avg_income > 0 THEN 
                    ((p.avg_income - p.avg_expense) / p.avg_income * 100)
                ELSE 0 
            END as peer_savings_rate
        FROM user_metrics u, peer_metrics p
    """

    result = db.execute(text(comparison_query)).fetchone()

    if not result:
        return {"message": "Недостаточно данных для сравнения"}

    your_savings_rate = float(result.your_savings_rate or 0)
    peer_savings_rate = float(result.peer_savings_rate or 15)  # Default 15%

    comparison = {
        "your_metrics": {
            "monthly_expense": float(result.your_expense or 0) * 30,
            "monthly_income": float(result.your_income or 0) * 30,
            "savings_rate": your_savings_rate
        },
        "peer_average": {
            "monthly_expense": float(result.peer_expense or 0) * 30,
            "monthly_income": float(result.peer_income or 0) * 30,
            "savings_rate": peer_savings_rate
        },
        "insights": []
    }

    # Генерируем insights на основе сравнения
    if your_savings_rate > peer_savings_rate:
        comparison["insights"].append({
            "type": "positive",
            "message": f"Вы сберегаете на {int(your_savings_rate - peer_savings_rate)}% больше, чем в среднем!",
            "emoji": "🌟"
        })
    else:
        comparison["insights"].append({
            "type": "improvement",
            "message": f"Люди вашей группы сберегают в среднем {peer_savings_rate:.1f}% дохода",
            "emoji": "📊"
        })

    return comparison
