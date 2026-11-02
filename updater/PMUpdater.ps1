<#
  Gela PM System - silent LAN updater (runs as SYSTEM from Task Scheduler)
  ======================================================================

  Registered by install_task.ps1 as the scheduled task
      \GelaPM\PM System Updater
  Triggers: at Windows start-up and every 15 minutes.

  What one run does
  -----------------
  1. Reads  %ProgramData%\GelaDairy\PMSystem\updater\config.json
     (share path + optional read-only share account; readable only by
     SYSTEM and Administrators).
  2. Opens the update share (workgroup: "net use" with that account, inside
     the SYSTEM logon session only - users' own drive mappings are untouched).
  3. Reads pm_system_update.json and compares the version with the installed
     version (HKLM\SOFTWARE\Gela Dairy Co.\PM System -> Version).
  4. Copies the installer to a SYSTEM-only cache and verifies its SHA-256.
  5. If PM_System.exe is running, writes status "pending" with a deadline
     (default 120 s). The app shows a Persian countdown, closes itself and
     re-opens after the update. If it is still running at the deadline the
     installer closes it.
  6. Runs the Inno Setup installer silently, writes status "done"/"failed".

  It never touches the SQL Server or PM_Database.

  Compatible with Windows PowerShell 4.0 / 5.1 (Windows 8.1, 10, 11).
#>

[CmdletBinding()]
param(
    # Test hooks (not used by the scheduled task)
    [string]$DataRoot = "",
    [string]$InstalledVersionOverride = "",
    [switch]$DryRun,
    # Full test used by Setup after every install (run as SYSTEM by selftest.ps1):
    #   -CheckOnly -ResultFile <path>   -> writes "OK|...", "WARN|..." or "FAIL|..."
    #   plus one "- [OK|WARN|FAIL] ..." line per check, and exits (never installs)
    [switch]$CheckOnly,
    [string]$ResultFile = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2

$AppName          = "PM System"
$ManifestName     = "pm_system_update.json"
$ExeName          = "PM_System.exe"
$RegistryKey      = "HKLM:\SOFTWARE\Gela Dairy Co.\PM System"
$DefaultShare     = "\\192.168.0.1\PM_System_Updates"
$DefaultGraceSec  = 120
$MaxAttempts      = 3

if (-not $DataRoot) { $DataRoot = Join-Path $env:ProgramData "GelaDairy\PMSystem\updater" }
$ConfigPath = Join-Path $DataRoot "config.json"
$StatusDir  = Join-Path $DataRoot "status"
$StatusPath = Join-Path $StatusDir "status.json"
$CacheDir   = Join-Path $DataRoot "cache"
$LogPath    = Join-Path $DataRoot "updater.log"
$StatePath  = Join-Path $DataRoot "state.json"   # attempt counters (SYSTEM only)

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

function Write-Log([string]$Message) {
    $line = "{0}  {1}" -f (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"), $Message
    try {
        if ((Test-Path $LogPath) -and ((Get-Item $LogPath).Length -gt 1MB)) {
            Move-Item -Force $LogPath ($LogPath + ".old")
        }
        Add-Content -Path $LogPath -Value $line -Encoding UTF8
    } catch { }
}

function Read-JsonFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $text = [IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8)
    if (-not $text.Trim()) { return $null }
    return ($text | ConvertFrom-Json)
}

function Write-JsonAtomic([string]$Path, $Object) {
    $json = $Object | ConvertTo-Json -Depth 4
    $tmp  = $Path + ".tmp"
    [IO.File]::WriteAllText($tmp, $json, (New-Object Text.UTF8Encoding($false)))
    # the app reads status.json every few seconds; if it has the file open at
    # this very moment the replace fails - try again shortly
    for ($i = 1; $i -le 10; $i++) {
        try { Move-Item -Force -LiteralPath $tmp -Destination $Path -ErrorAction Stop; return }
        catch { if ($i -eq 10) { throw }; Start-Sleep -Milliseconds 200 }
    }
}

function Get-Prop($Object, [string]$Name, $Default) {
    if ($null -eq $Object) { return $Default }
    $p = $Object.PSObject.Properties[$Name]
    if ($null -eq $p -or $null -eq $p.Value) { return $Default }
    return $p.Value
}

function ConvertTo-VersionTuple([string]$Text) {
    $t = ("" + $Text).Trim()
    if ($t.StartsWith("v") -or $t.StartsWith("V")) { $t = $t.Substring(1) }
    if ($t -notmatch '^\d+(\.\d+){0,3}$') { throw "Invalid version '$Text'" }
    $parts = @($t.Split(".") | ForEach-Object { [int]$_ })
    while ($parts.Count -lt 4) { $parts += 0 }
    return ,$parts
}

function Compare-Version([string]$A, [string]$B) {
    $x = ConvertTo-VersionTuple $A
    $y = ConvertTo-VersionTuple $B
    for ($i = 0; $i -lt 4; $i++) {
        if ($x[$i] -gt $y[$i]) { return 1 }
        if ($x[$i] -lt $y[$i]) { return -1 }
    }
    return 0
}

function Get-InstalledVersion {
    if ($InstalledVersionOverride) { return $InstalledVersionOverride }
    try {
        $v = (Get-ItemProperty -Path $RegistryKey -Name Version -ErrorAction Stop).Version
        if ($v) { return [string]$v }
    } catch { }
    return "0.0.0"
}

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

# Windows error numbers that net.exe prints ("System error 1326 has occurred.").
# The number is read, not the English word, so Persian/other-language Windows
# works too.  Host and share names are removed first (they contain digits).
$NetErrorCodes = @("1219", "1326", "86", "1327", "1330", "1331", "1909", "53", "64", "67", "1231", "1232", "1311")
function Get-NetErrorCode([string]$Text) {
    $clean = [regex]::Replace([string]$Text, '\\\\\S+', " ")
    foreach ($m in [regex]::Matches($clean, '(?<![\d.])(\d{2,4})(?![\d.])')) {
        if ($NetErrorCodes -contains $m.Groups[1].Value) { return $m.Groups[1].Value }
    }
    return ""
}

function Get-AppProcesses {
    $name = [IO.Path]::GetFileNameWithoutExtension($ExeName)
    return @(Get-Process -Name $name -ErrorAction SilentlyContinue)
}

function Set-Status([string]$State, [string]$Version, [string]$Message, [int]$GraceSec = 0) {
    $now = [DateTime]::UtcNow
    $status = [ordered]@{
        state        = $State
        version      = $Version
        message      = $Message
        updated_utc  = $now.ToString("o")
        deadline_utc = $(if ($GraceSec -gt 0) { $now.AddSeconds($GraceSec).ToString("o") } else { "" })
    }
    Write-JsonAtomic $StatusPath $status
}

# Failure of a scheduled run, shown to the user by the app (status\last_error.json).
$ErrorFile = Join-Path $StatusDir "last_error.json"
function Set-UpdateError([string]$Message) {
    try { Write-JsonAtomic $ErrorFile ([ordered]@{ message = $Message; time_utc = [DateTime]::UtcNow.ToString("o") }) } catch { }
}
function Clear-UpdateError {
    try { if (Test-Path -LiteralPath $ErrorFile) { Remove-Item -Force -LiteralPath $ErrorFile } } catch { }
}

function Get-FileSha256([string]$Path) {
    if (Get-Command Get-FileHash -ErrorAction SilentlyContinue) {
        return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
    }
    $sha = [Security.Cryptography.SHA256]::Create()
    $fs = [IO.File]::OpenRead($Path)
    try { return ([BitConverter]::ToString($sha.ComputeHash($fs)) -replace "-", "").ToLowerInvariant() }
    finally { $fs.Dispose(); $sha.Dispose() }
}

# --------------------------------------------------------------------------
# share access (workgroup-friendly)
# --------------------------------------------------------------------------

$script:MappedShare = $null

function Connect-ShareAs([string]$Share, [string]$User, [string]$Pass) {
    [void](Invoke-Exe "net.exe" @("use", $Share, "/delete", "/y"))
    $r = Invoke-Exe "net.exe" @("use", $Share, $Pass, "/user:$User", "/persistent:no")
    if ($r.Code -ne 0 -and (Get-NetErrorCode $r.Output) -eq "1219") {
        # This session already talks to the server under another identity
        # (for SYSTEM usually the computer account). Drop every connection to
        # that server in THIS logon session only, then try once more.
        $host_ = $Share.TrimStart("\").Split("\")[0]
        $server = "\\" + $host_
        [void](Invoke-Exe "net.exe" @("use", ($server + "\IPC$"), "/delete", "/y"))
        [void](Invoke-Exe "net.exe" @("use", $server, "/delete", "/y"))
        $list = Invoke-Exe "net.exe" @("use")
        foreach ($m in [regex]::Matches($list.Output, '(\\\\' + [regex]::Escape($host_) + '\\[^\s]+)')) {
            [void](Invoke-Exe "net.exe" @("use", $m.Value, "/delete", "/y"))
        }
        $r = Invoke-Exe "net.exe" @("use", $Share, $Pass, "/user:$User", "/persistent:no")
    }
    return $r
}

function Open-Share($Config) {
    $share = [string](Get-Prop $Config "share" $DefaultShare)
    $share = $share.TrimEnd("\")
    $user = [string](Get-Prop $Config "user" "")
    $pass = [string](Get-Prop $Config "password" "")

    if ($user -and -not $pass) {
        # net.exe would stop and wait for a typed password on a service account
        throw "No password is stored for the update account $user (updater settings are incomplete)."
    }
    if ($user -and ($env:OS -eq "Windows_NT")) {
        # ALWAYS connect with the configured read-only account. As SYSTEM, a
        # plain Test-Path can "see" the share through the computer account,
        # which has no read rights - files then fail with "Access is denied".
        # The connection lives only in the SYSTEM logon session.
        $r = Connect-ShareAs $share $user $pass
        if ($r.Code -ne 0) {
            throw (Get-NetFailText $share $user $r.Output)
        }
        $script:MappedShare = $share
    }
    if (Test-Path -LiteralPath (Join-Path $share $ManifestName)) { return $share }
    if (Test-Path -LiteralPath $share) { return $share }
    throw "Update share not reachable: $share"
}

function Close-Share {
    if ($script:MappedShare -and ($env:OS -eq "Windows_NT")) {
        [void](Invoke-Exe "net.exe" @("use", $script:MappedShare, "/delete", "/y"))
    }
}

# --------------------------------------------------------------------------
# release (manifest) - ONE code path for the real update and for the test
# --------------------------------------------------------------------------

$TaskName    = "\GelaPM\PM System Updater"
$LastRunPath = Join-Path $StatusDir "last_run.json"   # result of every scheduled run (read by the tester)

function Get-UnixNow { return [int64](([DateTime]::UtcNow.Ticks - 621355968000000000) / 10000000) }

function Get-Release([string]$Share) {
    # $null when no release is published; throws a clear message when the manifest is unusable
    $manifestPath = Join-Path $Share $ManifestName
    if (-not (Test-Path -LiteralPath $manifestPath)) { return $null }
    try { $manifest = Read-JsonFile $manifestPath }
    catch { throw "$ManifestName on the update share cannot be read: $($_.Exception.Message)" }
    if ($null -eq $manifest) { throw "$ManifestName on the update share is empty." }
    $appName = [string](Get-Prop $manifest "app_name" $AppName)
    if ($appName -ne $AppName) { throw "The release on the update share belongs to '$appName', not '$AppName'." }
    $version = [string](Get-Prop $manifest "version" "")
    try { [void](ConvertTo-VersionTuple $version) } catch { throw "The release manifest has an invalid version '$version'." }
    $installerName = [string](Get-Prop $manifest "installer" "")
    if (-not $installerName -or $installerName -match '[\\/]' -or $installerName.StartsWith(".") -or
        -not $installerName.ToLowerInvariant().EndsWith(".exe")) {
        throw "The release manifest has an invalid installer name '$installerName'."
    }
    $sha = ([string](Get-Prop $manifest "sha256" "")).ToLowerInvariant()
    if ($sha -notmatch '^[0-9a-f]{64}$') { throw "The release manifest has no valid SHA-256 checksum." }
    return New-Object PSObject -Property @{
        Version = $version; Installer = $installerName; Sha = $sha; Path = (Join-Path $Share $installerName)
    }
}

function Copy-Verified($Release, [string]$Target) {
    # copy the installer from the share and check its SHA-256; nothing is left behind on failure
    if (-not (Test-Path -LiteralPath $Release.Path)) {
        throw "Release $($Release.Version) is listed on the update share, but its installer $($Release.Installer) is missing."
    }
    $partial = $Target + ".partial"
    try {
        Copy-Item -LiteralPath $Release.Path -Destination $partial -Force
        $actual = Get-FileSha256 $partial
    } catch {
        Remove-Item -Force -LiteralPath $partial -ErrorAction SilentlyContinue
        throw "Copying the installer $($Release.Installer) from the update share failed: $($_.Exception.Message)"
    }
    if ($actual -ne $Release.Sha) {
        Remove-Item -Force -LiteralPath $partial -ErrorAction SilentlyContinue
        throw "The installer $($Release.Installer) on the update share does not match its SHA-256 checksum (damaged or incomplete copy). Publish the release again."
    }
    Move-Item -Force -LiteralPath $partial -Destination $Target
}

function Get-NetFailText([string]$Share, [string]$User, [string]$Out) {
    $err = Get-NetErrorCode $Out
    if ($err -eq "1219") {
        return "Windows keeps another connection to the server open, so the update account cannot log in (error 1219). Restart the PC and run the installer again."
    }
    if ($err -in @("1326", "86", "1327", "1330", "1331", "1909")) {
        return "The server rejected the update account $User (wrong user name or password, or the account is locked/expired)."
    }
    if ($err -in @("53", "64", "67", "1231", "1232", "1311")) {
        return "Cannot reach $Share (network cable, server off, or share missing)."
    }
    return "net use $Share as $User failed: $Out"
}

# --------------------------------------------------------------------------
# real update (scheduled task)
# --------------------------------------------------------------------------

$script:Run = [ordered]@{ started_unix = [int64]0; finished_unix = [int64]0; result = "running"; installed = ""; offered = ""; message = "" }
function Save-Run { try { Write-JsonAtomic $LastRunPath $script:Run } catch { } }
function Set-RunResult([string]$Result, [string]$Message = "") { $script:Run.result = $Result; $script:Run.message = $Message }

function Invoke-Update {
    $installed = Get-InstalledVersion
    $script:Run.installed = $installed

    $config = Read-JsonFile $ConfigPath
    if ((Get-Prop $config "enabled" $true) -eq $false) {
        Write-Log "Updater disabled in config."
        Set-RunResult "disabled" "Automatic updates are switched off in config.json."
        return 0
    }
    $grace = [int](Get-Prop $config "grace_seconds" $DefaultGraceSec)

    $share = Open-Share $config
    Clear-UpdateError       # the update share opened with the update account: the connection is healthy
    $release = Get-Release $share
    if ($null -eq $release) {
        Write-Log "No manifest at $(Join-Path $share $ManifestName)"
        Set-RunResult "no_release" "No release is published on the update share yet."
        return 0
    }
    $newVersion = $release.Version
    $script:Run.offered = $newVersion

    if ((Compare-Version $newVersion $installed) -le 0) {
        Write-Log "Up to date (installed $installed, offered $newVersion)."
        $st = Read-JsonFile $StatusPath
        if ((Get-Prop $st "state" "") -in @("pending", "installing")) { Set-Status "idle" $installed "" }
        Set-RunResult "up_to_date"
        return 0
    }

    # attempt counter: give up on a broken release after $MaxAttempts installer runs
    $state = Read-JsonFile $StatePath
    $attempts = 0
    if ((Get-Prop $state "version" "") -eq $newVersion) { $attempts = [int](Get-Prop $state "attempts" 0) }
    if ($attempts -ge $MaxAttempts) {
        $msg = "Version $newVersion failed to install $attempts times; waiting for a new release."
        Write-Log $msg
        Set-UpdateError $msg
        Set-RunResult "gave_up" $msg
        return 0
    }

    # copy + verify (a network error here is NOT counted as a failed release)
    $target = Join-Path $CacheDir $release.Installer
    Write-Log "Update $installed -> $newVersion : copying $($release.Path)"
    Copy-Verified $release $target
    Get-ChildItem -LiteralPath $CacheDir -Filter "*.exe" | Where-Object { $_.Name -ne $release.Installer } |
        Remove-Item -Force -ErrorAction SilentlyContinue

    # give running instances time to save and close
    if (@(Get-AppProcesses).Count -gt 0) {
        Write-Log "PM System is running; announcing update with $grace s countdown."
        Set-Status "pending" $newVersion "" $grace
        $deadline = (Get-Date).AddSeconds($grace + 5)
        while ((Get-Date) -lt $deadline -and @(Get-AppProcesses).Count -gt 0) { Start-Sleep -Seconds 2 }
    }

    Set-Status "installing" $newVersion ""
    # only real installer runs count towards $MaxAttempts
    Write-JsonAtomic $StatePath ([ordered]@{ version = $newVersion; attempts = $attempts + 1 })
    if ($DryRun) {
        Write-Log "DryRun: would run $target"
        Set-Status "done" $newVersion "dry-run"
        Set-RunResult "dry_run"
        return 0
    }

    $log = Join-Path $DataRoot ("install_" + $newVersion + ".log")
    $instArgs = @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
              "/FORCECLOSEAPPLICATIONS", "/SP-", ("/LOG=`"" + $log + "`""))
    Write-Log "Running installer: $target"
    $p = Start-Process -FilePath $target -ArgumentList $instArgs -Wait -PassThru
    if ($p.ExitCode -eq 0) {
        Write-Log "Installed $newVersion."
        Write-JsonAtomic $StatePath ([ordered]@{ version = $newVersion; attempts = 0; installed = $true })
        Set-Status "done" $newVersion ""
        $script:Run.installed = Get-InstalledVersion
        Set-RunResult "installed"
        return 0
    }
    Write-Log "Installer exit code $($p.ExitCode); see $log"
    Set-Status "failed" $newVersion ("exit " + $p.ExitCode)
    $msg = "Installing version " + $newVersion + " failed (installer exit code " + $p.ExitCode + "; log: " + $log + ")."
    Set-UpdateError $msg
    Set-RunResult "install_failed" $msg
    return 2
}

# --------------------------------------------------------------------------
# full test (Setup runs it AS SYSTEM after EVERY install; it never installs)
# Same functions as the real update: settings, task, share login, manifest,
# full installer download into the cache with SHA-256 check, version compare.
# --------------------------------------------------------------------------

$script:CheckLines = New-Object System.Collections.ArrayList
function Add-Check([string]$State, [string]$Text) {
    [void]$script:CheckLines.Add((New-Object PSObject -Property @{ State = $State; Text = $Text }))
}

function Test-UsersCanRead([string]$Path) {
    # $true / $false, or $null when it cannot be evaluated (not Windows)
    if ($env:OS -ne "Windows_NT" -or (Get-Variable -Name IsLinux -ValueOnly -ErrorAction SilentlyContinue)) { return $null }
    try { $acl = Get-Acl -LiteralPath $Path } catch { return $null }
    foreach ($ace in @($acl.Access)) {
        try {
            if ([string]$ace.AccessControlType -ne "Allow") { continue }
            $sid = $ace.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
            if ((@("S-1-5-32-545", "S-1-5-11", "S-1-1-0") -contains $sid) -and (([int]$ace.FileSystemRights -band 1) -ne 0)) {
                return $true
            }
        } catch { }
    }
    return $false
}

function Test-UpdaterTask {
    # the real task must exist, run as SYSTEM, be enabled, have a schedule and start an existing updater
    $q = Invoke-Exe "schtasks.exe" @("/Query", "/TN", $TaskName, "/XML")
    if ($q.Code -ne 0) { Add-Check "FAIL" "The scheduled task $TaskName is missing. Run the installer again."; return }
    try {
        $xml = New-Object Xml.XmlDocument
        $xml.LoadXml([regex]::Replace($q.Output, '^\s*<\?xml[^>]*\?>', ''))
    } catch {
        Add-Check "FAIL" "The scheduled task $TaskName cannot be read: $($_.Exception.Message)"
        return
    }
    $userNode = $xml.SelectSingleNode("//*[local-name()='Principal']/*[local-name()='UserId']")
    $enabledNode = $xml.SelectSingleNode("//*[local-name()='Settings']/*[local-name()='Enabled']")
    $triggers = @($xml.SelectNodes("//*[local-name()='Triggers']/*"))
    $argsNode = $xml.SelectSingleNode("//*[local-name()='Exec']/*[local-name()='Arguments']")
    $problems = @()
    $uid = ""
    if ($null -ne $userNode) { $uid = $userNode.InnerText.Trim() }
    if ($uid -notmatch '^(S-1-5-18|SYSTEM|NT AUTHORITY\\SYSTEM)$') { $problems += "it does not run as SYSTEM ('$uid')" }
    if ($null -ne $enabledNode -and $enabledNode.InnerText.Trim() -eq "false") { $problems += "it is disabled" }
    if ($triggers.Count -lt 1) { $problems += "it has no schedule" }
    $scriptPath = ""
    if ($null -ne $argsNode -and $argsNode.InnerText -match '-File\s+"([^"]+)"') { $scriptPath = $Matches[1] }
    if (-not $scriptPath -or -not (Test-Path -LiteralPath $scriptPath)) { $problems += "it does not start an existing PMUpdater.ps1 ('$scriptPath')" }
    if ($problems.Count -gt 0) {
        Add-Check "FAIL" ("The scheduled task $TaskName is wrong: " + ($problems -join "; ") + ". Run the installer again.")
    } else {
        Add-Check "OK" "Scheduled task: enabled, runs as SYSTEM, $($triggers.Count) schedule(s)"
    }

    # signed-in users must be able to START it: PM System asks for a check when it opens
    $canStart = $null
    try {
        $svc = New-Object -ComObject Schedule.Service
        $svc.Connect()
        $canStart = Test-RunRight ([string]$svc.GetFolder("\GelaPM").GetTask("PM System Updater").GetSecurityDescriptor(4))
    } catch { }
    if ($canStart -is [bool]) {
        if ($canStart) { Add-Check "OK" "Users can start the update check when PM System opens" }
        else { Add-Check "WARN" "Users cannot start the update check when PM System opens (updates still arrive every 15 minutes). Run the installer again." }
    }
}

function Test-RunRight([string]$Sddl) {
    # an allow ACE for signed-in users / users / everyone that includes "execute"
    foreach ($m in [regex]::Matches($Sddl, '\(A;[^;]*;([^;]*);[^;]*;[^;]*;(AU|BU|IU|WD)\)')) {
        $r = $m.Groups[1].Value
        if ($r -match '^0x([0-9a-fA-F]+)$') {
            $v = [Convert]::ToInt64($Matches[1], 16)
            if (($v -band 0x20) -or ($v -band 0x20000000) -or ($v -band 0x10000000)) { return $true }
        } elseif ($r -match 'GX|GA|FA|FX') { return $true }
    }
    return $false
}

function Test-ShareChain($Config) {
    $share = ([string](Get-Prop $Config "share" $DefaultShare)).TrimEnd("\")
    $user  = [string](Get-Prop $Config "user" "")
    $pass  = [string](Get-Prop $Config "password" "")
    if ($user -and -not $pass) { Add-Check "FAIL" "No password is stored for the update account $user. Run the installer again."; return }
    if ($user) {
        # always log in with the configured account, exactly like the real update
        $r = Connect-ShareAs $share $user $pass
        if ($r.Code -ne 0) { Add-Check "FAIL" (Get-NetFailText $share $user $r.Output); return }
        $script:MappedShare = $share
    }
    if (-not (Test-Path -LiteralPath $share)) { Add-Check "FAIL" "Update share not reachable: $share"; return }
    $who = $(if ($user) { $user } else { "this PC's own account" })
    Add-Check "OK" "Update share $share opened as $who"

    try { $release = Get-Release $share } catch { Add-Check "FAIL" $_.Exception.Message; return }
    if ($null -eq $release) {
        Add-Check "WARN" "No release is published on the update share yet, so the download could not be tested. Publish one with release.bat."
        return
    }

    # A silent update has just downloaded and verified this installer: check that copy.
    # Otherwise download the WHOLE installer into the cache and check it, then delete it.
    $done = $false
    $cached = Join-Path $CacheDir $release.Installer
    if (Test-Path -LiteralPath $cached) {
        try {
            if ((Get-FileSha256 $cached) -eq $release.Sha) {
                Add-Check "OK" "Release $($release.Version): installer downloaded by this update, checksum verified"
                $done = $true
            }
        } catch { }
    }
    if (-not $done) {
        if (-not (Test-Path -LiteralPath $CacheDir)) { New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null }
        $probe = Join-Path $CacheDir ("selftest_" + $release.Installer)
        try {
            Copy-Verified $release $probe
            Add-Check "OK" "Release $($release.Version): installer downloaded to the local cache, checksum verified"
        } catch {
            Add-Check "FAIL" $_.Exception.Message
            return
        } finally {
            Remove-Item -Force -LiteralPath $probe -ErrorAction SilentlyContinue
        }
    }

    $installed = Get-InstalledVersion
    if ((Compare-Version $release.Version $installed) -gt 0) {
        Add-Check "OK" "Release $($release.Version) is newer than this PC ($installed): it will be installed within 15 minutes"
    } else {
        Add-Check "OK" "This PC has the latest release ($installed)"
    }
}

function Invoke-Check {
    $script:CheckLines.Clear()
    $asSystem = ([Environment]::UserName -match '\$$|^SYSTEM$')

    $config = $null
    try { $config = Read-JsonFile $ConfigPath } catch { }
    if ($null -eq $config) {
        Add-Check "FAIL" "No updater settings ($ConfigPath). Run the installer again."
    } else {
        $u = [string](Get-Prop $config "user" "")
        Add-Check "OK" ("Settings: share " + ([string](Get-Prop $config "share" $DefaultShare)) + $(if ($u) { ", account $u" } else { "" }))
        if ((Get-Prop $config "enabled" $true) -eq $false) { Add-Check "FAIL" "Automatic updates are switched off in $ConfigPath." }
    }

    Test-UpdaterTask

    $canRead = Test-UsersCanRead $StatusDir
    if ($canRead -is [bool]) {
        if ($canRead) { Add-Check "OK" "Status folder readable by users (the app can show update messages)" }
        else { Add-Check "FAIL" "Users cannot read $StatusDir, so PM System cannot show update messages. Run the installer again." }
    }

    if ($null -ne $config) { Test-ShareChain $config }

    $fails = @($script:CheckLines | Where-Object { $_.State -eq "FAIL" })
    $warns = @($script:CheckLines | Where-Object { $_.State -eq "WARN" })
    $how = $(if ($asSystem) { "as SYSTEM, like the real updater" } else { "as " + [Environment]::UserName + ", NOT as SYSTEM" })
    if ($fails.Count -gt 0) { $head = "FAIL|" + $fails[0].Text }
    elseif ($warns.Count -gt 0) { $head = "WARN|" + $warns[0].Text }
    else { $head = "OK|Automatic updates work on this PC (full test $how)." }
    $lines = @($head) + @($script:CheckLines | ForEach-Object { "- [" + $_.State + "] " + $_.Text })
    return ($lines -join "`r`n")
}

if ($CheckOnly) {
    $result = "FAIL|Unknown error"
    try { $result = Invoke-Check } catch { $result = "FAIL|" + $_.Exception.Message }
    finally { Close-Share }
    Write-Log ("Setup check: " + (($result -split "`r?`n") -join " / "))
    if ($ResultFile) {
        # written in one step, so a reader never sees half a result
        $tmp = $ResultFile + ".tmp"
        [IO.File]::WriteAllText($tmp, $result, (New-Object Text.UTF8Encoding($true)))
        Move-Item -Force -LiteralPath $tmp -Destination $ResultFile
    }
    if ($result.StartsWith("FAIL")) { exit 1 } else { exit 0 }
}

# single instance per machine
$mutex = New-Object Threading.Mutex($false, "Global\GelaPM_Updater")
if (-not $mutex.WaitOne(0)) { exit 0 }
foreach ($d in @($DataRoot, $StatusDir, $CacheDir)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
}
$script:Run.started_unix = Get-UnixNow
Save-Run
$code = 0
try {
    $code = Invoke-Update
} catch {
    Write-Log ("ERROR: " + $_.Exception.Message)
    Set-UpdateError ("Automatic update check failed: " + $_.Exception.Message)
    Set-RunResult "error" $_.Exception.Message
    try {
        $st = Read-JsonFile $StatusPath
        if ((Get-Prop $st "state" "") -in @("pending", "installing")) { Set-Status "failed" (Get-Prop $st "version" "") $_.Exception.Message }
    } catch { }
    $code = 1
} finally {
    Close-Share
    $script:Run.finished_unix = Get-UnixNow
    Save-Run
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
exit $code
