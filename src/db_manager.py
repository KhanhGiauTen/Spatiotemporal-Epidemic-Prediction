"""
Database Manager for Spatiotemporal Epidemic Prediction Data Warehouse
Implements SQLAlchemy ORM models and database operations for Star Schema
"""

import os
from datetime import datetime, date
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    create_engine, Column, BigInteger, Integer, String, Boolean, DateTime,
    Date, Numeric, ForeignKey, func, inspect as sqlalchemy_inspect
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from sqlalchemy.pool import QueuePool, StaticPool


# Base class for all ORM models
Base = declarative_base()


# ============================================================================
# ORM MODELS - DIMENSION TABLES
# ============================================================================

class DimTime(Base):
    """
    Dimension table for temporal attributes
    Stores date and time-related attributes for fact records
    """
    __tablename__ = 'Dim_Time'
    
    time_id = Column(Integer, primary_key=True, autoincrement=False)
    date_full = Column(Date, nullable=False, unique=True, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    week_of_year = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=False)
    day_of_week = Column(String(10), nullable=False)
    is_weekend = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    exposure_facts = relationship(
        'FactExposure',
        back_populates='time_dimension',
        cascade='all, delete-orphan'
    )
    
    def __repr__(self):
        return f"<DimTime(time_id={self.time_id}, date_full={self.date_full})>"


class DimLocation(Base):
    """
    Dimension table for geographic/location attributes
    Stores site and location information
    """
    __tablename__ = 'Dim_Location'
    
    location_id = Column(Integer, primary_key=True, autoincrement=False)
    site_code = Column(String(50), nullable=False, unique=True, index=True)
    site_name = Column(String(255), nullable=False, index=True)
    region = Column(String(100))
    country = Column(String(100), default='South Africa')
    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    exposure_facts = relationship(
        'FactExposure',
        back_populates='location_dimension',
        cascade='all, delete-orphan'
    )
    
    def __repr__(self):
        return f"<DimLocation(location_id={self.location_id}, site_name={self.site_name})>"


class DimPatient(Base):
    """
    Dimension table for patient/individual attributes
    Stores demographic and health information
    """
    __tablename__ = 'Dim_Patient'
    
    patient_id = Column(Integer, primary_key=True, autoincrement=False)
    patient_code = Column(String(50), nullable=False, unique=True, index=True)
    age_group = Column(String(20), nullable=False, index=True)
    sex = Column(String(10), nullable=False, index=True)
    bmi_category = Column(String(50))
    smoking_status = Column(String(50))
    household_id = Column(String(50), index=True)
    role_in_network = Column(String(50), default='Contact')
    sars_status = Column(String(20), default='Unknown')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    exposure_facts = relationship(
        'FactExposure',
        foreign_keys='FactExposure.patient_id',
        back_populates='patient_dimension',
        cascade='all, delete-orphan'
    )
    contact_exposures = relationship(
        'FactExposure',
        foreign_keys='FactExposure.contact_patient_id',
        back_populates='contact_patient_dimension'
    )
    
    def __repr__(self):
        return f"<DimPatient(patient_id={self.patient_id}, patient_code={self.patient_code})>"


# ============================================================================
# ORM MODELS - FACT TABLE
# ============================================================================

class FactExposure(Base):
    """
    Fact table for exposure events
    Stores exposure combinations exceeding threshold from Iceberg Cube analysis
    Measures: count_exposure
    Dimensions: Time, Location, Patient, Contact
    """
    __tablename__ = 'Fact_Exposure'
    
    exposure_id = Column(BigInteger, primary_key=True, autoincrement=True)
    time_id = Column(Integer, ForeignKey('Dim_Time.time_id'), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey('Dim_Location.location_id'), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey('Dim_Patient.patient_id'), nullable=False, index=True)
    contact_patient_id = Column(Integer, ForeignKey('Dim_Patient.patient_id'), nullable=True, index=True)
    count_exposure = Column(Integer, nullable=False, default=1)
    exposure_strength = Column(Numeric(10, 4))
    sars_status_patient = Column(String(20))
    susceptibility_status = Column(String(50))
    variant_type = Column(String(100))
    contact_duration_category = Column(String(50))
    is_threshold_exceeded = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    time_dimension = relationship('DimTime', back_populates='exposure_facts')
    location_dimension = relationship('DimLocation', back_populates='exposure_facts')
    patient_dimension = relationship(
        'DimPatient',
        foreign_keys=[patient_id],
        back_populates='exposure_facts'
    )
    contact_patient_dimension = relationship(
        'DimPatient',
        foreign_keys=[contact_patient_id],
        back_populates='contact_exposures'
    )
    
    def __repr__(self):
        return (f"<FactExposure(exposure_id={self.exposure_id}, "
                f"time_id={self.time_id}, location_id={self.location_id}, "
                f"count_exposure={self.count_exposure})>")


