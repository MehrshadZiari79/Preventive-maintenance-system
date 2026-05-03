
```markdown
# 🥛 Dairy PM — سیستم مدیریت نگهداری پیشگیرانه

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![CustomTkinter](https://img.shields.io/badge/CustomTkinter-GUI-blue?style=for-the-badge)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-red?style=for-the-badge)
![SQL Server](https://img.shields.io/badge/SQL%20Server-Database-CC2927?style=for-the-badge&logo=microsoft-sql-server&logoColor=white)
![Status](https://img.shields.io/badge/Status-Production%20Ready-green?style=for-the-badge)

**سیستم مدیریت نگهداری پیشگیرانه تجهیزات**  
توسعه‌یافته برای **شرکت گلا** — آمل، ایران

> ⚠️ This is a **private internal tool** developed exclusively for Gela Dairy.  
> Not open source. All rights reserved.

</div>

---

## 📋 فهرست مطالب / Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Project Structure](#-project-structure)
- [Installation (SQL Server)](#-installation-sql-server)
- [Default Login](#-default-login)
- [Roles & Permissions](#-roles--permissions)
- [Backup & Restore](#-backup--restore)
- [Roadmap](#-roadmap)
- [Tech Stack](#-tech-stack)
- [Developer](#-developer)
- [License](#-license)

---

## 🔍 Overview

**Dairy PM** is a Windows desktop application built exclusively for the maintenance department of **Gela Dairy (گلا)** in Amol, Iran.

It provides a complete toolset for:
- Registering and tracking production equipment
- Scheduling and managing preventive maintenance (PM) plans
- Managing work orders (preventive, corrective, emergency, inspection)
- Tracking spare parts inventory and consumption
- Performing and recording inspections with checkpoints
- Generating professional reports (KPIs, MTBF, MTTR, OEE, cost analysis, risk scores)
- Full role‑based access control (Admin, Manager, Technician)
- Multi‑user support via SQL Server

The UI is **100% Persian** (except chart labels in English) with **Jalali (Shamsi) calendar** integration.

---

## ✨ Features (All Completed)

| Module | Description |
|---|---|
| 🔐 Authentication | Secure login with role‑based access control |
| 👥 User Management | Full CRUD — add, edit, deactivate users, assign roles |
| 🔧 Equipment Management | Equipment registry with status, category, and Jalali date support |
| 📅 PM Scheduling | Define periodic maintenance plans per equipment with checklists and required spare parts |
| 📝 Work Orders | Create, assign, start, complete, approve/reject maintenance tasks (Preventive, Corrective, Emergency, Inspection) |
| 🔩 Spare Parts | Full inventory management (add, edit, delete, stock IN/OUT, low‑stock alerts, transaction history) |
| 🔍 Inspections | Template-based inspection checklists, start/complete inspections, pass/fail/partial results |
| 📊 Reports & Dashboard | KPI cards, equipment performance (MTBF, MTTR, Availability, OEE), cost analysis, failure modes, risk scores, monthly PM/CM/EM trends, schedule compliance, technician performance |
| 📎 Excel Exports | One‑click export of any tab to a professionally formatted Excel file |
| 💾 Database Backup | Admin‑only backup of SQL Server database (saves `.bak` file on server) |
| 📋 Activity Log | Full audit trail of all user actions |
| 🌐 Multi‑User | Supports 10+ concurrent users via SQL Server |
| 🖥️ Modern UI | Navy/White/Red theme with responsive scrollable areas and custom‑styled scrollbars |

---

## 🗂 Project Structure

```
dairy_pm_app/
├── auth/
│   └── auth_manager.py
├── database/
│   ├── db.py                    # SQLAlchemy engine (SQL Server compatible)
│   ├── models.py                # All database models
│   ├── work_order.py            # WorkOrder model & enums
│   ├── *repositories.py         # Data access layers
│   └── seed.py                  # Initial admin seed (only runs once)
├── schemas/                     # Pydantic schemas for inspections
├── services/                    # Business logic services
├── utils/
│   ├── theme.py                 # Centralized colors, fonts
│   ├── backup.py                # SQL Server backup (admin only)
│   └── logger.py
├── views/                       # All UI views and dialogs
├── config.py
├── main.py
└── requirements.txt
```

---

## ⚙️ Installation (SQL Server)

> For internal IT setup on the company server and client PCs.

### Prerequisites (Server)

- Microsoft SQL Server (2017 or later) with TCP/IP enabled
- Port 1433 open in firewall
- A dedicated database (e.g., `PM_Database`)
- A SQL login for the application (e.g., `pm_app_user`) with `db_datareader`, `db_datawriter`, `db_ddladmin` rights (tables created automatically)

### Prerequisites (Client PC)

- Python 3.10 or higher
- pyodbc driver (ODBC Driver 17 for SQL Server)
- Network access to the SQL Server

### Steps on each client

```bash
# 1. Clone the repository
git clone https://github.com/MehrshadZiari79/Preventive-maintenance-system.git
cd Preventive-maintenance-system

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variable (in a .env file)
DATABASE_URL=mssql+pyodbc://pm_app_user:YourPassword@server_ip/PM_Database?driver=ODBC+Driver+17+for+SQL+Server

