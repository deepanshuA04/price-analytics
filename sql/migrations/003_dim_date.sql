CREATE TABLE dim_date (
    date_key TEXT PRIMARY KEY, -- ISO date, e.g. '2026-08-11'
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL, -- 0=Sunday .. 6=Saturday
    week_of_year INTEGER NOT NULL,
    is_weekend INTEGER NOT NULL
);
