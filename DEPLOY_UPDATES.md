# PM System v2.4: silent automatic updates

This guide covers setting up the server once, installing v2.4 on each PC once, and publishing a release from then on.

## How it works

```
 build PC                       server 192.168.0.1                       client PC
 ─────────                      ───────────────────                      ─────────
 build_release.bat  ──►  publish_update.py  ──►  E:\PM_System_Updates      Task Scheduler (SYSTEM)
                                                   pm_system_update.json  ◄── every 15 min + at start-up
                                                   PM_System_Setup_v*.exe      PMUpdater.ps1:
                                                                                - newer version? copy + SHA-256
                                                                                - app open? 2-min Persian countdown
                                                                                - run Setup silently as SYSTEM
                                                                                - app re-opens by itself
```

* Employees stay **standard users**. No UAC prompt appears, because the install runs as SYSTEM.
* The updater **never touches SQL Server or PM_Database**. It only replaces program files.
* Users never need access to the share. Only the SYSTEM task reads it, using a read-only account.

---

## 1. Server (one time, about 10 minutes, Remote Desktop to 192.168.0.1)

1. Create the folder `E:\PM_System_Updates`. Leave `E:\pm_backup` alone.
2. Create a **local user** for reading updates:
   `Computer Management → Local Users → New User`
   * name: `pm_update_reader`, with a strong password
   * tick *Password never expires*, untick *User must change password*
   * it does **not** need to be in any group except *Users*
3. Share the folder:
   `Properties → Sharing → Advanced Sharing → Share this folder`, share name `PM_System_Updates`
   * **Permissions**: remove *Everyone*. Add `pm_update_reader` with **Read**. Add your own admin account with **Full Control**, so you can publish.
4. NTFS (`Security` tab): `pm_update_reader` gets **Read & execute**, admins get Full control.
5. Test from the build PC: open `\\192.168.0.1\PM_System_Updates` and copy a `test.txt` into it.
6. **Machine-hours shift tables (once):** take a database backup, then run `deploy\add_machine_shift_tables.sql` in SQL Server Management Studio / Query Analyzer against `PM_Database`. It only adds two new tables and is safe to run twice. Until it is run, ساعت کار ماشین works in basic mode (stop reasons are not saved).

## 2. Each client PC (one time, as an administrator)

v2.3 clients cannot update themselves to v2.4 as standard users: the old updater would need a UAC password. So the first v2.4 install is done by hand, **once per PC**.

1. Run the installer (`installer_output\PM_System_Setup_v<version>.exe`, from a flash drive or the share) as an administrator and click through it. **Nothing has to be typed**: the update-share account is built into installers made by `release.bat` (it asks for the password once on the build PC and keeps it in `updater_account.local`, which is not part of the source code).
2. After **every** install - the first one, a manual reinstall and every silent automatic update - Setup runs the **full automatic-update test as the Windows SYSTEM account**, exactly like the real updater (a temporary task "\GelaPM\PM System Updater Check" is created, run and deleted). It uses the same code as a real update and checks:
   * the update settings and the stored password,
   * the real scheduled task: it exists, runs as SYSTEM, is enabled, has its schedule and starts an existing `PMUpdater.ps1`,
   * that normal users can read the status folder (so the app can show update messages),
   * log-in to the update share with the update account,
   * the release manifest,
   * **downloading the whole installer into the local cache and checking its SHA-256** (after a silent update it checks the copy that update just downloaded),
   * the version on the share against the installed version.

   Interactive installs show the result on the last page ("Automatic updates: OK - fully tested", or what is wrong); a failure also opens a message that says why. The program itself works either way. Every result is written to `C:\ProgramData\GelaDairy\PMSystem\updater\updater.log` and `...\updater\status\setup_check.txt`; if the last test failed, PM System warns the users.
3. Finish. The installer:
   * creates the hidden scheduled task `\GelaPM\PM System Updater` (runs as SYSTEM)
   * stores the share account in `C:\ProgramData\GelaDairy\PMSystem\updater\config.json`, which only SYSTEM and Administrators can read
   * starts PM System for **every Windows user at logon**, using the machine-wide Run key

For a silent first install, for example from a script:

```
PM_System_Setup_v2.4.0.exe /VERYSILENT /SHAREUSER=GELAAMOL\pm_update_reader /SHAREPASS=xxxxx
```

