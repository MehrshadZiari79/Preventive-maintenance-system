<#
  PM System - "updating, please wait" window (runs as the logged-in user).

  PM_System.exe starts it just before it closes for an update (after the
  2-minute countdown, or right away when a newer version is found at start-up).
  It shows what the SYSTEM updater writes to status.json (preparing ->
  installing -> done / failed), cannot be closed by mistake, and re-opens
  PM System at the end with --after-update.

  The app passes this text with -EncodedCommand, so no script-file execution
  policy is involved and Setup may replace this file meanwhile.
  Input (environment): GELAPM_APP_EXE, GELAPM_STATUS, GELAPM_VERSION
#>
$ErrorActionPreference = "SilentlyContinue"
$AppExe = [string]$env:GELAPM_APP_EXE
$StatusPath = [string]$env:GELAPM_STATUS
if (-not $StatusPath) { $StatusPath = Join-Path $env:ProgramData "GelaDairy\PMSystem\updater\status\status.json" }
$Want = [string]$env:GELAPM_VERSION

function Fa([string]$s) {
    $digits = [string][char]0x06F0 + [char]0x06F1 + [char]0x06F2 + [char]0x06F3 + [char]0x06F4 + [char]0x06F5 + [char]0x06F6 + [char]0x06F7 + [char]0x06F8 + [char]0x06F9
    $out = New-Object Text.StringBuilder
    foreach ($c in $s.ToCharArray()) {
        if ($c -ge [char]'0' -and $c -le [char]'9') { [void]$out.Append($digits[[int]$c - 48]) } else { [void]$out.Append($c) }
    }
    return $out.ToString()
}

# What to show for one status.json reading (kept apart from the window so it can be tested).
#   Kind: wait = keep waiting, done / failed = finished, open = nothing (more) to wait for
function Get-UpdateStep([string]$State, [string]$Version, [bool]$Seen, [int]$Elapsed, [string]$Want) {
    $v = $(if ($Version) { " " + (Fa $Version) } else { "" })
    if ($Elapsed -ge 900) {
        return @{ Kind = "open"; Seen = $Seen; Text = "به‌روزرسانی بیش از حد طول کشید؛ سیستم PM باز می‌شود." }
    }
    if ($State -eq "pending") {
        return @{ Kind = "wait"; Seen = $true; Text = "در حال آماده‌سازی نصب نسخه$v …" }
    }
    if ($State -eq "installing") {
        return @{ Kind = "wait"; Seen = $true; Text = "در حال نصب نسخه$v …" }
    }
    # "done"/"failed" may be left over from an earlier update: trust it only for this update
    $ours = $Seen -or ($Want -and $Version -eq $Want) -or $Elapsed -ge 10
    if ($State -eq "done" -and $ours) {
        return @{ Kind = "done"; Seen = $Seen; Text = "به‌روزرسانی انجام شد. سیستم PM باز می‌شود…" }
    }
    if ($State -eq "failed" -and $ours) {
        return @{ Kind = "failed"; Seen = $Seen; Text = "به‌روزرسانی انجام نشد؛ سیستم PM با نسخه فعلی باز می‌شود." }
    }
    if ($Elapsed -ge 30) {
        # the updater did not start an installation (nothing newer, or it was cancelled)
        return @{ Kind = "open"; Seen = $Seen; Text = "سیستم PM باز می‌شود…" }
    }
    return @{ Kind = "wait"; Seen = $Seen; Text = "در حال آماده‌سازی به‌روزرسانی…" }
}

if ($env:GELAPM_PROGRESS_NO_UI -eq "1") { return }   # tests load only the functions above

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()

$S = @{ T0 = Get-Date; Seen = $false; EndAt = $null; Started = $false; Allow = $false }
$navy = [Drawing.Color]::FromArgb(26, 42, 68)
$gray = [Drawing.Color]::FromArgb(95, 99, 104)

$form = New-Object Windows.Forms.Form
$form.Text = "به‌روزرسانی سیستم PM"
$form.RightToLeft = [Windows.Forms.RightToLeft]::Yes
$form.RightToLeftLayout = $true
$form.FormBorderStyle = [Windows.Forms.FormBorderStyle]::FixedDialog
$form.MaximizeBox = $false
$form.StartPosition = [Windows.Forms.FormStartPosition]::CenterScreen
$form.ClientSize = New-Object Drawing.Size(480, 232)
$form.BackColor = [Drawing.Color]::White
$form.TopMost = $true
try { if ($AppExe) { $form.Icon = [Drawing.Icon]::ExtractAssociatedIcon($AppExe) } } catch { }

