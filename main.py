from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import categories, accounts, transactions, budgets, tags, savings_goals, recurring_transactions, data_ops, \
    analytics
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

app = FastAPI(title="Personal Finance Tracker", version="2.0.0")

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
app.include_router(analytics.router, prefix="/api")  # /api/analytics
app.include_router(transactions.router, prefix="/api")  # /api/transactions
app.include_router(budgets.router, prefix="/api")  # /api/budgets
app.include_router(tags.router, prefix="/api")  # /api/tags
app.include_router(savings_goals.router, prefix="/api")  # /api/savings-goals
app.include_router(recurring_transactions.router, prefix="/api")  # /api/recurring-transactions
app.include_router(data_ops.router, prefix="/api")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def read_root():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)