# PM System v2.4: what changed and how to test it

No existing table or column was changed. Two **new** tables for the machine-hours shift log are added by `deploy/add_machine_shift_tables.sql`, which you run once after a backup. The page also works before the script is run (basic mode). `deploy/optional_fix_legacy_utc_times.sql` is optional. Neither script runs automatically.

**Persian RTL typing:** the native Rich Edit RTL patch (`utils/rtl_patch.py`) is switched **on** at start-up again. The Oct 7 `main.py` (written for the old updater) had dropped this call, which made multi-line boxes such as «شرح درخواست» type left-to-right. It must run before any page is loaded, and `main.py` does that again now. For troubleshooting only, `PM_DISABLE_RTL_PATCH=1` turns it off.

## Bugs fixed

| Area | Problem in v2.3 | Fix |
|---|---|---|
| Dashboard / Reports | `case([...])` syntax is rejected by SQLAlchemy 2.x, so the KPI summary, backlog, PM/CM ratio, equipment report and PM statistics raised an error. The dashboard showed "خطا در دریافت داده‌ها". | Version-safe `case()` |
| KPIs | "Completed" counted only APPROVED in most KPIs, but APPROVED + COMPLETED in personnel performance. | APPROVED + COMPLETED everywhere |
| MTBF | Counted only *approved* failures. | Every corrective/emergency work order except rejected ones |
| MTTR (equipment tab) | Total repair time divided by **all** failures, including ones with no times. | Average over timed, finished repairs |
| Availability / OEE | Repair time of unapproved work orders was used; the value could go negative. Quality was 100 % here but the pass rate elsewhere. | Availability = operating ÷ planned (production logs), limited to 0–100 %. Quality = inspection pass rate, with "na" answers ignored. |
| PM / schedule compliance | Overdue PMs that were never done were ignored, which inflated compliance. An explicit deadline counted same-day work as late. An empty "مدت مجاز" meant 0 days. | Open and overdue = late; deadline day is inclusive; minimum 1 day |
| Cost analysis | Joining part transactions multiplied labour and manual cost by the number of part lines. Work orders with only "IN" transactions disappeared. | Parts summed per work order first |
| Monthly trend | Gregorian months | Jalali months (e.g. 1405/07) |
| Work-order list cost | `float + Decimal` error was swallowed, so **spare parts were never added** to the total cost | Fixed (also cached: 1 query per part instead of per row) |
| Work-order PDF | Selected rows were ignored, so the PDF contained **all** visible work orders | Exports the selected rows |
| PDF selection dialogs | Check-box column on the left and columns reversed; Space/Enter toggled the wrong row; "file in use" gave a raw error | RTL order, keyboard in sync, clear Persian message |
| Work-order filters | Date filters and «اعمال فیلتر» were cut off the screen | Two filter rows |
| Machine hours | Editing the date was ignored. A second record on the same day silently overwrote the first. Default "from" was the Gregorian month start. The last day of a range could be dropped. There was no downtime field. | All fixed; the page was rebuilt |
| Role manager | Repair requests and personnel pages couldn't be granted. The layout was mirrored. A new role wasn't selected after creating it. Unsaved changes were lost. Names over 20 characters broke user saving. | Rebuilt; roles can also be renamed |
| Time | Several columns were written in UTC (3:30 behind). `datetime.now()` is wrong on PCs with an outdated Iran DST rule. | All "now" values = real Tehran time (tz database) |
| Theme | Pages switched the global ttk theme when opened (work orders → "default", others → "clam"), so the look changed depending on page order | One theme, set once |
| Top bar | Buttons squashed and the status text was invisible | Rebuilt, with a live Jalali clock |
| Updater | Network check ran on the UI thread (window could freeze). Standard users couldn't install (UAC). "Mandatory" could be declined. | New SYSTEM updater (see DEPLOY_UPDATES.md) |
| `__init__.py` (root) | Contained Windows batch commands, so it wasn't valid Python | Fixed |

