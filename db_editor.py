import sqlite3
import os

db_path = "pm_database.db"  # adjust if your database is elsewhere

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS production_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL,
    log_date TIMESTAMP NOT NULL,
    operating_hours REAL NOT NULL DEFAULT 0,
    planned_hours REAL NOT NULL DEFAULT 0,
    downtime_hours REAL NOT NULL DEFAULT 0,
    output_units INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (equipment_id) REFERENCES equipment (id)
);
""")
conn.commit()
conn.close()
print("Migration complete: production_logs table added.")