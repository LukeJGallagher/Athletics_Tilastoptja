-- Azure SQL Schema for Athletics Data
-- Run this in Azure Portal > Query Editor
-- Database: athletics_data

-- Drop existing table if rebuilding
-- IF OBJECT_ID('athletics_data', 'U') IS NOT NULL DROP TABLE athletics_data;

-- Create main athletics data table
CREATE TABLE athletics_data (
    id INT IDENTITY(1,1) PRIMARY KEY,
    Athlete_Name NVARCHAR(200),
    Athlete_CountryCode NVARCHAR(10),
    Gender NVARCHAR(10),
    Event NVARCHAR(100),
    Result NVARCHAR(50),
    result_numeric FLOAT,
    Position NVARCHAR(20),
    Round NVARCHAR(50),
    round_normalized NVARCHAR(50),
    Competition NVARCHAR(300),
    Competition_ID NVARCHAR(20),
    Start_Date DATE,
    year INT,
    wapoints FLOAT,
    Athlete_ID NVARCHAR(20),
    DOB DATE,
    sync_date DATETIME DEFAULT GETDATE()
);

-- Create indexes for common queries
CREATE INDEX idx_athlete_name ON athletics_data(Athlete_Name);
CREATE INDEX idx_country ON athletics_data(Athlete_CountryCode);
CREATE INDEX idx_event ON athletics_data(Event);
CREATE INDEX idx_competition_id ON athletics_data(Competition_ID);
CREATE INDEX idx_year ON athletics_data(year);
CREATE INDEX idx_athlete_id ON athletics_data(Athlete_ID);
CREATE INDEX idx_wapoints ON athletics_data(wapoints);

-- Verify table was created
SELECT 'Table created successfully' AS Status;
SELECT COUNT(*) AS RowCount FROM athletics_data;
