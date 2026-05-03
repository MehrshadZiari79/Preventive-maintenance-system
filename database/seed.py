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


def random_choice_weighted(items_with_weights):
    """items_with_weights: list of (item, weight)"""
    total = sum(w for _, w in items_with_weights)
    r = random.uniform(0, total)
    upto = 0
    for item, w in items_with_weights:
        if upto + w >= r:
            return item
        upto += w
    return items_with_weights[0][0]


def hash_password(password: str) -> str:
    import hashlib
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def seed_all():
    session = SessionLocal()
    if session.query(Equipment).count() > 0:
        print("✅ Database already has data. Skipping seed.")
        session.close()
        return

    print("🌱 Seeding comprehensive test data for all features...")

    # ========== 1. Users (8) ==========
    print("  👥 Creating users...")
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

    tech_data = [
        ("tech1", "احمد رضایی"),
        ("tech2", "محمد کریمی"),
        ("tech3", "سعید حسن‌پور"),
        ("tech4", "رضا نظری"),
        ("tech5", "علی مرادی"),
        ("tech6", "حسین طالبی"),
    ]
    for username, full_name in tech_data:
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
    tech_ids = [u.id for u in users if u.role == UserRole.TECHNICIAN.value]
    print(f"    Created {len(users)} users (1 admin, 1 manager, 6 technicians)")

    # ========== 2. Equipment (10 items) ==========
    print("  🔧 Creating equipment...")
    equipment_list = []
    # Define categories, criticalities, statuses
    eq_data = [
        {"code": "M-1001", "name": "پاستوریزاتور خط 1", "category": "فرآوری", "location": "سالن تولید", "criticality": EquipmentCriticality.CRITICAL.value},
        {"code": "M-1002", "name": "پاستوریزاتور خط 2", "category": "فرآوری", "location": "سالن تولید", "criticality": EquipmentCriticality.CRITICAL.value},
        {"code": "M-2001", "name": "هموژنایزر اصلی", "category": "فرآوری", "location": "سالن تولید", "criticality": EquipmentCriticality.HIGH.value},
        {"code": "M-2002", "name": "هموژنایزر پشتیبان", "category": "فرآوری", "location": "سالن تولید", "criticality": EquipmentCriticality.MEDIUM.value},
        {"code": "M-3001", "name": "دستگاه بسته‌بندی شیر", "category": "بسته‌بندی", "location": "سالن بسته‌بندی", "criticality": EquipmentCriticality.HIGH.value},
        {"code": "M-3002", "name": "دستگاه بسته‌بندی ماست", "category": "بسته‌بندی", "location": "سالن بسته‌بندی", "criticality": EquipmentCriticality.MEDIUM.value},
        {"code": "M-3003", "name": "دستگاه بسته‌بندی پنیر", "category": "بسته‌بندی", "location": "سالن بسته‌بندی", "criticality": EquipmentCriticality.LOW.value},
        {"code": "M-4001", "name": "کمپرسور هوا مرکزی", "category": "تاسیسات", "location": "موتورخانه", "criticality": EquipmentCriticality.HIGH.value},
        {"code": "M-4002", "name": "ترانسفورماتور", "category": "تاسیسات", "location": "موتورخانه", "criticality": EquipmentCriticality.CRITICAL.value},
        {"code": "M-5001", "name": "نوار نقاله تغذیه", "category": "حمل و نقل", "location": "سالن تولید", "criticality": EquipmentCriticality.MEDIUM.value},
    ]
    # Assign statuses: most operational, one in maintenance, one breakdown
    for i, data in enumerate(eq_data):
        status = EquipmentStatus.OPERATIONAL.value
        if i == 3:  # هموژنایزر پشتیبان
            status = EquipmentStatus.MAINTENANCE.value
        elif i == 6:  # دستگاه بسته‌بندی پنیر
            status = EquipmentStatus.BREAKDOWN.value
        eq = Equipment(
            code=data["code"],
            name=data["name"],
            category=data["category"],
            manufacturer=random.choice(["Alfa Laval", "Tetra Pak", "GEA", "Siemens", "Frigomat"]),
            model=f"{data['code']}-{random.randint(100, 999)}",
            serial_number=f"SN-{random.randint(10000, 99999)}",
            location=data["location"],
            installation_date=random_date(datetime(2015, 1, 1), datetime(2022, 12, 31)),
            status=status,
            criticality_level=data["criticality"],
            specifications=f"ظرفیت: {random.randint(1000, 5000)} لیتر در ساعت، توان: {random.randint(5, 50)} کیلووات",
            notes="تجهیز اصلی خط تولید"
        )
        session.add(eq)
        equipment_list.append(eq)
    session.flush()
    print(f"    Created {len(equipment_list)} equipment (with varied statuses)")

    # ========== 3. PM Schedules (12) ==========
    print("  📅 Creating PM schedules...")
    pm_list = []
    frequency_options = [
        ("daily", 1, 0.1), ("weekly", 7, 0.2), ("monthly", 30, 0.4), ("quarterly", 90, 0.2), ("annual", 365, 0.1)
    ]
    for eq in equipment_list:
        # Eventually add 1-2 PM per equipment
        freq, interval, _ = random.choice(frequency_options)
        last_done = random_date(datetime(2024, 1, 1), datetime(2024, 4, 1))
        next_due = last_done + timedelta(days=interval)
        is_active = random.random() > 0.2  # 80% active
        pm = PMSchedule(
            title=f"PM {freq} - {eq.name}",
            equipment_id=eq.id,
            technician_id=random.choice(tech_ids),
            frequency=freq,
            interval_days=interval,
            last_done=last_done if is_active else None,
            next_due=next_due if is_active else None,
            checklist=f"چک‌لیست {freq}:\n- بازدید بصری\n- روغن‌کاری\n- تست عملکرد\n- بررسی اتصالات",
            estimated_duration=random.randint(30, 180),
            is_active=is_active,
            notes="برنامه نگهداری پیشگیرانه"
        )
        session.add(pm)
        pm_list.append(pm)
    # Add extra PMs for critical equipment
    for eq in equipment_list[:3]:
        pm2 = PMSchedule(
            title=f"PM هفتگی نظافتی - {eq.name}",
            equipment_id=eq.id,
            technician_id=random.choice(tech_ids),
            frequency="weekly",
            interval_days=7,
            last_done=random_date(datetime(2024, 3, 1), datetime(2024, 4, 10)),
            next_due=datetime.now() + timedelta(days=random.randint(1, 14)),
            is_active=True,
            estimated_duration=45,
            checklist="نظافت و بازرسی سریع"
        )
        session.add(pm2)
        pm_list.append(pm2)
    session.flush()
    print(f"    Created {len(pm_list)} PM schedules (active and inactive)")

    # ========== 4. Spare Parts (8) with transactions ==========
    print("  🔧 Creating spare parts and transactions...")
    part_list = []
    spare_data = [
        ("SP-001", "بلبرینگ 6204", "بلبرینگ", "عدد", 5, 30, 150000),
        ("SP-002", "تسمه تایم", "تسمه", "عدد", 3, 20, 250000),
        ("SP-003", "شیر برقی", "شیرآلات", "عدد", 2, 15, 850000),
        ("SP-004", "فیلتر هوا", "فیلتر", "عدد", 4, 25, 45000),
        ("SP-005", "موتور گیربکس", "موتور", "عدد", 1, 5, 2500000),
        ("SP-006", "سنسور دما", "الکترونیک", "عدد", 3, 10, 320000),
        ("SP-007", "واشر پاستوریزاتور", "واشر", "عدد", 10, 50, 25000),
        ("SP-008", "پمپ روغن", "پمپ", "عدد", 2, 8, 1200000),
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
            supplier=random.choice(["تامین قطعه", "البرز تجهیز", "صنعت کار", "قطعه گستر"]),
            description=f"قطعه یدکی {name}",
            notes="موجودی اولیه"
        )
        session.add(part)
        part_list.append(part)
    session.flush()

    # Create many transactions (IN and OUT) for each part over last 6 months
    for part in part_list:
        for _ in range(random.randint(5, 12)):
            trans_type = random_choice_weighted([("IN", 0.4), ("OUT", 0.6)])
            qty = random.randint(1, 3)
            if trans_type == "OUT" and part.current_stock < qty:
                continue
            if trans_type == "OUT":
                part.current_stock -= qty
            else:
                part.current_stock += qty
            ref = f"REF-{random.randint(1000, 9999)}" if trans_type == "IN" else f"WO-{random.randint(100, 999)}"
            trans = SparePartTransaction(
                part_id=part.id,
                transaction_type=trans_type,
                quantity=qty,
                reference=ref,
                notes=f"تراکنش {trans_type} خودکار",
                created_at=random_date(datetime.now() - timedelta(days=180), datetime.now())
            )
            session.add(trans)
    session.flush()
    print(f"    Created {len(part_list)} spare parts with many transactions")

    # ========== 5. Work Orders (30+) covering all types, statuses, costs, and spans 6 months ==========
    print("  📝 Creating work orders...")
    wo_list = []
    # Helper to create work orders with varied dates
    now = datetime.now()
    for i in range(40):
        eq = random.choice(equipment_list)
        wo_type = random_choice_weighted([
            (WorkOrderType.PREVENTIVE, 0.3),
            (WorkOrderType.CORRECTIVE, 0.4),
            (WorkOrderType.EMERGENCY, 0.2),
            (WorkOrderType.INSPECTION, 0.1)
        ])
        status = random_choice_weighted([
            (WorkOrderStatus.PENDING, 0.2),
            (WorkOrderStatus.IN_PROGRESS, 0.2),
            (WorkOrderStatus.COMPLETED, 0.4),
            (WorkOrderStatus.APPROVED, 0.1),
            (WorkOrderStatus.REJECTED, 0.1)
        ])
        priority = random.choice([WorkOrderPriority.LOW, WorkOrderPriority.MEDIUM, WorkOrderPriority.HIGH, WorkOrderPriority.URGENT])
        scheduled_date = random_date(now - timedelta(days=180), now + timedelta(days=30))
        description = f"کار {wo_type.value} روی {eq.name}"
        parts_used = None
        manual_cost = 0.0
        cost_description = None
        if status == WorkOrderStatus.COMPLETED or status == WorkOrderStatus.APPROVED:
            # Add parts usage for some
            if random.random() > 0.6:
                selected_part = random.choice(part_list)
                qty = random.randint(1, 2)
                parts_used = json.dumps([{"part_id": selected_part.id, "quantity": qty}])
            manual_cost = random.choice([0, 250000, 500000, 1000000]) if random.random() > 0.5 else 0
            if manual_cost > 0:
                cost_description = f"هزینه تعمیرات {random.choice(['شب کاری', 'قطعه خاص', 'اجرت تکنسین'])}"
        start_time = None
        end_time = None
        if status in [WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.COMPLETED, WorkOrderStatus.APPROVED]:
            start_time = scheduled_date + timedelta(hours=random.randint(1, 48))
            if status != WorkOrderStatus.IN_PROGRESS:
                end_time = start_time + timedelta(hours=random.randint(2, 24))
        fail_time = scheduled_date - timedelta(days=random.randint(1, 5)) if wo_type in [WorkOrderType.CORRECTIVE, WorkOrderType.EMERGENCY] else None
        operator = admin if random.random() > 0.7 else random.choice(users)
        tech = random.choice(tech_ids)
        wo = WorkOrder(
            title=f"{wo_type.value} - {eq.name} - {scheduled_date.strftime('%Y%m%d')}",
            equipment_id=eq.id,
            type=wo_type,
            status=status,
            priority=priority,
            technician_id=tech,
            scheduled_date=scheduled_date,
            start_time=start_time,
            end_time=end_time,
            description=description,
            operator_id=operator.id if operator else None,
            failure_report_time=fail_time,
            operator_notes="مشاهده ناهنجاری" if fail_time else None,
            parts_used=parts_used,
            manual_cost=manual_cost,
            cost_description=cost_description,
            emergency_reported_by=operator.full_name if wo_type == WorkOrderType.EMERGENCY else None,
            created_at=scheduled_date - timedelta(days=random.randint(0, 3))
        )
        session.add(wo)
        wo_list.append(wo)
        # Also link some work orders to PM schedules
        if wo_type == WorkOrderType.PREVENTIVE and random.random() > 0.5:
            # find a PM for same equipment
            pm_match = next((pm for pm in pm_list if pm.equipment_id == eq.id and pm.is_active), None)
            if pm_match:
                wo.schedule_id = pm_match.id
    session.flush()
    print(f"    Created {len(wo_list)} work orders (covering all types, statuses, costs, spanning 6 months)")

    # ========== 6. Inspection Templates (6) ==========
    print("  🔍 Creating inspection templates...")
    template_list = []
    for eq in equipment_list[:6]:  # first 6 equipment
        template = InspectionTemplate(
            name=f"قالب بازرسی {eq.name}",
            description="بازرسی دوره‌ای ایمنی و عملکرد",
            equipment_id=eq.id,
            frequency=random.choice(["daily","weekly","monthly","quarterly"]),
            estimated_duration_minutes=random.randint(20, 90),
            is_active=True
        )
        session.add(template)
        session.flush()
        for j in range(1, random.randint(4, 7)):
            cp = InspectionCheckpoint(
                template_id=template.id,
                title=f"چک‌پوینت {j}",
                description=f"بررسی {random.choice(['ظاهر', 'دمای کارکرد', 'لرزش', 'صدا', 'نشتی', 'روغن‌کاری'])}",
                checkpoint_type=random.choice([CheckpointType.VISUAL.value, CheckpointType.MEASUREMENT.value]),
                order_number=j
            )
            session.add(cp)
        template_list.append(template)
    session.flush()
    print(f"    Created {len(template_list)} inspection templates with checkpoints")

    # ========== 7. Completed Inspections (12) with results ==========
    print("  📋 Creating completed inspections...")
    inspector = random.choice([u for u in users if u.role == UserRole.TECHNICIAN.value])
    inspection_count = 0
    for template in template_list:
        for _ in range(2):  # 2 inspections per template
            started = random_date(datetime.now() - timedelta(days=90), datetime.now() - timedelta(days=1))
            completed = started + timedelta(minutes=template.estimated_duration_minutes)
            result = random_choice_weighted([("pass", 0.5), ("fail", 0.3), ("partial", 0.2)])
            ins = Inspection(
                template_id=template.id,
                equipment_id=template.equipment_id,
                inspector_id=inspector.id,
                started_at=started,
                completed_at=completed,
                status=InspectionStatus.COMPLETED.value,
                overall_result=result,
                notes=f"نتیجه بازرسی: {result}"
            )
            session.add(ins)
            session.flush()
            # Add checkpoint results
            for cp in template.checkpoints:
                cp_result = "pass"
                if result == "fail":
                    cp_result = random.choice(["pass","fail"]) if random.random() > 0.3 else "fail"
                elif result == "partial":
                    cp_result = random.choice(["pass","fail","partial"])
                ir = InspectionResult(
                    inspection_id=ins.id,
                    checkpoint_id=cp.id,
                    result=cp_result,
                    comment=random.choice(["تأیید شد", "نیاز به تعمیر", "مشاهده شد"]),
                    recorded_at=completed
                )
                session.add(ir)
            inspection_count += 1
    session.flush()
    print(f"    Created {inspection_count} completed inspections (pass/fail/partial)")

    # ========== 8. Production Logs (last 90 days for all equipment) ==========
    print("  📊 Creating production logs...")
    log_count = 0
    for eq in equipment_list:
        for day in range(90, 0, -1):
            log_date = datetime.now().date() - timedelta(days=day)
            operating = random.uniform(18, 24) if eq.status == EquipmentStatus.OPERATIONAL.value else random.uniform(0, 10)
            planned = 24
            downtime = max(0, planned - operating)
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
    print(f"    Created {log_count} production logs (90 days x {len(equipment_list)} equipment)")

    print("\n✅ Seed completed successfully!")
    print(f"   Users: {len(users)}")
    print(f"   Equipment: {len(equipment_list)}")
    print(f"   PM Schedules: {len(pm_list)}")
    print(f"   Inspection Templates: {len(template_list)}")
    print(f"   Spare Parts: {len(part_list)}")
    print(f"   Work Orders: {len(wo_list)}")
    print(f"   Completed Inspections: {inspection_count}")
    print(f"   Production Logs: {log_count}")
    print("\n📌 All features now have sufficient test data for charts, KPIs, MTBF, OEE, risk scores, monthly trends.")
    session.close()


def seed_admin():
    seed_all()


if __name__ == "__main__":
    seed_all()