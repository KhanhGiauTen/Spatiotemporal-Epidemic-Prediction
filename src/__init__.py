"""
Spatiotemporal Epidemic Prediction - Source Package

Modules:
- db_manager: Database management and ORM models
- config: Database configuration management
- data_loader: ETL data loading into warehouse
"""

from .db_manager import DatabaseManager, get_database_manager, Base
from .config import DatabaseConfig
from .data_loader import DataWarehouseLoader

__all__ = [
    'DatabaseManager',
    'get_database_manager',
    'Base',
    'DatabaseConfig',
    'DataWarehouseLoader'
]

__version__ = '1.0.0'
