import importlib
import subprocess
import sys

packages = {
    "customtkinter": ("customtkinter", "5.2.2"),
    "sqlalchemy": ("sqlalchemy", "2.0.36"),
    "bcrypt": ("bcrypt", "4.2.1"),
    "apscheduler": ("apscheduler", "3.10.4"),
    "reportlab": ("reportlab", "4.2.5"),
    "openpyxl": ("openpyxl", "3.1.5"),
    "pillow": ("PIL", "11.0.0"),
    "pyinstaller": ("PyInstaller", "6.11.1"),
    "psycopg2-binary": ("psycopg2", "2.9.9"),
    "python-dotenv": ("dotenv", "1.0.1"),
}

def install(package, version):
    pkg_str = f"{package}=={version}"
    print(f"Installing {pkg_str}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg_str])

def get_installed_version(package):
    try:
        from importlib.metadata import version
        return version(package)
    except:
        return None

for pip_name, (import_name, required_version) in packages.items():
    try:
        importlib.import_module(import_name)
        installed_version = get_installed_version(pip_name)

        if installed_version == required_version:
            print(f"{pip_name}=={required_version} ✅ OK")
        else:
            print(f"{pip_name} ⚠️ version mismatch ({installed_version} != {required_version})")
            install(pip_name, required_version)

    except ImportError:
        print(f"{pip_name} ❌ missing")
        install(pip_name, required_version)

print("\nAll packages are ready ✅")