/*
 * SPATIOTEMPORAL EPIDEMIC PREDICTION - DATA WAREHOUSE
 * SQL Server Star Schema for Iceberg Cube result storage.
 *
 * PostgreSQL users can run sql/schema.sql.
 */

IF OBJECT_ID(N'dbo.Fact_Exposure', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Dim_Time (
        time_id INT NOT NULL CONSTRAINT pk_dim_time PRIMARY KEY,
        date_full DATE NOT NULL CONSTRAINT uq_dim_time_date UNIQUE,
        [year] INT NOT NULL,
        [month] INT NOT NULL,
        [day] INT NOT NULL,
        week_of_year INT NOT NULL,
        [quarter] INT NOT NULL,
        day_of_week VARCHAR(10) NOT NULL,
        is_weekend BIT NOT NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT df_dim_time_created_at DEFAULT SYSUTCDATETIME()
    );

    CREATE TABLE dbo.Dim_Location (
        location_id INT NOT NULL CONSTRAINT pk_dim_location PRIMARY KEY,
        site_code VARCHAR(50) NOT NULL CONSTRAINT uq_dim_location_site_code UNIQUE,
        site_name VARCHAR(255) NOT NULL,
        region VARCHAR(100) NULL,
        country VARCHAR(100) NOT NULL CONSTRAINT df_dim_location_country DEFAULT 'South Africa',
        latitude DECIMAL(10, 8) NULL,
        longitude DECIMAL(11, 8) NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT df_dim_location_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT df_dim_location_updated_at DEFAULT SYSUTCDATETIME()
    );

    CREATE TABLE dbo.Dim_Patient (
        patient_id INT NOT NULL CONSTRAINT pk_dim_patient PRIMARY KEY,
        patient_code VARCHAR(50) NOT NULL CONSTRAINT uq_dim_patient_patient_code UNIQUE,
        age_group VARCHAR(20) NOT NULL,
        sex VARCHAR(10) NOT NULL,
        bmi_category VARCHAR(50) NULL,
        smoking_status VARCHAR(50) NULL,
        household_id VARCHAR(50) NULL,
        role_in_network VARCHAR(50) NOT NULL CONSTRAINT df_dim_patient_role DEFAULT 'Contact',
        sars_status VARCHAR(20) NOT NULL CONSTRAINT df_dim_patient_sars DEFAULT 'Unknown',
        created_at DATETIME2 NOT NULL CONSTRAINT df_dim_patient_created_at DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL CONSTRAINT df_dim_patient_updated_at DEFAULT SYSUTCDATETIME()
    );

    CREATE TABLE dbo.Fact_Exposure (
        exposure_id BIGINT IDENTITY(1, 1) NOT NULL CONSTRAINT pk_fact_exposure PRIMARY KEY,
        time_id INT NOT NULL,
        location_id INT NOT NULL,
        patient_id INT NOT NULL,
        contact_patient_id INT NULL,
        count_exposure INT NOT NULL CONSTRAINT df_fact_exposure_count DEFAULT 1,
        exposure_strength DECIMAL(10, 4) NULL,
        sars_status_patient VARCHAR(20) NULL,
        susceptibility_status VARCHAR(50) NULL,
        variant_type VARCHAR(100) NULL,
        contact_duration_category VARCHAR(50) NULL,
        is_threshold_exceeded BIT NOT NULL CONSTRAINT df_fact_exposure_threshold DEFAULT 1,
        created_at DATETIME2 NOT NULL CONSTRAINT df_fact_exposure_created_at DEFAULT SYSUTCDATETIME(),

        CONSTRAINT fk_exposure_time FOREIGN KEY (time_id) REFERENCES dbo.Dim_Time(time_id),
        CONSTRAINT fk_exposure_location FOREIGN KEY (location_id) REFERENCES dbo.Dim_Location(location_id),
        CONSTRAINT fk_exposure_patient FOREIGN KEY (patient_id) REFERENCES dbo.Dim_Patient(patient_id),
        CONSTRAINT fk_exposure_contact FOREIGN KEY (contact_patient_id) REFERENCES dbo.Dim_Patient(patient_id),
        CONSTRAINT chk_fact_exposure_count_positive CHECK (count_exposure > 0)
    );

END;

IF OBJECT_ID(N'dbo.Fact_Iceberg_Cuboid', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Fact_Iceberg_Cuboid (
        cuboid_id BIGINT IDENTITY(1, 1) NOT NULL CONSTRAINT pk_fact_iceberg_cuboid PRIMARY KEY,
        run_id VARCHAR(64) NOT NULL,
        dimension_values_json NVARCHAR(MAX) NOT NULL,
        support_count INT NOT NULL,
        min_sup INT NOT NULL,
        month_id INT NULL,
        ind1_site VARCHAR(100) NULL,
        ind2_site VARCHAR(100) NULL,
        pair_sars VARCHAR(100) NULL,
        created_at DATETIME2 NOT NULL CONSTRAINT df_fact_iceberg_created_at DEFAULT SYSUTCDATETIME(),

        CONSTRAINT chk_iceberg_support_positive CHECK (support_count > 0),
        CONSTRAINT chk_iceberg_min_sup_positive CHECK (min_sup > 0)
    );
END;

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_dim_time_date')
    CREATE INDEX idx_dim_time_date ON dbo.Dim_Time(date_full);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_dim_time_year_month')
    CREATE INDEX idx_dim_time_year_month ON dbo.Dim_Time([year], [month]);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_dim_location_site_code')
    CREATE INDEX idx_dim_location_site_code ON dbo.Dim_Location(site_code);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_dim_location_site_name')
    CREATE INDEX idx_dim_location_site_name ON dbo.Dim_Location(site_name);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_dim_patient_patient_code')
    CREATE INDEX idx_dim_patient_patient_code ON dbo.Dim_Patient(patient_code);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_dim_patient_age_group')
    CREATE INDEX idx_dim_patient_age_group ON dbo.Dim_Patient(age_group);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_dim_patient_sex')
    CREATE INDEX idx_dim_patient_sex ON dbo.Dim_Patient(sex);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_dim_patient_household')
    CREATE INDEX idx_dim_patient_household ON dbo.Dim_Patient(household_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_fact_exposure_time')
    CREATE INDEX idx_fact_exposure_time ON dbo.Fact_Exposure(time_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_fact_exposure_location')
    CREATE INDEX idx_fact_exposure_location ON dbo.Fact_Exposure(location_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_fact_exposure_patient')
    CREATE INDEX idx_fact_exposure_patient ON dbo.Fact_Exposure(patient_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_fact_exposure_contact')
    CREATE INDEX idx_fact_exposure_contact ON dbo.Fact_Exposure(contact_patient_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_fact_exposure_composite')
    CREATE INDEX idx_fact_exposure_composite ON dbo.Fact_Exposure(time_id, location_id, patient_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_fact_exposure_threshold')
    CREATE INDEX idx_fact_exposure_threshold ON dbo.Fact_Exposure(is_threshold_exceeded);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_fact_iceberg_run')
    CREATE INDEX idx_fact_iceberg_run ON dbo.Fact_Iceberg_Cuboid(run_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_fact_iceberg_month')
    CREATE INDEX idx_fact_iceberg_month ON dbo.Fact_Iceberg_Cuboid(month_id);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_fact_iceberg_site_pair')
    CREATE INDEX idx_fact_iceberg_site_pair ON dbo.Fact_Iceberg_Cuboid(ind1_site, ind2_site);
GO

CREATE OR ALTER VIEW dbo.v_exposure_summary AS
SELECT
    fe.exposure_id,
    dt.date_full,
    dt.[year],
    dt.[month],
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
FROM dbo.Fact_Exposure fe
JOIN dbo.Dim_Time dt ON fe.time_id = dt.time_id
JOIN dbo.Dim_Location dl ON fe.location_id = dl.location_id
JOIN dbo.Dim_Patient dp ON fe.patient_id = dp.patient_id
WHERE fe.is_threshold_exceeded = 1;
GO

CREATE OR ALTER VIEW dbo.v_exposure_network AS
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
FROM dbo.Fact_Exposure fe
JOIN dbo.Dim_Time dt ON fe.time_id = dt.time_id
JOIN dbo.Dim_Location dl ON fe.location_id = dl.location_id
JOIN dbo.Dim_Patient dp_primary ON fe.patient_id = dp_primary.patient_id
LEFT JOIN dbo.Dim_Patient dp_contact ON fe.contact_patient_id = dp_contact.patient_id
WHERE fe.is_threshold_exceeded = 1
  AND fe.contact_patient_id IS NOT NULL;
GO

CREATE OR ALTER VIEW dbo.v_exposure_by_location_time AS
SELECT
    dt.[year],
    dt.[month],
    dt.date_full,
    dl.site_name,
    dl.region,
    COUNT(fe.exposure_id) AS total_exposures,
    SUM(fe.count_exposure) AS total_exposure_count,
    COUNT(DISTINCT fe.patient_id) AS unique_patients,
    COUNT(DISTINCT fe.contact_patient_id) AS unique_contacts,
    AVG(fe.exposure_strength) AS avg_exposure_strength
FROM dbo.Fact_Exposure fe
JOIN dbo.Dim_Time dt ON fe.time_id = dt.time_id
JOIN dbo.Dim_Location dl ON fe.location_id = dl.location_id
WHERE fe.is_threshold_exceeded = 1
GROUP BY dt.[year], dt.[month], dt.date_full, dl.site_name, dl.region;
GO
