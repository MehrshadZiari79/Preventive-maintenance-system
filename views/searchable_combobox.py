# views/searchable_combobox.py
import tkinter as tk
from tkinter import ttk

class SearchableCombobox(ttk.Combobox):
    """
    A Combobox that filters its dropdown list as the user types.
    Usage: same as ttk.Combobox, but with extra method `set_completion_list(items)`.
    """
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._full_list = []
        self.bind('<KeyRelease>', self._on_keyrelease)

    def set_completion_list(self, items):
        """Set the full list of items for searching."""
        self._full_list = list(items)
        self['values'] = self._full_list

    def _on_keyrelease(self, event):
        if event.keysym in ('BackSpace', 'Delete', 'Left', 'Right', 'Up', 'Down', 'Tab', 'Return'):
            return
        typed = self.get().lower()
        if typed == '':
            self['values'] = self._full_list
        else:
            filtered = [item for item in self._full_list if typed in item.lower()]
            self['values'] = filtered