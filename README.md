# 🥛 Dairy PM — Preventive Maintenance System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![CustomTkinter](https://img.shields.io/badge/CustomTkinter-GUI-blue?style=for-the-badge)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-red?style=for-the-badge)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**A desktop application for managing preventive maintenance in dairy production facilities.**  
Built with Python, CustomTkinter, SQLAlchemy, and SQLite.

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Project Structure](#-project-structure)
- [Installation](#-installation)
- [Usage](#-usage)
- [Roles & Permissions](#-roles--permissions)
- [Roadmap](#-roadmap)
- [Tech Stack](#-tech-stack)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🔍 Overview

**Dairy PM** is a Windows desktop application designed for maintenance teams in dairy production plants. It provides a full suite of tools to manage equipment, schedule preventive maintenance (PM), assign technicians, and track work orders — all in a Persian (Farsi) UI with Jalali calendar support.

The system follows a clean **three-layer architecture**: Model → Repository → View, making it easy to maintain and extend.

---

## ✨ Features

### ✅ Completed

| Module | Description |
|---|---|
| 🔐 Authentication | Login system with role-based access control |
| 👥 User Management | Full CRUD, role assignment, password management |
| 🔧 Equipment Management | Equipment registry with status tracking and Jalali date support |
| 📅 PM Scheduling | Define periodic maintenance plans per equipment |
| 📝 Work Orders | Create, assign, track, approve or reject maintenance tasks |

### 🚧 In Progress / Planned

| Module | Status |
|---|---|
| 🔩 Spare Parts Management | 🟡 Planned |
| 📊 Reports & Dashboard | 🟡 Planned |
| 🌐 LAN Multi-User (Client-Server) | 🔴 Critical |
| 📦 EXE Installer | 🟡 Planned |

---

## 🗂 Project Structure

```
dairy_pm_app/
├── auth/
│   └── auth_manager.py          # Authentication logic
├── database/
│   ├── db.py                    # SQLAlchemy session setup
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

## ⚙️ Installation

### Prerequisites

- Python 3.10 or higher
- pip

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/MehrshadZiari79/Preventive-maintenance-system.git
cd Preventive-maintenance-system

# 2. Create a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python main.py
```

---

## 🚀 Usage

On first launch, the database is automatically created and seeded with a default admin account:

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `admin123` |

> ⚠️ **Change the default password immediately after first login.**

---

## 👤 Roles & Permissions

| Role | Permissions |
|---|---|
| **Admin** | Full access — manage users, equipment, PM schedules, work orders |
| **Manager** | Approve/reject work orders, view all data |
| **Technician** | View assigned work orders, update status, log work done |

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
| Database | SQLite (local) → PostgreSQL (planned) |
| Calendar | tkcalendar (Jalali support) |
| Packaging | PyInstaller + Inno Setup (planned) |

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create your feature branch: `git checkout -b feat/your-feature`
3. Commit your changes: `git commit -m "feat: add your feature"`
4. Push to the branch: `git push origin feat/your-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

<div align="center">
Made with ❤️ for dairy maintenance teams
</div>
