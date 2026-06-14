import os
from pathlib import Path
from dotenv import load_dotenv

# Load from .env file inside MarketPredictor root folder
dotenv_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

class DBConfig:
    """PostgreSQL Database Configuration Loader"""
    
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "market_predictor")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "public")

    @classmethod
    def get_connection_string(cls) -> str:
        """Returns standard PostgreSQL connection string for tools like SQLAlchemy if needed"""
        return f"postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
    
    @classmethod
    def get_connection_params(cls) -> dict:
        """Returns parameter dictionary for psycopg2 connection"""
        return {
            "host": cls.DB_HOST,
            "port": cls.DB_PORT,
            "database": cls.DB_NAME,
            "user": cls.DB_USER,
            "password": cls.DB_PASSWORD
        }
