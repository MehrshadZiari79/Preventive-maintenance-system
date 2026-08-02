# 🥛 Dairy PM — سیستم مدیریت نگهداری پیشگیرانه

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![CustomTkinter](https://img.shields.io/badge/CustomTkinter-GUI-blue?style=for-the-badge)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-red?style=for-the-badge)
![SQL Server](https://img.shields.io/badge/SQL%20Server-Database-CC2927?style=for-the-badge&logo=microsoft-sql-server&logoColor=white)
![Status](https://img.shields.io/badge/Status-Production%20Ready-green?style=for-the-badge)

**سیستم مدیریت نگهداری پیشگیرانه تجهیزات**  
توسعه‌یافته برای **شرکت گلا — آمل، ایران**

> ⚠️ This is a private internal tool developed exclusively for Gela Dairy.  
> Not open source. All rights reserved.

</div>

---

# 📋 فهرست مطالب / Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Default Login](#default-login)
- [Roles & Permissions](#roles--permissions)
- [Backup & Restore](#backup--restore)
- [Roadmap](#roadmap)
- [Tech Stack](#tech-stack)
- [Developer](#developer)
- [License](#license)

---

# 🔍 Overview

**Dairy PM** is a Windows desktop application built exclusively for the maintenance department of **Gela Dairy (گلا)** in Amol, Iran.

The system provides a complete preventive maintenance management solution including:

- Equipment registration and tracking
- Preventive maintenance scheduling
- Work order lifecycle management
- Spare parts inventory management
- Inspection management
- KPI and maintenance reports
- Role-based access control
- Multi-user SQL Server deployment

Main capabilities:

- Preventive Maintenance (PM)
- Corrective Maintenance (CM)
- Emergency Maintenance (EM)
- Inspection workflows
- Spare parts consumption tracking
- Maintenance cost analysis
- MTBF / MTTR calculations
- Equipment availability analysis
- OEE monitoring
- Risk evaluation

The application interface is fully Persian with Jalali calendar support.

---

# ✨ Features

| Module | Description |
|---|---|
| 🔐 Authentication | Secure login with role-based access control |
| 👥 User Management | Add, edit, deactivate users and assign permissions |
| 🔧 Equipment Management | Equipment registry with categories, status and Jalali dates |
| 📅 PM Scheduling | Define maintenance plans with intervals, checklists and required spare parts |
| 📝 Work Orders | Create, assign, execute, approve and track maintenance tasks |
| 🔩 Spare Parts | Inventory, stock movement, alerts and transaction history |
| 🔍 Inspections | Template-based inspection checklists with results tracking |
| 📊 Reports Dashboard | MTBF, MTTR, OEE, availability, cost reports and maintenance KPIs |
| 📎 Excel Export | Export reports and tables to formatted Excel files |
| 💾 Database Backup | SQL Server backup functionality for administrators |
| 📋 Activity Logs | Complete user action history |
| 🌐 Multi User | Supports multiple concurrent users through SQL Server |
| 🖥️ Modern UI | Responsive Persian desktop interface with custom styling |

---

# 🗂 Project Structure

```text
dairy_pm_app/
│
├── auth/
│   └── auth_manager.py
│
├── database/
│   ├── db.py
│   ├── models.py
│   ├── work_order.py
│   ├── repositories.py
│   └── seed.py
│
├── schemas/
│
├── services/
│
├── utils/
│   ├── theme.py
│   ├── backup.py
│   └── logger.py
│
├── views/
│
├── config.py
├── main.py
└── requirements.txt
```
---

# ⚙️ Installation

> Internal deployment guide for company IT setup and client PCs.

## Server Requirements

- Microsoft SQL Server 2017 or later
- TCP/IP enabled
- Port 1433 available
- Dedicated application database (example: `PM_Database`)
- SQL user with required permissions

Recommended permissions:

```
db_datareader
db_datawriter
db_ddladmin
```

The application automatically creates required tables on first startup.

---

## Client Requirements

- Windows operating system
- Python 3.10+
- ODBC Driver 17 for SQL Server
- Network access to database server

---

## Installation Steps

### 1. Clone Repository

```bash
git clone https://github.com/MehrshadZiari79/Preventive-maintenance-system.git

cd Preventive-maintenance-system
```

---

### 2. Create Virtual Environment

```bash
python -m venv venv

venv\Scripts\activate
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Configure Database Connection

Create a `.env` file:

```env
DATABASE_URL=mssql+pyodbc://pm_app_user:YourPassword@server_ip/PM_Database?driver=ODBC+Driver+17+for+SQL+Server
```

Replace:

- `pm_app_user` with your SQL username
- `YourPassword` with your SQL password
- `server_ip` with the database server address

---

### 5. Run Application

```bash
python main.py
```

On first execution:

- Database tables are created automatically
- Initial administrator account is created
- Application starts with an empty database

No demo/sample data is inserted.

---

# 🔑 Default Login

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `admin123` |

⚠️ Change the default password immediately after the first login.

---

# 👤 Roles & Permissions

| Role | Persian Name | Permissions |
|---|---|---|
| Admin | مدیر سیستم | Full system access, user management, database backup, settings and approvals |
| Manager | مدیر | Equipment management, PM plans, approvals, reports and inventory management |
| Technician | تکنسین | View equipment, execute work orders, complete inspections and view assigned tasks |

Security is enforced at two levels:

- UI level (buttons and menus)
- Action validation level

---

# 📝 Work Order Types

The system supports:

| Type | Description |
|---|---|
| Preventive Maintenance | Scheduled maintenance activities |
| Corrective Maintenance | Repairs after equipment failure |
| Emergency Maintenance | Urgent maintenance operations |
| Inspection | Equipment inspection workflows |

Work order lifecycle:

```
Created
   ↓
Assigned
   ↓
Started
   ↓
Completed
   ↓
Approved / Rejected
```

---

# 💾 Backup & Restore

## Backup

Administrators can create database backups through:

```
پشتیبان دیتابیس
```

The system executes SQL Server:

```sql
BACKUP DATABASE
```

and stores the `.bak` file on the server.

Default location:

```
C:\Backups
```

---

## Restore

Database restoration is performed by a database administrator using:

```
SQL Server Management Studio (SSMS)
```

Recommended:

- Enable scheduled SQL Server Agent backups
- Keep multiple backup versions
- Store backups separately from the database server

---

# 🗺 Roadmap

## Development Status

All planned phases have been completed.

```
✅ Phase 1  - Authentication & Architecture
✅ Phase 2  - User Management
✅ Phase 3  - Equipment Management
✅ Phase 4  - Preventive Maintenance Scheduling
✅ Phase 5  - Work Orders
✅ Phase 6  - Spare Parts Management
✅ Phase 7  - Inspection System
✅ Phase 8  - Reports & KPIs
✅ Phase 9  - SQL Server Multi User Support
✅ Phase 10 - Modern Persian UI
✅ Phase 11 - Excel Export & Backup
```

**Overall Progress: 100% — Production Ready**
---

# 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Programming Language | Python 3.10+ |
| GUI Framework | Tkinter + CustomTkinter |
| ORM | SQLAlchemy |
| Database | Microsoft SQL Server |
| Database Driver | PyODBC |
| Charts & Analytics | Matplotlib |
| Excel Export | OpenPyXL |
| Calendar System | tkcalendar (Jalali Support) |
| Packaging | PyInstaller |

---

# 📊 Reporting & Analytics

The reporting module provides:

- Maintenance KPI dashboard
- MTBF calculation
- MTTR calculation
- Equipment availability analysis
- OEE monitoring
- Maintenance cost analysis
- Failure analysis
- Risk scoring
- PM compliance reports
- Technician performance reports
- Monthly maintenance trends

---

# 🖥 Deployment Architecture

The application is designed for enterprise internal deployment.

Architecture:

```
Client PCs
    |
    |
Python Desktop Application
    |
    |
SQL Server Database
    |
    |
Company Network
```

Supported environment:

- Multiple users
- Central database
- Role-based permissions
- Internal company network deployment

---

# 👨‍💻 Developer

**Mehrshad Ziari**

Computer Engineer  
Gela Dairy — Amol, Iran

Developed exclusively for internal maintenance management operations.

For bug reports or feature requests, contact the developer through internal company channels.

---

# 📄 License

## Proprietary Software

Copyright © 2025 Gela Dairy — Amol, Iran.

This software is developed exclusively for internal use at Gela Dairy.

Unauthorized:

- Copying
- Distribution
- Modification
- Commercial use

is strictly prohibited.

All rights reserved.

---
