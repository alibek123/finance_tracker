from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from config import DATABASE_URL

# Создаем engine с дополнительными параметрами
try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args={
            "client_encoding": "utf8",
            "connect_timeout": 10
        }
    )
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        print("✅ Successfully connected to database")
except Exception as e:
    print(f"❌ Database connection error: {e}")
    raise

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()  # Keep Base here for potential ORM routers in db_models.py