## New
* **ساعت کار ماشین: standard shift log** (the CMMS/OEE structure), with three tabs:
  * **برگه روزانه (شیفت)**: pick a date and shift. All machines are rows. Type start, finish and output, and Enter moves to the next cell like Excel. Typing only the output fills in the shift's times. Del clears a row ("didn't run").
    * Stops of the selected machine are entered below the sheet as from–to + reason. Unplanned reasons: mechanical, electrical/controls, utilities, no milk/material, changeover, process/quality, operator. Planned reasons: CIP, planned maintenance, break, no production plan.
    * Calculated: planned production = window − planned stops; run time = planned production − unplanned stops; availability = run ÷ planned production. Night shifts are supported, and overlapping or out-of-window stops are refused.
    * One "ذخیره همه" (Ctrl+S) saves the sheet. Leaving the page or changing the date asks about unsaved rows.
  * **سوابق تجهیز**: daily totals per machine (the previous page), with KPIs and Excel. Days entered through the sheet are edited there.
  * **علل توقف (پارتو)**: hours lost per reason in a period, largest first.
  * Shifts (1–3, name + times) are set with the ⚙ button by admin or manager.
  * Every save also writes the day's totals into `production_logs`, so dashboard, reports and OEE use the new data automatically.
* **Unfinished work-order reminder**: technician and manager only, at login and every 10 minutes. It's a non-blocking Persian notice with a sound and a "مشاهده دستور کارها" button. The database check runs in the background.
* **Silent auto-update** with a 2-minute countdown, and the app reopens itself.
* App starts for **every** Windows user at logon.
* All tables show RTL column order (first column on the right).
* Login window: company logo, version, live Jalali date.
* Users table shows role names in Persian.
* Technicians can add and edit machine-hours records (deleting still needs a role with delete permission).

## Faster
* Equipment-performance report: 4 grouped queries instead of 1–4 queries **per equipment**.
* Risk score: 1 grouped query instead of 1 per equipment.
* Dashboard loads only the 6 newest work orders and inspections (it loaded all of them).
* Work-order list: part prices cached per load.

## Things to decide later (not changed)
* ~~`init_db()` resets the admin password on every login; database passwords in `db.py` and `config.py`.~~ Fixed in the repository clean-up below.
* OEE "performance" is a fixed 95 % assumption (no ideal-rate data exists), and labour cost uses a fixed rate of 50 per hour. Both are unchanged.

## Logic audit fixes (v2.4.1)
* **Spare parts on finish are now all-or-nothing.** Before, if one part had too little stock, the parts before it were already deducted but the work order was not saved; finishing again deducted them a second time. Stock is now checked for every part first, and the deduction is saved in the same transaction as the work order. An invalid delay or cost is rejected before any stock moves.
* A finish time earlier than the work order's start time is rejected (it produced negative repair times in MTTR).
* Rejecting a finish request no longer stacks titles like «... (اصلاحی) (اصلاحی)».
* Auto-PM work order titles show the Jalali due date.
* Deleting equipment no longer fails with a database error when its work orders have technicians or completion personnel, or when it has machine shift sheet rows.
* Deleting several users at once now reports failures instead of silently skipping them.
* Spare parts statistics use one grouped query instead of one query per part (same numbers, faster page).
* New `release.bat`: one command builds, versions and publishes an update.

