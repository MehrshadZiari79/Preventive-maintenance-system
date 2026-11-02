# -*- mode: python ; coding: utf-8 -*-
# =============================================================================
#  Gela PM System - PyInstaller Spec
#  Audited for the current application architecture
#
#  Covers:
#    - Tkinter / ttk desktop UI
#    - Native Windows Persian RTL RichEdit patch
#    - Jalali calendar / jdatetime
#    - SQL Server + pymssql + legacy SQLAlchemy stack
#    - openpyxl Excel exports
#    - Pillow logo/image handling
#    - Matplotlib embedded dashboard/report charts
#    - Persian PDF text fallback (arabic-reshaper + python-bidi)
#    - Offline client deployment
#
#  IMPORTANT:
#    runtime_hook.py must call utils.rtl_patch.apply_rtl_patch() BEFORE
#    application views are created.
# =============================================================================

import glob
import os

# Matplotlib is embedded in Tkinter in this application. Force the build-time
# backend to TkAgg so PyInstaller does not auto-select an installed Qt backend
# (for example QtAgg/PyQt5) and pull an unnecessary Qt runtime into the bundle.
os.environ["MPLBACKEND"] = "TkAgg"

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


block_cipher = None

# -----------------------------------------------------------------------------
# Build environment
# -----------------------------------------------------------------------------

CONDA_ROOT = r"C:\ProgramData\anaconda3"
CONDA_BIN = os.path.join(CONDA_ROOT, "Library", "bin")
PIL_DIR = os.path.join(CONDA_ROOT, "Lib", "site-packages", "PIL")


# -----------------------------------------------------------------------------
# Pillow / image runtime DLLs
#
# Pillow extension modules loaded by the application use these DLLs in the
# Anaconda environment. They are placed beside the bootloader so Windows can
# resolve them at runtime.
# -----------------------------------------------------------------------------

REQUIRED_DLLS = [
    "tiff.dll",
    "libjpeg.dll",
    "openjp2.dll",
    "zlib.dll",
    "lcms2.dll",
    "freetype.dll",
    "libwebp.dll",
    "libwebpmux.dll",
    "libwebpdemux.dll",
    "libsharpyuv.dll",
    "libpng16.dll",
    "libtiff.dll",
    "VCRUNTIME140.dll",
]

extra_binaries = []

for dll_name in REQUIRED_DLLS:
    dll_path = os.path.join(CONDA_BIN, dll_name)
    if os.path.exists(dll_path):
        extra_binaries.append((dll_path, "."))
    else:
        print(f"WARNING: required Pillow DLL not found: {dll_path}")


# All Pillow extension modules used by the application -> PIL\
for pyd_path in glob.glob(os.path.join(PIL_DIR, "*.pyd")):
    extra_binaries.append((pyd_path, "PIL"))


# pymssql may carry platform-specific native dependencies. If available in the
# build environment, let PyInstaller's package hook contribute those DLLs.
try:
    extra_binaries.extend(collect_dynamic_libs("pymssql"))
except Exception as exc:
    print(f"WARNING: could not collect pymssql dynamic libraries: {exc}")


# -----------------------------------------------------------------------------
# Data files
# -----------------------------------------------------------------------------

# Matplotlib runtime data (fonts, stylelib, etc.). Do not use collect_all(),
# because it pulls unrelated Jupyter/dev packages into the client build.
mpl_datas = collect_data_files("matplotlib")

# Pillow package data only. Native .pyd files are handled explicitly above.
pil_datas = collect_data_files("PIL")

try:
    tz_datas = collect_data_files("tzdata")
except Exception as exc:
    print(f"WARNING: tzdata not collected ({exc}); Tehran time uses fixed +03:30.")
    tz_datas = []


# The application currently references only image assets under views/.
# Do NOT bundle the entire views source directory as data: PyInstaller already
# packages imported Python modules, and copying the whole source tree creates a
# second copy of .py files inside _internal.
APP_ASSETS = []

# Application version marker used by the runtime updater.
if os.path.exists("version.txt"):
    APP_ASSETS.append(("version.txt", "."))
else:
    print("WARNING: version.txt not found; runtime will fall back to installer metadata.")

for asset_name in (
    "gela-logo.ico",
    "gela-logo.png",
    "gela-logo.gif",
):
    if os.path.exists(asset_name):
        APP_ASSETS.append((asset_name, "."))
    else:
        print(f"WARNING: optional root asset not found: {asset_name}")

for asset_name in (
    "gela-logo.png",
    "gela-logo.gif",
):
    asset_path = os.path.join("views", asset_name)
    if os.path.exists(asset_path):
        APP_ASSETS.append((asset_path, "views"))
    else:
        print(f"WARNING: optional view asset not found: {asset_path}")


