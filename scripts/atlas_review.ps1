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
try {
    $output = & $atlasExe brain report --period daily 2>&1 | Out-String
    Add-Content -Path $logFile -Value "[$timestamp] $($output.Trim())"
    Add-Content -Path $logFile -Value "---"
} catch {
    Add-Content -Path $logFile -Value "[$timestamp] ERROR: $_"
}
