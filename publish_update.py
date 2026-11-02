"""
Gela PM System - Update Publisher (run on the build PC only)

Usage:
    python publish_update.py "installer_output\\PM_System_Setup_v2.4.0.exe" 2.4.0 "\\\\192.168.0.1\\PM_System_Updates" [--notes "..."] [--force]

What it does, in this order (clients never see a half-published release):
  1. checks the version: matches version.txt and the installer file name, and
     is newer than the version already published on the share;
  2. copies the installer to the share and verifies the SHA-256 of the copy;
  3. writes pm_system_update.json last (atomic replace).

Every client's SYSTEM updater task picks the release up within ~15 minutes and
installs it silently (2-minute countdown if PM System is open).

Note: the old v2.3 in-app updater read "update.json". That file is NOT written
any more, so v2.3 clients do not show a UAC prompt that standard users cannot
approve; install v2.4 once on each PC as an administrator (see DEPLOY_UPDATES.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path


APP_NAME = "PM System"
MANIFEST_NAME = "pm_system_update.json"


def normalize_version(value: str) -> str:
    text = value.strip().lstrip("vV").strip()
    parts = text.split(".")
    if not 1 <= len(parts) <= 4 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid version: {value!r}")
    while len(parts) < 3:
        parts.append("0")
    return ".".join(str(int(p)) for p in parts)


def version_tuple(value: str) -> tuple:
    parts = [int(p) for p in normalize_version(value).split(".")]
    return tuple(parts + [0] * (4 - len(parts)))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: dict) -> None:
    fd, temp_name = tempfile.mkstemp(prefix="update_", suffix=".json.tmp", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def check_version_consistency(installer: Path, version: str, force: bool) -> None:
    problems = []
    vt = Path(__file__).with_name("version.txt")
    if vt.exists():
        file_version = normalize_version(vt.read_text(encoding="utf-8-sig").split()[0])
        if file_version != version:
            problems.append(f"version.txt says {file_version}, publishing {version}")
    m = re.search(r"_v(\d+(?:\.\d+){0,3})\.exe$", installer.name, re.I)
    if m and normalize_version(m.group(1)) != version:
        problems.append(f"installer name says {m.group(1)}, publishing {version}")
    if problems:
        msg = "Version mismatch:\n  - " + "\n  - ".join(problems)
        if not force:
            raise ValueError(msg + "\n(use --force to publish anyway)")
        print("WARNING: " + msg)


def publish(installer: Path, version: str, update_root: Path, notes: str = "", force: bool = False) -> None:
    if not installer.is_file():
        raise FileNotFoundError(installer)
    version = normalize_version(version)
    check_version_consistency(installer, version, force)

    if not update_root.exists():
        raise FileNotFoundError(f"Update share not reachable: {update_root}")

    manifest_path = update_root / MANIFEST_NAME
    if manifest_path.exists():
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            old_version = normalize_version(str(old.get("version", "0")))
            if version_tuple(version) <= version_tuple(old_version) and not force:
                raise ValueError(
                    f"Share already offers {old_version}; new version must be higher "
                    f"(clients never downgrade). Use --force to re-publish.")
        except (ValueError, json.JSONDecodeError) as exc:
            if "must be higher" in str(exc):
                raise
            print(f"WARNING: existing manifest unreadable ({exc}); it will be replaced.")

    source_hash = sha256_file(installer)
    print(f"[1/4] Installer: {installer}")
    print(f"[2/4] SHA-256:   {source_hash}")

    # Copy under a temporary name and rename only after the SHA-256 check, so
    # an interrupted or damaged copy never sits on the share under the real
    # installer name (each one is ~170 MB); a failed copy is removed at once.
    target = update_root / installer.name
    partial = target.with_name(target.name + ".partial")
    try:
        shutil.copy2(installer, partial)
        copied_hash = sha256_file(partial)
        if copied_hash != source_hash:
            raise IOError("Copy on the share is corrupt (SHA-256 differs). Nothing was published.")
        os.replace(partial, target)
    except BaseException:
        try:
            partial.unlink()
        except OSError:
            pass
        raise
    print(f"[3/4] Copied and verified: {target}")

    payload = {
        "app_name": APP_NAME,
        "version": version,
        "installer": target.name,
        "sha256": copied_hash,
        "mandatory": True,
        "release_date": date.today().isoformat(),
        "notes": notes,
    }
    atomic_write_json(manifest_path, payload)
    print(f"[4/4] Manifest:  {manifest_path}")
    print("\nPublished. Clients install it within ~15 minutes.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Publish a PM System release to the update share.")
    ap.add_argument("installer")
    ap.add_argument("version")
    ap.add_argument("update_share")
    ap.add_argument("--notes", default="")
    ap.add_argument("--force", action="store_true", help="skip version checks")
    a = ap.parse_args()
    try:
        publish(Path(a.installer).resolve(), a.version, Path(a.update_share), a.notes, a.force)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