## v2.4.2 – approved logic changes, reports, shortcuts, screens
* **Users and equipment with history are kept.** Deleting a user who appears in work orders, inspections, repair requests or the activity log, or equipment with work orders, inspections or machine hours, is refused with a clear message; the app offers to deactivate it instead. Unused records can still be deleted.
* **Rejected finish → corrective work order** gets a fresh deadline (same allowed duration as the original, at least one day) instead of the old, already-passed one.
* **Inspections:** if every checkpoint is "not applicable" the overall result is *no result* instead of *partial*. «ذخیره پیشرفت» no longer completes the inspection after the first checkpoint (it used to, and the rest then failed).
* **Inventory value** uses the weighted average purchase price.
* **PM next due** stays: actual completion date + interval (confirmed).
* **Reports:** new tab «شاخص‌های استاندارد» – planned vs emergency work, PM compliance, availability, MTBF, MTTR, response time, repeat failures, backlog age, overdue PMs, bad actors, critical and most-used spare parts, repair requests. Tabs are in right-to-left order with shorter names, and cards wrap on narrow windows.
* **Dashboard:** «کارهای باز» showed 0 (wrong key) and «دستورکار باز» counted rejected work as open. Both now count pending approval, ready, in progress and finish requested.
* **Keyboard shortcuts** on every page and dialog (see README). Esc no longer switches the main window *into* full screen; it only leaves it.
* **Screens:** dialogs are kept inside the visible screen (taskbar excluded, correct monitor on dual screens); save buttons stay visible on 1366×768 and 1280×720 laptops; pages fill tall monitors; the work-order finish dialog no longer cuts its right side.
* **Speed and size:** unused imports removed; charts and the database layer load in the background while the login screen is open; pandas/sympy/extra matplotlib backends kept out of the installer.

## Role management (مدیریت نقش‌ها و مجوزها)

**Logic.** The permission matrix of a custom role was ignored on most pages: work orders and repair requests only knew the built-in role names, equipment ignored «ایجاد/ویرایش», spare-parts delete was tied to edit, and personnel, reports and activity log refused every custom role even when «مشاهده» was ticked. Now every page uses one rule (`AuthManager.allows`): built-in roles behave exactly as before; custom roles get what is ticked.

| Change | Detail |
|---|---|
| New action «تأیید» | Work orders only: approve creation, final approval, reject a finish request, move back a workflow stage, generate PM work orders. Before, a custom role could never approve. |
| Actions per page | Only actions that mean something can be ticked (dashboard, reports, activity log: «مشاهده» only); the rest show «—». Ticking any action switches «مشاهده» on. |
| Users stay with the admin | «مدیریت کاربران» can never be given to a custom role (whoever manages users could make himself admin). |
| Work orders | «شروع کار» / «ارسال گزارش اتمام» now need «ایجاد/ویرایش» (all built-in roles have it). |
| Equipment | «حذف» also covers the category / location lists. |
| Delete a role | Asks which role its users move to (they were silently made «تکنسین», which could give them more rights). |
| Names | A custom role may not use a built-in role's Persian name («مدیر» …). |
| Activity log | Creating, changing, renaming and deleting roles is logged (entity `role`). |

**Window.** Roles grouped (built-in, locked / custom) with user counts; built-in roles show their **real** permissions read-only (✓ / ✕ / ◐ partly) instead of empty boxes; «＋ نقش جدید» can start from a copy of any role; rename / copy / delete act on the selected role; «بازگردانی» discards changes; click a page name to toggle its row, «همه» to toggle a column; summary line; inline errors in the small dialogs.

## Look and feel refresh (ظاهر جدید)

Only the look changed. Page logic, database, PDF/Excel layouts and Persian typing are untouched. Setting `PM_CLASSIC_UI=1` before starting the program switches the dialogs, table additions and header styling back to the old look; the new side menu always stays.

