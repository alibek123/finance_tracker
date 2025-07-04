from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import categories, accounts, transactions, budgets, tags, savings_goals, recurring_transactions, data_ops
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

# Импортируем улучшенную аналитику
from routers.analytics import router as analytics_router

app = FastAPI(
    title="Personal Finance Tracker",
    version="2.1.0",
    description="Улучшенный трекер личных финансов с умной аналитикой"
)

# CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Consider restricting this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(categories.router, prefix="/api")  # /api/categories
app.include_router(accounts.router, prefix="/api")  # /api/accounts
app.include_router(analytics_router, prefix="/api")  # /api/analytics (обновленная аналитика)
app.include_router(transactions.router, prefix="/api")  # /api/transactions
app.include_router(budgets.router, prefix="/api")  # /api/budgets
app.include_router(tags.router, prefix="/api")  # /api/tags
app.include_router(savings_goals.router, prefix="/api")  # /api/savings-goals
app.include_router(recurring_transactions.router, prefix="/api")  # /api/recurring-transactions
app.include_router(data_ops.router, prefix="/api")  # /api/data

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def read_root():
    return FileResponse("static/index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.1.0",
        "features": [
            "smart_analytics",
            "spending_patterns",
            "subscriptions_tracking",
            "improved_forecasting",
            "enhanced_dashboard"
        ]
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)