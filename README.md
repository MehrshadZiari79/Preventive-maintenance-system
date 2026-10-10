<div align="center">

<img src="views/gela-logo.png" alt="Gela Dairy" width="96">

# Gela PM System

**سیستم مدیریت نگهداری و تعمیرات — شرکت گلا، آمل**

Maintenance management for the Gela Dairy plant: equipment, preventive maintenance,
work orders, repair requests, inspections, spare parts, machine hours and maintenance KPIs.

![Version](https://img.shields.io/badge/version-2.4.0-1A2A44)
![Platform](https://img.shields.io/badge/platform-Windows%208.1%2B%20x64-1A2A44)
![Python](https://img.shields.io/badge/python-3.13-1A2A44)
![Database](https://img.shields.io/badge/database-SQL%20Server-1A2A44)
![License](https://img.shields.io/badge/license-proprietary-555)

</div>

> Internal software of Gela Dairy Co. It is not open source and is not licensed for use
> outside the company. See [License](#license).

---

## Contents

- [Overview](#overview)
- [Modules](#modules)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Development setup](#development-setup)
- [Building a release](#building-a-release)
- [Installing on client PCs](#installing-on-client-pcs)
- [Automatic updates](#automatic-updates)
- [Database](#database)
- [Roles and permissions](#roles-and-permissions)
- [Work order workflow](#work-order-workflow)
- [KPI definitions](#kpi-definitions)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Changelog](#changelog)
- [Maintainer](#maintainer)
- [License](#license)

---

## Overview

Gela PM System is a Windows desktop application used by the maintenance and production
departments of Gela Dairy in Amol. All clients work against one central SQL Server
database on the company LAN, so every user sees the same equipment, plans, work orders and
history.

- Persian (RTL) interface throughout, including mixed Persian/English text entry through
  the native Windows Rich Edit control
- Jalali calendar everywhere; all times are Iran time (Asia/Tehran), independent of the
  client PC's time-zone settings
- Role-based access with built-in and custom roles
- Silent, centrally managed updates for standard (non-admin) Windows users
- No Internet access required. Clients only need the LAN.

---

## Modules

| Module | Persian | What it covers |
|---|---|---|
| Dashboard | داشبورد | Live overview: work order status, PM compliance, overdue PMs, low stock, equipment risk |
| Equipment | تجهیزات | Equipment register with code, category, location, criticality and technical data |
| PM schedule | برنامه PM | Preventive maintenance plans: interval, checklist, required parts and allowed duration. Due work orders are generated automatically. |
| Work orders | دستور کارها | Preventive, corrective and emergency work from approval to completion, with personnel, parts and cost |
| Repair requests | حکم درخواست تعمیرات | Fault reports from production units, assignment and completion |
| Personnel & departments | پرسنل و دپارتمان‌ها | Maintenance staff and their departments; who actually performed each job |
| Inspections | بازرسی‌ها | Template-based inspection checklists and results |
| Spare parts | قطعات یدکی | Stock, movements (in/out), minimum levels and value |
| Machine hours | ساعت کار ماشین | Shift log per machine: run window, stops with reasons, output, availability, Pareto of stop reasons |
| Reports & analysis | تحلیل و گزارشات | MTBF, MTTR, availability, OEE, PM/CM ratio, schedule compliance, costs, failure analysis, personnel performance, monthly trends |
| Users | مدیریت کاربران | User accounts and the role/permission manager |
| Activity log | لاگ فعالیت | Who did what and when |

Lists export to formatted Excel, and work orders, PM plans and repair requests print to A4
PDF forms with columns for handwritten reports and signatures.

---

## Architecture

```
   Client PCs (Windows, standard users)               Server 192.168.0.1
 ┌───────────────────────────────────────┐        ┌─────────────────────────────────┐
 │ PM_System.exe  (PyInstaller, onedir)  │  TDS   │ SQL Server  ·  PM_Database       │
 │   Tkinter/ttk UI · SQLAlchemy 2       │ ─────► │   port 1433                      │
 │   pymssql                             │        │                                 │
 │                                       │  SMB   │ \\192.168.0.1\PM_System_Updates │
 │ Task "\GelaPM\PM System Updater"      │ ─────► │   pm_system_update.json          │
 │   (SYSTEM, every 15 min)              │ (read) │   PM_System_Setup_v*.exe         │
 └───────────────────────────────────────┘        └─────────────────────────────────┘
```

| Layer | Technology |
|---|---|
| UI | Tkinter / ttk (one shared theme in `utils/theme.py`) |
| RTL text | Windows Rich Edit through `utils/rtl_patch.py`; text is stored in logical Unicode order |
| Data access | SQLAlchemy 2.x ORM with repositories in `database/` |
| Database driver | pymssql (legacy TDS 7.0 compatibility for the existing server) |
| Dates | jdatetime and a custom Jalali date entry (`views/jalali_date_entry.py`) |
| Charts | Matplotlib (TkAgg) |
| Excel / PDF | openpyxl; Pillow + arabic-reshaper/python-bidi for Persian PDF output |
| Packaging | PyInstaller 6 (one-folder) + Inno Setup 6 |
| Updates | PowerShell scheduled task running as SYSTEM (`updater/`) |

---

## Requirements

**Server**
- Microsoft SQL Server reachable on TCP 1433 (the production server is legacy; the
  application avoids features newer servers would need)
- Database `PM_Database` and an application login with read/write rights on its tables
- A file share for updates (see [Automatic updates](#automatic-updates))

**Client PCs**
- Windows 8.1 or later, 64-bit
- LAN access to the server; no Python installation needed

**Build PC**
- Anaconda / Python 3.13 (64-bit)
- Packages from `requirements.txt`
- Inno Setup 6

---

## Development setup

```powershell
git clone https://github.com/MehrshadZiari79/Preventive-maintenance-system.git
cd Preventive-maintenance-system

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

python main.py
```

Connection settings for the production database are in `database/db.py`.

For local experiments the connection can be redirected without editing code:

```powershell
$env:PM_DATABASE_URL = "mssql+pymssql://user:password@test-server:1433/PM_Database_Test"
python main.py
```

Never point development or test scripts at the production database.

---

## Building a release

1. Set the new version in **`version.txt`** (for example `2.4.1`). It is the only place the
   version is edited.
2. Run **`build_release.bat`**. It builds the application with PyInstaller and packages
   `installer_output\PM_System_Setup_v<version>.exe` with Inno Setup.
3. Install the new setup on one test PC and check it before publishing.

---

## Installing on client PCs

The first installation on each PC is done once by an administrator:

1. Run `PM_System_Setup_v<version>.exe` as administrator.
2. On the **Automatic updates** page, enter the update share and its read-only account.
3. Finish. PM System now starts for every Windows user at logon, and the updater task is
   registered.

Silent installation is also supported:

```
PM_System_Setup_v2.4.0.exe /VERYSILENT /SHAREUSER=192.168.0.1\pm_update_reader /SHAREPASS=********
```

Uninstalling removes the program and the updater task only. The database on the server is
never touched.

---

## Automatic updates

Publish a tested installer from the build PC:

```powershell
python publish_update.py installer_output\PM_System_Setup_v2.4.1.exe 2.4.1 \\192.168.0.1\PM_System_Updates --notes "..."
```

The script checks that the version is consistent and higher than the published one. It
copies the installer, verifies the SHA-256 of the copy and only then writes the manifest.

On every client, the scheduled task checks the share every 15 minutes and at start-up.
When a newer version is published, it copies and verifies the installer and installs it
silently as SYSTEM, so no UAC prompt appears for standard users. If PM System is open, users
get a two-minute Persian countdown to save their work, after which the application closes,
updates and reopens.

Logs are in `C:\ProgramData\GelaDairy\PMSystem\updater\`. The full procedure, including
the one-time server setup, is in [DEPLOY_UPDATES.md](DEPLOY_UPDATES.md).

---

## Database

- The application does **not** create or alter tables at start-up.
- Schema additions are delivered as reviewed SQL scripts in `deploy/` and are run once by
  the database administrator after a full backup:

| Script | Purpose |
|---|---|
| `deploy/add_machine_shift_tables.sql` | Adds the machine-hours shift log (`machine_shift_logs`, `machine_downtime_events`). Required for stop reasons. |
| `deploy/optional_fix_legacy_utc_times.sql` | Optional one-time correction of timestamps saved in UTC by versions up to 2.3 |

- Backups are taken on the server with SQL Server's own tools (manual backups or a SQL
  Server Agent job). Keep several generations and store copies off the server.
- Updates replace program files only; they never modify `PM_Database`.

---

## Roles and permissions

| Role | Persian | Access |
|---|---|---|
| `admin` | مدیر سیستم | Everything, including users, roles and the activity log |
| `manager` | مدیر | All operational modules, approvals, reports, shift settings |
| `technician` | تکنسین | Dashboard, equipment, work orders, repair requests, inspections, spare parts, reports, machine hours |
| `production_expert` | کارشناس تولید | Dashboard, equipment, work orders and repair requests |
| custom roles | — | Per-module *view / create-edit / delete* rights set in the role manager |

Custom roles are created under **Users → Role manager**.

---

## Work order workflow

```
PENDING_APPROVAL ─► PENDING ─► IN_PROGRESS ─► FINISH_REQUESTED ─► APPROVED
        │                                              │
        └──────────────► REJECTED ◄────────────────────┘
```

Completion records the personnel who actually performed the work, which can differ from
the user account that entered it. Authorised users can move a work order back to an
earlier stage.

---

## KPI definitions

All KPIs use the date range selected in the report. A work order counts as *finished*
when its status is `APPROVED` (or `COMPLETED` for older records).

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

---

## Project structure

```
dairy_pm_app/
├── main.py                     entry point (RTL editor, login, update watcher)
├── auth/                       login, permissions, role management
├── database/                   SQLAlchemy models and repositories
│   ├── db.py                   connection and session factory
│   ├── models.py               core tables
│   ├── work_order.py           work order model
│   ├── machine_shift.py        machine-hours shift log model
│   └── *_repository.py         data access per module
├── services/                   business logic, Excel/PDF export, time calculations
├── views/                      screens and dialogs (Tkinter)
├── utils/
│   ├── theme.py                colours, fonts, shared ttk theme
│   ├── date_helpers.py         Iran time and Jalali formatting
│   ├── rtl_patch.py            native Persian/BiDi editors
│   └── update_client.py        in-app update countdown
├── updater/                    SYSTEM updater (PowerShell) and relaunch helper
├── deploy/                     one-time SQL scripts
├── PM_System.spec              PyInstaller build definition
├── Setup.iss                   Inno Setup installer
├── build_release.bat           build + package
├── publish_update.py           publish a release to the update share
└── version.txt                 application version
```

---

## Troubleshooting

| Symptom | Check |
|---|---|
| "Cannot connect" at login | Can the PC reach `192.168.0.1:1433`? Is SQL Server running? |
| A PC does not receive updates | Task Scheduler → `GelaPM` → *Last Run Result*; `C:\ProgramData\GelaDairy\PMSystem\updater\updater.log` |
| Update fails repeatedly | `install_<version>.log` in the same folder. After three failed attempts the PC waits for the next version. |
| Machine hours shows a yellow "basic mode" notice | `deploy/add_machine_shift_tables.sql` has not been run yet |
| Persian text in a multi-line box reads left-to-right | Make sure `PM_DISABLE_RTL_PATCH` is not set on that PC |

---

## Changelog

Release notes are kept in [CHANGES_v2.4.md](CHANGES_v2.4.md).

---

## Maintainer

**Mehrshad Ziari** — Computer Engineer, Gela Dairy, Amol

Report bugs and feature requests through the company's internal channels.

---

## License

Copyright © 2025–2026 Gela Dairy Co., Amol, Iran. All rights reserved.

This software is proprietary and was developed for internal use at Gela Dairy. Copying,
distribution, modification or use outside the company without written permission is not
permitted.
