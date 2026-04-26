# database/seed.py
import random
import json
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
    if session.query(Equipment).count() > 0:
        print("✅ Database already has data. Skipping seed.")
        session.close()
        return

    print("🌱 Seeding comprehensive test data...")

    # ========== 1. Users (4) ==========
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

    # ========== 2. Equipment (4 items) ==========
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
            manufacturer=random.choice(["Alfa Laval", "Tetra Pak", "GEA", "Siemens"]),
            model=f"{data['code']}-{random.randint(100, 999)}",
            serial_number=f"SN-{random.randint(10000, 99999)}",
            location=data["location"],
            installation_date=random_date(datetime(2018, 1, 1), datetime(2022, 12, 31)),
            status=EquipmentStatus.OPERATIONAL.value,
            criticality_level=data["criticality"],
            specifications=f"ظرفیت: {random.randint(1000, 5000)} لیتر در ساعت، توان: {random.randint(5, 50)} کیلووات",
            notes="تجهیز اصلی خط تولید"
        )
        session.add(eq)
        equipment_list.append(eq)
    session.flush()
    print(f"    Created {len(equipment_list)} equipment")

    # ========== 3. PM Schedules (4, one per equipment) ==========
    print("  📅 Creating PM schedules...")
    pm_list = []
    tech_ids = [u.id for u in users if u.role == UserRole.TECHNICIAN.value]
    frequency_options = [
        ("daily", 1),
        ("weekly", 7),
        ("monthly", 30),
        ("quarterly", 90),
    ]
    for i, eq in enumerate(equipment_list):
        freq, interval = frequency_options[i % len(frequency_options)]
        last_done = random_date(datetime(2024, 1, 1), datetime(2024, 3, 1))
        next_due = last_done + timedelta(days=interval)
        parts_required = json.dumps([
            {"part_id": 1, "quantity": 2},
            {"part_id": 2, "quantity": 1}
        ]) if i == 0 else None
        pm = PMSchedule(
            title=f"PM {freq} - {eq.name}",
            equipment_id=eq.id,
            technician_id=random.choice(tech_ids),
            frequency=freq,
            interval_days=interval,
            last_done=last_done,
            next_due=next_due,
            checklist=f"چک‌لیست {freq}:\n- بازدید بصری\n- روغن‌کاری\n- تست عملکرد\n- بررسی اتصالات",
            estimated_duration=random.randint(30, 180),
            is_active=True,
            notes="برنامه نگهداری پیشگیرانه خودکار",
            parts_required=parts_required
        )
        session.add(pm)
        pm_list.append(pm)
    session.flush()
    print(f"    Created {len(pm_list)} PM schedules")

    # ========== 4. Inspection Templates (2) ==========
    print("  🔍 Creating inspection templates...")
    template_list = []
    for i, eq in enumerate(equipment_list[:2]):
        template = InspectionTemplate(
            name=f"قالب بازرسی {eq.name}",
            description="بازرسی دوره‌ای ایمنی و عملکرد",
            equipment_id=eq.id,
            frequency="monthly",
            estimated_duration_minutes=30,
            is_active=True
        )
        session.add(template)
        session.flush()
        for j in range(1, 4):
            cp = InspectionCheckpoint(
                template_id=template.id,
                title=f"چک‌پوینت {j}",
                description=f"بررسی {random.choice(['ظاهر', 'دمای کارکرد', 'لرزش', 'صدا', 'نشتی'])}",
                checkpoint_type=random.choice([CheckpointType.VISUAL.value, CheckpointType.MEASUREMENT.value]),
                order_number=j
            )
            session.add(cp)
        template_list.append(template)
    session.flush()
    print(f"    Created {len(template_list)} inspection templates")

    # ========== 5. Spare Parts (4) with initial stock and a few transactions ==========
    print("  🔧 Creating spare parts and transactions...")
    part_list = []
    spare_data = [
        ("SP-001", "بلبرینگ 6204", "بلبرینگ", "عدد", 5, 20, 150000),
        ("SP-002", "تسمه تایم", "تسمه", "عدد", 3, 12, 250000),
        ("SP-003", "شیر برقی", "شیرآلات", "عدد", 2, 8, 850000),
        ("SP-004", "فیلتر هوا", "فیلتر", "عدد", 4, 18, 45000),
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
            supplier=random.choice(["تامین قطعه", "البرز تجهیز", "صنعت کار"]),
            description=f"قطعه یدکی {name}",
            notes="موجودی اولیه"
        )
        session.add(part)
        part_list.append(part)
    session.flush()

    # Create some transactions (IN and OUT) for each part
    for part in part_list:
        for _ in range(random.randint(2, 4)):
            trans_type = random.choice(["IN", "OUT"])
            qty = random.randint(1, 3)
            if trans_type == "OUT" and part.current_stock < qty:
                continue
            if trans_type == "OUT":
                part.current_stock -= qty
            else:
                part.current_stock += qty
            trans = SparePartTransaction(
                part_id=part.id,
                transaction_type=trans_type,
                quantity=qty,
                reference=f"REF-{random.randint(100, 999)}",
                notes=f"تراکنش {trans_type} خودکار",
                created_at=random_date(datetime(2024, 1, 1), datetime.now())
            )
            session.add(trans)
    session.flush()
    print(f"    Created {len(part_list)} spare parts with transactions")

    # ========== 6. Work Orders (6: covering all types, statuses, costs, and links) ==========
    print("  📝 Creating work orders...")
    work_order_list = []

    # 1. Preventive work order linked to PM schedule (pending)
    pm = pm_list[0]
    wo_preventive = WorkOrder(
        title=f"PM: {pm.title}",
        equipment_id=pm.equipment_id,
        schedule_id=pm.id,
        type=WorkOrderType.PREVENTIVE,
        status=WorkOrderStatus.PENDING,
        priority=WorkOrderPriority.MEDIUM,
        technician_id=pm.technician_id,
        scheduled_date=pm.next_due,
        description="کار پیشگیرانه خودکار بر اساس PM",
        manual_cost=0.0,
        cost_description=None,
        created_at=datetime.now()
    )
    session.add(wo_preventive)
    work_order_list.append(wo_preventive)

    # 2. Corrective work order (in progress) with no cost yet
    wo_corrective_progress = WorkOrder(
        title="تعمیر هموژنایزر - ویبراسیون",
        equipment_id=equipment_list[1].id,
        type=WorkOrderType.CORRECTIVE,
        status=WorkOrderStatus.IN_PROGRESS,
        priority=WorkOrderPriority.HIGH,
        technician_id=tech_ids[0],
        scheduled_date=datetime.now() - timedelta(days=1),
        start_time=datetime.now() - timedelta(days=1, hours=3),
        description="لرزش غیرعادی هنگام کار",
        operator_id=admin.id,
        failure_report_time=datetime.now() - timedelta(days=2),
        operator_notes="صدا و لرزش زیاد",
        manual_cost=0.0,
        cost_description=None,
        created_at=datetime.now() - timedelta(days=2)
    )
    session.add(wo_corrective_progress)
    work_order_list.append(wo_corrective_progress)

    # 3. Completed corrective work order with manual cost and spare parts usage
    wo_corrective_completed = WorkOrder(
        title="تعمیر پاستوریزاتور - نشتی",
        equipment_id=equipment_list[0].id,
        type=WorkOrderType.CORRECTIVE,
        status=WorkOrderStatus.COMPLETED,
        priority=WorkOrderPriority.HIGH,
        technician_id=tech_ids[0],
        scheduled_date=datetime.now() - timedelta(days=5),
        start_time=datetime.now() - timedelta(days=5, hours=2),
        end_time=datetime.now() - timedelta(days=4, hours=5),
        description="تعویض واشر و شیر",
        operator_id=admin.id,
        failure_report_time=datetime.now() - timedelta(days=6),
        operator_notes="نشتی از شیر تخلیه",
        parts_used=json.dumps([{"part_id": part_list[2].id, "quantity": 1}]),
        manual_cost=750000.0,
        cost_description="هزینه تعمیرکار شب کاری",
        created_at=datetime.now() - timedelta(days=6)
    )
    session.add(wo_corrective_completed)
    work_order_list.append(wo_corrective_completed)

    # 4. Emergency work order (pending, with emergency_reported_by)
    wo_emergency = WorkOrder(
        title="خرابی ناگهانی کمپرسور",
        equipment_id=equipment_list[3].id,
        type=WorkOrderType.EMERGENCY,
        status=WorkOrderStatus.PENDING,
        priority=WorkOrderPriority.URGENT,
        technician_id=tech_ids[0],
        scheduled_date=datetime.now() + timedelta(hours=2),
        description="کمپرسور روشن نمی‌شود",
        operator_id=admin.id,
        failure_report_time=datetime.now() - timedelta(hours=1),
        operator_notes="هیچ صدایی نمی‌دهد",
        emergency_reported_by=admin.full_name,
        manual_cost=0.0,
        cost_description=None,
        created_at=datetime.now() - timedelta(hours=1)
    )
    session.add(wo_emergency)
    work_order_list.append(wo_emergency)

    # 5. Inspection work order (completed)
    wo_inspection = WorkOrder(
        title="بازرسی سالانه پاستوریزاتور",
        equipment_id=equipment_list[0].id,
        type=WorkOrderType.INSPECTION,
        status=WorkOrderStatus.COMPLETED,
        priority=WorkOrderPriority.MEDIUM,
        technician_id=tech_ids[0],
        scheduled_date=datetime.now() - timedelta(days=8),
        start_time=datetime.now() - timedelta(days=8, hours=1),
        end_time=datetime.now() - timedelta(days=7, hours=3),
        description="بازرسی کامل توسط تکنسین",
        operator_id=admin.id,
        operator_notes="تجهیز در وضعیت خوب",
        manual_cost=200000.0,
        cost_description="هزینه بازرسی بیرون",
        created_at=datetime.now() - timedelta(days=9)
    )
    session.add(wo_inspection)
    work_order_list.append(wo_inspection)

    # 6. Another preventive work order (approved, to test approval flow)
    pm2 = pm_list[1]
    wo_approved = WorkOrder(
        title=f"PM: {pm2.title} (تأیید شده)",
        equipment_id=pm2.equipment_id,
        schedule_id=pm2.id,
        type=WorkOrderType.PREVENTIVE,
        status=WorkOrderStatus.APPROVED,
        priority=WorkOrderPriority.LOW,
        technician_id=pm2.technician_id,
        scheduled_date=pm2.next_due + timedelta(days=5),
        description="برنامه PM با تاخیر تأیید شد",
        manual_cost=0.0,
        created_at=datetime.now() - timedelta(days=1)
    )
    session.add(wo_approved)
    work_order_list.append(wo_approved)

    session.flush()
    print(f"    Created {len(work_order_list)} work orders (covering all types, statuses, costs)")

    # ========== 7. Completed Inspections (with results) ==========
    print("  🔎 Creating completed inspections...")
    inspection_count = 0
    # Inspection for first template (pass)
    template1 = template_list[0]
    inspector = random.choice([u for u in users if u.role == UserRole.TECHNICIAN.value])
    started1 = random_date(datetime(2024, 2, 1), datetime.now() - timedelta(days=5))
    completed1 = started1 + timedelta(minutes=template1.estimated_duration_minutes)
    ins1 = Inspection(
        template_id=template1.id,
        equipment_id=template1.equipment_id,
        inspector_id=inspector.id,
        started_at=started1,
        completed_at=completed1,
        status=InspectionStatus.COMPLETED.value,
        overall_result="pass",
        notes="همه چیز عادی است"
    )
    session.add(ins1)
    session.flush()
    for cp in template1.checkpoints:
        ir = InspectionResult(
            inspection_id=ins1.id,
            checkpoint_id=cp.id,
            result="pass",
            comment="تأیید شد",
            recorded_at=completed1
        )
        session.add(ir)
    inspection_count += 1

    # Inspection for second template (fail)
    template2 = template_list[1]
    started2 = random_date(datetime(2024, 2, 15), datetime.now() - timedelta(days=2))
    completed2 = started2 + timedelta(minutes=template2.estimated_duration_minutes)
    ins2 = Inspection(
        template_id=template2.id,
        equipment_id=template2.equipment_id,
        inspector_id=inspector.id,
        started_at=started2,
        completed_at=completed2,
        status=InspectionStatus.COMPLETED.value,
        overall_result="fail",
        notes="لرزش بیش از حد و نشتی روغن"
    )
    session.add(ins2)
    session.flush()
    for i, cp in enumerate(template2.checkpoints):
        # First checkpoint passes, second fails, third passes (to get partial)
        result = "fail" if i == 1 else "pass"
        ir = InspectionResult(
            inspection_id=ins2.id,
            checkpoint_id=cp.id,
            result=result,
            comment="نیاز به تعمیر" if result == "fail" else "تأیید شد",
            recorded_at=completed2
        )
        session.add(ir)
    inspection_count += 1

    session.flush()
    print(f"    Created {inspection_count} completed inspections (one pass, one fail)")

    # ========== 8. Production Logs (last 10 days for first 2 equipment) ==========
    print("  📊 Creating production logs...")
    log_count = 0
    for eq in equipment_list[:2]:
        for day in range(10):
            log_date = datetime.now().date() - timedelta(days=day)
            operating = random.uniform(20, 24)
            planned = 24
            downtime = planned - operating
            output = random.randint(800, 1200) if operating > 20 else random.randint(300, 600)
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
    print(f"    Created {log_count} production logs (10 days x 2 equipment)")

    print("\n✅ Seed completed successfully!")
    print(f"   Users: {len(users)}")
    print(f"   Equipment: {len(equipment_list)}")
    print(f"   PM Schedules: {len(pm_list)}")
    print(f"   Inspection Templates: {len(template_list)}")
    print(f"   Spare Parts: {len(part_list)}")
    print(f"   Work Orders: {len(work_order_list)} (includes preventive, corrective, emergency, inspection, approved)")
    print(f"   Completed Inspections: {inspection_count}")
    print(f"   Production Logs: {log_count}")
    print("\n📌 Test coverage includes:")
    print("   - All work order types and statuses")
    print("   - Manual cost and cost description")
    print("   - Spare parts usage (JSON in parts_used)")
    print("   - PM schedules linked to work orders")
    print("   - Completed and failed inspections")
    print("   - Production logs for OEE calculation")
    print("   - Emergency work orders with reporter")
    session.close()


def seed_admin():
    seed_all()


if __name__ == "__main__":
    seed_all()