import os
import urllib.parse
from dotenv import load_dotenv

# Загрузка переменных окружения
try:
    load_dotenv()
except ImportError:
    pass

def get_database_url():
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "finance_db")
    default_schema = os.getenv("DB_SCHEMA", "finance")

    db_password_encoded = urllib.parse.quote_plus(db_password)
    schema_encoded = urllib.parse.quote_plus(default_schema)

    return (
        f"postgresql://{db_user}:{db_password_encoded}@{db_host}:{db_port}/{db_name}"
        f"?client_encoding=utf8&options=-csearch_path%3D{schema_encoded}"
    )

DATABASE_URL = os.getenv("DATABASE_URL", get_database_url())

# Other configurations can go here
# e.g., API_PREFIX = "/api"