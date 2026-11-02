/* ==========================================================================
   Gela PM System - OPTIONAL one-time correction of old UTC timestamps
   ==========================================================================

   You do NOT have to run this. The application works without it.

   Background
   ----------
   Up to v2.3 a few columns were written in UTC (3:30 hours behind Tehran)
   while everything else was written in Iran time:
       inspections.started_at / completed_at / created_at
       inspection_results.recorded_at
       users.last_login / created_at
       spare_part_transactions.created_at
   From v2.4 on, ALL timestamps are written in Iran time. Rows written before
   the upgrade therefore still show 3:30 hours too early (and an inspection
   done after 20:30 shows the previous day).

   This script moves only those OLD rows forward by 3h30m.

   BEFORE RUNNING
   --------------
   1. Take a full manual backup of PM_Database (as you always do).
   2. Set @cutoff below to the moment v2.4 was installed on the FIRST client
      (Tehran time). Rows at/after that moment are already correct and are
      not touched. Running the script twice would shift the rows twice, so
      run it ONCE.
   3. Run it in SQL Server Management Studio / Query Analyzer against
      PM_Database. Works on SQL Server 2000 and newer.

   Note: rows from before 1401/06/30 (Sept 2022), when Iran still used
   daylight saving, will be 1 hour off during the old summer periods.
   ========================================================================== */

SET NOCOUNT ON
DECLARE @cutoff DATETIME
SET @cutoff = '2026-10-15 08:00:00'   -- <== CHANGE: v2.4 install time (Tehran)

BEGIN TRANSACTION

UPDATE dbo.inspections
   SET started_at = DATEADD(minute, 210, started_at)
 WHERE started_at IS NOT NULL AND started_at < DATEADD(minute, -210, @cutoff)

UPDATE dbo.inspections
   SET completed_at = DATEADD(minute, 210, completed_at)
 WHERE completed_at IS NOT NULL AND completed_at < DATEADD(minute, -210, @cutoff)

UPDATE dbo.inspections
   SET created_at = DATEADD(minute, 210, created_at)
 WHERE created_at IS NOT NULL AND created_at < DATEADD(minute, -210, @cutoff)

UPDATE dbo.inspection_results
   SET recorded_at = DATEADD(minute, 210, recorded_at)
 WHERE recorded_at IS NOT NULL AND recorded_at < DATEADD(minute, -210, @cutoff)

UPDATE dbo.users
   SET last_login = DATEADD(minute, 210, last_login)
 WHERE last_login IS NOT NULL AND last_login < DATEADD(minute, -210, @cutoff)

UPDATE dbo.users
   SET created_at = DATEADD(minute, 210, created_at)
 WHERE created_at IS NOT NULL AND created_at < DATEADD(minute, -210, @cutoff)

UPDATE dbo.spare_part_transactions
   SET created_at = DATEADD(minute, 210, created_at)
 WHERE created_at IS NOT NULL AND created_at < DATEADD(minute, -210, @cutoff)

/* Check the numbers above, then: COMMIT  (or ROLLBACK to undo) */
-- COMMIT TRANSACTION
-- ROLLBACK TRANSACTION
