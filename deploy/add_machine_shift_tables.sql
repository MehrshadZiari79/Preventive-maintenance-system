/* ==========================================================================
   Gela PM System - machine-hours shift log tables (run ONCE)
   ==========================================================================

   Adds two NEW tables. Nothing existing is changed or deleted.

       machine_shift_logs        one row per machine + date + shift
       machine_downtime_events   the stops inside a shift (from-to + reason)

   Before running: take a full manual backup of PM_Database.
   Run it as the application login (pm_app) - db_setup.bat does this.
   The existing tables (equipment, ...) belong to that login, and the new
   tables must be created next to them so the link to equipment works.
   Safe to run twice: existing tables are left alone.
   Works on SQL Server 2000 and newer.
   ========================================================================== */

SET NOCOUNT ON

IF OBJECT_ID('machine_shift_logs') IS NULL
BEGIN
    CREATE TABLE machine_shift_logs (
        id                      INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        equipment_id            INT           NOT NULL
                                REFERENCES equipment(id),
        log_date                DATETIME      NOT NULL,   -- day the shift started (00:00)
        shift_name              NVARCHAR(30)  NOT NULL,
        start_time              DATETIME      NULL,
        end_time                DATETIME      NULL,
        planned_stop_minutes    INT           NOT NULL DEFAULT 0,
        unplanned_stop_minutes  INT           NOT NULL DEFAULT 0,
        output_units            INT           NULL,
        notes                   NVARCHAR(500) NULL,
        created_by              NVARCHAR(100) NULL,
        created_at              DATETIME      NULL,
        updated_at              DATETIME      NULL
    )
    CREATE UNIQUE INDEX ux_machine_shift_logs_eq_day_shift
        ON machine_shift_logs (equipment_id, log_date, shift_name)
    CREATE INDEX ix_machine_shift_logs_day
        ON machine_shift_logs (log_date)
    PRINT 'Created machine_shift_logs'
END
ELSE
    PRINT 'machine_shift_logs already exists - left unchanged'
GO

IF OBJECT_ID('machine_downtime_events') IS NULL
BEGIN
    CREATE TABLE machine_downtime_events (
        id                INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        shift_log_id      INT           NOT NULL
                          REFERENCES machine_shift_logs(id) ON DELETE CASCADE,
        start_time        DATETIME      NOT NULL,
        end_time          DATETIME      NOT NULL,
        duration_minutes  INT           NOT NULL,
        category          NVARCHAR(30)  NOT NULL,
        is_planned        BIT           NOT NULL DEFAULT 0,
        detail            NVARCHAR(300) NULL,
        created_at        DATETIME      NULL
    )
    CREATE INDEX ix_machine_downtime_events_log
        ON machine_downtime_events (shift_log_id)
    PRINT 'Created machine_downtime_events'
END
ELSE
    PRINT 'machine_downtime_events already exists - left unchanged'
GO

/* The application login must be able to read/write the new tables.
   If PM System uses a restricted login (pm_app), grant it: */
IF USER_NAME() <> 'pm_app' AND EXISTS (SELECT * FROM sysusers WHERE name = 'pm_app')
BEGIN
    GRANT SELECT, INSERT, UPDATE, DELETE ON machine_shift_logs TO pm_app
    GRANT SELECT, INSERT, UPDATE, DELETE ON machine_downtime_events TO pm_app
    PRINT 'Permissions granted to pm_app'
END
GO