# 5. Run the application
python main.py
```

On first run, all tables are created automatically. The seed script inserts only one admin user (if no users exist). No sample data is added – the database starts empty.

---

## 🔑 Default Login

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `admin123` |

> ⚠️ **Change the default password immediately after first login.**

---

## 👤 Roles & Permissions

| Role | Persian | Permissions |
|---|---|---|
| **Admin** | مدیر سیستم | Full access — manage users, view activity logs, backup database, delete any equipment, approve/reject work orders, all settings |
| **Manager** | مدیر | Manage equipment, PM schedules, approve/reject work orders, manage spare parts, manage inspection templates, view all reports |
| **Technician** | تکنسین | View equipment and PMs, create/start/complete work orders, perform inspections, view spare part history |

All permissions are enforced at the UI level (buttons hidden) and action level (message guards).

---

## 💾 Backup & Restore

- **Backup**: Admin clicks "پشتیبان دیتابیس" → executes SQL Server `BACKUP DATABASE`. The `.bak` file is saved on the server (default path `C:\Backups`).
- **Restore**: Not implemented in the client – must be done by DBA using SQL Server Management Studio.
- **Recommendation**: Schedule regular SQL Server Agent backup jobs.

---

## 🗺️ Roadmap (Fully Completed)

All planned features have been implemented. The application is **production ready**.

```
✅ Phase 1-3  – Authentication & Architecture
✅ Phase 4    – User Management
✅ Phase 5    – Equipment Management
✅ Phase 6    – Work Orders (all types, approval workflow)
✅ Phase 7    – Spare Parts Management
✅ Phase 8    – Inspections & Reports (KPIs, MTBF, OEE, cost, risk)
✅ Phase 9    – Multi‑User SQL Server Support
✅ Phase 10   – Modern UI/UX (Navy/White/Red theme, Persian labels)
✅ Phase 11   – Excel Exports & Backup
```

**Overall Progress: 100%** – Ready for deployment.

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| GUI | Tkinter + CustomTkinter |
| ORM | SQLAlchemy |
| Database | SQL Server (production) – SQLite support removed |
| Charts | Matplotlib |
| Excel Export | OpenPyXL |
| Calendar | tkcalendar (Jalali support) |
| Packaging | PyInstaller (EXE generated) |

---

## 👨‍💻 Developer

**Mehrshad Ziari**  
Computer Engineer — Gela Dairy, Amol, Iran

> For bug reports or feature requests, contact the developer directly through internal company channels.

---

## 📄 License

**Proprietary — All Rights Reserved**

Copyright © 2025 Gela Dairy — Amol, Iran.  
This software is developed exclusively for internal use at Gela Dairy.  
Unauthorized copying, distribution, or use is strictly prohibited.
```

