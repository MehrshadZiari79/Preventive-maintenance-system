import os
import sys

def _setup_dll_search_path():
    if getattr(sys, 'frozen', False):
        # The directory where the executable and all collected DLLs live
        meipass = sys._MEIPASS
        if hasattr(os, 'add_dll_directory'):
            # Windows 8+ allows adding a specific directory
            os.add_dll_directory(meipass)
        else:
            # Fallback: add to PATH
            os.environ['PATH'] = meipass + os.pathsep + os.environ.get('PATH', '')

_setup_dll_search_path()