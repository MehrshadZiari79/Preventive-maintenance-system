# utils/update_client.py
"""
App side of the silent updater.

The SYSTEM scheduled task (updater/PMUpdater.ps1) does all the network,
verification and installation work. This module only:

  * polls the LOCAL file  %ProgramData%\\GelaDairy\\PMSystem\\updater\\status\\status.json
    every few seconds (no network, no database, never blocks the UI);
  * when an update is "pending", shows a Persian countdown that cannot be
    dismissed, so the user can finish/save what they are doing;
  * at the deadline (or when the user presses «الان بروزرسانی شود») opens the
    «در حال به‌روزرسانی… لطفاً صبر کنید» window (updater/update_progress.ps1,
    a separate process), closes the application, and that window re-opens it
    when the installation is done;
  * at start-up (run_startup_update_check, before the login window) asks the
    SYSTEM updater to check the share now; a newer version is installed right
    away with the same window;
  * after a successful update shows a short "updated to vX" notice once.

Nothing happens when running from source (only the frozen EXE reacts).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path

POLL_MS = 4000
STALE_PENDING_SECONDS = 60      # a pending deadline this far in the past is leftover, not a countdown
STALE_INSTALLING_SECONDS = 1800 # an "installing" older than this is leftover of an interrupted update
LAUNCH_CHECK_SECONDS = 20       # start-up check: wait this long for the updater to start/answer
LAUNCH_DOWNLOAD_SECONDS = 120   # ... and this long while it is still busy (e.g. downloading)
UPDATER_TASK = r"\GelaPM\PM System Updater"
ERROR_RECHECK_SECONDS = 1800    # look again for an updater error every 30 minutes
STATUS_PATH = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / \
    "GelaDairy" / "PMSystem" / "updater" / "status" / "status.json"
ERROR_PATH = STATUS_PATH.parent / "last_error.json"   # written by PMUpdater.ps1 on failure, removed on success
LAST_RUN_PATH = STATUS_PATH.parent / "last_run.json"  # result of every updater run (PMUpdater.ps1)
_VERSION_RE = re.compile(r"^\d+(?:\.\d+){0,3}$")

_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


# ---------------------------------------------------------------------------
# version helpers
# ---------------------------------------------------------------------------

def _version_tuple(text):
    text = str(text or "").strip().lstrip("vV")
    if not _VERSION_RE.match(text):
        return None
    parts = [int(p) for p in text.split(".")]
    return tuple(parts + [0] * (4 - len(parts)))


def install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def current_version() -> str:
    """Installed version: registry (written by Setup) -> version.txt -> 0."""
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\Gela Dairy Co.\PM System") as key:
                value, _ = winreg.QueryValueEx(key, "Version")
                if _version_tuple(value):
                    return str(value)
        except OSError:
            pass
    for base in (install_dir(), Path(getattr(sys, "_MEIPASS", install_dir()))):
        try:
            value = (base / "version.txt").read_text(encoding="utf-8-sig").split()[0]
            if _version_tuple(value):
                return value
        except (OSError, IndexError):
            continue
    return "0.0.0"


def read_status():
    try:
        with open(STATUS_PATH, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _parse_utc(text):
    if not text:
        return None
    text = str(text).strip()
    m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})?$", text)
    if not m:
        return None
    base = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")
    return base.replace(tzinfo=timezone.utc)


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def active_update(status, current):
    """
    Version (str) of an update that the SYSTEM updater is preparing or
    installing RIGHT NOW for a version newer than `current`; otherwise None.
    Leftovers of an interrupted update (old "pending"/"installing") are ignored.
    """
    if not isinstance(status, dict):
        return None
    state = status.get("state")
    new = _version_tuple(status.get("version"))
    cur = _version_tuple(current) or (0, 0, 0, 0)
    if state not in ("pending", "installing") or not new or new <= cur:
        return None
    now = datetime.now(timezone.utc)
    if state == "pending":
        deadline = _parse_utc(status.get("deadline_utc"))
        if deadline is None or (deadline - now).total_seconds() < -STALE_PENDING_SECONDS:
            return None
    else:
        updated = _parse_utc(status.get("updated_utc"))
        if updated is None or (now - updated).total_seconds() > STALE_INSTALLING_SECONDS:
            return None
    return str(status.get("version"))


# ---------------------------------------------------------------------------
# "updating, please wait" window (separate process: the app must be closed
# while Setup replaces its files)
# ---------------------------------------------------------------------------

def _start_relaunch_helper():
    """Fallback: copy relaunch.cmd to %TEMP% and start it hidden (re-opens the app, no window)."""
    src = install_dir() / "updater" / "relaunch.cmd"
    if not src.is_file():
        return
    try:
        dst = Path(tempfile.gettempdir()) / "gelapm_relaunch.cmd"
        shutil.copyfile(src, dst)
        flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
                 | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        subprocess.Popen(
            [os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"), "/c", str(dst),
             str(Path(sys.executable).resolve())],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags, close_fds=True,
        )
    except Exception as exc:  # the update still happens; only auto-reopen is lost
        print("relaunch helper:", exc)


def _start_update_window(version=""):
    """
    Start updater/update_progress.ps1 as the logged-in user: the «در حال
    به‌روزرسانی… لطفاً صبر کنید» window that follows the installation and
    re-opens PM System when it is done.  The script text is passed with
    -EncodedCommand (no execution-policy problem; Setup may replace the file).
    """
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return
    try:
        import base64
        script = (install_dir() / "updater" / "update_progress.ps1").read_text(encoding="utf-8-sig")
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / \
            "WindowsPowerShell" / "v1.0" / "powershell.exe"
        env = dict(os.environ,
                   GELAPM_APP_EXE=str(Path(sys.executable).resolve()),
                   GELAPM_STATUS=str(STATUS_PATH),
                   GELAPM_VERSION=str(version or ""))
        flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
                 | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        subprocess.Popen(
            [str(powershell), "-NoProfile", "-NonInteractive", "-STA", "-WindowStyle", "Hidden",
             "-EncodedCommand", encoded],
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags, close_fds=True,
        )
    except Exception as exc:
        print("update window:", exc)
        _start_relaunch_helper()


def hand_over_to_updater(version=""):
    """Show the 'updating' window and leave, so Setup can replace the program files."""
    _start_update_window(version)
    os._exit(0)


# ---------------------------------------------------------------------------
# countdown window
# ---------------------------------------------------------------------------

class _CountdownWindow(tk.Toplevel):
    def __init__(self, root, version, deadline, on_now):
        super().__init__(root)
        from utils.theme import NAVY, WHITE, TEXT_DARK, TEXT_MUTED, WARNING_SOFT, FONT_HEADING, FONT_NORMAL, FONT_SMALL
        self.deadline = deadline
        self.title("بروزرسانی سیستم PM")
        self.configure(bg=WHITE)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)   # cannot be dismissed
        try:
            self.attributes("-topmost", True)
            self.attributes("-toolwindow", True)
        except tk.TclError:
            pass

        head = tk.Frame(self, bg=NAVY, padx=20, pady=12)
        head.pack(fill="x")
        tk.Label(head, text="نسخه جدید سیستم PM آماده نصب است", font=FONT_HEADING,
                 bg=NAVY, fg=WHITE).pack(anchor="e")
        tk.Label(head, text=f"نسخه {version}", font=FONT_SMALL, bg=NAVY, fg="#C9D6EA").pack(anchor="e")

        body = tk.Frame(self, bg=WHITE, padx=20, pady=14)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="لطفاً کار در حال انجام را ذخیره کنید.\n"
                            "برنامه پس از پایان زمان زیر بسته، به‌روزرسانی و دوباره باز می‌شود.",
                 font=FONT_NORMAL, bg=WHITE, fg=TEXT_DARK, justify="right").pack(anchor="e")
        self.counter = tk.Label(body, text="", font=("Tahoma", 26, "bold"), bg=WARNING_SOFT,
                                fg="#B45309", padx=20, pady=6)
        self.counter.pack(fill="x", pady=12)
        tk.Label(body, text="به‌روزرسانی حدود یک دقیقه طول می‌کشد و اطلاعات پایگاه داده تغییری نمی‌کند.",
                 font=FONT_SMALL, bg=WHITE, fg=TEXT_MUTED).pack(anchor="e")

        btn = tk.Button(body, text="کارم را ذخیره کردم، الان بروزرسانی شود", command=on_now,
                        font=FONT_NORMAL, bg=NAVY, fg=WHITE, activebackground="#2C3E6B",
                        activeforeground=WHITE, relief="flat", bd=0, padx=14, pady=7, cursor="hand2")
        btn.pack(anchor="w", pady=(12, 0))

        self.update_idletasks()
        w, h = max(440, self.winfo_reqwidth()), self.winfo_reqheight()
        x = (self.winfo_screenwidth() - w) // 2
        y = max(20, (self.winfo_screenheight() - h) // 3)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def set_remaining(self, seconds):
        seconds = max(0, int(seconds))
        self.counter.configure(text=f"{seconds // 60:02d}:{seconds % 60:02d}".translate(_FA))


# ---------------------------------------------------------------------------
# watcher
# ---------------------------------------------------------------------------

class UpdateWatcher:
    def __init__(self, root):
        self.root = root
        self.current = current_version()
        self.window = None
        self.closing = False
        self._after = None

    def start(self):
        self._schedule(1500)
        self._maybe_show_updated_notice()
        self._maybe_warn_update_check()
        self._maybe_warn_update_error()
        self._error_checked_at = time.monotonic()

    def _schedule(self, ms=POLL_MS):
        try:
            self._after = self.root.after(ms, self._poll)
        except tk.TclError:
            pass

    def _poll(self):
        if self.closing:
            return
        try:
            self._check()
        except Exception as exc:
            print("update watcher:", exc)
        if time.monotonic() - getattr(self, "_error_checked_at", 0) > ERROR_RECHECK_SECONDS:
            self._error_checked_at = time.monotonic()
            try:
                self._maybe_warn_update_error()
            except Exception as exc:
                print("update error check:", exc)
        self._schedule(1000 if self.window is not None else POLL_MS)

    def _check(self):
        status = read_status()
        state = (status or {}).get("state")
        new = _version_tuple((status or {}).get("version"))
        cur = _version_tuple(self.current) or (0, 0, 0, 0)

        if state == "installing" and active_update(status, self.current):
            # Setup is already replacing the files (for example the countdown of
            # another user ran out): leave now and show the progress window.
            self._version = str(status.get("version"))
            self._close_now()
            return

        if state != "pending" or not new or new <= cur:
            if self.window is not None:          # update cancelled / finished elsewhere
                self.window.destroy()
                self.window = None
            return

        deadline = _parse_utc(status.get("deadline_utc"))
        if deadline is None:
            return                               # incomplete status: never close the app for it
        remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
        if remaining < -STALE_PENDING_SECONDS:
            # A "pending" left behind by an interrupted update (PC restarted during
            # the countdown). The SYSTEM updater replaces it on its next run; the
            # app must not close itself at every start meanwhile.
            if self.window is not None:
                self.window.destroy()
                self.window = None
            return
        self._version = str(status.get("version"))
        if self.window is None:
            self.window = _CountdownWindow(self.root, status.get("version"), deadline, self._close_now)
        self.window.set_remaining(remaining)
        try:
            self.window.lift()
        except tk.TclError:
            pass
        if remaining <= 0:
            self._close_now()

    def _close_now(self):
        if self.closing:
            return
        self.closing = True
        _start_update_window(getattr(self, "_version", ""))
        try:
            self.root.destroy()
        finally:
            os._exit(0)

    def _maybe_show_updated_notice(self):
        """One-time 'updated to vX' toast for this Windows user."""
        status = read_status() or {}
        if status.get("state") != "done" or status.get("version") is None:
            return
        if _version_tuple(status.get("version")) != _version_tuple(self.current):
            return
        marker_dir = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "GelaDairy" / "PMSystem"
        marker = marker_dir / "last_seen_version.txt"
        try:
            if marker.read_text(encoding="utf-8").strip() == self.current:
                return
        except OSError:
            pass
        try:
            marker_dir.mkdir(parents=True, exist_ok=True)
            marker.write_text(self.current, encoding="utf-8")
        except OSError:
            pass

        def show():
            try:
                from views.ui_kit import Toast
                Toast(self.root, "سیستم PM به‌روزرسانی شد",
                      [f"نسخه فعلی: {self.current}"], tone="success", timeout_ms=8000)
            except Exception:
                pass
        self.root.after(1200, show)


    def _maybe_warn_update_error(self):
        _maybe_warn_update_error_impl(self)

    def _maybe_warn_update_check(self):
        """
        Setup tests the automatic updates after every install and stores the
        result in status/setup_check.txt.  If that test failed, tell the user
        once (per result) so the problem is noticed and reported.
        """
        path = STATUS_PATH.parent / "setup_check.txt"
        try:
            text = path.read_text(encoding="utf-8-sig").strip()
            stamp = str(int(path.stat().st_mtime))
        except OSError:
            return
        if not text.startswith("FAIL|"):
            return
        marker_dir = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "GelaDairy" / "PMSystem"
        marker = marker_dir / "last_update_check_warning.txt"
        try:
            if marker.read_text(encoding="utf-8").strip() == stamp:
                return
        except OSError:
            pass
        try:
            marker_dir.mkdir(parents=True, exist_ok=True)
            marker.write_text(stamp, encoding="utf-8")
        except OSError:
            pass
        # first line "FAIL|<reason>", then one "- [..] ..." line per check
        detail = text.splitlines()[0].split("|", 1)[1].strip()[:180]

        def show():
            try:
                from views.ui_kit import Toast
                Toast(self.root, "به‌روزرسانی خودکار روی این رایانه کار نمی‌کند",
                      ["لطفاً به واحد فناوری اطلاعات اطلاع دهید.", detail],
                      tone="warning", timeout_ms=15000)
            except Exception:
                pass
        self.root.after(2500, show)


def _maybe_warn_update_error_impl(self):
    """
    The SYSTEM updater writes status/last_error.json when its scheduled run
    fails (server off, wrong password, bad installer...). Tell the user about
    it, at most once per day for the same message.
    """
    try:
        with open(ERROR_PATH, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return
    if not isinstance(data, dict):
        return
    msg = str(data.get("message") or "").strip()
    if not msg:
        return
    key = datetime.now().strftime("%Y-%m-%d") + "|" + msg[:200]
    marker_dir = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "GelaDairy" / "PMSystem"
    marker = marker_dir / "last_update_error_warning.txt"
    try:
        if marker.read_text(encoding="utf-8").strip() == key:
            return
    except OSError:
        pass
    try:
        marker_dir.mkdir(parents=True, exist_ok=True)
        marker.write_text(key, encoding="utf-8")
    except OSError:
        pass
    detail = msg[:180]

    def show():
        try:
            from views.ui_kit import Toast
            Toast(self.root, "به‌روزرسانی خودکار انجام نشد",
                  ["لطفاً به واحد فناوری اطلاعات اطلاع دهید.", detail],
                  tone="warning", timeout_ms=15000)
        except Exception:
            pass
    self.root.after(3000, show)


# ---------------------------------------------------------------------------
# start-up check (before the login window): is a newer version on the share?
# ---------------------------------------------------------------------------

def _trigger_updater_task():
    """
    Ask the SYSTEM updater task to run now.  Setup allows every signed-in user
    to START this task (not to change it); it then checks the share as SYSTEM.
    """
    try:
        r = subprocess.run(["schtasks.exe", "/Run", "/TN", UPDATER_TASK],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=20)
        return r.returncode == 0
    except Exception:
        return False


def _as_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class _StartupCheck:
    """
    «در حال بررسی نسخه جدید…» window.  Starts the updater task in the
    background and watches its files:
      * status.json says a newer version is being prepared/installed -> found;
      * last_run.json shows a run that finished after start-up      -> nothing new;
      * no answer within LAUNCH_CHECK_SECONDS (or LAUNCH_DOWNLOAD_SECONDS while
        the updater is busy), or the user presses «ادامه» -> start normally.
    """

    def __init__(self, current, trigger=_trigger_updater_task):
        from tkinter import ttk
        from utils.theme import NAVY, WHITE, TEXT_DARK, TEXT_MUTED, FONT_HEADING, FONT_NORMAL, FONT_SMALL
        self.current = current
        self.trigger = trigger
        self.t0 = time.time()
        self.triggered = None            # None while starting the task, then True / False
        self.found = None                # newer version being installed
        self.done = False

        root = self.root = tk.Tk()
        root.title("سیستم PM")
        root.configure(bg=WHITE)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self._finish)
        try:
            icon = install_dir() / "_internal" / "gela-logo.ico"
            if icon.is_file():
                root.iconbitmap(str(icon))
        except tk.TclError:
            pass

        head = tk.Frame(root, bg=NAVY, padx=18, pady=10)
        head.pack(fill="x")
        tk.Label(head, text="سیستم نگهداری و تعمیرات (PM)", font=FONT_HEADING,
                 bg=NAVY, fg=WHITE).pack(anchor="e")
        body = tk.Frame(root, bg=WHITE, padx=18, pady=14)
        body.pack(fill="both", expand=True)
        self.label = tk.Label(body, text="در حال بررسی نسخه جدید…", font=FONT_NORMAL,
                              bg=WHITE, fg=TEXT_DARK, justify="right", wraplength=380)
        self.label.pack(anchor="e")
        self.bar = ttk.Progressbar(body, mode="indeterminate", length=340)
        self.bar.pack(fill="x", pady=(10, 6))
        self.bar.start(12)
        self.hint = tk.Label(body, text="لطفاً چند لحظه صبر کنید.", font=FONT_SMALL,
                             bg=WHITE, fg=TEXT_MUTED, justify="right", wraplength=380)
        self.hint.pack(anchor="e")
        self.skip = tk.Button(body, text="ادامه بدون انتظار", command=self._finish,
                              font=FONT_SMALL, bg="#E5E7EB", fg=TEXT_DARK, relief="flat",
                              padx=12, pady=3, cursor="hand2")

        self._fit(extra=34)

    def _fit(self, extra=0):
        """Size the window to its (wrapped) text and keep it centred."""
        root = self.root
        root.update_idletasks()
        w, h = max(440, root.winfo_reqwidth()), root.winfo_reqheight() + extra
        x = (root.winfo_screenwidth() - w) // 2
        y = max(20, (root.winfo_screenheight() - h) // 3)
        root.geometry(f"{w}x{h}+{x}+{y}")

    def run(self):
        """Blocks until the check is over; returns the version to install, or None."""
        import threading
        threading.Thread(target=self._start_task, daemon=True).start()
        self.root.after(300, self._poll)
        self.root.after(6000, self._show_skip)
        self.root.mainloop()
        return self.found

    def _start_task(self):
        ok = False
        try:
            ok = bool(self.trigger())
        finally:
            self.triggered = ok

    def _show_skip(self):
        if not self.done and self.found is None:
            try:
                self.skip.pack(anchor="w", pady=(10, 0))
                self._fit()
            except tk.TclError:
                pass

    def _poll(self):
        if self.done:
            return
        version = active_update(read_status(), self.current)
        if version:
            self._on_found(version)
            return
        if self.triggered is False:
            self._finish()               # this PC cannot start the updater (older installation)
            return
        run = _read_json(LAST_RUN_PATH) or {}
        started, finished = _as_int(run.get("started_unix")), _as_int(run.get("finished_unix"))
        if self.triggered and finished >= int(self.t0) - 1:
            self._finish()               # a run finished after start-up: nothing new to install
            return
        now = time.time()
        busy = bool(started) and not finished and now - started < 600
        elapsed = now - self.t0
        if busy and elapsed > 8:
            self.hint.configure(text="اگر نسخه جدیدی باشد، دریافت آن چند لحظه طول می‌کشد.")
        if elapsed > (LAUNCH_DOWNLOAD_SECONDS if busy else LAUNCH_CHECK_SECONDS):
            self._finish()
            return
        self.root.after(400, self._poll)

    def _on_found(self, version):
        self.found = version
        self.label.configure(text=f"نسخه جدید {str(version).translate(_FA)} پیدا شد.\n"
                                  "سیستم PM برای نصب آن بسته می‌شود؛ لطفاً صبر کنید…")
        self.hint.configure(text="پس از پایان به‌روزرسانی، برنامه خودکار باز می‌شود.")
        try:
            self.skip.pack_forget()
            self._fit()
        except tk.TclError:
            pass
        self.root.after(1500, self._finish)

    def _finish(self):
        if self.done:
            return
        self.done = True
        try:
            self.bar.stop()
            self.root.destroy()
        except tk.TclError:
            pass


def run_startup_update_check():
    """
    Called by main.py BEFORE the login window.  Asks the SYSTEM updater to
    check the update share now.  If a newer version is found, or is being
    installed already, the «در حال به‌روزرسانی… لطفاً صبر کنید» window takes
    over and this process exits; otherwise it returns and PM System starts.
    Skipped right after an update (--after-update) and when run from source.
    """
    if os.name != "nt":
        return
    if not getattr(sys, "frozen", False) and os.environ.get("PM_UPDATE_WATCHER_DEV") != "1":
        return
    if "--after-update" in sys.argv[1:]:
        return
    version = None
    try:
        current = current_version()
        version = active_update(read_status(), current) or _StartupCheck(current).run()
    except Exception as exc:          # never block start-up because of the check
        print("start-up update check:", exc)
        return
    if version:
        hand_over_to_updater(version)


def start_update_watcher(root):
    """Attach the watcher to a Tk root (login window, then main window)."""
    if not getattr(sys, "frozen", False) and os.environ.get("PM_UPDATE_WATCHER_DEV") != "1":
        return None
    if getattr(root, "_gela_update_watcher", None):
        return root._gela_update_watcher
    watcher = UpdateWatcher(root)
    root._gela_update_watcher = watcher
    watcher.start()
    return watcher
