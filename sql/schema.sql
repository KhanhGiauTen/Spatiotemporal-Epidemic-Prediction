/**
 * SPATIOTEMPORAL EPIDEMIC PREDICTION - DATA WAREHOUSE
 * Star Schema Design for Iceberg Cube Results Storage
 * 
 * Schema Overview:
 * - Dim_Time: Temporal dimension
 * - Dim_Location: Geographic dimension (sites)
 * - Dim_Patient: Patient/Individual dimension
 * - Fact_Exposure: Core fact table tracking exposure events exceeding threshold
 */

-- ============================================================================
-- DIMENSION TABLES
-- ============================================================================

/**
 * Dim_Time: Temporal Dimension
 * Stores date and time attributes for fact records
 */
CREATE TABLE Dim_Time (
    time_id INT PRIMARY KEY NOT NULL,
    date_full DATE NOT NULL,
    year INT NOT NULL,
    month INT NOT NULL,
    day INT NOT NULL,
    week_of_year INT NOT NULL,
    quarter INT NOT NULL,
    day_of_week VARCHAR(10) NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date_full)
);

-- Create index on date_full for efficient time-based queries
CREATE INDEX idx_dim_time_date ON Dim_Time(date_full);
CREATE INDEX idx_dim_time_year_month ON Dim_Time(year, month);


/**
 * Dim_Location: Geographic Dimension
 * Stores location/site information
 */
