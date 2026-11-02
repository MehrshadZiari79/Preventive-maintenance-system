import os
import sys

# Add project root to path (only needed if you run from outside)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _install_rtl_support():
    """
    Native Windows Persian/BiDi editing (utils/rtl_patch.py).

    MUST run before any view module is imported: it replaces tk.Text with the
    Windows Rich Edit editor, so multi-line boxes such as «شرح درخواست» type
    right-to-left with correct Persian + English ordering
    (e.g. «سلام این یک test است»).

    This is the behaviour of the v2.3 build that staff use. The call was
    accidentally dropped from main.py when the auto-updater was added
    (Oct 7), which made those boxes left-to-right again. It is restored here.

    Troubleshooting only: PM_DISABLE_RTL_PATCH=1 turns it off.
    """
    if os.environ.get("PM_DISABLE_RTL_PATCH") == "1":
        return
    try:
        from utils.rtl_patch import apply_rtl_patch
        apply_rtl_patch()
    except Exception as exc:  # never block start-up because of the patch
        print("RTL patch could not be applied:", exc)


_install_rtl_support()

try:
    # keep fixed-size dialogs inside small / laptop screens
    from utils.screen_fit import install as _install_screen_fit
    _install_screen_fit()
except Exception as _exc:  # never block start-up
    print("screen fit could not be installed:", _exc)

from views.login_view import LoginView                      # noqa: E402
from utils.update_client import (                           # noqa: E402
    run_startup_update_check, start_update_watcher,
)


def _warm_up_imports():
    """
    While the user types the password, load the heavy libraries the first
    page needs (charts, ORM models) in the background, so the dashboard
    opens faster after login.  Import only - no Tk calls - so it is safe off
    the UI thread.  Failures are ignored; the page imports them again.
    """
    for module in (
        "numpy",
        "matplotlib.figure",
        "matplotlib.backends.backend_tkagg",
        "database.models",
        "database.work_order_repository",
        "views.main_view",
        "views.dashboard_view",
    ):
        try:
            __import__(module)
        except Exception:
            pass


def main():
    # Is a newer version on the update share? «در حال بررسی نسخه جدید…» for a
    # few seconds; if one is found, the «در حال به‌روزرسانی» window installs it
    # and re-opens the program (this process exits). Never blocks for long.
    run_startup_update_check()

    # Styled message boxes and success toasts (views/ux.py).  Set
    # PM_CLASSIC_UI=1 to keep the plain Windows boxes.
    try:
        from views.ux import install_dialogs
        install_dialogs()
    except Exception as exc:
        print("ux dialogs:", exc)

    # Do NOT initialize database here - let login screen appear first.
    app = LoginView()

    import threading
    app.after(300, lambda: threading.Thread(target=_warm_up_imports, daemon=True).start())

    # Watches the local status file written by the SYSTEM updater task and
    # shows the 2-minute countdown when a forced update is about to install.
    # It never touches the network or the database on the UI thread.
    start_update_watcher(app)

    app.mainloop()


if __name__ == "__main__":
    main()
