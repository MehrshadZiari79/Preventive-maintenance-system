APP_TITLE = "سیستم نگهداری پیشگیرانه"

class Colors:
    PRIMARY    = "#1a237e"
    SECONDARY  = "#1565c0"
    SUCCESS    = "#2e7d32"
    WARNING    = "#f57f17"
    DANGER     = "#c62828"
    LIGHT      = "#f5f5f5"
    WHITE      = "#ffffff"
    TEXT_DARK  = "#212121"
    TEXT_LIGHT = "#757575"
    BORDER     = "#e0e0e0"

class Fonts:
    FAMILY  = "Tahoma"   # best built-in font for Persian on Windows
    TITLE   = ("Tahoma", 18, "bold")
    HEADING = ("Tahoma", 14, "bold")
    NORMAL  = ("Tahoma", 12)
    SMALL   = ("Tahoma", 10)

from enum import Enum

class UserRole(str, Enum):
    ADMIN      = "admin"
    MANAGER    = "manager"
    TECHNICIAN = "technician"

class EquipmentStatus(str, Enum):
    ACTIVE      = "active"
    INACTIVE    = "inactive"
    MAINTENANCE = "maintenance"
    RETIRED     = "retired"

class MaintenanceFrequency(str, Enum):
    DAILY   = "daily"
    WEEKLY  = "weekly"
    MONTHLY = "monthly"
    YEARLY  = "yearly"

class WorkOrderType(str, Enum):
    PREVENTIVE  = "preventive"
    CORRECTIVE  = "corrective"
    INSPECTION  = "inspection"

class WorkOrderStatus(str, Enum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    CANCELLED   = "cancelled"

class InspectionResult(str, Enum):
    PASS    = "pass"
    FAIL    = "fail"
    PARTIAL = "partial"

# Persian labels for enums
ROLE_LABELS = {
    "admin":      "مدیر سیستم",
    "manager":    "مدیر",
    "technician": "تکنسین",
}

EQUIPMENT_STATUS_LABELS = {
    "active":      "فعال",
    "inactive":    "غیرفعال",
    "maintenance": "در تعمیر",
    "retired":     "بازنشسته",
}

WORK_ORDER_STATUS_LABELS = {
    "pending":     "در انتظار",
    "in_progress": "در حال انجام",
    "completed":   "تکمیل شده",
    "cancelled":   "لغو شده",
}

WORK_ORDER_TYPE_LABELS = {
    "preventive": "پیشگیرانه",
    "corrective": "اصلاحی",
    "inspection": "بازرسی",
}

FREQUENCY_LABELS = {
    "daily":   "روزانه",
    "weekly":  "هفتگی",
    "monthly": "ماهانه",
    "yearly":  "سالانه",
}

INSPECTION_RESULT_LABELS = {
    "pass":    "قبول",
    "fail":    "رد",
    "partial": "جزئی",
}
