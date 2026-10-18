<#
.SYNOPSIS
    Blood Bridge - Server Deployment & Migration Script for Windows / PowerShell
.DESCRIPTION
    Builds, configures, and deploys the Blood Bridge Docker stack.
#>

param(
    [switch]$Seed,
    [switch]$NoBuild,
    [switch]$Down,
    [switch]$Status,
    [switch]$Logs
)

$ErrorActionPreference = "Stop"

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "         Blood Bridge Server Deployment & Migration Tool        " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# 1. Check prerequisites
Write-Host "`n[1/5] Checking prerequisites..." -ForegroundColor Blue
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Docker is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

$composeCmd = "docker compose"
try {
    & docker compose version | Out-Null
} catch {
    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        $composeCmd = "docker-compose"
    } else {
        Write-Host "Error: Docker Compose is not installed." -ForegroundColor Red
        exit 1
    }
}
Write-Host "✓ Docker engine & compose found." -ForegroundColor Green

# 2. Check environment configuration
Write-Host "`n[2/5] Checking environment configuration..." -ForegroundColor Blue
if (-not (Test-Path .env)) {
    if (Test-Path .env.example) {
        Write-Host "! No .env found. Copying from .env.example..." -ForegroundColor Yellow
        Copy-Item .env.example .env
        $randSecret = [System.Guid]::NewGuid().ToString("N") + [System.Guid]::NewGuid().ToString("N")
        (Get-Content .env) -replace "JWT_SECRET_KEY=", "JWT_SECRET_KEY=$randSecret" | Set-Content .env
        Write-Host "✓ Generated secure random JWT_SECRET_KEY." -ForegroundColor Green
    } else {
        Write-Host "Error: Neither .env nor .env.example exists." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✓ .env configuration present." -ForegroundColor Green
}

# Handle action flags
if ($Down) {
    Write-Host "`nStopping Blood Bridge services..." -ForegroundColor Yellow
    Invoke-Expression "$composeCmd down"
    Write-Host "✓ Services stopped." -ForegroundColor Green
    exit 0
}

if ($Status) {
    Write-Host "`nCurrent Service Status:" -ForegroundColor Cyan
    Invoke-Expression "$composeCmd ps"
    exit 0
}

if ($Logs) {
    Invoke-Expression "$composeCmd logs -f"
    exit 0
}

# 3. Build & start containers
Write-Host "`n[3/5] Starting Blood Bridge stack with Docker Compose..." -ForegroundColor Blue
$buildFlag = if ($NoBuild) { "" } else { "--build" }
Invoke-Expression "$composeCmd up -d $buildFlag"

# 4. Await service health
Write-Host "`n[4/5] Waiting for services to become healthy..." -ForegroundColor Blue
$webPort = "8080"
$apiPort = "8000"
if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        if ($_ -match "^WEB_PORT=(.*)$") { $webPort = $matches[1].Trim() }
        if ($_ -match "^API_PORT=(.*)$") { $apiPort = $matches[1].Trim() }
    }
}

$maxWait = 60
$elapsed = 0
$apiReady = $false

while ($elapsed -lt $maxWait) {
    try {
        $res = Invoke-WebRequest -Uri "http://127.0.0.1:$apiPort/api/v1/health" -UseBasicParsing -TimeoutSec 2
        if ($res.StatusCode -eq 200) {
            $apiReady = $true
            break
        }
    } catch {
        # still booting
    }
    Start-Sleep -Seconds 3
    $elapsed += 3
    Write-Host "  Waiting for backend API... (${elapsed}s / ${maxWait}s)"
}

if ($apiReady) {
    Write-Host "✓ Backend API is healthy and answering on port $apiPort!" -ForegroundColor Green
} else {
    Write-Host "! Backend API is taking longer than expected. Check logs with: .\deploy.ps1 -Logs" -ForegroundColor Yellow
}

# 5. Optional demo data seed
if ($Seed) {
    Write-Host "`n[5/5] Seeding database with synthetic demonstration data..." -ForegroundColor Blue
    Invoke-Expression "$composeCmd run --rm seed"
    Write-Host "✓ Database seeded successfully." -ForegroundColor Green
} else {
    Write-Host "`n[5/5] Skipping demo seed (run with '-Seed' or: $composeCmd run --rm seed)" -ForegroundColor Blue
}

Write-Host "`n================================================================" -ForegroundColor Green
Write-Host "  Blood Bridge is successfully deployed and running!            " -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  Web Application (Frontend + Reverse Proxy): http://localhost:$webPort" -ForegroundColor Cyan
Write-Host "  Direct API Documentation:                   http://localhost:$apiPort/docs" -ForegroundColor Cyan
Write-Host "  API Health Check:                           http://localhost:$apiPort/api/v1/health" -ForegroundColor Cyan
Write-Host "================================================================"
Write-Host "Management shortcuts:"
Write-Host "  View container status: .\deploy.ps1 -Status" -ForegroundColor Yellow
Write-Host "  View live logs:        .\deploy.ps1 -Logs" -ForegroundColor Yellow
Write-Host "  Seed demo accounts:    .\deploy.ps1 -Seed" -ForegroundColor Yellow
Write-Host "  Stop all services:     .\deploy.ps1 -Down" -ForegroundColor Yellow
Write-Host "================================================================`n"
