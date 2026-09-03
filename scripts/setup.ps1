# PR-Warden — Windows setup (PowerShell)
# Registers the GitHub App, starts tunnel + server, and installs a logon
# auto-start task so the reviewer survives reboots.
#
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "=== PR-Warden setup (Windows) ===" -ForegroundColor Cyan

# 1. Python venv + engine
if (-not (Test-Path ".venv")) {
    Write-Host "[*] Creating venv..."
    py -3.12 -m venv .venv
}
& ".venv\Scripts\python.exe" -m pip install -q --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -q "pr-agent"

# 2. Config
if (-not (Test-Path "config\warden.toml")) {
    Copy-Item "config\warden.toml.example" "config\warden.toml"
}
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[*] Created .env — edit GITHUB_APP_ID / WEBHOOK_SECRET after app registration." -ForegroundColor Yellow
}

# 3. Python exec path for scheduled task
$PyExe = (Resolve-Path ".venv\Scripts\python.exe").Path

# 4. Generate manifest
Write-Host "[*] Generating GitHub App manifest..."
& $PyExe src\manifest.py create --base-url "http://127.0.0.1:3000" --name ($env:GITHUB_APP_NAME ?? "pr-warden")

# 5. Build autostart script (starts tunnel + server at logon)
$serverPy = Join-Path $Root "src\run_server.py"
$startAll = @"
@echo off
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
REM Ollama
where ollama >nul 2>&1 && start "" ollama serve
timeout /t 4 >nul
REM Tailscale Funnel (permanent public URL) — fall back to ngrok if absent
where tailscale >nul 2>&1 && tailscale funnel --bg ${env:PORT:-3000} >nul 2>&1
where ngrok >nul 2>&1 && start "" ngrok http ${env:PORT:-3000} >nul 2>&1
REM Server
"$PyExe" "$serverPy"
"@
$startAll | Set-Content "start_all.cmd" -Encoding ascii

# 6. Register logon auto-start task
$action  = New-ScheduledTaskAction -Execute "$Root\start_all.cmd" -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName "PR-Warden-AutoReview" -Action $action -Trigger $trigger -Settings $settings -Description "PR-Warden AI reviewer autostart" -Force | Out-Null

Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Cyan
Write-Host "  1. Register the GitHub App from the manifest, then:"
Write-Host "     .venv\Scripts\python.exe src\manifest.py capture"
Write-Host "  2. Start the server:  .venv\Scripts\python.exe src\run_server.py"
Write-Host "  3. Install the app on your repos — open a test PR and watch it get reviewed."
Write-Host "  Auto-start task 'PR-Warden-AutoReview' installed for your logon." -ForegroundColor Green
