DROP VIEW IF EXISTS v_run_log_status;

-- Answers: the dashboard status tile's source - the most recent run's outcome
-- and the trailing load-reliability percentage, computed straight from
-- run_log rather than estimated.
-- Grain: a single summary row (this view always returns exactly one row).
-- Caveat: "reliability" means a run passed every quality gate, not raw
-- uptime - a run that completed but failed a check counts against it, by
-- design (see README > GitHub Actions).
CREATE VIEW v_run_log_status AS
SELECT
    (SELECT run_date FROM run_log ORDER BY run_id DESC LIMIT 1) AS latest_run_date,
    (SELECT status FROM run_log ORDER BY run_id DESC LIMIT 1) AS latest_run_status,
    (SELECT finished_at FROM run_log ORDER BY run_id DESC LIMIT 1) AS latest_run_finished_at,
    (SELECT COUNT(*) FROM run_log) AS total_runs,
    (SELECT COUNT(*) FROM run_log WHERE status = 'success') AS successful_runs,
    ROUND(
        100.0 * (SELECT COUNT(*) FROM run_log WHERE status = 'success')
        / NULLIF((SELECT COUNT(*) FROM run_log), 0),
        2
    ) AS reliability_pct;
