<#
  Gela PM System - registers the silent updater (called by Setup.exe)
  ==================================================================

  * Creates %ProgramData%\GelaDairy\PMSystem\updater with locked-down ACLs:
        updater\            SYSTEM + Administrators full, Users list-only
        updater\config.json SYSTEM + Administrators only (share password)
        updater\cache\      SYSTEM + Administrators only (installers)
        updater\status\     + Users read (the app reads status.json)
  * Optionally installs a new config.json (passed by Setup from the wizard
    page or from /SHAREUSER= /SHAREPASS= command-line parameters).
  * Registers the scheduled task "\GelaPM\PM System Updater" running as
    SYSTEM at start-up and every 15 minutes.  Signed-in users may START it
    (PM System asks for a check when it opens) but not change it.

  Usage (Setup does this):
    powershell -NoProfile -ExecutionPolicy Bypass -File install_task.ps1 -AppDir "C:\Program Files\PM_System" [-ConfigFile <tmp json>]
    powershell ... -File install_task.ps1 -Remove
#>
[CmdletBinding()]
param(
    [string]$AppDir = "",
    [string]$ConfigFile = "",
    [int]$IntervalMinutes = 15,
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$TaskName = "\GelaPM\PM System Updater"
$DataRoot = Join-Path $env:ProgramData "GelaDairy\PMSystem\updater"
$SYSTEM = "*S-1-5-18"; $ADMINS = "*S-1-5-32-544"; $USERS = "*S-1-5-32-545"

function Invoke-Exe([string]$Exe, [string[]]$ExeArgs) {
    # Windows PowerShell 5.1 turns ANY stderr text of a native program into a
    # terminating error when $ErrorActionPreference is "Stop" (for example
    # "net use x /delete" -> "The network connection could not be found.").
    # Run native tools with "Continue" and judge them by their exit code.
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

function Invoke-Icacls([string[]]$IcaclsArgs) {
    $r = Invoke-Exe "icacls.exe" $IcaclsArgs
    if ($r.Code -ne 0) { throw "icacls $($IcaclsArgs -join ' ') failed: $($r.Output)" }
}

if ($Remove) {
    [void](Invoke-Exe "schtasks.exe" @("/Delete", "/TN", $TaskName, "/F"))
    exit 0
}

if (-not $AppDir) { $AppDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path) }
$script = Join-Path $AppDir "updater\PMUpdater.ps1"
if (-not (Test-Path -LiteralPath $script)) { throw "Updater script not found: $script" }

# ---- folders + ACLs --------------------------------------------------------
foreach ($d in @($DataRoot, (Join-Path $DataRoot "cache"), (Join-Path $DataRoot "status"))) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
}
Invoke-Icacls @($DataRoot, "/inheritance:r", "/grant:r", "${SYSTEM}:(OI)(CI)F", "${ADMINS}:(OI)(CI)F", "${USERS}:(RX)")
Invoke-Icacls @((Join-Path $DataRoot "status"), "/grant:r", "${USERS}:(OI)(CI)RX")

# ---- config -----------------------------------------------------------------
$configPath = Join-Path $DataRoot "config.json"
if ($ConfigFile -and (Test-Path -LiteralPath $ConfigFile)) {
    $text = [IO.File]::ReadAllText($ConfigFile, [Text.Encoding]::UTF8)
    [void]($text | ConvertFrom-Json)       # validate
    [IO.File]::WriteAllText($configPath, $text, (New-Object Text.UTF8Encoding($false)))
    Remove-Item -Force -LiteralPath $ConfigFile -ErrorAction SilentlyContinue
} elseif (-not (Test-Path -LiteralPath $configPath)) {
    $default = '{ "share": "\\\\192.168.0.1\\PM_System_Updates", "user": "", "password": "", "grace_seconds": 120, "enabled": true }'
    [IO.File]::WriteAllText($configPath, $default, (New-Object Text.UTF8Encoding($false)))
}
Invoke-Icacls @($configPath, "/inheritance:r", "/grant:r", "${SYSTEM}:F", "${ADMINS}:F")

# ---- scheduled task -----------------------------------------------------------
$start = (Get-Date).AddMinutes(2).ToString("yyyy-MM-ddTHH:mm:ss")
$psExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
$esc = [Security.SecurityElement]

$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>Gela Dairy Co.</Author>
    <Description>Installs new PM System releases from the company update share.</Description>
  </RegistrationInfo>
  <Triggers>
    <BootTrigger>
      <Enabled>true</Enabled>
      <Delay>PT2M</Delay>
      <Repetition><Interval>PT${IntervalMinutes}M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>
    </BootTrigger>
    <TimeTrigger>
      <Enabled>true</Enabled>
      <StartBoundary>$start</StartBoundary>
      <Repetition><Interval>PT${IntervalMinutes}M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>
    </TimeTrigger>
  </Triggers>
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
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>true</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
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

$xmlPath = Join-Path $env:TEMP ("gelapm_task_" + [Guid]::NewGuid().ToString("N") + ".xml")
[IO.File]::WriteAllText($xmlPath, $xml, [Text.Encoding]::Unicode)
try {
    $r = Invoke-Exe "schtasks.exe" @("/Create", "/TN", $TaskName, "/XML", $xmlPath, "/F")
    if ($r.Code -ne 0) { throw "schtasks /Create failed: $($r.Output)" }
} finally {
    Remove-Item -Force -LiteralPath $xmlPath -ErrorAction SilentlyContinue
}

# ---- let signed-in users START the updater ------------------------------------
# PM System asks the updater to check for a new version when it opens. Users
# get read + run on the task (and read on its folder) - they cannot change it;
# the task still runs as SYSTEM with this fixed script.
function Test-RunRight([string]$Sddl) {
    foreach ($m in [regex]::Matches($Sddl, '\(A;[^;]*;([^;]*);[^;]*;[^;]*;(AU|BU|IU|WD)\)')) {
        $r = $m.Groups[1].Value
        if ($r -match '^0x([0-9a-fA-F]+)$') {
            $v = [Convert]::ToInt64($Matches[1], 16)
            if (($v -band 0x20) -or ($v -band 0x20000000) -or ($v -band 0x10000000)) { return $true }
        } elseif ($r -match 'GX|GA|FA|FX') { return $true }
    }
    return $false
}
function Grant-UsersRun($Object) {
    $sd = [string]$Object.GetSecurityDescriptor(4)          # DACL only
    if (Test-RunRight $sd) { return }
    $Object.SetSecurityDescriptor($sd + "(A;;GRGX;;;AU)", 0)
}
try {
    $svc = New-Object -ComObject Schedule.Service
    $svc.Connect()
    $folder = $svc.GetFolder("\GelaPM")
    try { Grant-UsersRun $folder } catch { }
    Grant-UsersRun ($folder.GetTask("PM System Updater"))
} catch {
    Write-Warning "Users cannot start the updater task (updates still run every $IntervalMinutes minutes): $($_.Exception.Message)"
}
exit 0
