# Registers (or re-registers, idempotently) the two Windows Scheduled Tasks
# that make ATLAS run continuously: ATLAS-Tick (operational loop, every 30
# minutes) and ATLAS-Review (strategic cycle, daily at 06:00). Both survive
# reboots and don't depend on any process - Claude Code, a terminal, this
# script itself - staying open.
#
# Safe to re-run: unregisters an existing task of the same name before
# creating it fresh, rather than erroring or duplicating.
#
# To check status:   Get-ScheduledTask -TaskName "ATLAS-Tick","ATLAS-Review"
# To pause:           Disable-ScheduledTask -TaskName "ATLAS-Tick"
# To remove entirely: Unregister-ScheduledTask -TaskName "ATLAS-Tick" -Confirm:$false

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Register-AtlasTask {
    param(
        [string]$Name,
        [string]$ScriptPath,
        $Trigger
    )

    $existing = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false
    }

    $argumentString = '-NoProfile -ExecutionPolicy Bypass -File "' + $ScriptPath + '"'
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argumentString
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $Trigger -Settings $settings -Description "ATLAS Business Operating System" | Out-Null
    Write-Output "Registered: $Name"
}

# Task Scheduler rejects [TimeSpan]::MaxValue as out of range; 10 years is
# the standard practical stand-in for "repeat indefinitely".
$tickTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 3650)
Register-AtlasTask -Name "ATLAS-Tick" -ScriptPath (Join-Path $repoRoot "scripts\atlas_tick.ps1") -Trigger $tickTrigger

$reviewTrigger = New-ScheduledTaskTrigger -Daily -At "06:00"
Register-AtlasTask -Name "ATLAS-Review" -ScriptPath (Join-Path $repoRoot "scripts\atlas_review.ps1") -Trigger $reviewTrigger

Write-Output ""
Write-Output "Done. Verify with: Get-ScheduledTask -TaskName 'ATLAS-Tick','ATLAS-Review' | Select TaskName, State"