# -----------------------------------------------------------------------------
# Analysis
# -----------------------------------------------------------------------------

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=extra_binaries,
    datas=APP_ASSETS + mpl_datas + pil_datas + tz_datas,
    hiddenimports=[
        # =====================================================================
        # Database / ORM
        # =====================================================================
        "pymssql",
        "sqlalchemy",
        "sqlalchemy.dialects.mssql",
        "sqlalchemy.dialects.mssql.pymssql",
        "sqlalchemy.pool",
        "sqlalchemy.orm",
        "sqlalchemy.sql",
        "sqlalchemy.ext",

        # =====================================================================
        # Excel
        # =====================================================================
        "openpyxl",
        "openpyxl.cell._writer",

        # =====================================================================
        # Persian / Jalali date handling
        # =====================================================================
        "jdatetime",
        # Asia/Tehran time zone data for utils.date_helpers (Windows has no
        # system IANA database; falls back to fixed +03:30 if missing).
        "zoneinfo",
        "tzdata",

        # =====================================================================
        # Persian/Arabic PDF fallback text rendering
        #
        # Current services/pdf_service.py first tries Pillow/RAQM and falls
        # back to these modules when RAQM is unavailable on the client.
        # =====================================================================
        "arabic_reshaper",
        "bidi",
        "bidi.algorithm",

        # =====================================================================
        # Native RTL editor used by utils/rtl_patch.py
        # =====================================================================
        "utils.rtl_patch",
        "utils.rtl_text_widget",

        # Shared look (v2.4.7): styled dialogs, table badges, Ctrl+K search
        "views.ux",
        "views.command_palette",

        # Database settings (git-ignored file, must exist on the build PC)
        "database.db_secrets",

        # =====================================================================
        # Matplotlib embedded Tk backend
        # =====================================================================
        # The application uses TkAgg. The spec also forces MPLBACKEND above
        # to prevent PyInstaller from selecting QtAgg merely because PyQt5 is
        # installed in the build environment.
        "numpy",
        "matplotlib",
        "matplotlib.backends",
        "matplotlib.backends.backend_tkagg",
        "matplotlib.backends._backend_tk",
        "matplotlib.figure",
        "matplotlib.pyplot",
        "matplotlib.patches",
        "matplotlib.ticker",
        "matplotlib.dates",

        # =====================================================================
        # Pillow
        # =====================================================================
        "PIL",
        "PIL.Image",
        "PIL.ImageTk",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        "PIL.ImageFilter",
        "PIL.features",
        "PIL._imaging",
        "PIL._imagingcms",
        "PIL._imagingft",
        "PIL._imagingmath",
        "PIL._imagingmorph",
        "PIL._imagingtk",
        "PIL._webp",
        "PIL._tkinter_finder",
        "PIL.JpegImagePlugin",
        "PIL.PngImagePlugin",
        "PIL.GifImagePlugin",
        "PIL.BmpImagePlugin",
        "PIL.TiffImagePlugin",
        "PIL.IcoImagePlugin",
    ],
    hookspath=[],
    runtime_hooks=["runtime_hook.py"],
    excludes=[
        # =====================================================================
        # Notebook / scientific extras not used by the application
        # =====================================================================
        "IPython",
        "jupyter",
        "jupyterlab",
        "notebook",
        "nbconvert",
        "nbformat",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "matplotlib.backends.backend_qt",
        "matplotlib.backends.backend_qtagg",
        "matplotlib.backends.qt_compat",
        "bokeh",
        "panel",
        "altair",
        "plotly",
        "scipy",
        "sklearn",
        "skimage",
        "statsmodels",
        "numba",
        "numexpr",
        "astropy",
        "h5py",
        "tables",
        "pyarrow",
        "dask",
        "distributed",
        "aiohttp",
        "tornado",
        "flask",
        "werkzeug",
        "sphinx",
        "docutils",
        "black",
        "yapf",
        "astroid",
        "jedi",
        "botocore",
        "cryptography",
        "bcrypt",
        "llvmlite",
        "zmq",
        "lmdb",
        "lz4",
        "zstandard",

        # =====================================================================
        # Tests / development-only packages
        # =====================================================================
        "numpy.testing",
        "matplotlib.tests",
        "pytest",
        "unittest",
        "tkinter.test",
        "turtle",

        # =====================================================================
        # Legacy calendar package
        #
        # The application now uses views/jalali_date_entry.py + jdatetime.
        # tkcalendar/Babel are therefore intentionally not forced into the
        # frozen application.
        # =====================================================================
        "tkcalendar",

        # Not used by the application; keep them out of the bundle even when
        # the build environment (Anaconda) has them installed.
        "pandas",
        "sympy",
        "networkx",
        "matplotlib.backends.backend_wx",
        "matplotlib.backends.backend_wxagg",
        "matplotlib.backends.backend_gtk3",
        "matplotlib.backends.backend_gtk3agg",
        "matplotlib.backends.backend_webagg",
        "matplotlib.backends.backend_macosx",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)


# -----------------------------------------------------------------------------
# Python archive
# -----------------------------------------------------------------------------

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)


# -----------------------------------------------------------------------------
# EXE
# -----------------------------------------------------------------------------

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PM_System",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="gela-logo.ico",
)


# -----------------------------------------------------------------------------
# One-folder distribution
# -----------------------------------------------------------------------------

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="PM_System",
)

# PyInstaller 6.x places the supporting files from a COLLECT onedir build
# inside the contents directory (_internal by default). The Inno Setup script
# therefore consumes: dist\PM_System\PM_System.exe + dist\PM_System\_internal\*
