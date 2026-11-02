# -*- coding: utf-8 -*-
"""
PM System - Shared Personnel Selection Dialog
==============================================

A single, reusable multi-select Personnel picker used by:
    - Repair Request completion editing
    - Work Order completion editing

Important workflow rule:
    This dialog is ONLY opened from an edit/finish workflow.
    It is not used for creating a new Repair Request or Work Order.

Search scope:
    All Personnel across all Departments.

Search fields:
    - Personnel code
    - Full name
    - Department name

The dialog keeps selected Personnel IDs even while the visible list is
filtered, so filtering never silently removes a previously selected person.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from utils.theme import (
    NAVY,
    NAVY_LIGHT,
    WHITE,
    GRAY_BG,
    GRAY_BORDER,
    TEXT_DARK,
    TEXT_LIGHT,
    SUCCESS,
    FONT_TITLE,
    FONT_NORMAL,
    FONT_SMALL,
)


BG = GRAY_BG
PRIMARY = NAVY
PRIMARY_LIGHT = NAVY_LIGHT
TEXT = TEXT_DARK
BORDER = GRAY_BORDER


class PersonnelSelectionDialog(tk.Toplevel):
    """
    Modal multi-select Personnel dialog.

    Parameters
    ----------
    parent:
        Parent Tk widget.
    personnel:
        Iterable of Personnel ORM objects. Department must already be eager
        loaded or safely accessible on the object.
    selected_ids:
        Existing Personnel IDs to preselect.
    title:
        Window title.
    """

    def __init__(
        self,
        parent,
        personnel=None,
        selected_ids=None,
        title="انتخاب پرسنل انجام‌دهنده",
    ):
        super().__init__(parent)

        self.parent = parent
        self.result = None
        self._accepted = False

        self.title(title)
        self.configure(bg=BG)
        self.geometry("760x680")
        self.minsize(620, 520)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self.search_var = tk.StringVar()
        self.selected_ids = {
            int(value)
            for value in (selected_ids or [])
            if self._safe_int(value) is not None and self._safe_int(value) > 0
        }

        self._records = []
        self._record_by_id = {}
        self._visible_ids = []
        self._rendering = False

        self._prepare_personnel(personnel or [])
        self._build_ui()
        self._render()
        self._center()

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _event: self._cancel())
        self.bind("<Control-Return>", lambda _event: self._accept())
        self.after_idle(self._focus_search)

    @staticmethod
    def _safe_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _text(value):
        return str(value or "").strip()

    def _prepare_personnel(self, personnel):
        records = []
        seen_ids = set()

        for person in personnel:
            pid = self._safe_int(getattr(person, "id", None))
            if pid is None or pid <= 0 or pid in seen_ids:
                continue

            code = self._text(getattr(person, "personnel_code", ""))
            name = self._text(getattr(person, "full_name", ""))
            department = getattr(person, "department", None)
            department_name = self._text(getattr(department, "name", ""))

            if not name and not code:
                continue

            display = " - ".join(
                value
                for value in (code, name, department_name)
                if value
            )

            search_text = " ".join(
                value
                for value in (code, name, department_name)
                if value
            ).casefold()

            record = {
                "id": pid,
                "code": code,
                "name": name,
                "department": department_name,
                "display": display,
                "search_text": search_text,
            }

            records.append(record)
            self._record_by_id[pid] = record
            seen_ids.add(pid)

        records.sort(
            key=lambda item: (
                item["name"].casefold(),
                item["code"].casefold(),
                item["department"].casefold(),
            )
        )
        self._records = records

    def _build_ui(self):
        header = tk.Frame(self, bg=PRIMARY, height=70)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="👥  انتخاب پرسنل انجام‌دهنده",
            font=FONT_TITLE,
            bg=PRIMARY,
            fg=WHITE,
            anchor="e",
        ).pack(fill="both", expand=True, padx=20)

        tk.Label(
            self,
            text="جستجو در تمام پرسنل و تمام دپارتمان‌ها بر اساس کد، نام یا واحد",
            font=FONT_SMALL,
            bg=BG,
            fg=TEXT_LIGHT,
            anchor="e",
        ).pack(fill="x", padx=20, pady=(12, 6))

        search_frame = tk.Frame(self, bg=WHITE, bd=1, relief="solid")
        search_frame.pack(fill="x", padx=20, pady=(0, 10))
        search_frame.grid_columnconfigure(0, weight=1)

        self.search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            justify="right",
            font=FONT_NORMAL,
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=10, pady=10, ipady=4)

        tk.Label(
            search_frame,
            text="جستجوی پرسنل:",
            font=FONT_SMALL,
            bg=WHITE,
            fg=TEXT,
        ).grid(row=0, column=1, padx=(6, 10))

        self.search_var.trace_add("write", self._on_search_changed)

        list_frame = tk.Frame(self, bg=WHITE, bd=1, relief="solid")
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.listbox = tk.Listbox(
            list_frame,
            selectmode=tk.EXTENDED,
            exportselection=False,
            height=16,
            font=FONT_NORMAL,
            justify="right",
            bg=WHITE,
            fg=TEXT,
            selectbackground=PRIMARY_LIGHT,
            selectforeground=WHITE,
            relief="flat",
            bd=0,
            activestyle="none",
        )
        self.listbox.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.listbox.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.bind("<<ListboxSelect>>", self._on_selection_changed)
        self.listbox.bind("<Double-1>", lambda _event: self._accept())

        controls = tk.Frame(self, bg=BG)
        controls.pack(fill="x", padx=20, pady=(0, 10))

        tk.Button(
            controls,
            text="انتخاب همه موارد نمایان",
            command=self._select_all_visible,
            bg=WHITE,
            fg=TEXT,
            relief="solid",
            bd=1,
            cursor="hand2",
            font=FONT_SMALL,
            padx=12,
            pady=5,
        ).pack(side="right", padx=3)

        tk.Button(
            controls,
            text="لغو انتخاب موارد نمایان",
            command=self._clear_visible,
            bg=WHITE,
            fg=TEXT,
            relief="solid",
            bd=1,
            cursor="hand2",
            font=FONT_SMALL,
            padx=12,
            pady=5,
        ).pack(side="right", padx=3)

        self.count_label = tk.Label(
            controls,
            text="انتخاب‌شده: ۰",
            font=FONT_SMALL,
            bg=BG,
            fg=TEXT_LIGHT,
        )
        self.count_label.pack(side="left", padx=6)

        footer = tk.Frame(
            self,
            bg=WHITE,
            height=72,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        tk.Button(
            footer,
            text="انصراف",
            command=self._cancel,
            bg=BG,
            fg=TEXT,
            relief="solid",
            bd=1,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=22,
            pady=8,
        ).pack(side="left", padx=14, pady=12)

        tk.Button(
            footer,
            text="✅ تأیید انتخاب",
            command=self._accept,
            bg=SUCCESS,
            fg=WHITE,
            activebackground=SUCCESS,
            activeforeground=WHITE,
            relief="flat",
            bd=0,
            cursor="hand2",
            font=FONT_NORMAL,
            padx=24,
            pady=8,
        ).pack(side="right", padx=14, pady=12)

    def _focus_search(self):
        try:
            self.search_entry.focus_set()
        except Exception:
            pass

    def _center(self):
        try:
            self.update_idletasks()
            width = min(self.winfo_width(), self.winfo_screenwidth() - 80)
            height = min(self.winfo_height(), self.winfo_screenheight() - 90)
            x = max(10, (self.winfo_screenwidth() - width) // 2)
            y = max(10, (self.winfo_screenheight() - height) // 2)
            self.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass

    def _filtered_records(self):
        query = self._text(self.search_var.get()).casefold()
        if not query:
            return list(self._records)

        parts = [part for part in query.split() if part]
        return [
            record
            for record in self._records
            if all(part in record["search_text"] for part in parts)
        ]

    def _on_search_changed(self, *_args):
        try:
            self.after_idle(self._render)
        except Exception:
            self._render()

    def _render(self):
        if self._rendering or not hasattr(self, "listbox"):
            return

        self._rendering = True
        try:
            records = self._filtered_records()
            self._visible_ids = [record["id"] for record in records]

            self.listbox.delete(0, tk.END)

            for record in records:
                index = self.listbox.size()
                self.listbox.insert(tk.END, record["display"])
                if record["id"] in self.selected_ids:
                    self.listbox.selection_set(index)

            self._update_count()
        finally:
            self._rendering = False

    def _on_selection_changed(self, _event=None):
        if self._rendering:
            return

        try:
            selected_indices = set(self.listbox.curselection())
            visible_set = set(self._visible_ids)

            # Only mutate selections for currently visible Personnel.
            self.selected_ids.difference_update(visible_set)

            for index in selected_indices:
                if 0 <= index < len(self._visible_ids):
                    self.selected_ids.add(self._visible_ids[index])

            self._update_count()
        except Exception:
            pass

    def _select_all_visible(self):
        for pid in self._visible_ids:
            self.selected_ids.add(int(pid))
        self._render()

    def _clear_visible(self):
        for pid in self._visible_ids:
            self.selected_ids.discard(int(pid))
        self._render()

    def _update_count(self):
        try:
            self.count_label.config(
                text=f"انتخاب‌شده: {len(self.selected_ids):,}"
            )
        except Exception:
            pass

    def _accept(self):
        if not self.selected_ids:
            messagebox.showwarning(
                "انتخاب پرسنل",
                "حداقل یک پرسنل انجام‌دهنده را انتخاب کنید.",
                parent=self,
            )
            return

        self.result = sorted(int(pid) for pid in self.selected_ids)
        self._accepted = True
        self.destroy()

    def _cancel(self):
        self.result = None
        self._accepted = False
        self.destroy()
