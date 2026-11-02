<#
  PM System - automatic update test (run on a client PC, as Administrator)
  =======================================================================

  Start menu: "PM System" > "Test automatic updates"   (asks for admin rights)
  or:  powershell -NoProfile -ExecutionPolicy Bypass -File "<app>\updater\test_autoupdate.ps1"

  1. This PC: installed version, update settings (password is NOT shown),
     scheduled task, when the updater last ran.
  2. The FULL test as SYSTEM (the same one Setup runs after every install):
     settings, task, status folder rights, share login, release manifest,
     download of the whole installer with SHA-256 check, version compare.
  3. One REAL run of the scheduled updater right now, as SYSTEM.  It installs
     only when a newer release is published on the update share.  If PM System
     is open it shows its 2-minute countdown first, then re-opens.
  4. RESULT: PASS or FAIL, with the exact reason.  A copy of everything shown
     is saved to %ProgramData%\GelaDairy\PMSystem\updater\last_test_report.txt

  Exit code 0 = PASS, 1 = FAIL.
#>
[CmdletBinding()]
param(
    [string]$AppDir = "",
    [int]$WaitSeconds = 900
)

$ErrorActionPreference = "Continue"
$TaskFolder  = "\GelaPM\"
$TaskLeaf    = "PM System Updater"
$TaskName    = $TaskFolder + $TaskLeaf
$DataRoot    = Join-Path $env:ProgramData "GelaDairy\PMSystem\updater"
$StatusPath  = Join-Path $DataRoot "status\status.json"
$LastRunPath = Join-Path $DataRoot "status\last_run.json"
$LogPath     = Join-Path $DataRoot "updater.log"
$ConfigPath  = Join-Path $DataRoot "config.json"
$ReportPath  = Join-Path $DataRoot "last_test_report.txt"
$RegKey      = "HKLM:\SOFTWARE\Gela Dairy Co.\PM System"
$Psh         = (Get-Process -Id $PID).Path

$script:Problems = @()
$script:Warnings = @()
$script:Report = New-Object System.Collections.ArrayList

function Add-Report([string]$Text) { [void]$script:Report.Add($Text) }
function Out-Step([string]$Text) { Write-Host ""; Write-Host "== $Text" -ForegroundColor Cyan; Add-Report ""; Add-Report "== $Text" }
function Out-Info([string]$Text) { Write-Host "   $Text"; Add-Report "   $Text" }
function Out-Ok([string]$Text)   { Write-Host "   [OK]   $Text" -ForegroundColor Green; Add-Report "   [OK]   $Text" }
function Out-Warn([string]$Text) { Write-Host "   [WARN] $Text" -ForegroundColor Yellow; Add-Report "   [WARN] $Text"; $script:Warnings += $Text }
function Out-Bad([string]$Text)  { Write-Host "   [FAIL] $Text" -ForegroundColor Red; Add-Report "   [FAIL] $Text"; $script:Problems += $Text }

function Invoke-Exe([string]$Exe, [string[]]$ExeArgs) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $lines = @(& $Exe @ExeArgs 2>&1 | ForEach-Object { "$_" } | Where-Object { $_ -and $_ -ne "System.Management.Automation.RemoteException" })
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $old }
    return New-Object PSObject -Property @{ Code = $code; Output = (($lines -join " ").Trim()) }
}

function Read-Json([string]$Path) {
    try {
        if (Test-Path -LiteralPath $Path) { return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json) }
    } catch { }
    return $null
}

function Get-UnixNow { return [int64](([DateTime]::UtcNow.Ticks - 621355968000000000) / 10000000) }

function Get-RegVersion {
    try { return [string](Get-ItemProperty -Path $RegKey -Name Version -ErrorAction Stop).Version } catch { return "" }
}

# byte offset of the log (not a line count: the log is rotated at 1 MB)
function Get-LogOffset {
    if (-not (Test-Path -LiteralPath $LogPath)) { return [long]0 }
    return [long](Get-Item -LiteralPath $LogPath).Length
}

