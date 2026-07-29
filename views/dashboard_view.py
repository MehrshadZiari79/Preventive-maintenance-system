# views/dashboard_view.py
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from database.report_repository import ReportRepository
from database.equipment_repository import EquipmentRepository
from database.work_order_repository import WorkOrderRepository
from database.pm_repository import PMRepository
from database.spare_parts_repository import SparePartsRepository
from database.inspection_repository import InspectionRepository
from database.db import SessionLocal
from utils.theme import (
    NAVY, NAVY_LIGHT, WHITE, RED, GRAY_BG, GRAY_BORDER,
    TEXT_DARK, TEXT_LIGHT, SUCCESS, WARNING,
    FONT_TITLE, FONT_HEADING, FONT_SUBHEADING, FONT_NORMAL, FONT_SMALL, FONT_KPI
)

CARD_BG      = "#FFFFFF"
CARD_BORDER  = "#E8ECF0"
SECTION_BG   = "#F4F6F9"
HEADER_H     = 72
ACCENT_TEAL  = "#0D9488"
ACCENT_AMBER = "#D97706"
ACCENT_ROSE  = "#DC2626"
ACCENT_BLUE  = "#1D4ED8"
ACCENT_PURP  = "#7C3AED"
STRIP_H      = 4

STATUS_COLORS = {
    "PENDING":          ("#FEF3C7", "#92400E"),
    "IN_PROGRESS":      ("#DBEAFE", "#1E40AF"),
    "APPROVED":         ("#D1FAE5", "#065F46"),
    "REJECTED":         ("#FEE2E2", "#991B1B"),
    "PENDING_APPROVAL": ("#EDE9FE", "#5B21B6"),
    "FINISH_REQUESTED": ("#FFF7ED", "#C2410C"),
}

STATUS_FA = {
    "PENDING":          "در انتظار",
    "IN_PROGRESS":      "در حال انجام",
    "APPROVED":         "تکمیل شده",
    "PENDING_APPROVAL": "در انتظار تأیید",
    "FINISH_REQUESTED": "درخواست اتمام",
    "REJECTED":         "رد شده",
}