### Test a client at any time: "Test automatic updates"
Start menu → **PM System** → **Test automatic updates** (asks for administrator rights). Or, in PowerShell as administrator:
`powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Program Files\PM_System\updater\test_autoupdate.ps1"`

1. **This PC** - installed version, update settings (the password is never shown), scheduled task, when the updater last ran.
2. **Full test as SYSTEM** - the same test Setup runs (see above).
3. **One real run of the updater, now, as SYSTEM.** If another run is in progress it waits for it first. It installs only when a newer release is on the share; if PM System is open it shows its 2-minute countdown, updates and opens again.
4. **RESULT: PASS / FAIL** with the exact reason. The report is saved to `C:\ProgramData\GelaDairy\PMSystem\updater\last_test_report.txt` - send that file when something fails.

To see a real silent installation: publish a new release with `release.bat`, then run the test on a client - step 4 shows `UPDATE INSTALLED: x -> y`.

Every scheduled run also writes its result to `...\updater\status\last_run.json` and its details to `...\updater\updater.log`.

## 3. Publishing a new release (every time)

On the build PC, after changing the code, double-click **`release.bat`** (or run
`release.bat "توضیح تغییرات"` to attach release notes). It does everything in one go:

1. Checks Python packages, Inno Setup and write access to the update share **before** changing anything.
2. Picks the next version automatically: the higher of `version.txt` and the version already on the share, plus one in the **4th number**: `2.4.6.1` → `2.4.6.2` → `2.4.6.3` … (`2.4.6.9` → `2.4.6.10`). You never edit the version for a normal release.
   To start a new series, write it in `version.txt` (for example `2.4.7`); the next release is then `2.4.7.1`. Clients update from any lower version (`2.4.6.12` → `2.4.7.1` works).
3. Builds with PyInstaller and Inno Setup.
4. Publishes: copies the installer, verifies the copy's SHA-256, then writes `pm_system_update.json` last.
5. Keeps only the **newest 2 installers** (this release + the previous one, ~170 MB each) on the update share **and** in `installer_output` on the build PC; older ones are deleted automatically (chosen by version number, not file date). The installer is copied to the share under a temporary name and renamed only after its SHA-256 check, so an interrupted copy never stays behind.

If anything fails before publishing, `version.txt` is restored and nothing reaches the clients. Each run is logged in `release_logs\`.
Environment overrides: `PM_UPDATE_SHARE` (default `\\192.168.0.1\PM_System_Updates`) and `PM_ISCC` (path to `ISCC.exe`).

The manual route (`build_release.bat`, then `publish_update.py`) still works if needed.

Every PC that is switched on installs it within about 15 minutes, and **at the latest when someone opens PM System**:
   * **When PM System is opened**, a small window «در حال بررسی نسخه جدید…» appears for a few seconds: the program asks the SYSTEM updater to check the share right now (signed-in users may start the updater task, not change it). If a newer version is there, the window says so, PM System closes and the **«در حال به‌روزرسانی سیستم PM»** window installs it and opens PM System again. If nothing is new, or the server does not answer within 20 seconds, the login window opens as usual (a user can also press «ادامه بدون انتظار»).
   * **If PM System is closed**, the install happens silently.
   * **If it is open**, users see a countdown: **"نسخه جدید سیستم PM آماده نصب است"**. They have 2 minutes to save their work, or can press *«کارم را ذخیره کردم، الان بروزرسانی شود»*.
   * **While it installs**, the window **«در حال به‌روزرسانی سیستم PM»** shows each step (preparing, installing version x, done), a progress bar and the elapsed time, and asks the user to wait and not to switch the PC off. It cannot be closed by mistake. When the installation is finished it opens PM System again, followed by a short "updated" notice. If an installation fails, it says so and opens the current version.

### If something goes wrong
* A broken release is retried 3 times per PC, then that PC waits for the next version. To roll back, publish a **higher** version that contains the old code. Clients never downgrade.
* To stop updates on one PC, set `"enabled": false` in its `config.json` as an administrator.
* To change the countdown, edit `"grace_seconds"` in `config.json` (default 120).
* Installer logs: `C:\ProgramData\GelaDairy\PMSystem\updater\install_<version>.log`.

## 4. Security notes
* The SHA-256 check protects against a corrupt or partial copy. Trust comes from the share permissions: **only admins may write to `PM_System_Updates`**.
* `pm_update_reader` can only read installers. If its password leaks, nobody can change the installers.
* Signing the installer with a code-signing certificate is still recommended later.
