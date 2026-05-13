"""
Database Configuration Module
Handles database connection settings from environment variables
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class DatabaseConfig:
    """Database configuration using environment variables"""
    
    # Database type: sqlite, postgresql, mysql
    DB_TYPE = os.getenv('DB_TYPE', 'sqlite')
    
    # SQLite settings
    SQLITE_DB_NAME = os.getenv('SQLITE_DB_NAME', 'warehouse')
    
    # PostgreSQL settings
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', 5432))
    POSTGRES_USER = os.getenv('POSTGRES_USER', '')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'warehouse_db')
    
    # MySQL settings
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
    MYSQL_USER = os.getenv('MYSQL_USER', '')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
    MYSQL_DB = os.getenv('MYSQL_DB', 'warehouse_db')
    
    # Connection settings
    SQLALCHEMY_ECHO = os.getenv('SQLALCHEMY_ECHO', 'False').lower() == 'true'
    SQLALCHEMY_POOL_SIZE = int(os.getenv('SQLALCHEMY_POOL_SIZE', 10))
    SQLALCHEMY_MAX_OVERFLOW = int(os.getenv('SQLALCHEMY_MAX_OVERFLOW', 20))
    
    @classmethod
    def get_connection_string(cls) -> str:
        """
        Build connection string based on configuration
        
        Returns:
            SQLAlchemy connection string
        """
        if cls.DB_TYPE == 'sqlite':
            return f'sqlite:///{cls.SQLITE_DB_NAME}.db'
        elif cls.DB_TYPE == 'postgresql':
            return (
                f'postgresql://{cls.POSTGRES_USER}:{cls.POSTGRES_PASSWORD}'
                f'@{cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}/{cls.POSTGRES_DB}'
            )
        elif cls.DB_TYPE == 'mysql':
            return (
                f'mysql+pymysql://{cls.MYSQL_USER}:{cls.MYSQL_PASSWORD}'
                f'@{cls.MYSQL_HOST}:{cls.MYSQL_PORT}/{cls.MYSQL_DB}'
            )
        else:
            raise ValueError(f"Unsupported database type: {cls.DB_TYPE}")
    
    @classmethod
    def get_config_summary(cls) -> dict:
        """Get configuration summary for logging"""
        return {
            'db_type': cls.DB_TYPE,
            'host': (
                cls.POSTGRES_HOST if cls.DB_TYPE == 'postgresql'
                else cls.MYSQL_HOST if cls.DB_TYPE == 'mysql'
                else 'local'
            ),
            'database': (
                cls.SQLITE_DB_NAME if cls.DB_TYPE == 'sqlite'
                else cls.POSTGRES_DB if cls.DB_TYPE == 'postgresql'
                else cls.MYSQL_DB
            ),
            'echo_sql': cls.SQLALCHEMY_ECHO
        }
