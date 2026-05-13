"""
Data Loader Module
Loads data from ETL output into the Data Warehouse
Converts raw data into dimension and fact table formats
"""

import pandas as pd
from datetime import datetime, date
from typing import List, Dict, Any, Tuple
from pathlib import Path


class DataWarehouseLoader:
    """
    Loads and transforms data from ETL sources into Data Warehouse format
    """
    
    def __init__(self, data_dir: str = 'data/processed'):
        """
        Initialize data loader
        
        Args:
            data_dir: Directory containing processed data files
        """
        self.data_dir = Path(data_dir)
        self.df_final_dataset = None
        self.df_contact_network = None
    
    def load_source_data(self):
        """Load source data from CSV files"""
        try:
            final_dataset_path = self.data_dir / 'sashts_final_dataset.csv'
            network_path = self.data_dir / '../raw/sashts_contact_network.csv'
            
            self.df_final_dataset = pd.read_csv(final_dataset_path)
            self.df_contact_network = pd.read_csv(network_path)
            
            print(f"✓ Loaded final dataset: {len(self.df_final_dataset)} rows")
            print(f"✓ Loaded contact network: {len(self.df_contact_network)} rows")
            
        except FileNotFoundError as e:
            print(f"✗ Error loading data: {e}")
            raise
    
    # ========================================================================
    # DIMENSION TABLE LOADERS
    # ========================================================================
    
    def generate_time_dimension(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """
        Generate time dimension table
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            List of time dimension records
        """
        time_records = []
        current_date = start_date
        time_id = 1
        
        while current_date <= end_date:
            time_id_val = int(current_date.strftime('%Y%m%d'))
            record = {
                'time_id': time_id_val,
                'date_full': current_date,
                'year': current_date.year,
                'month': current_date.month,
                'day': current_date.day,
                'week_of_year': current_date.isocalendar()[1],
                'quarter': (current_date.month - 1) // 3 + 1,
                'day_of_week': current_date.strftime('%A'),
                'is_weekend': current_date.weekday() >= 5
            }
            time_records.append(record)
            current_date = pd.Timestamp(current_date) + pd.Timedelta(days=1)
            time_id += 1
        
        return time_records
    
    def generate_location_dimension(self) -> List[Dict[str, Any]]:
        """
        Generate location dimension from unique sites
        
        Returns:
            List of location dimension records
        """
        if self.df_final_dataset is None:
            raise ValueError("Source data not loaded. Call load_source_data() first.")
        
        sites = self.df_final_dataset['site'].unique()
        location_records = []
        
        for location_id, site in enumerate(sites, 1):
            record = {
                'location_id': location_id,
                'site_code': site.upper().replace(' ', '_'),
                'site_name': site,
                'region': site,  # Can be enhanced with mapping
                'country': 'South Africa'
            }
            location_records.append(record)
        
        return location_records
    
    def generate_patient_dimension(self) -> List[Dict[str, Any]]:
        """
        Generate patient dimension from individuals
        
        Returns:
            List of patient dimension records
        """
        if self.df_final_dataset is None:
            raise ValueError("Source data not loaded. Call load_source_data() first.")
        
        patient_records = []
        patient_id = 1
        
        for _, row in self.df_final_dataset.iterrows():
            record = {
                'patient_id': patient_id,
                'patient_code': row['indid'],
                'age_group': row.get('agegrp9', 'Unknown'),
                'sex': row.get('sex', 'Unknown'),
                'bmi_category': row.get('bmicat', None),
                'smoking_status': row.get('smokecignow1', None),
                'household_id': row.get('hhid', None),
                'role_in_network': row.get('index', 'Contact'),
                'sars_status': row.get('sars', 'Unknown')
            }
            patient_records.append(record)
            patient_id += 1
        
        return patient_records
    
    # ========================================================================
    # FACT TABLE LOADER
    # ========================================================================
    
    def generate_exposure_facts(
        self,
        site_to_location_id: Dict[str, int],
        patient_code_to_id: Dict[str, int],
        threshold: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Generate exposure fact records from contact network
        
        Args:
            site_to_location_id: Mapping of site names to location IDs
            patient_code_to_id: Mapping of patient codes to patient IDs
            threshold: Minimum exposure count to include
            
        Returns:
            List of exposure fact records
        """
        if self.df_contact_network is None:
            raise ValueError("Contact network data not loaded. Call load_source_data() first.")
        
        exposure_facts = []
        exposure_id = 1
        
        for _, row in self.df_contact_network.iterrows():
            # Extract patient information
            patient_code = row.get('patient_id') or row.get('indid')
            contact_code = row.get('contact_id') or row.get('contact_indid')
            
            if patient_code not in patient_code_to_id:
                continue
            
            # Get location
            site = row.get('site', 'Unknown')
            location_id = site_to_location_id.get(site, 1)
            
            # Create fact record
            fact = {
                'exposure_id': exposure_id,
                'time_id': int(datetime.now().strftime('%Y%m%d')),  # Can be customized
                'location_id': location_id,
                'patient_id': patient_code_to_id.get(patient_code),
                'contact_patient_id': patient_code_to_id.get(contact_code),
                'count_exposure': row.get('exposure_count', 1),
                'exposure_strength': row.get('contact_strength', None),
                'sars_status_patient': row.get('sars_status', 'Unknown'),
                'susceptibility_status': row.get('susceptibility', None),
                'variant_type': row.get('variant', None),
                'contact_duration_category': row.get('contact_duration', None),
                'is_threshold_exceeded': row.get('exposure_count', 1) >= threshold
            }
            
            if fact['patient_id'] is not None:  # Only add if we have valid patient ID
                exposure_facts.append(fact)
                exposure_id += 1
        
        return exposure_facts
    
    # ========================================================================
    # MAIN LOADING ORCHESTRATION
    # ========================================================================
    
    def load_to_warehouse(
        self,
        db_manager,
        start_date: date = date(2022, 1, 1),
        end_date: date = date(2024, 12, 31),
        threshold: int = 2
    ) -> Dict[str, int]:
        """
        Load all data into warehouse tables
        
        Args:
            db_manager: DatabaseManager instance
            start_date: Time dimension start date
            end_date: Time dimension end date
            threshold: Exposure threshold for fact table
            
        Returns:
            Summary of loaded records
        """
        self.load_source_data()
        session = db_manager.get_session()
        
        try:
            # Load dimensions
            print("\n📊 Loading Dimensions...")
            
            time_records = self.generate_time_dimension(start_date, end_date)
            time_count = db_manager.insert_time_dimension(session, time_records)
            print(f"  ✓ Time dimension: {time_count} records")
            
            location_records = self.generate_location_dimension()
            location_count = db_manager.insert_location_dimension(session, location_records)
            print(f"  ✓ Location dimension: {location_count} records")
            
            patient_records = self.generate_patient_dimension()
            patient_count = db_manager.insert_patient_dimension(session, patient_records)
            print(f"  ✓ Patient dimension: {patient_count} records")
            
            # Create lookup dictionaries
            site_to_location_id = {
                r['site_name']: r['location_id'] for r in location_records
            }
            patient_code_to_id = {
                r['patient_code']: r['patient_id'] for r in patient_records
            }
            
            # Load facts
            print("\n🔍 Loading Fact Table...")
            exposure_facts = self.generate_exposure_facts(
                site_to_location_id,
                patient_code_to_id,
                threshold
            )
            exposure_count = db_manager.insert_exposure_fact(session, exposure_facts)
            print(f"  ✓ Exposure facts: {exposure_count} records")
            
            # Summary
            summary = {
                'time_records': time_count,
                'location_records': location_count,
                'patient_records': patient_count,
                'exposure_records': exposure_count
            }
            
            print(f"\n✅ Data loading completed!")
            print(f"   Summary: {summary}")
            
            return summary
            
        except Exception as e:
            session.rollback()
            print(f"✗ Error during data loading: {e}")
            raise
        finally:
            session.close()


if __name__ == '__main__':
    """
    Example usage
    """
    from db_manager import get_database_manager
    
    # Create database manager
    db_manager = get_database_manager(db_type='sqlite', database='warehouse')
    db_manager.create_all_tables()
    
    # Load data
    loader = DataWarehouseLoader(data_dir='../../data/processed')
    summary = loader.load_to_warehouse(db_manager)
