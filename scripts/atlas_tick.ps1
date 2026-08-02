# Runs one CEOBrain.tick() cycle (plan -> prioritize -> risk-gate ->
# delegate -> monitor, plus every pipeline-advance bridge including
# advance_intelligence) and appends a timestamped log entry.
#
# Registered as the recurring "ATLAS-Tick" Windows Scheduled Task — see
# register_scheduled_tasks.ps1. Every real action this triggers still goes
# through the unmodified RiskPolicy fail-closed gate; this script only
# decides *when* tick() runs, never what it's allowed to do.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$atlasExe = "$env:APPDATA\Python\Python313\Scripts\atlas.exe"
$logDir = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "tick.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

Set-Location $repoRoot
# $ErrorActionPreference = "Stop" applies to cmdlets, not native exes — but
# combined with 2>&1 on a native command, PS 5.1 wraps each stderr line as
# its own terminating ErrorRecord, so the first stderr line aborts the
# pipeline and only that one line ever reaches $output. Relaxed to
# "Continue" for just this call so a real multi-line Python traceback gets
# captured in full instead of truncated to its first line.
$previous = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$output = (& $atlasExe brain tick 2>&1 | Out-String).Trim()
$ErrorActionPreference = $previous

$status = if ($LASTEXITCODE -eq 0) { "" } else { "ERROR (exit $LASTEXITCODE): " }
Add-Content -Path $logFile -Value "[$timestamp] $status$output"
