-- One row per pipeline run. The dashboard status tile and the load-reliability
-- number in the README are both computed from this table, not estimated.
CREATE TABLE run_log (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    rows_in INTEGER NOT NULL DEFAULT 0,
    rows_loaded INTEGER NOT NULL DEFAULT 0,
    rows_rejected INTEGER NOT NULL DEFAULT 0,
    checks_passed INTEGER NOT NULL DEFAULT 0,
    checks_failed INTEGER NOT NULL DEFAULT 0,
    failed_check_names TEXT, -- JSON array of check names that failed
    status TEXT NOT NULL DEFAULT 'running', -- running | success | failed
    duration_seconds REAL
);