| Area | What changed |
|---|---|
| Page headers | Every page has the same white header: title and subtitle on the right, buttons on the left, thin bottom line |
| Buttons | One navy main button per page (افزودن / جدید), outlined secondary buttons (Excel, PDF, بروزرسانی), red only for «اضطراری»; red outline for delete |
| Side menu | Grouped (نگهداری و تعمیرات / تحلیل / سازمان و دسترسی), one icon set (Segoe MDL2 / Fluent icons on Windows 10/11, emoji fallback), user card and «خروج» at the bottom. Ctrl+1…9 follows the new order |
| Tables | Coloured status badge in the «وضعیت» column; whole-row status colours removed on work orders, PM and users; light zebra rows and hover highlight; «در حال بارگذاری…» and an empty message with «پاک کردن فیلترها» |
| Counter + chips | «۵ از ۹۶ دستور کار» above the main table of each page, with every active filter as a removable chip |
| Messages | Styled RTL dialogs replace the Windows message boxes (same answers: Yes/No/Cancel, Esc = No/Cancel). Short success messages are a toast in the corner instead of an OK box |
| Forms | Missing or wrong fields get a red frame and a note under the field instead of a pop-up (work order, emergency, PM, equipment, user, spare part, personnel and parts dialogs) |
| Ctrl+K | Quick search: pages, quick actions, equipment by code/name, work order by number |
| Dates | Old automatic PM titles «[A-PM] … 2026-10-21» are shown with the Jalali date everywhere (the database row is not rewritten). Excel «تاریخ تهیه» and default export file names use Jalali date/time |
| Work orders | «وضعیت» and «اپراتور» columns swapped, so the status is visible without scrolling. «ویرایش» and «تغییر وضعیت» (move back to an earlier stage) are open to every role that can open the page; «تأیید» no longer covers the stage change |
| Repair requests | A new request is entered in its own window («＋ درخواست جدید» / Ctrl+N), same entries and rules as before, with inline errors and «اکنون» for the breakdown time. Fixes: the on-page form shared the table's selected row, so filling it in after clicking a row **updated that request** instead of creating a new one |
| Manual | New user manual `PM_System_Manual.pdf` (26 pages, real screenshots), source in `docs/manual/`, rebuilt with `python generate_manual.py`. The old manual printed a default password; the new one does not |

## Windows test checklist (one PC, before publishing)
1. Install over v2.3 as admin and enter the share account. In Task Scheduler, `\GelaPM\PM System Updater` should exist.
2. Log in as each role. Technician and manager get the reminder after about 3 seconds; admin does not.
3. Type mixed Persian/English (`سلام این یک test است`) in «شرح درخواست» (repair request), in a work-order description and in a role name. The text must start on the right and read in the correct order.
4. Dashboard shows numbers (no "خطا در دریافت داده‌ها"). In Reports, every tab opens.
5. ساعت کار ماشین → برگه روزانه:
   * For one machine, type start 07:00, finish 15:00 and output 4000.
   * Add stop 09:10–09:40 «برقی» and stop 12:00–12:45 «شستشو CIP».
   * Expect: planned stop 0:45, breakdown 0:30, production time 7:15, run 6:45, availability 93.1 %.
   * Save, change the date and come back: the values are still there. Check the تب سوابق تجهیز and علل توقف tabs too.
6. Work orders: select 2 rows → PDF contains exactly those 2.
7. Publish a test version 2.4.1 and watch the countdown, the restart, and the "updated" notice.
8. Shortcuts with the **Persian** keyboard layout active: Ctrl+F (search), Ctrl+N (new), Esc (closes the dialog), Ctrl+S in a form, F1 (list). Typing «سلام این یک test است» still works in every box.
9. On a laptop (1366×768, or 1920×1080 at 150 % scaling): open «PM جدید», «دستور کار جدید», «قالب بازرسی», «مدیریت نقش‌ها», «گزارش اتمام کار». The save buttons must be visible without moving the window.
10. Reports → «شاخص‌های استاندارد» opens and shows numbers for the selected period.

## Repository clean-up and secrets

* **No passwords in the source any more.** The database server, login and password moved from `database/db.py` (Base64) and `config.py` (plain text) to `database/db_secrets.py`, which is git-ignored and bundled into the build by PyInstaller. Template: `database/db_secrets.example.py`. `release.py` and `build_release.bat` refuse to build without it. The connection URL is exactly the same as before.
* `init_db()` no longer resets the `admin` password to a value written in the code on every login. It only creates `admin` (with `INITIAL_ADMIN_PASSWORD` from `db_secrets.py`) when the users table is empty.
* Removed unused files: `config.py`, `requirements.py` (outdated package list), `t_jalal.py`, `views/logo_E.py`, `views/views.zip`, `utils/backup.py` (SQLite-era), `utils/.idea/`. `test_auto_pm_date_full.py` moved to `tools/`.
* `gela-logo.ico/.png/.gif` are in the project root again (Setup.iss and the spec use them there).
* New README (screenshots, setup, release, roles, KPIs), LICENSE, `.gitignore` for secrets, local data, logs and editor folders.

