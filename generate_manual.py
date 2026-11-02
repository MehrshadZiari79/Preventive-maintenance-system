# generate_manual.py
"""
Build the user manual PDF (PM_System_Manual.pdf) from docs/manual/manual.html.

The manual is written as an HTML page (Persian, right-to-left, Vazirmatn
font, real screenshots in docs/manual/img).  Setup.iss installs the PDF in
the program's docs folder and on the desktop.

    python generate_manual.py

Uses Microsoft Edge (present on every Windows 10/11 PC) in headless mode, or
Playwright's Chromium if it is installed.  To change the manual, edit
docs/manual/manual.html and run this script again.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "docs" / "manual" / "manual.html"
PDF = ROOT / "PM_System_Manual.pdf"


def _edge() -> str | None:
    candidates = [
        shutil.which("msedge"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        shutil.which("chrome"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def build_with_playwright() -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(HTML.as_uri(), wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        page.pdf(
            path=str(PDF), format="A4", print_background=True,
            display_header_footer=True, header_template="<div></div>",
            footer_template=('<div style="width:100%;font-size:8px;color:#9CA3AF;'
                             'text-align:center;font-family:sans-serif">'
                             '<span class="pageNumber"></span> / <span class="totalPages"></span></div>'),
            margin={"top": "16mm", "bottom": "18mm", "left": "15mm", "right": "15mm"},
        )
        browser.close()
    return True


def build_with_edge() -> bool:
    exe = _edge()
    if not exe:
        return False
    cmd = [exe, "--headless", "--disable-gpu", "--no-pdf-header-footer",
           f"--print-to-pdf={PDF}", HTML.as_uri()]
    return subprocess.run(cmd, capture_output=True).returncode == 0 and PDF.exists()


def main() -> int:
    if not HTML.exists():
        print("docs/manual/manual.html not found")
        return 1
    if build_with_playwright() or build_with_edge():
        print(f"Manual saved: {PDF}")
        return 0
    print("Neither Playwright nor Microsoft Edge / Chrome was found.\n"
          "Open docs/manual/manual.html in Edge and print it to PDF "
          "(A4, background graphics on) as PM_System_Manual.pdf.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
