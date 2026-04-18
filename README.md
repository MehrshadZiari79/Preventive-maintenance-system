# 🥛 Dairy PM — سیستم مدیریت نگهداری پیشگیرانه

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![CustomTkinter](https://img.shields.io/badge/CustomTkinter-GUI-blue?style=for-the-badge)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-red?style=for-the-badge)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Status](https://img.shields.io/badge/Status-Internal%20Use%20Only-orange?style=for-the-badge)

**سیستم داخلی مدیریت نگهداری پیشگیرانه تجهیزات**  
توسعه‌یافته برای شرکت **گلا ** — آمل، ایران

> ⚠️ This is a **private internal tool** developed exclusively for Gela Dairy.  
> Not open source. All rights reserved.

</div>

---

## 📋 فهرست مطالب / Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Project Structure](#-project-structure)
- [Installation](#-installation-internal)
- [Default Login](#-default-login)
- [Roles & Permissions](#-roles--permissions)
- [Roadmap](#-roadmap)
- [Tech Stack](#-tech-stack)
- [Developer](#-developer)
- [License](#-license)

---

## 🔍 Overview

**Dairy PM** is a Windows desktop application built exclusively for the maintenance department of **Gela Dairy (گلا دری)**, located in Amol, Iran.

It provides a complete toolset for:
- Registering and tracking production equipment
- Scheduling and managing preventive maintenance (PM) plans
- Assigning tasks to technicians and tracking work orders
- Approving completed maintenance work through a supervisor workflow

The UI is fully in **Persian (Farsi)** with **Jalali (Shamsi) calendar** support, designed for the company's maintenance team.

---

## ✨ Features

### ✅ Completed

| Module | Description |
|---|---|
| 🔐 Authentication | Secure login with role-based access control |
| 👥 User Management | Full CRUD — add, edit, deactivate users and assign roles |
| 🔧 Equipment Management | Equipment registry with status tracking and Jalali date support |
| 📅 PM Scheduling | Define periodic maintenance plans per equipment with checklists |
| 📝 Work Orders | Create, assign, track, approve or reject maintenance tasks |

### 🚧 Planned

| Module | Status |
|---|---|
| 🔩 Spare Parts Management | 🟡 Planned — Phase 7 |
| 📊 Reports & Dashboard | 🟡 Planned — Phase 8 |
| 🌐 LAN Multi-User Support | 🔴 Critical — Phase 9 |
| 📦 EXE Installer | 🟡 Planned — Phase 10 |

---

## 🗂 Project Structure

```
dairy_pm_app/
├── auth/
│   └── auth_manager.py          # Authentication logic
├── database/
│   ├── db.py                    # SQLAlchemy session & engine
│   ├── models.py                # User, Equipment, PMSchedule models
│   ├── work_order.py            # WorkOrder model & enums
│   ├── equipment_repository.py
│   ├── user_repository.py
│   ├── pm_repository.py
│   └── work_order_repository.py
├── utils/
│   └── constants.py
├── views/
│   ├── login_view.py
│   ├── main_view.py
│   ├── users_view.py / user_dialog.py
│   ├── equipment_view.py / equipment_dialog.py
│   ├── pm_view.py / pm_dialog.py
│   └── work_order_view.py / work_order_dialog.py
├── config.py
├── main.py
└── requirements.txt
```

---

## ⚙️ Installation (Internal)

> For IT / setup on a new office PC only.

### Prerequisites

- Python 3.10 or higher
- pip

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/MehrshadZiari79/Preventive-maintenance-system.git
cd Preventive-maintenance-system

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python main.py
```

The database (`pm_database.db`) is created automatically on first run.

---

## 🔑 Default Login

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `admin123` |

> ⚠️ **Change the default password immediately after first setup.**

---

## 👤 Roles & Permissions

| Role | Persian | Permissions |
|---|---|---|
| **Admin** | مدیر سیستم | Full access — manage all data, users, and settings |
| **Manager** | سرپرست | Approve/reject work orders, view all reports |
| **Technician** | تکنسین | View assigned tasks, update work order status |

---

## 🗺️ Roadmap

```
Phase 1-3  ✅  Authentication & Architecture
Phase 4    ✅  User Management
Phase 5    ✅  Equipment Management
Phase 6    ✅  Work Orders
Phase 7    🔴  Spare Parts Management
Phase 8    🟡  Reports & Dashboard (MTBF, MTTR, Charts)
Phase 9    🔴  LAN Multi-User (FastAPI + PostgreSQL)
Phase 10   🟡  EXE Installer (PyInstaller + Inno Setup)
```

**Overall Progress: ████████░░░░░░░░░░ ~50%**

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| GUI | CustomTkinter + Tkinter |
| ORM | SQLAlchemy |
| Database | SQLite (current) → PostgreSQL (planned for LAN) |
| Calendar | tkcalendar (Jalali support) |
| Packaging | PyInstaller + Inno Setup (planned) |

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