class DashboardView(ttk.Frame):
    def __init__(self, parent, current_user):
        super().__init__(parent)
        self.current_user = current_user
        self.report_repo  = ReportRepository(SessionLocal)
        self.eq_repo      = EquipmentRepository(SessionLocal)
        self.wo_repo      = WorkOrderRepository(SessionLocal)
        self.pm_repo      = PMRepository(SessionLocal)
        self.sp_repo      = SparePartsRepository(SessionLocal)
        self.ins_repo     = InspectionRepository(SessionLocal)

        self._build_ui()
        self._refresh_all()

    def _on_show(self):
        # The outer scroll will handle the region; just refresh data
        self._refresh_all()

    def _build_ui(self):
        self._build_header()
        # Content area – no internal scrollbar, relies on outer MainView
        self.content_frame = tk.Frame(self, bg=SECTION_BG)
        self.content_frame.pack(fill=tk.BOTH, expand=True)

    def _build_header(self):
        hdr = tk.Frame(self, bg=NAVY, height=HEADER_H)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        right = tk.Frame(hdr, bg=NAVY)
        right.pack(side=tk.RIGHT, padx=24, fill=tk.Y)
        tk.Label(right, text="📊", font=("Tahoma", 20), bg=NAVY, fg=WHITE).pack(side=tk.RIGHT, pady=16)
        title_col = tk.Frame(right, bg=NAVY)
        title_col.pack(side=tk.RIGHT, padx=(0, 10), fill=tk.Y)
        tk.Label(title_col, text="داشبورد مدیریت",
                 font=FONT_TITLE, bg=NAVY, fg=WHITE).pack(anchor="e", pady=(14, 0))
        tk.Label(title_col, text="نمای کلی سیستم نگهداری پیشگیرانه",
                 font=FONT_SMALL, bg=NAVY, fg=WHITE).pack(anchor="e")

        left = tk.Frame(hdr, bg=NAVY)
        left.pack(side=tk.LEFT, padx=24, fill=tk.Y)

        self._hdr_time = tk.Label(left, text="", font=FONT_SMALL, bg=NAVY, fg=NAVY_LIGHT)
        self._hdr_time.pack(anchor="w", pady=(18, 0))
        # self._tick_header()  -- kept if needed later

        refresh_btn = tk.Button(
            left, text="🔄  بروزرسانی", font=FONT_SMALL,
            bg=NAVY_LIGHT, fg=WHITE, relief="flat",
            cursor="hand2", padx=14, pady=6,
            command=self._refresh_all
        )
        refresh_btn.pack(anchor="w", pady=(6, 0))

        tk.Frame(self, bg=CARD_BORDER, height=1).pack(fill=tk.X)

    def _refresh_all(self):
        # Clear and rebuild everything inside content_frame
        for w in self.content_frame.winfo_children():
            w.destroy()

        self.kpi_data  = self.report_repo.get_kpi_summary()
        self.backlog   = self.report_repo.get_backlog_analysis()
        self.pm_cm     = self.report_repo.get_pm_cm_ratio()
        self.risk_data = self.report_repo.get_equipment_risk_score()[:5]

        recent_wos   = self.wo_repo.get_all(status_filter=None, type_filter=None)[:5]
        low_stock    = self.sp_repo.get_low_stock()[:5]
        upcoming_pms = self.pm_repo.get_upcoming_pms_dict(days=7)[:5]
        recent_ins   = self.ins_repo.get_all_inspections()[:5]

        self._build_kpi_grid()
        self._build_charts_section()
        self._build_lists_grid(recent_wos, low_stock, upcoming_pms, recent_ins)
        self._build_quick_actions()

    def _section_label(self, parent, text, icon=""):
        row = tk.Frame(parent, bg=SECTION_BG)
        row.pack(fill=tk.X, padx=20, pady=(18, 6))
        tk.Label(row, text=f"{icon}  {text}" if icon else text,
                 font=FONT_HEADING, bg=SECTION_BG, fg=TEXT_DARK).pack(side=tk.RIGHT)
        tk.Frame(row, bg=CARD_BORDER, height=1).pack(side=tk.RIGHT, fill=tk.X,
                                                      expand=True, padx=(0, 12), pady=8)

    def _build_kpi_grid(self):
        self._section_label(self.content_frame, "شاخص‌های کلیدی عملکرد", "📌")
        frame = tk.Frame(self.content_frame, bg=SECTION_BG)
        frame.pack(fill=tk.X, padx=20, pady=(0, 4))

        total    = self.kpi_data['total_work_orders']
        done     = self.kpi_data['completed_work_orders']
        rate     = (done / max(1, total) * 100)
        low_stk  = len(self.sp_repo.get_low_stock())
        overdue  = self.pm_repo.get_overdue_count()
        emerg    = self.kpi_data.get('emergency_work_orders', 0)
        total_eq = self.kpi_data['total_equipment']
        pm_comp  = self.kpi_data['pm_compliance_rate']

        kpis = [
            ("دستورات کار",    total,              ACCENT_BLUE,  "📋", f"مجموع ثبت شده"),
            ("تکمیل شده",      done,               SUCCESS,      "✅", f"{rate:.0f}٪ از کل"),
            ("نرخ تکمیل",      f"{rate:.1f}٪",     SUCCESS,      "📈", "درصد موفقیت"),
            ("انطباق PM",      f"{pm_comp:.1f}٪",  ACCENT_TEAL,  "🎯", "نگهداری پیشگیرانه"),
            ("قطعات کم‌موجود", low_stk,            ACCENT_AMBER, "⚠️", "نیاز به تأمین"),
            ("PM معوق",        overdue,            ACCENT_ROSE,  "🔴", "سررسید گذشته"),
            ("اضطراری",        emerg,              RED,          "🚨", "دستورات فوری"),
            ("کل تجهیزات",     total_eq,           NAVY,         "⚙️", "تجهیزات ثبت شده"),
        ]

        for i, (title, value, color, icon, sub) in enumerate(kpis):
            r, c = divmod(i, 4)
            self._kpi_card(frame, title, value, color, icon, sub, r, c)

        for c in range(4):
            frame.columnconfigure(c, weight=1)

    def _kpi_card(self, parent, title, value, color, icon, subtitle, row, col):
        shadow = tk.Frame(parent, bg=CARD_BORDER)
        shadow.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        card = tk.Frame(shadow, bg=CARD_BG)
        card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        tk.Frame(card, bg=color, height=STRIP_H).pack(fill=tk.X)
        inner = tk.Frame(card, bg=CARD_BG)
        inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        top = tk.Frame(inner, bg=CARD_BG)
        top.pack(fill=tk.X)
        tk.Label(top, text=icon, font=("Tahoma", 16), bg=CARD_BG, fg=color).pack(side=tk.RIGHT)
        tk.Label(top, text=title, font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(side=tk.RIGHT, padx=(0, 6))

        tk.Label(inner, text=str(value), font=FONT_KPI, bg=CARD_BG, fg=color).pack(anchor="center", pady=(6, 2))
        tk.Label(inner, text=subtitle, font=FONT_SMALL, bg=CARD_BG, fg=TEXT_LIGHT).pack(anchor="center")
        tk.Frame(card, bg=SECTION_BG, height=1).pack(fill=tk.X, side=tk.BOTTOM)

    def _build_charts_section(self):
        self._section_label(self.content_frame, "تحلیل بصری", "📊")
        container = tk.Frame(self.content_frame, bg=SECTION_BG)
        container.pack(fill=tk.X, padx=20, pady=(0, 4))

        row1 = tk.Frame(container, bg=SECTION_BG)
        row1.pack(fill=tk.X, pady=(0, 8))
        row1.columnconfigure(0, weight=1)
        row1.columnconfigure(1, weight=1)

        self._chart_card(row1, self._draw_equipment_pie,   "وضعیت تجهیزات",     0)
        self._chart_card(row1, self._draw_pm_cm_bar,       "توزیع دستورکارها",   1)

        if self.risk_data:
            row2 = tk.Frame(container, bg=SECTION_BG)
            row2.pack(fill=tk.X, pady=(0, 8))
            self._risk_table_card(row2)

    def _chart_card(self, parent, draw_fn, title, col):
        shadow = tk.Frame(parent, bg=CARD_BORDER)
        shadow.grid(row=0, column=col, padx=6, pady=0, sticky="nsew")
        card = tk.Frame(shadow, bg=CARD_BG)
        card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        hdr = tk.Frame(card, bg=CARD_BG, pady=10)
        hdr.pack(fill=tk.X, padx=16)
        tk.Label(hdr, text=title, font=FONT_SUBHEADING, bg=CARD_BG, fg=TEXT_DARK).pack(side=tk.RIGHT)
        tk.Frame(card, bg=CARD_BORDER, height=1).pack(fill=tk.X, padx=12)

        chart_frame = tk.Frame(card, bg=CARD_BG)
        chart_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        draw_fn(chart_frame)

    def _draw_equipment_pie(self, parent):
        eq_stats = self.eq_repo.get_stats()
        labels = ['Operational', 'Maintenance', 'Breakdown', 'Inactive']
        sizes  = [eq_stats.get('operational', 0), eq_stats.get('maintenance', 0),
                  eq_stats.get('breakdown', 0),   eq_stats.get('inactive', 0)]
        colors = [SUCCESS, WARNING, RED, TEXT_LIGHT]

        fig = Figure(figsize=(4.5, 3.2), dpi=88, facecolor=CARD_BG)
        ax  = fig.add_subplot(111)
        ax.set_facecolor(CARD_BG)
        if sum(sizes) > 0:
            wedges, texts, autotexts = ax.pie(
                sizes, labels=labels, autopct='%1.1f%%',
                colors=colors, startangle=90,
                wedgeprops=dict(linewidth=1.5, edgecolor='white'),
            )
            for at in autotexts:
                at.set_fontsize(8); at.set_color('white'); at.set_fontweight('bold')
        else:
            ax.text(0.5, 0.5, 'No Data', ha='center', va='center', color=TEXT_LIGHT, fontsize=11)
            ax.set_axis_off()

        fig.tight_layout(pad=0.5)
        cv = FigureCanvasTkAgg(fig, parent)
        cv.draw()
        cv.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _draw_pm_cm_bar(self, parent):
        pm = self.pm_cm.get('preventive_count', 0)
        cm = self.pm_cm.get('corrective_count', 0)
        em = self.pm_cm.get('emergency_count', 0)
        ratio = (pm / cm) if cm > 0 else float(pm)

        fig = Figure(figsize=(4.5, 3.2), dpi=88, facecolor=CARD_BG)
        ax  = fig.add_subplot(111); ax.set_facecolor(CARD_BG)
        bars = ax.bar(['PM', 'CM', 'EM'], [pm, cm, em],
                      color=[ACCENT_TEAL, ACCENT_ROSE, ACCENT_AMBER],
                      width=0.5, edgecolor='white', linewidth=1.5)

        for bar, val in zip(bars, [pm, cm, em]):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1, str(val),
                        ha='center', va='bottom', fontsize=9, fontweight='bold', color=TEXT_DARK)

        ax.set_title(f"PM/CM = {ratio:.2f}", fontsize=9, color=TEXT_LIGHT, pad=4)
        ax.set_ylabel("Count", fontsize=8, color=TEXT_LIGHT)
        ax.tick_params(colors=TEXT_LIGHT, labelsize=8)
        ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(CARD_BORDER); ax.spines['bottom'].set_color(CARD_BORDER)
        ax.yaxis.grid(True, color=CARD_BORDER, linewidth=0.8)
        ax.set_axisbelow(True)

        fig.tight_layout(pad=0.5)
        cv = FigureCanvasTkAgg(fig, parent)
        cv.draw()
        cv.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _risk_table_card(self, parent):
        shadow = tk.Frame(parent, bg=CARD_BORDER)
        shadow.pack(fill=tk.X)
        card = tk.Frame(shadow, bg=CARD_BG)
        card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        hdr = tk.Frame(card, bg=CARD_BG, pady=10)
        hdr.pack(fill=tk.X, padx=16)
        tk.Label(hdr, text="⚠️  تجهیزات پرریسک", font=FONT_SUBHEADING, bg=CARD_BG, fg=TEXT_DARK).pack(side=tk.RIGHT)
        tk.Frame(card, bg=CARD_BORDER, height=1).pack(fill=tk.X, padx=12)

        body = tk.Frame(card, bg=CARD_BG)
        body.pack(fill=tk.X, padx=16, pady=10)

        cols = [("تجهیز", 260, "e"), ("امتیاز ریسک", 100, "center"), ("سطح", 80, "center")]
        for i, (txt, w, anchor) in enumerate(cols):
            tk.Label(body, text=txt, font=FONT_SMALL, bg=CARD_BG,
                     fg=TEXT_LIGHT, width=w // 8, anchor=anchor).grid(
                row=0, column=i, padx=6, pady=(0, 4), sticky="ew")

        for row_i, eq in enumerate(self.risk_data[:5], start=1):
            score = eq.get('risk_score', 0)
            level = eq.get('risk_level', '')
            if score >= 70 or level == "HIGH":
                color, badge_bg = ACCENT_ROSE, "#FEE2E2"; level_fa = "بالا"
            elif score >= 40 or level == "MEDIUM":
                color, badge_bg = ACCENT_AMBER, "#FEF3C7"; level_fa = "متوسط"
            else:
                color, badge_bg = SUCCESS, "#D1FAE5"; level_fa = "پایین"

            bg = CARD_BG if row_i % 2 == 0 else SECTION_BG
            tk.Label(body, text=eq.get('equipment_name', '—'),
                     font=FONT_NORMAL, bg=bg, fg=TEXT_DARK,
                     anchor="e").grid(row=row_i, column=0, padx=6, pady=3, sticky="ew")
            tk.Label(body, text=f"{score:.0f}",
                     font=FONT_NORMAL, bg=bg, fg=color,
                     anchor="center").grid(row=row_i, column=1, padx=6, pady=3)
            badge = tk.Label(body, text=level_fa, font=FONT_SMALL,
                             bg=badge_bg, fg=color, padx=8, pady=2)
            badge.grid(row=row_i, column=2, padx=6, pady=3)

        for c in range(3):
            body.columnconfigure(c, weight=1 if c == 0 else 0)

    def _build_lists_grid(self, recent_wos, low_stock, upcoming_pms, recent_ins):
        self._section_label(self.content_frame, "آخرین رویدادها", "🕒")
        container = tk.Frame(self.content_frame, bg=SECTION_BG)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 4))
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)

        self._list_card(container, "📝  دستورکارهای اخیر",   recent_wos,   self._wo_row,   0, 0)
        self._list_card(container, "⚠️  قطعات کم‌موجود",    low_stock,    self._sp_row,   0, 1)
        self._list_card(container, "📅  برنامه‌های PM نزدیک", upcoming_pms, self._pm_row,   1, 0)
        self._list_card(container, "🔍  بازرسی‌های اخیر",    recent_ins,   self._ins_row,  1, 1)

    def _list_card(self, parent, title, items, row_fn, row, col):
        shadow = tk.Frame(parent, bg=CARD_BORDER)
        shadow.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        card = tk.Frame(shadow, bg=CARD_BG)
        card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        hdr = tk.Frame(card, bg=CARD_BG, pady=10)
        hdr.pack(fill=tk.X, padx=14)
        tk.Label(hdr, text=title, font=FONT_SUBHEADING, bg=CARD_BG, fg=TEXT_DARK).pack(side=tk.RIGHT)
        if items:
            tk.Label(hdr, text=f"{len(items)}", font=FONT_SMALL,
                     bg=NAVY, fg=WHITE, padx=6, pady=1).pack(side=tk.LEFT)
        tk.Frame(card, bg=CARD_BORDER, height=1).pack(fill=tk.X, padx=12)

        body = tk.Frame(card, bg=CARD_BG)
        body.pack(fill=tk.BOTH, expand=True)

        if not items:
            tk.Label(body, text="موردی یافت نشد", font=FONT_SMALL,
                     bg=CARD_BG, fg=TEXT_LIGHT).pack(pady=20)
            return

        for i, item in enumerate(items):
            bg = CARD_BG if i % 2 == 0 else SECTION_BG
            row_widget = tk.Frame(body, bg=bg, cursor="hand2")
            row_widget.pack(fill=tk.X)
            row_fn(row_widget, item, bg)
            tk.Frame(body, bg=CARD_BORDER, height=1).pack(fill=tk.X)

    def _wo_row(self, parent, wo, bg):
        eq_name    = wo.equipment.name if wo.equipment else "—"
        status_key = wo.status.name if hasattr(wo.status, 'name') else str(wo.status)
        status_fa  = STATUS_FA.get(status_key, status_key)
        s_bg, s_fg = STATUS_COLORS.get(status_key, (SECTION_BG, TEXT_DARK))

        tk.Label(parent, text=f"WO#{wo.id}", font=("Tahoma", 9, "bold"),
                 bg=bg, fg=NAVY, width=6, anchor="e").pack(side=tk.RIGHT, padx=(8, 4), pady=8)
        tk.Label(parent, text=eq_name, font=FONT_SMALL,
                 bg=bg, fg=TEXT_DARK).pack(side=tk.RIGHT, padx=4, pady=8)
        badge = tk.Label(parent, text=status_fa, font=("Tahoma", 8),
                         bg=s_bg, fg=s_fg, padx=6, pady=2)
        badge.pack(side=tk.LEFT, padx=8, pady=8)

    def _sp_row(self, parent, part, bg):
        pct = int((part.current_stock / max(1, part.min_stock)) * 100)
        color = ACCENT_ROSE if pct < 50 else ACCENT_AMBER
        tk.Label(parent, text=part.name, font=FONT_SMALL,
                 bg=bg, fg=TEXT_DARK).pack(side=tk.RIGHT, padx=12, pady=8)
        info = tk.Label(parent, text=f"{part.current_stock} / {part.min_stock}",
                        font=("Tahoma", 8, "bold"), bg=bg, fg=color)
        info.pack(side=tk.LEFT, padx=8, pady=8)

    def _pm_row(self, parent, pm, bg):
        eq_name = pm.get("equipment_name", "—")
        # Display the next due date in Gregorian (English) format
        due_dt = pm.get("next_due_dt")
        due_str = due_dt.strftime("%Y-%m-%d") if due_dt else "—"
        title   = pm.get("title", "")

        tk.Label(parent, text=title or eq_name, font=FONT_SMALL,
                 bg=bg, fg=TEXT_DARK).pack(side=tk.RIGHT, padx=12, pady=8)
        tk.Label(parent, text=due_str, font=("Tahoma", 8),
                 bg=bg, fg=ACCENT_AMBER).pack(side=tk.LEFT, padx=8, pady=8)

    def _ins_row(self, parent, ins, bg):
        eq_name = ins.equipment.name if ins.equipment else "—"
        result_map = {"pass": "قبول", "fail": "رد", "partial": "جزئی", None: "در حال انجام"}
        result_fa  = result_map.get(ins.overall_result, "در حال انجام")
        r_color    = SUCCESS if ins.overall_result == "pass" else \
                     ACCENT_ROSE if ins.overall_result == "fail" else ACCENT_AMBER
        tmpl = ins.template.name if ins.template else "—"

        tk.Label(parent, text=tmpl, font=FONT_SMALL,
                 bg=bg, fg=TEXT_DARK).pack(side=tk.RIGHT, padx=12, pady=8)
        tk.Label(parent, text=eq_name, font=("Tahoma", 8),
                 bg=bg, fg=TEXT_LIGHT).pack(side=tk.RIGHT, padx=4, pady=8)
        tk.Label(parent, text=result_fa, font=("Tahoma", 8, "bold"),
                 bg=bg, fg=r_color).pack(side=tk.LEFT, padx=8, pady=8)

    def _build_quick_actions(self):
        self._section_label(self.content_frame, "عملیات سریع", "⚡")
        outer = tk.Frame(self.content_frame, bg=CARD_BORDER)
        outer.pack(fill=tk.X, padx=20, pady=(0, 20))
        card = tk.Frame(outer, bg=CARD_BG)
        card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        btn_frame = tk.Frame(card, bg=CARD_BG)
        btn_frame.pack(padx=20, pady=16)

        actions = [
            ("➕  دستور کار جدید",  ACCENT_BLUE,  self._goto_work_orders),
            ("⚙️  افزودن تجهیز",    NAVY,          self._goto_equipment),
            ("🔧  ورود/خروج قطعه",  ACCENT_TEAL,  self._goto_spare_parts),
            ("📅  برنامه PM جدید",  ACCENT_PURP,  self._goto_pm),
            ("🔍  بازرسی جدید",     ACCENT_AMBER, self._goto_inspections),
        ]
        for i, (text, color, cmd) in enumerate(actions):
            btn = tk.Button(
                btn_frame, text=text, font=FONT_NORMAL,
                bg=color, fg=WHITE, activebackground=NAVY_LIGHT, activeforeground=WHITE,
                relief="flat", cursor="hand2", padx=18, pady=10, command=cmd,
            )
            btn.grid(row=0, column=i, padx=8, pady=4)
            btn.bind("<Enter>", lambda e, b=btn, c=color: b.config(bg=NAVY))
            btn.bind("<Leave>", lambda e, b=btn, c=color: b.config(bg=c))

    def _goto_work_orders(self):  self._navigate("work_orders")
    def _goto_equipment(self):    self._navigate("equipment")
    def _goto_spare_parts(self):  self._navigate("spare_parts")
    def _goto_pm(self):           self._navigate("pm_schedule")
    def _goto_inspections(self):  self._navigate("inspection")   # note: key is "inspection"

    def _navigate(self, view_key):
        root = self.winfo_toplevel()
        if hasattr(root, "_show_view"):
            root._show_view(view_key)