function New-Label([int]$Y, [int]$H, [float]$Size, [bool]$Bold, $Color, [string]$Text) {
    $l = New-Object Windows.Forms.Label
    $l.AutoSize = $false
    $l.Location = New-Object Drawing.Point(20, $Y)
    $l.Size = New-Object Drawing.Size(440, $H)
    $style = $(if ($Bold) { [Drawing.FontStyle]::Bold } else { [Drawing.FontStyle]::Regular })
    $l.Font = New-Object Drawing.Font("Tahoma", $Size, $style)
    $l.ForeColor = $Color
    $l.TextAlign = [Drawing.ContentAlignment]::MiddleCenter
    $l.Text = $Text
    $form.Controls.Add($l)
    return $l
}

$head = New-Label 0 56 13 $true ([Drawing.Color]::White) "در حال به‌روزرسانی سیستم PM"
$head.Location = New-Object Drawing.Point(0, 0)
$head.Size = New-Object Drawing.Size(480, 56)
$head.BackColor = $navy
$status = New-Label 70 28 10.5 $true $navy "در حال آماده‌سازی به‌روزرسانی…"
$bar = New-Object Windows.Forms.ProgressBar
$bar.Location = New-Object Drawing.Point(40, 106)
$bar.Size = New-Object Drawing.Size(400, 18)
$bar.Style = [Windows.Forms.ProgressBarStyle]::Marquee
$bar.MarqueeAnimationSpeed = 30
$form.Controls.Add($bar)
$note = New-Label 134 46 9 $false $gray "لطفاً صبر کنید و رایانه را خاموش نکنید.`nاطلاعات پایگاه داده تغییری نمی‌کند و سیستم PM پس از پایان خودکار باز می‌شود."
$clock = New-Label 186 26 9 $false $gray ("زمان سپری‌شده: " + (Fa "00:00"))

function Finish {
    $timer.Stop()
    if (-not $S.Started -and $AppExe -and (Test-Path -LiteralPath $AppExe)) {
        $S.Started = $true
        Start-Process -FilePath $AppExe -ArgumentList "--after-update"
    }
    $S.Allow = $true
    $form.Close()
}

$form.Add_FormClosing({
    param($sender, $e)
    if (-not $S.Allow -and $e.CloseReason -eq [Windows.Forms.CloseReason]::UserClosing) { $e.Cancel = $true }
})

$timer = New-Object Windows.Forms.Timer
$timer.Interval = 1000
$timer.Add_Tick({
    $now = Get-Date
    $el = [int][Math]::Floor(($now - $S.T0).TotalSeconds)
    $clock.Text = "زمان سپری‌شده: " + (Fa ("{0:00}:{1:00}" -f [Math]::Floor($el / 60), ($el % 60)))
    if ($S.EndAt) { if ($now -ge $S.EndAt) { Finish }; return }
    $st = $null
    try { $st = Get-Content -LiteralPath $StatusPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { }
    $state = ""; $ver = ""
    if ($st) { $state = [string]$st.state; $ver = [string]$st.version }
    $step = Get-UpdateStep $state $ver $S.Seen $el $Want
    $S.Seen = [bool]$step.Seen
    $status.Text = $step.Text
    if ($step.Kind -eq "done") {
        $status.ForeColor = [Drawing.Color]::FromArgb(22, 163, 74)
        $bar.Style = [Windows.Forms.ProgressBarStyle]::Continuous; $bar.Value = 100
        $S.EndAt = $now.AddSeconds(3)          # let Setup finish and exit
    } elseif ($step.Kind -eq "failed") {
        $status.ForeColor = [Drawing.Color]::FromArgb(220, 38, 38)
        $bar.Style = [Windows.Forms.ProgressBarStyle]::Continuous; $bar.Value = 0
        $S.EndAt = $now.AddSeconds(6)
    } elseif ($step.Kind -eq "open") {
        $S.EndAt = $now.AddSeconds(2)
    }
})
$timer.Start()
[void]$form.ShowDialog()
$timer.Dispose()
