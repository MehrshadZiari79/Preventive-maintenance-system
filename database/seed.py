# database/seed.py
"""
Seed database with initial data and test data for all modules.
Run this script once to populate the database for testing.
"""
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
from auth.auth_manager import hash_password  # Import the standalone function

# ==================== Helper Functions ====================

def random_date(start: datetime, end: datetime) -> datetime:
    """Return random datetime between start and end."""
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)


def random_choice_weighted(items, weights=None):
    """Pick random item with optional weights."""
    return random.choices(items, weights=weights, k=1)[0]


# ==================== Seed Main ====================

def seed_all():
    session = SessionLocal()

    print("🌱 Seeding database with test data...")

    # ========== 1. Users ==========
    print("  📋 Creating users...")
    users = []

    # Admin
    admin = session.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            full_name="مدیر سیستم",
            role=UserRole.ADMIN.value,
            is_active=True
        )
        session.add(admin)
        users.append(admin)

    # Manager
    manager = session.query(User).filter(User.username == "manager").first()
    if not manager:
        manager = User(
            username="manager",
            password_hash=hash_password("manager123"),
            full_name="مدیر نگهداری",
            role=UserRole.MANAGER.value,
            is_active=True
        )
        session.add(manager)
        users.append(manager)

    # Technicians
    tech_names = [
        ("tech1", "احمد رضایی"),
        ("tech2", "محمد کریمی"),
        ("tech3", "علی حسینی"),
        ("tech4", "رضا محمدی"),
        ("tech5", "حسین احمدی"),
    ]
    for username, full_name in tech_names:
        tech = session.query(User).filter(User.username == username).first()
        if not tech:
            tech = User(
                username=username,
                password_hash=hash_password("tech123"),
                full_name=full_name,
                role=UserRole.TECHNICIAN.value,
                is_active=True
            )
            session.add(tech)
            users.append(tech)

    session.commit()

    # ========== 2. Equipment ==========
    print("  🔧 Creating equipment...")
    equipment_list = []

    equipment_data = [
        {"code": "M-1001", "name": "پاستوریزاتور خط ۱", "category": "فرآوری", "location": "سالن تولید", "criticality": EquipmentCriticality.CRITICAL.value},
        {"code": "M-1002", "name": "پاستوریزاتور خط ۲", "category": "فرآوری", "location": "سالن تولید", "criticality": EquipmentCriticality.HIGH.value},
        {"code": "M-2001", "name": "هموژنایزر", "category": "فرآوری", "location": "سالن تولید", "criticality": EquipmentCriticality.CRITICAL.value},
        {"code": "M-3001", "name": "مخزن استریل", "category": "ذخیره‌سازی", "location": "سالن استریل", "criticality": EquipmentCriticality.HIGH.value},
        {"code": "M-4001", "name": "دستگاه بسته‌بندی", "category": "بسته‌بندی", "location": "سالن بسته‌بندی", "criticality": EquipmentCriticality.MEDIUM.value},
        {"code": "M-5001", "name": "کمپرسور هوا", "category": "تاسیسات", "location": "موتورخانه", "criticality": EquipmentCriticality.LOW.value},
        {"code": "M-6001", "name": "چیلر", "category": "سرمایش", "location": "موتورخانه", "criticality": EquipmentCriticality.MEDIUM.value},
        {"code": "M-7001", "name": "نوار نقاله", "category": "جابجایی", "location": "سالن بسته‌بندی", "criticality": EquipmentCriticality.LOW.value},
        {"code": "M-8001", "name": "دستگاه لیبل‌زن", "category": "بسته‌بندی", "location": "سالن بسته‌بندی", "criticality": EquipmentCriticality.MEDIUM.value},
        {"code": "M-9001", "name": "دیگ بخار", "category": "تاسیسات", "location": "موتورخانه", "criticality": EquipmentCriticality.HIGH.value},
    ]

    for data in equipment_data:
        eq = session.query(Equipment).filter(Equipment.code == data["code"]).first()
        if not eq:
            eq = Equipment(
                code=data["code"],
                name=data["name"],
                category=data["category"],
                manufacturer=random.choice(["Alfa Laval", "Tetra Pak", "GEA", "SPX Flow", "Siemens"]),
                model=f"{data['code']}-{random.randint(100, 999)}",
                serial_number=f"SN-{random.randint(10000, 99999)}",
                location=data["location"],
                installation_date=random_date(datetime(2018, 1, 1), datetime(2023, 12, 31)),
                status=random_choice_weighted(
                    [EquipmentStatus.OPERATIONAL.value, EquipmentStatus.MAINTENANCE.value,
                     EquipmentStatus.BREAKDOWN.value, EquipmentStatus.INACTIVE.value],
                    weights=[0.7, 0.15, 0.1, 0.05]
                ),
                criticality_level=data["criticality"],
                specifications=f"ظرفیت: {random.randint(1000, 10000)} لیتر در ساعت",
                notes="تجهیز اصلی خط تولید"
            )
            session.add(eq)
            equipment_list.append(eq)

    session.commit()

    # ========== 3. PM Schedules ==========
    print("  📅 Creating PM schedules...")
    pm_list = []

    frequency_options = [
        (PMFrequency.DAILY.value, 1),
        (PMFrequency.WEEKLY.value, 7),
        (PMFrequency.MONTHLY.value, 30),
        (PMFrequency.QUARTERLY.value, 90),
        (PMFrequency.BIANNUAL.value, 180),
        (PMFrequency.ANNUAL.value, 365),
    ]

    for eq in equipment_list:
        # Create 1-3 PM schedules per equipment
        for _ in range(random.randint(1, 3)):
            freq, interval = random.choice(frequency_options)
            last_done = random_date(datetime(2023, 1, 1), datetime.now() - timedelta(days=30))
            next_due = last_done + timedelta(days=interval)
            pm = PMSchedule(
                title=f"PM برنامه {freq} - {eq.name}",
                equipment_id=eq.id,
                technician_id=random.choice([u.id for u in users if u.role == UserRole.TECHNICIAN.value]),
                frequency=freq,
                interval_days=interval,
                last_done=last_done,
                next_due=next_due,
                checklist=f"چک‌لیست {freq}:\n- بازدید بصری\n- روغن‌کاری\n- تمیزکاری\n- تست عملکرد",
                estimated_duration=random.randint(30, 240),
                is_active=random.choice([True, False]) if random.random() > 0.2 else True,
                notes="برنامه نگهداری پیشگیرانه"
            )
            session.add(pm)
            pm_list.append(pm)

    session.commit()

    # ========== 4. Inspection Templates ==========
    print("  🔍 Creating inspection templates...")
    template_list = []

    checkpoint_types = [CheckpointType.VISUAL.value, CheckpointType.MEASUREMENT.value,
                        CheckpointType.FUNCTIONAL.value, CheckpointType.SAFETY.value]

    for eq in equipment_list:
        template = InspectionTemplate(
            name=f"قالب بازرسی {eq.name}",
            description="بازرسی دوره ای تجهیز",
            equipment_id=eq.id,
            frequency=random.choice(["daily", "weekly", "monthly", "quarterly"]),
            estimated_duration_minutes=random.randint(15, 90),
            is_active=True
        )
        session.add(template)
        session.flush()

        # Add 5-15 checkpoints
        for i in range(1, random.randint(5, 15)):
            cp = InspectionCheckpoint(
                template_id=template.id,
                title=f"چک‌پوینت {i}",
                description=f"بررسی {random.choice(['وضعیت ظاهری', 'دمای کارکرد', 'فشار', 'لرزش', 'صدا', 'نشتی'])}",
                checkpoint_type=random.choice(checkpoint_types),
                order_number=i
            )
            session.add(cp)

        template_list.append(template)

    session.commit()

    # ========== 5. Spare Parts ==========
    print("  🔧 Creating spare parts...")
    part_list = []

    spare_data = [
        ("SP-001", "بلبرینگ 6204", "بلبرینگ", "عدد", 10, 50, 150000),
        ("SP-002", "تسمه تایم", "تسمه", "عدد", 5, 20, 250000),
        ("SP-003", "شیر برقی", "شیرآلات", "عدد", 3, 15, 850000),
        ("SP-004", "سنسور دما", "الکترونیک", "عدد", 2, 10, 1200000),
        ("SP-005", "فیلتر هوا", "فیلتر", "عدد", 8, 30, 45000),
        ("SP-006", "روغن هیدرولیک", "روانکار", "لیتر", 20, 100, 35000),
        ("SP-007", "واشر آب‌بند", "واشر", "عدد", 15, 60, 12000),
        ("SP-008", "موتور الکتریکی", "موتور", "عدد", 1, 5, 5500000),
        ("SP-009", "پمپ آب", "پمپ", "عدد", 2, 8, 3200000),
        ("SP-010", "کلید حرارتی", "الکتریک", "عدد", 4, 20, 180000),
    ]

    for code, name, category, unit, min_stock, max_stock, price in spare_data:
        part = session.query(SparePart).filter(SparePart.part_number == code).first()
        if not part:
            part = SparePart(
                part_number=code,
                name=name,
                category=category,
                unit=unit,
                min_stock=min_stock,
                current_stock=random.randint(min_stock, max_stock),
                unit_price=price,
                location=f"انبار {random.choice(['اصلی', 'ب', 'سردخانه'])}",
                supplier=random.choice(["تامین قطعه", "صنایع دقیق", "البرز تجهیز"]),
                description=f"قطعه یدکی {name}",
                notes="موجودی اولیه"
            )
            session.add(part)
            part_list.append(part)

    session.commit()

    # ========== 6. Stock Transactions ==========
    print("  📦 Creating stock transactions...")
    for part in part_list:
        # Create 3-8 transactions per part
        for _ in range(random.randint(3, 8)):
            trans_type = random.choice(["IN", "OUT"])
            qty = random.randint(1, 10)
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
                created_at=random_date(datetime(2023, 1, 1), datetime.now())
            )
            session.add(trans)

    session.commit()

    # ========== 7. Work Orders ==========
    print("  📝 Creating work orders...")
    work_order_list = []

    wo_types = [WorkOrderType.PREVENTIVE, WorkOrderType.CORRECTIVE, WorkOrderType.INSPECTION, WorkOrderType.PM]
    wo_statuses = [WorkOrderStatus.PENDING, WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.COMPLETED, WorkOrderStatus.APPROVED, WorkOrderStatus.REJECTED]
    priorities = [WorkOrderPriority.LOW, WorkOrderPriority.MEDIUM, WorkOrderPriority.HIGH, WorkOrderPriority.URGENT]

    # Create 50 work orders
    for i in range(50):
        wo_type = random.choice(wo_types)
        eq = random.choice(equipment_list)
        scheduled = random_date(datetime(2023, 1, 1), datetime.now() + timedelta(days=60))
        status = random.choice(wo_statuses)
        start_time = None
        end_time = None
        if status in [WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.COMPLETED, WorkOrderStatus.APPROVED]:
            start_time = scheduled + timedelta(hours=random.randint(1, 48))
            if status in [WorkOrderStatus.COMPLETED, WorkOrderStatus.APPROVED]:
                end_time = start_time + timedelta(hours=random.randint(1, 24))

        wo = WorkOrder(
            title=f"{wo_type.name} - {eq.name} - {i+1}",
            equipment_id=eq.id,
            type=wo_type,
            status=status,
            priority=random.choice(priorities),
            technician_id=random.choice([u.id for u in users if u.role == UserRole.TECHNICIAN.value]),
            scheduled_date=scheduled,
            start_time=start_time,
            end_time=end_time,
            description=f"کار {wo_type.name} روی تجهیز {eq.name}",
            parts_used=f"قطعات: {random.choice([p.name for p in part_list[:3]])}",
            created_at=random_date(datetime(2023, 1, 1), datetime.now())
        )
        session.add(wo)
        work_order_list.append(wo)

    session.commit()

    # ========== 8. Inspections (completed) ==========
    print("  🔎 Creating completed inspections...")
    inspection_list = []

    for template in template_list:
        # Create 2-5 inspections per template
        for _ in range(random.randint(2, 5)):
            inspector = random.choice([u for u in users if u.role == UserRole.TECHNICIAN.value])
            started = random_date(datetime(2023, 1, 1), datetime.now())
            completed = started + timedelta(minutes=template.estimated_duration_minutes)
            status = random_choice_weighted([InspectionStatus.COMPLETED.value, InspectionStatus.CANCELLED.value], [0.9, 0.1])
            overall_result = random_choice_weighted(["pass", "fail", "partial"], [0.6, 0.2, 0.2]) if status == InspectionStatus.COMPLETED.value else None

            ins = Inspection(
                template_id=template.id,
                equipment_id=template.equipment_id,
                inspector_id=inspector.id,
                started_at=started,
                completed_at=completed if status == InspectionStatus.COMPLETED.value else None,
                status=status,
                overall_result=overall_result,
                notes=f"یادداشت بازرسی خودکار"
            )
            session.add(ins)
            session.flush()

            # Add results for each checkpoint
            if status == InspectionStatus.COMPLETED.value:
                for cp in template.checkpoints:
                    result = random_choice_weighted(["pass", "fail", "na"], [0.7, 0.2, 0.1])
                    ir = InspectionResult(
                        inspection_id=ins.id,
                        checkpoint_id=cp.id,
                        result=result,
                        comment=f"نتیجه: {result} - بررسی خودکار" if result == "fail" else None,
                        recorded_at=completed
                    )
                    session.add(ir)

    session.commit()

    # ========== 9. Production Logs (for OEE/MTBF) ==========
    print("  📊 Creating production logs...")
    for eq in equipment_list:
        # Create logs for last 30 days
        for day in range(30):
            log_date = datetime.now().date() - timedelta(days=day)
            operating = random.uniform(20, 24)  # hours
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

    session.commit()

    print("\n✅ Seeding completed successfully!")
    print(f"   Users: {len(users)}")
    print(f"   Equipment: {len(equipment_list)}")
    print(f"   PM Schedules: {len(pm_list)}")
    print(f"   Inspection Templates: {len(template_list)}")
    print(f"   Spare Parts: {len(part_list)}")
    print(f"   Work Orders: {len(work_order_list)}")
    print(f"   Completed Inspections: {session.query(Inspection).count()}")
    print(f"   Production Logs: {session.query(ProductionLog).count()}")
    session.close()


# Backward compatibility for main.py
seed_admin = seed_all


if __name__ == "__main__":
    seed_all()