# ============================================================================
# DATABASE CONNECTION & SESSION MANAGEMENT
# ============================================================================

class DatabaseManager:
    """
    Manages database connections and operations for the Data Warehouse
    Supports multiple database backends (PostgreSQL, MySQL, SQLite)
    """
    
    def __init__(self, connection_string: str, echo: bool = False):
        """
        Initialize database manager with connection string
        
        Args:
            connection_string: SQLAlchemy connection string
                Examples:
                - PostgreSQL: postgresql://user:password@localhost:5432/warehouse_db
                - MySQL: mysql+pymysql://user:password@localhost:3306/warehouse_db
                - SQLite: sqlite:///./warehouse.db
                - SQL Server: mssql+pyodbc://user:password@host:1433/db?driver=ODBC+Driver+18+for+SQL+Server
            echo: Whether to echo SQL statements (for debugging)
        """
        self.connection_string = connection_string
        engine_kwargs = {"echo": echo}
        if connection_string == "sqlite:///:memory:":
            engine_kwargs.update(
                {
                    "poolclass": StaticPool,
                    "connect_args": {"check_same_thread": False},
                }
            )
        elif not connection_string.startswith("sqlite"):
            engine_kwargs.update(
                {
                    "poolclass": QueuePool,
                    "pool_size": 10,
                    "max_overflow": 20,
                    "pool_pre_ping": True,
                }
            )

        self.engine = create_engine(connection_string, **engine_kwargs)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
    
    def create_all_tables(self):
        """Create all tables based on ORM model definitions"""
        Base.metadata.create_all(self.engine)
        print("✓ All tables created successfully")
    
    def drop_all_tables(self):
        """Drop all tables (USE WITH CAUTION)"""
        Base.metadata.drop_all(self.engine)
        print("✓ All tables dropped successfully")
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()
    
    def close(self):
        """Close database connection"""
        self.engine.dispose()
    
    # ========================================================================
    # DIMENSION TABLE OPERATIONS
    # ========================================================================
    
    def insert_time_dimension(self, session: Session, time_records: List[Dict[str, Any]]) -> int:
        """
        Insert time dimension records
        
        Args:
            session: SQLAlchemy session
            time_records: List of dictionaries with time attributes
            
        Returns:
            Number of records inserted
        """
        session.bulk_insert_mappings(DimTime, time_records)
        session.commit()
        return len(time_records)
    
    def insert_location_dimension(self, session: Session, location_records: List[Dict[str, Any]]) -> int:
        """
        Insert location dimension records
        
        Args:
            session: SQLAlchemy session
            location_records: List of dictionaries with location attributes
            
        Returns:
            Number of records inserted
        """
        session.bulk_insert_mappings(DimLocation, location_records)
        session.commit()
        return len(location_records)
    
    def insert_patient_dimension(self, session: Session, patient_records: List[Dict[str, Any]]) -> int:
        """
        Insert patient dimension records
        
        Args:
            session: SQLAlchemy session
            patient_records: List of dictionaries with patient attributes
            
        Returns:
            Number of records inserted
        """
        session.bulk_insert_mappings(DimPatient, patient_records)
        session.commit()
        return len(patient_records)
    
    # ========================================================================
    # FACT TABLE OPERATIONS
    # ========================================================================
    
    def insert_exposure_fact(self, session: Session, exposure_records: List[Dict[str, Any]]) -> int:
        """
        Insert exposure fact records
        
        Args:
            session: SQLAlchemy session
            exposure_records: List of dictionaries with exposure attributes
            
        Returns:
            Number of records inserted
        """
        session.bulk_insert_mappings(FactExposure, exposure_records)
        session.commit()
        return len(exposure_records)
    
    def insert_exposure_fact_single(self, session: Session, **kwargs) -> FactExposure:
        """
        Insert a single exposure fact record
        
        Args:
            session: SQLAlchemy session
            **kwargs: Exposure attributes
            
        Returns:
            Created FactExposure object
        """
        exposure = FactExposure(**kwargs)
        session.add(exposure)
        session.commit()
        session.refresh(exposure)
        return exposure
    
    # ========================================================================
    # QUERY OPERATIONS
    # ========================================================================
    
    def get_exposure_by_location_time(
        self,
        session: Session,
        location_id: int,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """
        Query exposures filtered by location and date range
        
        Args:
            session: SQLAlchemy session
            location_id: Location dimension ID
            start_date: Start date
            end_date: End date
            
        Returns:
            List of exposure records
        """
        query = (
            session.query(FactExposure)
            .join(DimTime)
            .filter(
                FactExposure.location_id == location_id,
                DimTime.date_full >= start_date,
                DimTime.date_full <= end_date,
                FactExposure.is_threshold_exceeded == True
            )
        )
        return [
            {
                'exposure_id': r.exposure_id,
                'count_exposure': r.count_exposure,
                'date': r.time_dimension.date_full,
                'sars_status': r.sars_status_patient,
                'variant': r.variant_type
            }
            for r in query.all()
        ]
    
    def get_exposure_summary(self, session: Session) -> Dict[str, Any]:
        """
        Get overall exposure summary statistics
        
        Args:
            session: SQLAlchemy session
            
        Returns:
            Dictionary with summary statistics
        """
        total_exposures = session.query(func.count(FactExposure.exposure_id)).scalar()
        total_exposure_count = session.query(func.sum(FactExposure.count_exposure)).scalar()
        unique_patients = session.query(func.count(func.distinct(FactExposure.patient_id))).scalar()
        unique_locations = session.query(func.count(func.distinct(FactExposure.location_id))).scalar()
        
        return {
            'total_exposures': total_exposures,
            'total_exposure_measure': total_exposure_count,
            'unique_patients': unique_patients,
            'unique_locations': unique_locations
        }
    
    def get_patient_exposures(
        self,
        session: Session,
        patient_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get all exposures for a specific patient
        
        Args:
            session: SQLAlchemy session
            patient_id: Patient dimension ID
            
        Returns:
            List of exposure records
        """
        query = (
            session.query(FactExposure)
            .filter(FactExposure.patient_id == patient_id)
            .order_by(FactExposure.created_at.desc())
        )
        return [
            {
                'exposure_id': r.exposure_id,
                'date': r.time_dimension.date_full,
                'location': r.location_dimension.site_name,
                'count_exposure': r.count_exposure,
                'variant': r.variant_type
            }
            for r in query.all()
        ]
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database"""
        return table_name in [table.name for table in Base.metadata.tables.values()]
    
    def get_row_count(self, session: Session, model_class) -> int:
        """Get row count for a specific table"""
        mapper = sqlalchemy_inspect(model_class)
        primary_key = mapper.primary_key[0]
        return int(session.query(func.count(primary_key)).scalar() or 0)
    
    def delete_all_exposure_facts(self, session: Session) -> int:
        """Delete all exposure facts (for reloading data)"""
        count = session.query(FactExposure).delete()
        session.commit()
        return count


# ============================================================================
# HELPER FUNCTION
# ============================================================================

def get_database_manager(
    db_type: str = 'sqlite',
    host: str = 'localhost',
    port: int = None,
    database: str = 'warehouse_db',
    user: str = None,
    password: str = None,
    echo: bool = False
) -> DatabaseManager:
    """
    Factory function to create DatabaseManager with appropriate connection string
    
    Args:
        db_type: Database type ('sqlite', 'postgresql', 'mysql', 'mssql')
        host: Database host
        port: Database port
        database: Database name
        user: Database user
        password: Database password
        echo: Whether to echo SQL statements
        
    Returns:
        DatabaseManager instance
    """
    
    if db_type == 'sqlite':
        if database == ':memory:':
            connection_string = 'sqlite:///:memory:'
        elif database.startswith('sqlite:'):
            connection_string = database
        elif database.endswith('.db'):
            connection_string = f'sqlite:///{database}'
        else:
            connection_string = f'sqlite:///{database}.db'
    elif db_type == 'postgresql':
        port = port or 5432
        connection_string = f'postgresql://{user}:{password}@{host}:{port}/{database}'
    elif db_type == 'mysql':
        port = port or 3306
        connection_string = f'mysql+pymysql://{user}:{password}@{host}:{port}/{database}'
    elif db_type in {'mssql', 'sqlserver'}:
        port = port or 1433
        driver = os.getenv('MSSQL_ODBC_DRIVER', 'ODBC Driver 18 for SQL Server')
        driver_param = driver.replace(' ', '+')
        connection_string = (
            f'mssql+pyodbc://{user}:{password}@{host}:{port}/{database}'
            f'?driver={driver_param}&TrustServerCertificate=yes'
        )
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
    
    return DatabaseManager(connection_string, echo=echo)


if __name__ == '__main__':
    """
    Example usage of DatabaseManager
    """
    # Create SQLite database manager
    db_manager = get_database_manager(db_type='sqlite', database='warehouse', echo=False)
    
    # Create all tables
    db_manager.create_all_tables()
    
    # Get a session
    session = db_manager.get_session()
    
    # Example: Insert sample time dimension
    sample_time = {
        'time_id': 1,
        'date_full': date(2024, 1, 1),
        'year': 2024,
        'month': 1,
        'day': 1,
        'week_of_year': 1,
        'quarter': 1,
        'day_of_week': 'Monday',
        'is_weekend': False
    }
    db_manager.insert_time_dimension(session, [sample_time])
    print("✓ Sample data inserted successfully")
    
    # Get summary
    summary = db_manager.get_exposure_summary(session)
    print(f"Exposure Summary: {summary}")
    
    session.close()
    print("✓ Database connection closed")