CREATE TABLE Dim_Location (
    location_id INT PRIMARY KEY NOT NULL,
    site_code VARCHAR(50) NOT NULL UNIQUE,
    site_name VARCHAR(255) NOT NULL,
    region VARCHAR(100),
    country VARCHAR(100) DEFAULT 'South Africa',
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dim_location_site_code ON Dim_Location(site_code);
CREATE INDEX idx_dim_location_site_name ON Dim_Location(site_name);


/**
 * Dim_Patient: Individual/Patient Dimension
 * Stores demographic and health attributes of individuals
 */
CREATE TABLE Dim_Patient (
    patient_id INT PRIMARY KEY NOT NULL,
    patient_code VARCHAR(50) NOT NULL UNIQUE,
    age_group VARCHAR(20) NOT NULL,
    sex VARCHAR(10) NOT NULL,
    bmi_category VARCHAR(50),
    smoking_status VARCHAR(50),
    household_id VARCHAR(50),
    role_in_network VARCHAR(50) DEFAULT 'Contact',  -- 'Index' or 'Contact'
    sars_status VARCHAR(20) DEFAULT 'Unknown',      -- 'Positive', 'Negative', 'Unknown'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dim_patient_patient_code ON Dim_Patient(patient_code);
CREATE INDEX idx_dim_patient_age_group ON Dim_Patient(age_group);
CREATE INDEX idx_dim_patient_sex ON Dim_Patient(sex);
CREATE INDEX idx_dim_patient_household ON Dim_Patient(household_id);


-- ============================================================================
-- FACT TABLE
-- ============================================================================

/**
 * Fact_Exposure: Fact Table
 * Core fact table storing exposure combinations that exceed threshold
 * in Iceberg Cube analysis results.
 * 
 * Each row represents a unique exposure event/combination with:
 * - Spatial dimension (Location)
 * - Temporal dimension (Time)
 * - Individual dimension (Patient)
 * - Contact dimension (Contact/Exposed Patient)
 * - Measures (Count_Exposure)
 */
CREATE TABLE Fact_Exposure (
    exposure_id BIGINT PRIMARY KEY NOT NULL AUTO_INCREMENT,
    time_id INT NOT NULL,
    location_id INT NOT NULL,
    patient_id INT NOT NULL,
    contact_patient_id INT,
    count_exposure INT NOT NULL DEFAULT 1,
    exposure_strength DECIMAL(10, 4),
    sars_status_patient VARCHAR(20),
    susceptibility_status VARCHAR(50),
    variant_type VARCHAR(100),
    contact_duration_category VARCHAR(50),
    is_threshold_exceeded BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Key Constraints
    CONSTRAINT fk_exposure_time FOREIGN KEY (time_id) REFERENCES Dim_Time(time_id),
    CONSTRAINT fk_exposure_location FOREIGN KEY (location_id) REFERENCES Dim_Location(location_id),
    CONSTRAINT fk_exposure_patient FOREIGN KEY (patient_id) REFERENCES Dim_Patient(patient_id),
    CONSTRAINT fk_exposure_contact FOREIGN KEY (contact_patient_id) REFERENCES Dim_Patient(patient_id)
);

-- Create indexes for optimal query performance
CREATE INDEX idx_fact_exposure_time ON Fact_Exposure(time_id);
CREATE INDEX idx_fact_exposure_location ON Fact_Exposure(location_id);
CREATE INDEX idx_fact_exposure_patient ON Fact_Exposure(patient_id);
CREATE INDEX idx_fact_exposure_contact ON Fact_Exposure(contact_patient_id);
CREATE INDEX idx_fact_exposure_composite ON Fact_Exposure(time_id, location_id, patient_id);
CREATE INDEX idx_fact_exposure_threshold ON Fact_Exposure(is_threshold_exceeded);

-- ============================================================================
-- VIEWS FOR ANALYSIS
-- ============================================================================

/**
 * View: v_exposure_summary
 * Summary view combining exposure facts with dimension data
 */
CREATE VIEW v_exposure_summary AS
SELECT 
    fe.exposure_id,
    dt.date_full,
    dt.year,
    dt.month,
    dl.site_name,
    dl.region,
    dp.patient_code,
    dp.age_group,
    dp.sex,
    fe.count_exposure,
    fe.sars_status_patient,
    fe.susceptibility_status,
    fe.variant_type,
    fe.is_threshold_exceeded,
    fe.created_at
FROM Fact_Exposure fe
JOIN Dim_Time dt ON fe.time_id = dt.time_id
JOIN Dim_Location dl ON fe.location_id = dl.location_id
JOIN Dim_Patient dp ON fe.patient_id = dp.patient_id
WHERE fe.is_threshold_exceeded = TRUE;


/**
 * View: v_exposure_network
 * Network view showing exposure relationships between patients
 */
CREATE VIEW v_exposure_network AS
SELECT 
    fe.exposure_id,
    dt.date_full,
    dl.site_name,
    dp_primary.patient_code AS primary_patient_code,
    dp_primary.age_group AS primary_age_group,
    dp_contact.patient_code AS contact_patient_code,
    dp_contact.age_group AS contact_age_group,
    fe.count_exposure,
    fe.sars_status_patient,
    fe.variant_type
FROM Fact_Exposure fe
JOIN Dim_Time dt ON fe.time_id = dt.time_id
JOIN Dim_Location dl ON fe.location_id = dl.location_id
JOIN Dim_Patient dp_primary ON fe.patient_id = dp_primary.patient_id
LEFT JOIN Dim_Patient dp_contact ON fe.contact_patient_id = dp_contact.patient_id
WHERE fe.is_threshold_exceeded = TRUE
  AND fe.contact_patient_id IS NOT NULL;


/**
 * View: v_exposure_by_location_time
 * Aggregated view for location-time analysis
 */
CREATE VIEW v_exposure_by_location_time AS
SELECT 
    dt.year,
    dt.month,
    dt.date_full,
    dl.site_name,
    dl.region,
    COUNT(fe.exposure_id) AS total_exposures,
    SUM(fe.count_exposure) AS total_exposure_count,
    COUNT(DISTINCT fe.patient_id) AS unique_patients,
    COUNT(DISTINCT fe.contact_patient_id) AS unique_contacts,
    AVG(fe.exposure_strength) AS avg_exposure_strength
FROM Fact_Exposure fe
JOIN Dim_Time dt ON fe.time_id = dt.time_id
JOIN Dim_Location dl ON fe.location_id = dl.location_id
WHERE fe.is_threshold_exceeded = TRUE
GROUP BY dt.year, dt.month, dt.date_full, dl.site_name, dl.region;


-- ============================================================================
-- MATERIALIZED VIEW (Optional - for performance optimization)
-- ============================================================================

/**
 * Materialized view for frequently accessed aggregations
 * Useful for large fact tables
 */
CREATE TABLE MV_Exposure_Daily_Summary AS
SELECT 
    dt.date_full,
    dl.location_id,
    dl.site_name,
    COUNT(fe.exposure_id) AS daily_exposures,
    SUM(fe.count_exposure) AS total_exposure_measure,
    COUNT(DISTINCT fe.patient_id) AS daily_unique_patients
FROM Fact_Exposure fe
JOIN Dim_Time dt ON fe.time_id = dt.time_id
JOIN Dim_Location dl ON fe.location_id = dl.location_id
WHERE fe.is_threshold_exceeded = TRUE
GROUP BY dt.date_full, dl.location_id, dl.site_name;

CREATE INDEX idx_mv_exposure_daily_date ON MV_Exposure_Daily_Summary(date_full);
CREATE INDEX idx_mv_exposure_daily_location ON MV_Exposure_Daily_Summary(location_id);
