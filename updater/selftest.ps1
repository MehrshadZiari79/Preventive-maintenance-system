<#
  Gela PM System - automatic-update self-test (run by Setup after EVERY install)
  ==============================================================================

  The real updater runs as the Windows SYSTEM account, so testing it from the
  logged-in administrator is not enough (SYSTEM connects to the network
  differently).  This script therefore:

    1. registers a one-off scheduled task "\GelaPM\PM System Updater Check"
       that runs  PMUpdater.ps1 -CheckOnly  AS SYSTEM.  That is the FULL test,
       with the same code as a real update: settings, the real scheduled task,
       status folder rights, share login, release manifest, download of the
       whole installer into the cache with SHA-256 check, version compare;
    2. starts it and waits (max. 240 s) for its result file,
    3. deletes the task again,
    4. writes the result ("OK|...", "WARN|..." or "FAIL|...") to -ResultFile
       and to %ProgramData%\GelaDairy\PMSystem\updater\status\setup_check.txt
       (the app reads that file and warns if the check failed).

  The test never installs anything.  Result file: first line "OK|...",
  "WARN|..." or "FAIL|...", then one "- [OK|WARN|FAIL] ..." line per check.

  Usage (Setup does this):
    powershell -NoProfile -ExecutionPolicy Bypass -File selftest.ps1 -AppDir "C:\Program Files\PM_System" -ResultFile "<tmp>\update_check.txt"
#>
[CmdletBinding()]
param(
    [string]$AppDir = "",
    [string]$ResultFile = "",
    [int]$TimeoutSeconds = 240
)

$ErrorActionPreference = "Stop"
$CheckTask = "\GelaPM\PM System Updater Check"
$DataRoot  = Join-Path $env:ProgramData "GelaDairy\PMSystem\updater"
$StatusDir = Join-Path $DataRoot "status"
$SysResult = Join-Path $StatusDir "setup_check.txt"
$LogPath   = Join-Path $DataRoot "updater.log"

function Invoke-Exe([string]$Exe, [string[]]$ExeArgs) {
    # Windows PowerShell 5.1: stderr of a native tool must not become a
    # terminating error, so run it with "Continue" and use the exit code.
    $old = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $lines = @(& $Exe @ExeArgs 2>&1 | ForEach-Object { "$_" } | Where-Object { $_ -and $_ -ne "System.Management.Automation.RemoteException" })
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $old
    }
    return New-Object PSObject -Property @{ Code = $code; Output = (($lines -join " ").Trim()) }
}

function Write-Log([string]$Message) {
    try {
        $line = "{0}  {1}" -f (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"), $Message
        Add-Content -Path $LogPath -Value $line -Encoding UTF8
    } catch { }
}

function Save-Result([string]$Text) {
    # UTF-8 WITH BOM: Setup (Inno) and the app both read it correctly
    $utf8 = New-Object Text.UTF8Encoding($true)
    try { [IO.File]::WriteAllText($SysResult, $Text, $utf8) } catch { }
    if ($ResultFile) {
        try { [IO.File]::WriteAllText($ResultFile, $Text, $utf8) } catch { }
    }
}

$result = "FAIL|The automatic-update test could not run."
$xmlPath = $null
$taskCreated = $false
try {
    if (-not $AppDir) { $AppDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path) }
    $updater = Join-Path $AppDir "updater\PMUpdater.ps1"
    if (-not (Test-Path -LiteralPath $updater)) { throw "Updater script not found: $updater" }
    if (-not (Test-Path -LiteralPath $StatusDir)) { New-Item -ItemType Directory -Force -Path $StatusDir | Out-Null }
    if (Test-Path -LiteralPath $SysResult) { Remove-Item -Force -LiteralPath $SysResult }

    $psExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$updater`" -CheckOnly -ResultFile `"$SysResult`""
    $esc = [Security.SecurityElement]
    $xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>Gela Dairy Co.</Author>
    <Description>One-off test of the PM System automatic updates (created and removed by Setup).</Description>
  </RegistrationInfo>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>false</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>true</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$($esc::Escape($psExe))</Command>
      <Arguments>$($esc::Escape($arguments))</Arguments>
      <WorkingDirectory>$($esc::Escape($DataRoot))</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@
    $xmlPath = Join-Path $env:TEMP ("gelapm_check_" + [Guid]::NewGuid().ToString("N") + ".xml")
    [IO.File]::WriteAllText($xmlPath, $xml, [Text.Encoding]::Unicode)

    $r = Invoke-Exe "schtasks.exe" @("/Create", "/TN", $CheckTask, "/XML", $xmlPath, "/F")
    if ($r.Code -ne 0) { throw "could not create the test task: $($r.Output)" }
    $taskCreated = $true
    $r = Invoke-Exe "schtasks.exe" @("/Run", "/TN", $CheckTask)
    if ($r.Code -ne 0) { throw "could not start the test task: $($r.Output)" }

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $text = ""
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 700
        if (Test-Path -LiteralPath $SysResult) {
            try { $text = ([IO.File]::ReadAllText($SysResult, [Text.Encoding]::UTF8)).Trim() } catch { $text = "" }
            if ($text -match '^(OK|WARN|FAIL)\|') { break }
        }
    }
    if ($text -match '^(OK|WARN|FAIL)\|') {
        $result = $text
    } else {
        $result = "FAIL|The automatic-update test did not finish within $TimeoutSeconds seconds (server unreachable or very slow network)."
    }
} catch {
    $result = "FAIL|Automatic-update test error: " + $_.Exception.Message
} finally {
    if ($taskCreated) { [void](Invoke-Exe "schtasks.exe" @("/Delete", "/TN", $CheckTask, "/F")) }
    if ($xmlPath) { Remove-Item -Force -LiteralPath $xmlPath -ErrorAction SilentlyContinue }
}

Save-Result $result
Write-Log ("Install self-test: " + (($result -split "`r?`n") -join " / "))
if ($result.StartsWith("FAIL")) { exit 1 }
exit 0
