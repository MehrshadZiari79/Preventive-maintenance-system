"""
Gela PM System - one-command release
====================================

Run on the build PC after changing the code:

    release.bat                       (double-click)
    release.bat "توضیح تغییرات"        (optional release notes)

What it does
------------
1. Pre-flight: Python packages, Inno Setup and the update share are checked
   BEFORE anything is changed.
2. Version: the highest of version.txt and the version already on the share,
   plus one in the 4th number (2.4.6.1 -> 2.4.6.2; 2.4.6 -> 2.4.6.1).
   To start a new series, write it in version.txt (e.g. 2.4.7): the next
   release is then 2.4.7.1.
3. Builds the application (PyInstaller) and the installer (Inno Setup).
4. Publishes the installer to the update share (copy, SHA-256 check of the
   copy, manifest written last). Every client installs it within ~15 minutes.
5. Keeps only the newest 2 installers (this release + the previous one) on the
   update share AND in installer_output on this PC; older ones are deleted.

If any step before publishing fails, version.txt is restored and nothing is
published.  Full output of each run is saved in release_logs\\.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------- settings
ROOT = Path(__file__).resolve().parent
UPDATE_SHARE = os.environ.get("PM_UPDATE_SHARE", r"\\192.168.0.1\PM_System_Updates")
ISCC_CANDIDATES = [
    os.environ.get("PM_ISCC", ""),
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]
KEEP_INSTALLERS = 2          # the current release + the one before it (~170 MB each)

sys.path.insert(0, str(ROOT))
from publish_update import (  # noqa: E402
    MANIFEST_NAME, normalize_version, publish, version_tuple,
)

LOG_DIR = ROOT / "release_logs"
_log_file = None


def say(text=""):
    print(text, flush=True)
    if _log_file:
        _log_file.write(text + "\n")
        _log_file.flush()


def fail(text):
    say("")
    say("ERROR: " + text)
    say("Nothing was published.")
    return 1


def run(cmd, title, secret=None):
    say(f"\n--- {title} ---")
    shown = " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd)
    if secret:
        shown = shown.replace(secret, "********")
    say("> " + shown)
    proc = subprocess.Popen(
        [str(c) for c in cmd], cwd=str(ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )
    for line in proc.stdout:
        if _log_file:
            _log_file.write(line)
        # keep the console readable: only warnings/errors and the last lines
        low = line.lower()
        if "error" in low or "successful" in low or "completed successfully" in low:
            print("  " + line.rstrip(), flush=True)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"{title} failed (exit {proc.returncode}). See {_log_file.name if _log_file else 'log'}.")


ACCOUNT_FILE = ROOT / "updater_account.local"
DEFAULT_SHARE_USER = r"GELAAMOL\pm_update_reader"


def updater_account():
    """
    The read-only update-share account that is built into the installer, so
    nobody types anything on the client PCs.  Kept only in
    updater_account.local on this PC (git-ignored), asked once.
    """
    if ACCOUNT_FILE.exists():
        lines = ACCOUNT_FILE.read_text(encoding="utf-8").splitlines()
        if len(lines) >= 2 and lines[0].strip() and lines[1]:
            return lines[0].strip(), lines[1]
    import getpass
    print("\nThe installer needs the update-share account (asked only once).")
    print("  (just press Enter for the user name)")
    user = input(f"  User name [{DEFAULT_SHARE_USER}]: ").strip() or DEFAULT_SHARE_USER
    if "\\" not in user:
        raise RuntimeError(f"'{user}' is not a user name like GELAAMOL\\pm_update_reader. Run release.bat again.")
    password = getpass.getpass(f"  Password of {user}: ")
    if not password:
        raise RuntimeError("The update-share password is required.")
    if getpass.getpass("  Type the password again: ") != password:
        raise RuntimeError("The two passwords are different. Run release.bat again.")
    ACCOUNT_FILE.write_text(user + "\n" + password + "\n", encoding="utf-8")
    say(f"  saved in {ACCOUNT_FILE.name} (only on this PC)")
    return user, password


def bump_build(version):
    """Raise only the 4th number: 2.4.6.1 -> 2.4.6.2, 2.4.6 -> 2.4.6.1, 2.4.6.9 -> 2.4.6.10."""
    parts = [int(p) for p in normalize_version(version).split(".")]
    while len(parts) < 4:
        parts.append(0)
    parts[3] += 1
    return ".".join(str(p) for p in parts)


def share_version(share: Path):
    manifest = share / MANIFEST_NAME
    if not manifest.exists():
        return None
    try:
        return normalize_version(str(json.loads(manifest.read_text(encoding="utf-8-sig")).get("version", "")))
    except Exception:
        return None


def _share_ok(share: Path) -> bool:
    """True if the share can be opened; Windows errors (1326 etc.) count as 'no'."""
    try:
        return share.exists()
    except OSError:
        return False


def _net(*args):
    """Run net.exe with a clean argument list (no shell); returns (code, text)."""
    proc = subprocess.run(["net", "use", *args], capture_output=True, text=True,
                          errors="replace")
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def connect_publish_share(share: Path):
    """
    Publishing needs an account with WRITE rights on the share. The Windows
    account this PC is logged in with may not have them (or the server
    rejects its saved password), so when the share cannot be opened the
    publisher's own account is asked for and used for this run only.
    Returns True when a connection was made (then it is removed at exit).
    """
    if _share_ok(share):
        return False
    import atexit
    import getpass
    server = "\\\\" + str(share).lstrip("\\").split("\\")[0]
    say("\n  The update share cannot be opened with this Windows account.")
    user = os.environ.get("PM_PUBLISH_USER", "").strip() or input(
        "  Publisher account with WRITE access (e.g. GELAAMOL\\your_name): ").strip()
    if "\\" not in user:
        raise RuntimeError(f"'{user}' is not a user name like GELAAMOL\\your_name.")
    password = getpass.getpass(f"  Password of {user}: ")
    if not password:
        raise RuntimeError("The publisher password is required.")
    # drop stale connections to this server (error 1219 otherwise)
    _net(server + "\\IPC$", "/delete", "/y")
    _net(str(share), "/delete", "/y")
    code, text = _net(str(share), password, f"/user:{user}", "/persistent:no")
    if code != 0:
        raise RuntimeError(f"Cannot log in to {share} as {user}: {text}")
    atexit.register(_net, str(share), "/delete", "/y")
    say(f"  connected to {share} as {user}")
    return True


def preflight(share: Path):
    say("--- Pre-flight checks ---")
    for module in ("PyInstaller", "sqlalchemy", "jdatetime", "pymssql"):
        try:
            __import__(module)
        except Exception:
            raise RuntimeError(f"Python package '{module}' is missing in {sys.executable}")
    say("  Python packages ......... OK")

    iscc = next((p for p in ISCC_CANDIDATES if p and Path(p).is_file()), None)
    if not iscc:
        raise RuntimeError("Inno Setup (ISCC.exe) not found. Install Inno Setup 6 or set PM_ISCC.")
    say(f"  Inno Setup .............. {iscc}")

    if not _share_ok(share):
        raise RuntimeError(f"Update share not reachable: {share}")
    try:
        fd, probe = tempfile.mkstemp(prefix="write_test_", dir=str(share))
        os.close(fd)
        os.remove(probe)
    except OSError as exc:
        raise RuntimeError(f"No write permission on {share}: {exc}")
    say(f"  Update share ............ {share} (writable)")
    for name in ("PM_System.spec", "Setup.iss", "version.txt", "main.py"):
        if not (ROOT / name).exists():
            raise RuntimeError(f"{name} not found in {ROOT}")
    # The database settings are kept out of the source code (and GitHub);
    # without this file the program would be built with no database.
    if not (ROOT / "database" / "db_secrets.py").exists():
        raise RuntimeError("database\\db_secrets.py is missing. Copy database\\db_secrets.example.py "
                           "to db_secrets.py and fill in the database settings.")
    say("  Database settings ....... database\\db_secrets.py")
    return iscc


_INSTALLER_RE = re.compile(r"^PM_System_Setup_v(\d+(?:\.\d+){0,3})\.exe$", re.IGNORECASE)


def _installer_version(path: Path):
    """Version tuple from 'PM_System_Setup_v2.4.6.2.exe', or None for other files."""
    match = _INSTALLER_RE.match(path.name)
    if not match:
        return None
    try:
        return version_tuple(match.group(1))
    except ValueError:
        return None


def cleanup_installers(folder: Path, current_installer: str, where: str):
    """
    Keep only the newest KEEP_INSTALLERS installers in `folder`: the one just
    published and the newest older one (a PC that is still downloading the
    previous release can finish).  Older ones are deleted, by VERSION (not by
    file date), together with leftovers of interrupted copies (*.partial).
    Never deletes the current installer or anything newer than it.
    """
    if not folder.is_dir():
        return
    current = _installer_version(Path(current_installer))
    freed = 0
    removed = []

    for leftover in folder.glob("PM_System_Setup_v*.exe.partial"):
        try:
            size = leftover.stat().st_size
            leftover.unlink()
            freed += size
            removed.append(leftover.name)
        except OSError as exc:
            say(f"  {where}: could not remove {leftover.name}: {exc}")

    older = []
    for path in folder.glob("PM_System_Setup_v*.exe"):
        version = _installer_version(path)
        if version is None or path.name.lower() == current_installer.lower():
            continue
        if current is not None and version >= current:
            continue                      # never touch the current or a newer one
        older.append((version, path))
    older.sort(key=lambda item: item[0], reverse=True)

    for _version, path in older[KEEP_INSTALLERS - 1:]:
        try:
            size = path.stat().st_size
            path.unlink()
            freed += size
            removed.append(path.name)
        except OSError as exc:
            say(f"  {where}: could not remove {path.name}: {exc}")

    for name in removed:
        say(f"  {where}: removed {name}")
    kept = [current_installer] + [p.name for _v, p in older[:KEEP_INSTALLERS - 1]]
    say(f"  {where}: keeping {', '.join(kept)}"
        + (f"  (freed {freed / 1024 / 1024:,.0f} MB)" if freed else ""))


def main():
    global _log_file
    notes = " ".join(sys.argv[1:]).strip()
    LOG_DIR.mkdir(exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    _log_file = open(LOG_DIR / f"release_{stamp}.log", "w", encoding="utf-8")

    share = Path(UPDATE_SHARE)
    say("=" * 60)
    say(" PM System - release")
    say("=" * 60)
    try:
        connect_publish_share(share)
        iscc = preflight(share)
        share_user, share_pass = updater_account()
    except Exception as exc:
        return fail(str(exc))

    version_file = ROOT / "version.txt"
    old_text = version_file.read_text(encoding="utf-8-sig")
    try:
        local = normalize_version(old_text.split()[0])
    except (ValueError, IndexError):
        return fail("version.txt does not contain a valid version.")
    on_share = share_version(share)
    base = local
    if on_share and version_tuple(on_share) > version_tuple(local):
        base = on_share
    new_version = bump_build(base)
    say(f"\n  version.txt {local}   share {on_share or '-'}   ->   new version {new_version}")

    version_file.write_text(new_version + "\r\n", encoding="utf-8")
    try:
        run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "PM_System.spec"], "PyInstaller")
        if not (ROOT / "dist" / "PM_System" / "PM_System.exe").exists():
            raise RuntimeError("PyInstaller finished but dist\\PM_System\\PM_System.exe is missing.")
        run([iscc, f"/DAppVersion={new_version}", f"/DShareUser={share_user}",
             f"/DSharePass={share_pass}", "Setup.iss"], "Inno Setup", secret=share_pass)
        installer = ROOT / "installer_output" / f"PM_System_Setup_v{new_version}.exe"
        if not installer.exists():
            raise RuntimeError(f"Installer not found: {installer}")
    except Exception as exc:
        version_file.write_text(old_text, encoding="utf-8")
        say(f"\n  version.txt restored to {local}")
        return fail(str(exc))

    say("\n--- Publishing ---")
    try:
        publish(installer, new_version, share, notes)
    except Exception as exc:
        say("  The build is kept in installer_output; version.txt stays at " + new_version)
        return fail(f"publishing failed: {exc}")
    say("\n--- Cleaning up old installers ---")
    cleanup_installers(share, installer.name, "update share")
    cleanup_installers(installer.parent, installer.name, "build PC")

    say("")
    say("=" * 60)
    say(f" Released {new_version}. Clients update within about 15 minutes.")
    say("=" * 60)
    return 0


if __name__ == "__main__":
    code = main()
    if _log_file:
        _log_file.close()
    sys.exit(code)