# lines written after $Offset; if the log was rotated meanwhile, read the new file from its start
function Get-NewLogLines([long]$Offset) {
    if (-not (Test-Path -LiteralPath $LogPath)) { return @() }
    $len = [long](Get-Item -LiteralPath $LogPath).Length
    if ($len -lt $Offset) { $Offset = 0 }
    if ($len -eq $Offset) { return @() }
    $fs = [IO.File]::Open($LogPath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    try {
        [void]$fs.Seek($Offset, [IO.SeekOrigin]::Begin)
        $sr = New-Object IO.StreamReader($fs, [Text.Encoding]::UTF8)
        $text = $sr.ReadToEnd()
    } finally { $fs.Dispose() }
    return @($text -split "`r?`n" | Where-Object { $_ -ne "" })
}

function Test-TaskRunning {
    # Task Scheduler state (language independent); last_run.json as a fallback
    if (Get-Command Get-ScheduledTask -ErrorAction SilentlyContinue) {
        try { return ([string](Get-ScheduledTask -TaskPath $TaskFolder -TaskName $TaskLeaf -ErrorAction Stop).State -eq "Running") } catch { }
    }
    $lr = Read-Json $LastRunPath
    if ($lr -and [string]$lr.result -eq "running" -and [int64]$lr.finished_unix -eq 0 -and
        ((Get-UnixNow) - [int64]$lr.started_unix) -lt 3600) { return $true }
    return $false
}

function Start-UpdaterTask {
    if (Get-Command Start-ScheduledTask -ErrorAction SilentlyContinue) {
        try { Start-ScheduledTask -TaskPath $TaskFolder -TaskName $TaskLeaf -ErrorAction Stop; return "" }
        catch { }
    }
    $r = Invoke-Exe "schtasks.exe" @("/Run", "/TN", $TaskName)
    if ($r.Code -ne 0) { return $r.Output }
    return ""
}

function Save-Report {
    try {
        $lines = @("PM System - automatic update test", ("Date: " + (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")),
                   ("Computer: " + $env:COMPUTERNAME)) + @($script:Report)
        [IO.File]::WriteAllLines($ReportPath, [string[]]$lines, (New-Object Text.UTF8Encoding($true)))
        Write-Host ""
        Write-Host "Report saved: $ReportPath"
    } catch { }
}

function Finish {
    Write-Host ""
    if ($script:Problems.Count -eq 0) {
        if ($script:Warnings.Count -eq 0) { $line = "RESULT: PASS - automatic updates work on this PC."; $color = "Green" }
        else { $line = "RESULT: PASS with warnings - automatic updates work; read the WARN lines."; $color = "Yellow" }
        $code = 0
    } else {
        $line = "RESULT: FAIL - $($script:Problems.Count) problem(s). Send the report file to the developer."
        $color = "Red"; $code = 1
    }
    Write-Host $line -ForegroundColor $color
    Add-Report ""; Add-Report $line
    Save-Report
    exit $code
}

# ------------------------------------------------------------------ 0. this PC
Out-Step "1. This PC"
$isAdmin = $true
try {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $isAdmin = (New-Object Security.Principal.WindowsPrincipal $id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
} catch { }
if (-not $isAdmin) {
    Out-Bad "Run this test as Administrator (Start menu > PM System > Test automatic updates)."
    Finish
}
Out-Ok "running as Administrator on $env:COMPUTERNAME"

if (-not $AppDir) {
    try { $AppDir = (Get-ItemProperty -Path $RegKey -Name InstallPath -ErrorAction Stop).InstallPath } catch { }
}
if (-not $AppDir) { $AppDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path) }
if (-not (Test-Path -LiteralPath (Join-Path $AppDir "updater\PMUpdater.ps1"))) {
    Out-Bad "PM System is not installed here (updater not found in '$AppDir')."
    Finish
}
Out-Ok "application folder: $AppDir"

$installed = Get-RegVersion
if ($installed) { Out-Ok "installed version: $installed" }
else { Out-Bad "installed version not found in the registry ($RegKey) - run the installer again" }

$cfg = Read-Json $ConfigPath
if ($null -eq $cfg) {
    Out-Bad "no update settings ($ConfigPath) - run the installer again"
} else {
    Out-Ok "update share: $($cfg.share)   account: $($cfg.user)   (password not shown)"
}

$task = Invoke-Exe "schtasks.exe" @("/Query", "/TN", $TaskName)
if ($task.Code -eq 0) { Out-Ok "scheduled task $TaskName is registered" }
else { Out-Bad "scheduled task $TaskName is missing - run the installer again" }

$prev = Read-Json $LastRunPath
if ($prev -and [int64]$prev.finished_unix -gt 0) {
    $ago = [int](((Get-UnixNow) - [int64]$prev.finished_unix) / 60)
    Out-Info "the updater last ran $ago minute(s) ago, result: $($prev.result)"
    if ($ago -gt 30) { Out-Warn "the updater has not run for $ago minutes (it should run every 15 minutes; was the PC off or asleep?)" }
} else {
    Out-Info "no previous automatic run recorded yet"
}

# ------------------------------------------------------- 2. full test as SYSTEM
Out-Step "2. Full test as SYSTEM (the same test Setup runs after every install)"
$selftest = Join-Path $AppDir "updater\selftest.ps1"
$tmpResult = Join-Path $env:TEMP ("gelapm_test_" + [Guid]::NewGuid().ToString("N") + ".txt")
if (Test-Path -LiteralPath $selftest) {
    Out-Info "running (up to 4 minutes: it downloads the whole installer once) ..."
    & $Psh -NoProfile -ExecutionPolicy Bypass -File $selftest -AppDir $AppDir -ResultFile $tmpResult | Out-Null
    $text = ""
    if (Test-Path -LiteralPath $tmpResult) { $text = ([IO.File]::ReadAllText($tmpResult, [Text.Encoding]::UTF8)).Trim() }
    Remove-Item -LiteralPath $tmpResult -Force -ErrorAction SilentlyContinue
    $lines = @($text -split "`r?`n" | Where-Object { $_.Trim() -ne "" })
    $details = @($lines | Select-Object -Skip 1)
    if ($lines.Count -eq 0) {
        Out-Bad "the full test returned no result"
    } elseif ($details.Count -eq 0) {
        # a test that stopped before any check (for example the test task could not be created)
        if ($lines[0] -match '^OK\|(.*)') { Out-Ok $Matches[1] }
        elseif ($lines[0] -match '^WARN\|(.*)') { Out-Warn $Matches[1] }
        else { Out-Bad ($lines[0] -replace '^[A-Z]+\|', '') }
    } else {
        foreach ($d in $details) {
            if ($d -match '^- \[OK\] (.*)') { Out-Ok $Matches[1] }
            elseif ($d -match '^- \[WARN\] (.*)') { Out-Warn $Matches[1] }
            elseif ($d -match '^- \[FAIL\] (.*)') { Out-Bad $Matches[1] }
            else { Out-Info $d }
        }
    }
} else {
    Out-Bad "selftest.ps1 not found in $AppDir\updater - run the installer again"
}

# ------------------------------------------- 3. one real run of the updater
Out-Step "3. One real run of the scheduled updater, as SYSTEM"
if (Get-Process -Name "PM_System" -ErrorAction SilentlyContinue) {
    Out-Info "PM System is open. If a newer release is found it shows a 2-minute countdown, closes, updates and opens again."
}

# a run that is already in progress must finish first (Task Scheduler would ignore a second start)
$waitUntil = (Get-Date).AddSeconds($WaitSeconds)
if (Test-TaskRunning) {
    Out-Info "an automatic run is already in progress - waiting for it to finish ..."
    while ((Get-Date) -lt $waitUntil -and (Test-TaskRunning)) { Start-Sleep -Seconds 3 }
    if (Test-TaskRunning) { Out-Bad "the automatic run already in progress did not finish within $WaitSeconds seconds"; Finish }
}

$t0 = Get-UnixNow
$offset = Get-LogOffset
$startError = Start-UpdaterTask
$run = $null
if ($startError) {
    Out-Bad "could not start the updater task: $startError"
} else {
    Out-Info "started, waiting for the result (max $WaitSeconds s) ..."
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    $startBy = (Get-Date).AddSeconds(120)
    $saidPending = $false; $saidInstalling = $false
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        $lr = Read-Json $LastRunPath
        if ($lr -and [int64]$lr.started_unix -ge $t0) {
            if ([int64]$lr.finished_unix -gt 0) { $run = $lr; break }
        } elseif ((Get-Date) -gt $startBy) {
            break
        }
        $st = Read-Json $StatusPath
        if ($st -and [string]$st.state -eq "pending" -and -not $saidPending) {
            Out-Info "new version $($st.version) found - PM System shows its countdown on this PC ..."; $saidPending = $true
        }
        if ($st -and [string]$st.state -eq "installing" -and -not $saidInstalling) {
            Out-Info "installing version $($st.version) silently ..."; $saidInstalling = $true
        }
    }
}

$newLines = @(Get-NewLogLines $offset)
foreach ($l in $newLines) { Out-Info ("log: " + $l) }

# --------------------------------------------------------------- 4. verdict
Out-Step "4. Result of the real run"
if (-not $startError) {
    $lr = Read-Json $LastRunPath
    if ($null -eq $run) {
        if (-not $lr -and $newLines.Count -gt 0) {
            Out-Bad "this PC runs an older updater without run results - install the current PM System installer first"
        } elseif ($lr -and [int64]$lr.started_unix -ge $t0) {
            Out-Bad "the updater started but did not finish within $WaitSeconds seconds (very slow network, or the installer hangs)"
        } else {
            Out-Bad "the scheduled task did not start the updater within 2 minutes (Task Scheduler service, or a policy blocks PowerShell)"
        }
    } else {
        $result = [string]$run.result
        switch ($result) {
            "up_to_date" {
                Out-Ok "the updater ran as SYSTEM: this PC is up to date (installed $($run.installed), latest on the share $($run.offered))"
                Out-Info "The silent installation itself runs only when a newer release exists. To watch it here:"
                Out-Info "publish a new release with release.bat on the build PC, then run this test again."
            }
            "installed" {
                $now = Get-RegVersion
                $exe = Join-Path $AppDir "PM_System.exe"
                if ($now -ne [string]$run.offered) {
                    Out-Bad "the installer reported success, but the registry shows version '$now' instead of '$($run.offered)'"
                } elseif (-not (Test-Path -LiteralPath $exe)) {
                    Out-Bad "version $now is registered, but $exe is missing"
                } else {
                    Out-Ok "UPDATE INSTALLED: $installed -> $now (registry and program file confirm it)"
                }
            }
            "no_release" { Out-Warn "the updater works, but no release is published on the update share yet" }
            "dry_run"    { Out-Warn "the updater is in test (dry-run) mode and did not install" }
            "disabled"   { Out-Bad "automatic updates are switched off in $ConfigPath" }
            default      { Out-Bad ("the updater reported: " + $(if ($run.message) { [string]$run.message } else { $result })) }
        }
    }
}

Finish
