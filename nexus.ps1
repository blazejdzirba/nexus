# NEXUS-AI Control Utility
param (
    [Parameter(Mandatory=$false)][string]$run
)

# 1. Automatyczna aktywacja środowiska i ścieżek
if (-not $env:VIRTUAL_ENV) {
    Write-Host "[NEXUS] Aktywacja venv..." -ForegroundColor Cyan
    . .\venv\Scripts\activate
}
$env:PYTHONPATH = (Get-Item .).FullName

# 2. Logika komend
switch ($run) {
    "feed"    { python core/api/data_feed.py }
    "test"    { python backtester.py }
    "live"    { python main.py }
    "clean"   { 
        Remove-Item -Path ./logs/trades/*.json -Force
        Write-Host "[NEXUS] Logi wyczyszczone." -ForegroundColor Yellow 
    }
    default   { 
        Write-Host "Użycie: .\nexus.ps1 [feed | test | live | clean]" -ForegroundColor White
        Write-Host "Status: Środowisko gotowe, PYTHONPATH ustawiony." -ForegroundColor Green
    }
}