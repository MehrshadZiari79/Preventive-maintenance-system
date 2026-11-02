<div align="center">

<img src="views/gela-logo.png" alt="Gela Dairy" width="96">

# Gela PM System

**سیستم مدیریت نگهداری و تعمیرات — شرکت لبنی گلا، آمل**

Desktop maintenance management (CMMS) for the Gela Dairy plant: equipment, preventive
maintenance, work orders, repair requests, inspections, spare parts, machine hours and
maintenance KPIs, in Persian with the Jalali calendar.

![Version](https://img.shields.io/badge/version-2.4-1A2A44)
![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11%20x64-1A2A44)
![Python](https://img.shields.io/badge/python-3.13-1A2A44)
![UI](https://img.shields.io/badge/UI-Tkinter%20%2F%20ttk-1A2A44)
![Database](https://img.shields.io/badge/database-SQL%20Server-1A2A44)
![License](https://img.shields.io/badge/license-proprietary-555)
[![build](https://github.com/MehrshadZiari79/Preventive-maintenance-system/actions/workflows/build.yml/badge.svg)](https://github.com/MehrshadZiari79/Preventive-maintenance-system/actions/workflows/build.yml)
[![CodeQL](https://github.com/MehrshadZiari79/Preventive-maintenance-system/actions/workflows/codeql.yml/badge.svg)](https://github.com/MehrshadZiari79/Preventive-maintenance-system/actions/workflows/codeql.yml)

**Designed and built by [Mehrshad Ziari](https://github.com/MehrshadZiari79) for Gela Dairy Co., Amol, Iran**

<img src="docs/manual/img/dashboard.png" alt="Dashboard" width="860">

</div>

> [!IMPORTANT]
> This is production software of **Gela Dairy Co.**, designed and developed by **Mehrshad Ziari**.
> The code is public so the work can be seen; it is **not open source**. Using, copying or
> modifying any part of it requires written permission: **MehrshadZiari79@gmail.com**.
> See [License](#license).

<div dir="rtl">

### خلاصه فارسی

**سیستم مدیریت نگهداری و تعمیرات (نت) شرکت لبنی گلا** — طراحی و توسعه: **مهرشاد زیاری**

نرم‌افزار دسکتاپ فارسی و راست‌به‌چپ برای واحد نگهداری و تعمیرات کارخانه: شناسنامه تجهیزات،
برنامه‌های نگهداری پیشگیرانه (PM) با ساخت خودکار دستور کار، گردش کامل دستور کارها از تأیید تا
اتمام، حکم درخواست تعمیرات، بازرسی‌ها، انبار قطعات یدکی، ساعت کار ماشین‌آلات و توقف‌ها، و
گزارش‌های استاندارد نت (MTBF، MTTR، دسترس‌پذیری، OEE و …) با خروجی Excel و PDF.
همه تاریخ‌ها شمسی و به وقت تهران هستند، دسترسی‌ها بر اساس نقش است و نسخه‌های جدید بدون
نیاز به کاربر مدیر، به‌صورت خودکار روی همه کامپیوترها نصب می‌شوند.

این کد برای نمایش کار منتشر شده و **متن‌باز نیست**. هرگونه استفاده، کپی یا تغییر نیازمند
اجازه کتبی است: <span dir="ltr">MehrshadZiari79@gmail.com</span>

</div>

---

## Contents

- [Overview](#overview)
- [Screenshots](#screenshots)
- [Modules](#modules)
- [Interface](#interface)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Getting started (development)](#getting-started-development)
- [Database settings](#database-settings)
- [Building and publishing a release](#building-and-publishing-a-release)
- [Installing on client PCs](#installing-on-client-pcs)
- [Automatic updates](#automatic-updates)
- [Database](#database)
- [Roles and permissions](#roles-and-permissions)
- [Work order workflow](#work-order-workflow)
- [KPI definitions](#kpi-definitions)
- [Keyboard shortcuts](#keyboard-shortcuts)
- [User manual](#user-manual)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Changelog](#changelog)
- [Maintainer](#maintainer)
- [License](#license)

---

## Overview

Gela PM System is a Windows desktop application used by the maintenance and production
departments of Gela Dairy in Amol. Every client works against one central SQL Server
database on the company LAN, so all users see the same equipment, plans, work orders and
history.

- **Persian (RTL) everywhere**, including mixed Persian/English typing through the native
  Windows Rich Edit control
- **Jalali calendar and Iran time** (Asia/Tehran) everywhere, independent of the client PC's
  time-zone settings or an outdated Iran DST rule
- **Role-based access** with four built-in roles and custom roles (page × action matrix)
- **Silent, centrally managed updates** for standard (non-admin) Windows users, with a
  self-test that runs after every install
- **LAN only**: clients need no Internet access and no Python installation

---

## Screenshots

| | |
|---|---|
| ![Dashboard](docs/manual/img/dashboard.png) **Dashboard** | ![Work orders](docs/manual/img/work_orders.png) **Work orders**: status badges, row counter, filter chips |
| ![PM schedule](docs/manual/img/pm_filtered.png) **PM schedule** with filters | ![Equipment](docs/manual/img/equipment.png) **Equipment register** |
| ![Repair request dialog](docs/manual/img/repair_request_new.png) **New repair request** (dialog) | ![Inline errors](docs/manual/img/form_errors.png) **Inline form errors** |
| ![Reports](docs/manual/img/reports.png) **Reports & KPIs** | ![Machine hours](docs/manual/img/machine_hours.png) **Machine hours** shift sheet |
| ![Inspections](docs/manual/img/inspection.png) **Inspections** | ![Spare parts](docs/manual/img/spare_parts.png) **Spare parts** |
| ![Role manager](docs/manual/img/roles.png) **Role & permission manager** | ![Quick search](docs/manual/img/palette.png) **Ctrl+K quick search** |
| ![Dialogs](docs/manual/img/dialogs.png) **Styled confirm dialog + toast** | ![Collapsed menu](docs/manual/img/collapsed.png) **Collapsed side menu** |

All screenshots are in [`docs/manual/img/`](docs/manual/img). They were taken from the real
program against a test database.

---

## Modules

| Module | Persian | What it covers |
|---|---|---|
| Dashboard | داشبورد | Live overview: PM compliance, completion rate, open/emergency work, overdue PMs, low stock |
| Equipment | تجهیزات | Equipment register: code, category, location, status, technical data; category and location lists |
| PM schedule | برنامه PM | Preventive plans: interval, checklist, required parts, allowed duration. Due work orders are generated automatically (`[A-PM] …`). Filters by status, category, location, department, interval, history and dates; printable PDF. |
| Work orders | دستور کارها | Corrective, preventive, inspection and emergency work from approval to completion, with personnel, parts and cost |
| Repair requests | حکم درخواست تعمیرات | Fault reports from production units (entered in a dialog), executing department, completion with the actual personnel |
| Personnel & departments | پرسنل و دپارتمان‌ها | Maintenance staff and departments; who actually performed each job |
| Inspections | بازرسی‌ها | Template-based checklists, results pass / fail / partial |
| Spare parts | قطعات یدکی | Stock, stock in/out with history, minimum levels, inventory value; parts used on work orders are deducted automatically |
| Machine hours | ساعت کار ماشین | Shift sheet per machine: run window, stops with reasons (planned / unplanned), output, availability; Pareto of stop reasons |
| Reports & analysis | تحلیل و گزارشات | Scorecard (planned vs reactive work, PM compliance, response time, backlog age, repeat failures), MTBF, MTTR, availability, OEE, costs, failures, personnel, work orders, repair requests; Excel and PDF |
| Users | مدیریت کاربران | User accounts and the role / permission manager |
| Activity log | لاگ فعالیت | Who did what and when |

Lists export to formatted Excel. Work orders, PM plans and repair requests print to A4 PDF
forms with columns for handwritten reports and signatures; the PDF lists the active filters.

---

## Interface

The shared look lives in `utils/theme.py` (tokens: colours, type scale, spacing) and
`views/ux.py` (behaviour). Every page gets it automatically when the main window shows it.

| Element | Behaviour |
|---|---|
| Page header | One white header on every page: title and subtitle on the right, actions on the left |
| Buttons | One navy main action per page, outlined secondary actions, red only for «اضطراری» / delete |
| Side menu | Grouped (نگهداری و تعمیرات / تحلیل / سازمان و دسترسی), Segoe MDL2 / Fluent icons, collapsible, user card and logout at the bottom |
| Tables | Coloured status badge in the «وضعیت» column, zebra rows, hover, «در حال بارگذاری…», empty state with «پاک کردن فیلترها» |
| Counter + chips | «۵ از ۹۶ دستور کار» above the main table and every active filter as a removable chip |
| Messages | Styled RTL dialogs replace the Windows message boxes (same return values); short successes are a toast |
| Forms | Missing / wrong fields get a red frame and a note under the field |
| Quick search | **Ctrl+K**: pages, quick actions, equipment by code/name, work order by number |

Setting the environment variable `PM_CLASSIC_UI=1` on a PC switches the dialogs, table
additions and header styling back to the plain look. Program logic is the same either way.

---

## Architecture

```
   Client PCs (Windows, standard users)               Server
 ┌───────────────────────────────────────┐        ┌─────────────────────────────────┐
 │ PM_System.exe  (PyInstaller, onedir)  │  TDS   │ SQL Server  ·  PM_Database      │
 │   Tkinter/ttk UI · SQLAlchemy 2       │ ─────► │   port 1433                     │
 │   pymssql                             │        │                                 │
 │                                       │  SMB   │ \\<server>\PM_System_Updates     │
 │ Task "\GelaPM\PM System Updater"      │ ─────► │   pm_system_update.json         │
 │   (SYSTEM, every 15 min + at start)   │ (read) │   PM_System_Setup_v*.exe (2)    │
 └───────────────────────────────────────┘        └─────────────────────────────────┘
```

| Layer | Technology |
|---|---|
| UI | Tkinter / ttk, one theme (`utils/theme.py`) and shared behaviour (`views/ux.py`) |
| RTL text | Windows Rich Edit through `utils/rtl_patch.py`; text is stored in logical Unicode order |
| Data access | SQLAlchemy 2.x ORM, repositories in `database/` |
| Database driver | pymssql (TDS 7.0 for the existing legacy server) |
| Dates | jdatetime, `utils/date_helpers.py` (Tehran clock), Jalali date entry (`views/jalali_date_entry.py`) |
| Charts | Matplotlib (TkAgg) |
| Excel / PDF | openpyxl; Pillow + arabic-reshaper / python-bidi for Persian PDF |
| Packaging | PyInstaller 6 (one-folder) + Inno Setup 6 |
| Updates | PowerShell scheduled task running as SYSTEM (`updater/`), WinForms progress window |
| Manual | HTML (`docs/manual/`) printed to PDF by Edge / Chromium |

---

## Requirements

**Server**
- Microsoft SQL Server reachable on TCP 1433
- Database `PM_Database` and an application login with read/write rights on its tables
- A file share for updates (see [Automatic updates](#automatic-updates))

**Client PCs**
- Windows 10 or 11, 64-bit (Windows 8.1 works; the side-menu icons then fall back to emoji)
- LAN access to the server. No Python needed.

**Build PC**
- Python 3.13, 64-bit (Anaconda is used in production)
- Packages from `requirements.txt`
- Inno Setup 6
- `database/db_secrets.py` (see [Database settings](#database-settings))

---

## Getting started (development)

```powershell
git clone https://github.com/MehrshadZiari79/Preventive-maintenance-system.git
cd Preventive-maintenance-system

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

copy database\db_secrets.example.py database\db_secrets.py   # then edit it
python main.py
```

To work against a **test** database without touching the settings file:

```powershell
$env:PM_DATABASE_URL = "mssql+pymssql://user:password@test-server:1433/PM_Database_Test"
python main.py
```

Never point development or test scripts at the production database.

---

## Database settings

No server address, login or password is stored in the source code.

| File | In Git | Purpose |
|---|---|---|
| `database/db_secrets.example.py` | yes | Template with placeholder values |
| `database/db_secrets.py` | **no** (`.gitignore`) | Real settings: `DB_SERVER`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `INITIAL_ADMIN_PASSWORD` |
| `updater_account.local` | **no** | Read-only update-share account, asked once by `release.py` |

`database/db.py` imports `db_secrets.py`; PyInstaller bundles it into the program on the build
PC. `release.py` and `build_release.bat` refuse to build when the file is missing, so a release
can never ship without database settings. `INITIAL_ADMIN_PASSWORD` is used only once, to create
the `admin` account on an empty database.

---

## Building and publishing a release

Versions have four parts and each release raises only the last one: `2.4.6.1 → 2.4.6.2`.
To start a new series, write it in `version.txt` (for example `2.4.7`).

On the build PC, double-click **`release.bat`** (optionally `release.bat "release notes"`). It:

1. checks Python packages, Inno Setup, `db_secrets.py` and write access to the update share
   (asks for the publisher account when the share needs one),
2. raises the version (the higher of `version.txt` and the version on the share),
3. builds with PyInstaller and packages `installer_output\PM_System_Setup_v<version>.exe`,
4. publishes it (copy as `.partial`, SHA-256 check, then the manifest),
5. keeps only the **two newest installers** on the share and in `installer_output\`.

If a step fails before publishing, `version.txt` is restored and nothing is published. Logs are
in `release_logs\`. For a build without publishing, run `build_release.bat`.

The user manual PDF is rebuilt with `python generate_manual.py` (see [User manual](#user-manual)).

---

## Installing on client PCs

The first installation on each PC is done once by an administrator:

1. Run `PM_System_Setup_v<version>.exe` as administrator.
2. On the **Automatic updates** page, enter the update share and its read-only account.
3. Finish. Setup registers the updater task, starts PM System for every Windows user at logon,
   and runs the **full automatic-update self-test** as SYSTEM. The result is shown on the
   last page.

Silent installation:

```
PM_System_Setup_v<version>.exe /VERYSILENT /SHAREUSER=<domain>\<reader> /SHAREPASS=********
```

Uninstalling removes the program and the updater task only. The database is never touched.

---

## Automatic updates

- The SYSTEM task `\GelaPM\PM System Updater` checks the share every 15 minutes and at
  start-up. A newer version is copied, verified (SHA-256) and installed silently, so standard
  users never see UAC.
- **At program start** the app checks the share for a few seconds («در حال بررسی نسخه جدید…»);
  if a newer version exists, the «در حال به‌روزرسانی سیستم PM» window shows the progress and
  the program reopens afterwards.
- **While the program is open**, users get a two-minute Persian countdown to save their work.
- Only installer failures count towards the 3-attempt limit; network problems do not. Users are
  warned about failed scheduled runs.
- Start menu → **Test automatic updates** (run as administrator) runs the full SYSTEM self-test
  and one real update run, and saves `last_test_report.txt`.

Logs: `C:\ProgramData\GelaDairy\PMSystem\updater\`. Full procedure and the one-time server
setup: [DEPLOY_UPDATES.md](DEPLOY_UPDATES.md).

---

## Database

- The application does **not** create or alter tables at start-up.
- Schema additions are reviewed SQL scripts in `deploy/`, run once by the database
  administrator after a full backup (`db_setup.bat` runs the first one):

| Script | Purpose |
|---|---|
| `deploy/add_machine_shift_tables.sql` | Machine-hours shift log (`machine_shift_logs`, `machine_downtime_events`). Required for stop reasons. |
| `deploy/optional_fix_legacy_utc_times.sql` | Optional one-time correction of timestamps saved in UTC by versions up to 2.3 |

- Backups are taken on the server with SQL Server's own tools. Keep several generations and
  store copies off the server.
- Updates replace program files only; they never modify `PM_Database`.

---

## Roles and permissions

Actions per page: **مشاهده** (read), **ایجاد / ویرایش** (write), **تأیید** (approve, work
orders only) and **حذف** (delete).

| Page | admin | manager | technician | production_expert |
|---|---|---|---|---|
| Dashboard | full | read | read | read |
| Equipment | full | read, write, delete | read, write | read |
| PM schedule | full | read, write, delete | — | — |
| Work orders | full | full | read, write | read, write, approve creation |
| Repair requests | full | read, write, delete | read, write | read, write |
| Personnel & departments | full | read, write, delete | — | — |
| Inspections | full | read, write, delete | read | — |
| Spare parts | full | read, write, delete | read, write, delete | — |
| Reports | full | read | read | — |
| Machine hours | full | read, write, delete | read, write | — |
| Users, Activity log | full | — | — | — |

- **Approve** on work orders = approve creation, final approval, reject a finish request,
  generate PM work orders.
- **Editing a work order and changing its status** (moving it back to an earlier stage) is open
  to every role that can open the work-orders page.
- **Delete** on equipment also allows managing the category and location lists.
- Custom roles are created under **Users → مدیریت نقش‌ها**. User management is never granted to
  a custom role. Changes apply at the user's next login.

---

## Work order workflow

```
PENDING_APPROVAL ─► PENDING ─► IN_PROGRESS ─► FINISH_REQUESTED ─► APPROVED
        │                                              │
        └──────────────► REJECTED ◄────────────────────┘
```

- Auto-generated PM work orders start in `PENDING_APPROVAL` with the title
  `[A-PM] <plan> <Jalali date>`.
- The finish report records the personnel who actually did the work (from the responsible
  department), the parts used (deducted from stock) and manual cost.
- Final approval of a PM work order moves the plan's next due date.
- Rejecting a finish request creates a follow-up corrective work order linked as its parent.
- `APPROVED` and `REJECTED` cannot be moved back.

---

## KPI definitions

All KPIs use the date range selected in the report. A work order counts as *finished* when its
status is `APPROVED` (or `COMPLETED` for older records).

| KPI | Definition |
|---|---|
| Failures | Corrective + emergency work orders in the period, excluding rejected |
| MTTR | Average repair time (end − start) of finished corrective/emergency work orders |
| MTBF | Operating hours ÷ failures (from machine hours) |
| Availability | Run time ÷ planned production time (from machine hours) |
| Planned production time | Shift window − planned stops (CIP, planned maintenance, breaks, no plan) |
| Run time | Planned production time − unplanned stops |
| Quality | Inspection pass rate, ignoring "not applicable" answers; 100 % when there are no inspections |
| OEE | Availability × performance × quality. Performance is a fixed 95 % assumption. |
| PM / schedule compliance | Work finished by its deadline ÷ all work due. Open work past its deadline counts as late. |
| Cost | Spare parts + labour (repair hours × fixed rate) + manual cost, per work order |
| Planned work % | Finished preventive/PM/inspection work ÷ all finished work. Reference ≥ 80 % |
| Emergency work % | Finished emergency work ÷ all finished work. Reference ≤ 10 % |
| Response time | Work order created → work started, for corrective/emergency work |
| Repeat failure | The same equipment fails again within 30 days of its previous failure |
| Backlog age | Open work grouped by days since creation |
| Inventory value | Stock × weighted average purchase price |

Reference values are common industry (SMRP) figures, shown for comparison only.

---

## Keyboard shortcuts

They work on every page, also with the Persian keyboard layout. **F1** shows the list in the app.

| Keys | Action |
|---|---|
| Ctrl+K | Quick search: page, equipment, work order number |
| Ctrl+N | New record |
| Ctrl+E or F2 | Edit the selected row |
| Enter | Open / edit the selected row |
| Delete | Delete the selected row |
| Ctrl+F | Go to the search box |
| Ctrl+R or F5 | Refresh |
| Ctrl+P | Print / PDF of the page |
| Ctrl+S | Save (dialogs and the machine-hours sheet) |
| Ctrl+1 … Ctrl+9 | Open the n-th item of the side menu |
| Esc | Close a dialog (asks first if there are unsaved changes) / leave full screen |
| F11 | Full screen |

---

## User manual

- Persian user manual: [`PM_System_Manual.pdf`](PM_System_Manual.pdf) (installed with the
  program in `docs\` and on the desktop).
- Source: [`docs/manual/manual.html`](docs/manual/manual.html) with screenshots in
  `docs/manual/img/` and the Vazirmatn font (OFL) in `docs/manual/fonts/`.
- Rebuild after editing: `python generate_manual.py` (uses Microsoft Edge headless, or
  Playwright if installed).

---

## Project structure

```
Preventive-maintenance-system/
├── main.py                       entry point (RTL editor, update check, login)
├── auth/                         login, permissions (AuthManager.allows), role management
├── database/
│   ├── db.py                     connection + session factory (settings from db_secrets.py)
│   ├── db_secrets.example.py     template for the private settings file
│   ├── models.py, work_order.py  ORM models
│   ├── machine_shift.py          machine-hours shift log model
│   └── *_repository.py           data access per module
├── services/                     business logic, Auto-PM, Excel/PDF export, machine time
├── views/                        pages and dialogs (Tkinter)
│   ├── main_view.py              main window, side menu, page routing
│   ├── ux.py                     shared look: headers, buttons, dialogs, tables, field errors
│   ├── ui_kit.py                 small building blocks (cards, toast, pills)
│   ├── command_palette.py        Ctrl+K quick search
│   └── shortcuts.py              keyboard shortcuts
├── utils/
│   ├── theme.py                  colours, fonts, spacing, ttk theme
│   ├── date_helpers.py           Tehran clock and Jalali formatting
│   ├── rtl_patch.py              native Persian/BiDi editors
│   ├── update_client.py          start-up update check and in-app countdown
│   └── error_log.py              %LOCALAPPDATA%\GelaDairy\PMSystem\error.log
├── updater/                      SYSTEM updater, self-test, progress window, tester (PowerShell)
├── deploy/                       one-time SQL scripts
├── docs/manual/                  user manual source, screenshots, font
├── tools/                        manual test scripts (use a TEST database only)
├── schemas/                      pydantic schemas
├── PM_System.spec                PyInstaller build definition
├── Setup.iss                     Inno Setup installer
├── release.bat / release.py      build + publish + keep two installers
├── build_release.bat             build only
├── publish_update.py             publish a hand-built installer
├── generate_manual.py            HTML manual → PDF
├── db_setup.bat / db_setup.py    run deploy/add_machine_shift_tables.sql
├── version.txt                   application version
├── CHANGES_v2.4.md               release notes
└── DEPLOY_UPDATES.md             update system: setup, testing, troubleshooting
```

---

## Troubleshooting

| Symptom | Check |
|---|---|
| "Cannot connect" at login | Can the PC reach the SQL Server on port 1433? Is SQL Server running? |
| Build stops: `db_secrets.py is missing` | Copy `database/db_secrets.example.py` to `db_secrets.py` and fill it in |
| A PC does not receive updates | Start menu → *Test automatic updates*; Task Scheduler → GelaPM → Last Run Result; `updater.log` |
| Update fails repeatedly | `install_<version>.log` in the updater folder. After three failed installs the PC waits for the next version. |
| Machine hours shows a "basic mode" notice | `deploy/add_machine_shift_tables.sql` has not been run yet |
| Persian text in a multi-line box reads left-to-right | Make sure `PM_DISABLE_RTL_PATCH` is not set on that PC |
| Dialogs or tables look wrong on one PC | Set `PM_CLASSIC_UI=1` on that PC and report it with `error.log` |
| Unexpected error | `%LOCALAPPDATA%\GelaDairy\PMSystem\error.log` |

---

## Changelog

Release notes are in [CHANGES_v2.4.md](CHANGES_v2.4.md).

---

## Maintainer

**Mehrshad Ziari** — Computer Engineer, Gela Dairy Co., Amol, Iran
Designer and sole developer of this system.

- Permission requests and questions: **MehrshadZiari79@gmail.com**
- Security problems: see [SECURITY.md](SECURITY.md)

---

## License

Copyright © 2025–2026 Gela Dairy Co., Amol, Iran, and Mehrshad Ziari. All rights reserved.

The source is visible for reference and portfolio purposes only. It is **not open source**:
no part of the code, documentation or screenshots may be used, copied, modified or
distributed without prior written permission. Requests: **MehrshadZiari79@gmail.com**.
See [LICENSE](LICENSE) and [NOTICE](NOTICE). The bundled Vazirmatn font
(`docs/manual/fonts/`) is licensed under the SIL Open Font License 1.1.
