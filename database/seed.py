# database/seed.py
import random
from datetime import datetime, timedelta
from database.db import SessionLocal
from database.models import (
    User, UserRole, Equipment, EquipmentStatus, EquipmentCriticality,
    PMSchedule, PMFrequency, InspectionTemplate, InspectionCheckpoint,
    CheckpointType, Inspection, InspectionStatus, InspectionResult,
    SparePart, SparePartTransaction, ProductionLog
)
from database.work_order import WorkOrder, WorkOrderType, WorkOrderStatus, WorkOrderPriority


def random_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)


def hash_password(password: str) -> str:
    import hashlib
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def seed_all():
    session = SessionLocal()
    # Check if database already has data (e.g., any equipment)
    if session.query(Equipment).count() > 0:
        print("✅ Database already has data. Skipping seed.")
        session.close()
        return

    print("🌱 Seeding database with minimal test data...")

    # ========== 1. Users ==========
    print("  📋 Creating users...")
    users = []
    admin = User(
        username="admin",
        password_hash=hash_password("admin123"),
        full_name="مدیر سیستم",
        role=UserRole.ADMIN.value,
        is_active=True
    )
    session.add(admin)
    users.append(admin)

    manager = User(
        username="manager",
        password_hash=hash_password("manager123"),
        full_name="مدیر نگهداری",
        role=UserRole.MANAGER.value,
        is_active=True
    )
    session.add(manager)
    users.append(manager)

    tech_names = [
        ("tech1", "احمد رضایی"),
        ("tech2", "محمد کریمی"),
    ]
    for username, full_name in tech_names:
        tech = User(
            username=username,
            password_hash=hash_password("tech123"),
            full_name=full_name,
            role=UserRole.TECHNICIAN.value,
            is_active=True
        )
        session.add(tech)
        users.append(tech)

    session.flush()
    print(f"    Created {len(users)} users")

    # ========== 2. Equipment ==========
    print("  🔧 Creating equipment...")
    equipment_list = []
    equipment_data = [
        {"code": "M-1001", "name": "پاستوریزاتور", "category": "فرآوری", "location": "سالن تولید", "criticality": EquipmentCriticality.CRITICAL.value},
        {"code": "M-2001", "name": "هموژنایزر", "category": "فرآوری", "location": "سالن تولید", "criticality": EquipmentCriticality.HIGH.value},
        {"code": "M-3001", "name": "دستگاه بسته‌بندی", "category": "بسته‌بندی", "location": "سالن بسته‌بندی", "criticality": EquipmentCriticality.MEDIUM.value},
        {"code": "M-4001", "name": "کمپرسور هوا", "category": "تاسیسات", "location": "موتورخانه", "criticality": EquipmentCriticality.LOW.value},
    ]
    for data in equipment_data:
        eq = Equipment(
            code=data["code"],
            name=data["name"],
            category=data["category"],
            manufacturer=random.choice(["Alfa Laval", "Tetra Pak", "GEA"]),
            model=f"{data['code']}-{random.randint(100, 999)}",
            serial_number=f"SN-{random.randint(10000, 99999)}",
            location=data["location"],
            installation_date=random_date(datetime(2020, 1, 1), datetime(2023, 12, 31)),
            status=EquipmentStatus.OPERATIONAL.value,
            criticality_level=data["criticality"],
            specifications=f"ظرفیت: {random.randint(1000, 5000)} لیتر در ساعت",
            notes="تجهیز اصلی خط تولید"
        )
        session.add(eq)
        equipment_list.append(eq)
    session.flush()
    print(f"    Created {len(equipment_list)} equipment")

    # ========== 3. PM Schedules ==========
    print("  📅 Creating PM schedules...")
    pm_list = []
    frequency_options = [("weekly", 7), ("monthly", 30), ("quarterly", 90)]
    tech_ids = [u.id for u in users if u.role == UserRole.TECHNICIAN.value]
    for i, eq in enumerate(equipment_list[:4]):
        freq, interval = frequency_options[i % len(frequency_options)]
        last_done = random_date(datetime(2024, 1, 1), datetime(2024, 3, 1))
        next_due = last_done + timedelta(days=interval)
        pm = PMSchedule(
            title=f"PM {freq} - {eq.name}",
            equipment_id=eq.id,
            technician_id=random.choice(tech_ids),
            frequency=freq,
            interval_days=interval,
            last_done=last_done,
            next_due=next_due,
            checklist=f"چک‌لیست {freq}:\n- بازدید بصری\n- روغن‌کاری\n- تست عملکرد",
            estimated_duration=random.randint(30, 120),
            is_active=True,
            notes="برنامه نگهداری پیشگیرانه نمونه"
        )
        session.add(pm)
        pm_list.append(pm)
    session.flush()
    print(f"    Created {len(pm_list)} PM schedules")

    # ========== 4. Inspection Templates ==========
    print("  🔍 Creating inspection templates...")
    template_list = []
    for eq in equipment_list[:2]:
        template = InspectionTemplate(
            name=f"قالب بازرسی {eq.name}",
            description="بازرسی دوره‌ای ساده",
            equipment_id=eq.id,
            frequency="monthly",
            estimated_duration_minutes=30,
            is_active=True
        )
        session.add(template)
        session.flush()  # ensure template gets an ID before checkpoints
        for i in range(1, 4):
            cp = InspectionCheckpoint(
                template_id=template.id,
                title=f"چک‌پوینت {i}",
                description=f"بررسی {random.choice(['ظاهر', 'دما', 'صدا'])}",
                checkpoint_type=CheckpointType.VISUAL.value,
                order_number=i
            )
            session.add(cp)
        template_list.append(template)
    session.flush()
    print(f"    Created {len(template_list)} inspection templates")

    # ========== 5. Spare Parts ==========
    print("  🔧 Creating spare parts...")
    part_list = []
    spare_data = [
        ("SP-001", "بلبرینگ 6204", "بلبرینگ", "عدد", 5, 20, 150000),
        ("SP-002", "تسمه تایم", "تسمه", "عدد", 2, 10, 250000),
        ("SP-003", "شیر برقی", "شیرآلات", "عدد", 1, 5, 850000),
        ("SP-004", "فیلتر هوا", "فیلتر", "عدد", 3, 15, 45000),
    ]
    for code, name, category, unit, min_stock, max_stock, price in spare_data:
        part = SparePart(
            part_number=code,
            name=name,
            category=category,
            unit=unit,
            min_stock=min_stock,
            current_stock=random.randint(min_stock, max_stock),
            unit_price=price,
            location="انبار اصلی",
            supplier=random.choice(["تامین قطعه", "البرز تجهیز"]),
            description=f"قطعه یدکی {name}",
            notes="موجودی اولیه"
        )
        session.add(part)
        part_list.append(part)
    session.flush()
    print(f"    Created {len(part_list)} spare parts")

    # ========== 6. Work Orders ==========
    print("  📝 Creating work orders...")
    work_order_list = []
    # preventive work orders
    for pm in pm_list[:2]:
        wo = WorkOrder(
            title=f"PM: {pm.title}",
            equipment_id=pm.equipment_id,
            schedule_id=pm.id,
            type=WorkOrderType.PREVENTIVE,
            status=WorkOrderStatus.PENDING,
            priority=WorkOrderPriority.MEDIUM,
            technician_id=pm.technician_id,
            scheduled_date=pm.next_due,
            description=f"کار پیشگیرانه خودکار از {pm.title}",
            parts_used=pm.parts_required,
            created_at=datetime.now()
        )
        session.add(wo)
        work_order_list.append(wo)
    # corrective work order
    eq = equipment_list[0]
    wo_corr = WorkOrder(
        title=f"تعمیر اضطراری {eq.name}",
        equipment_id=eq.id,
        type=WorkOrderType.CORRECTIVE,
        status=WorkOrderStatus.IN_PROGRESS,
        priority=WorkOrderPriority.HIGH,
        technician_id=tech_ids[0],
        scheduled_date=datetime.now() - timedelta(days=2),
        start_time=datetime.now() - timedelta(days=2, hours=1),
        description="خرابی ناگهانی - تعویض بلبرینگ",
        operator_id=admin.id,
        failure_report_time=datetime.now() - timedelta(days=2, hours=2),
        operator_notes="صدای غیرعادی از موتور",
        created_at=datetime.now() - timedelta(days=3)
    )
    session.add(wo_corr)
    work_order_list.append(wo_corr)
    # emergency work order
    wo_emergency = WorkOrder(
        title=f"EMERGENCY: قطعی برق {equipment_list[1].name}",
        equipment_id=equipment_list[1].id,
        type=WorkOrderType.EMERGENCY,
        status=WorkOrderStatus.PENDING,
        priority=WorkOrderPriority.URGENT,
        technician_id=tech_ids[0],
        scheduled_date=datetime.now() + timedelta(hours=2),
        description="قطع ناگهانی برق، دستگاه از کار افتاده",
        operator_id=admin.id,
        failure_report_time=datetime.now() - timedelta(minutes=30),
        operator_notes="هیچ چراغی روشن نیست",
        emergency_reported_by=admin.full_name,
        created_at=datetime.now()
    )
    session.add(wo_emergency)
    work_order_list.append(wo_emergency)
    session.flush()
    print(f"    Created {len(work_order_list)} work orders (including 1 emergency)")

    # ========== 7. Completed Inspections ==========
    print("  🔎 Creating completed inspections...")
    inspection_count = 0
    for template in template_list:
        inspector = random.choice([u for u in users if u.role == UserRole.TECHNICIAN.value])
        started = random_date(datetime(2024, 1, 1), datetime.now() - timedelta(days=10))
        completed = started + timedelta(minutes=template.estimated_duration_minutes)
        ins = Inspection(
            template_id=template.id,
            equipment_id=template.equipment_id,
            inspector_id=inspector.id,
            started_at=started,
            completed_at=completed,
            status=InspectionStatus.COMPLETED.value,
            overall_result="pass",
            notes="بازرسی با موفقیت انجام شد"
        )
        session.add(ins)
        session.flush()  # <-- CRITICAL: Force ID generation before adding results
        for cp in template.checkpoints:
            ir = InspectionResult(
                inspection_id=ins.id,
                checkpoint_id=cp.id,
                result="pass",
                comment="تأیید شد",
                recorded_at=completed
            )
            session.add(ir)
        inspection_count += 1
    session.flush()
    print(f"    Created {inspection_count} completed inspections")

    # ========== 8. Production Logs ==========
    print("  📊 Creating production logs...")
    log_count = 0
    for eq in equipment_list[:2]:
        for day in range(7):
            log_date = datetime.now().date() - timedelta(days=day)
            operating = random.uniform(20, 24)
            planned = 24
            downtime = planned - operating
            output = random.randint(800, 1200) if operating > 20 else random.randint(300, 700)
            pl = ProductionLog(
                equipment_id=eq.id,
                log_date=datetime.combine(log_date, datetime.min.time()),
                operating_hours=round(operating, 2),
                planned_hours=planned,
                downtime_hours=round(downtime, 2),
                output_units=output
            )
            session.add(pl)
            log_count += 1
    session.commit()
    print(f"    Created {log_count} production logs")

    print("\n✅ Seeding completed successfully!")
    print(f"   Users: {len(users)}")
    print(f"   Equipment: {len(equipment_list)}")
    print(f"   PM Schedules: {len(pm_list)}")
    print(f"   Inspection Templates: {len(template_list)}")
    print(f"   Spare Parts: {len(part_list)}")
    print(f"   Work Orders: {len(work_order_list)} (includes 1 emergency)")
    print(f"   Completed Inspections: {inspection_count}")
    print(f"   Production Logs: {log_count}")
    session.close()


def seed_admin():
    seed_all()


if __name__ == "__main__":
    seed_all()