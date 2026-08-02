# Runs one CEOBrain.review() cycle (evaluate applied proposals, Strategist
# capital reallocation, evidence-gated improvement proposals, executive
# report) and appends the full report output to a timestamped log entry.
#
# Registered as the recurring "ATLAS-Review" Windows Scheduled Task — see
# register_scheduled_tasks.ps1. Runs far less often than ATLAS-Tick: this
# is the slow strategic cycle, not the operational loop.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$atlasExe = "$env:APPDATA\Python\Python313\Scripts\atlas.exe"
$logDir = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "review.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

Set-Location $repoRoot
# See atlas_tick.ps1 for why this is "Continue", not "Stop", around the
# native call — avoids truncating a real multi-line traceback to its first
# line (PS 5.1's 2>&1-on-native-exe behavior, documented gotcha).
$previous = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$output = (& $atlasExe brain report --period daily 2>&1 | Out-String).Trim()
$ErrorActionPreference = $previous

$status = if ($LASTEXITCODE -eq 0) { "" } else { "ERROR (exit $LASTEXITCODE): " }
Add-Content -Path $logFile -Value "[$timestamp] $status$output"
Add-Content -Path $logFile -Value "---"
