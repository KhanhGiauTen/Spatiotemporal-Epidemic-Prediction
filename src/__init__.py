"""
Spatiotemporal Epidemic Prediction - Source Package

Modules:
- db_manager: Database management and ORM models
- config: Database configuration management
- data_loader: ETL data loading into warehouse
- star_tree: Star Tree prefix tree for trajectory compression
"""

from .db_manager import DatabaseManager, get_database_manager, Base
from .config import DatabaseConfig
from .data_loader import DataWarehouseLoader
from .star_tree import StarNode, StarTree
from .star_cubing import starcubing

__all__ = [
    'DatabaseManager',
    'get_database_manager',
    'Base',
    'DatabaseConfig',
    'DataWarehouseLoader',
    'StarNode',
    'StarTree'
    ,'starcubing'
]

__version__ = '1.0.0'
