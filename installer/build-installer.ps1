# Build installer for CryptoConsult
# Requires: Inno Setup 6, Node.js

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$InstallerDir = $PSScriptRoot
$IssFile = Join-Path $InstallerDir "CryptoConsult.iss"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$FrontendStandaloneDir = Join-Path $ProjectRoot "dist\frontend-standalone"

# Check Inno Setup
$iscc = $null
try {
    $iscc = (Get-Command iscc -ErrorAction Stop).Source
} catch {
    $isccPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if (Test-Path $isccPath) {
        $iscc = $isccPath
    } else {
        Write-Error "Inno Setup not found. Install from https://jrsoftware.org/isdl.php"
    }
}

Write-Host "Building installer..." -ForegroundColor Cyan
Write-Host "  Project: $ProjectRoot"
Write-Host "  Script: $IssFile"

# 1. Production build frontend (standalone)
Write-Host "`n[1/3] Building frontend (standalone)..." -ForegroundColor Yellow
Push-Location $FrontendDir
try {
    if (-not (Test-Path "node_modules")) {
        Write-Host "  npm install..."
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
    }
    Write-Host "  npm run build..."
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
    if (-not (Test-Path ".next\standalone\server.js")) {
        throw "Standalone server.js not found. Check output: standalone in next.config.js"
    }
} finally {
    Pop-Location
}

# 2. Prepare standalone folder for installer
Write-Host "`n[2/3] Preparing frontend-standalone..." -ForegroundColor Yellow
Remove-Item -Path $FrontendStandaloneDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $FrontendStandaloneDir | Out-Null
Copy-Item -Path "$FrontendDir\.next\standalone\*" -Destination $FrontendStandaloneDir -Recurse -Force
New-Item -ItemType Directory -Force -Path "$FrontendStandaloneDir\.next" | Out-Null
Copy-Item -Path "$FrontendDir\.next\static" -Destination "$FrontendStandaloneDir\.next\static" -Recurse -Force
if (Test-Path "$FrontendDir\public") {
    Copy-Item -Path "$FrontendDir\public\*" -Destination "$FrontendStandaloneDir\public" -Recurse -Force -ErrorAction SilentlyContinue
}
Copy-Item -Path "$FrontendDir\start-frontend.bat" -Destination $FrontendStandaloneDir -Force
Write-Host "  Done: $FrontendStandaloneDir"

# 3. Build Inno Setup installer
Write-Host "`n[3/3] Building Inno Setup installer..." -ForegroundColor Yellow
$OutputDir = Join-Path $ProjectRoot "dist\installer"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

& $iscc $IssFile

if ($LASTEXITCODE -ne 0) {
    exit 1
}
Write-Host "`nInstaller created: $OutputDir" -ForegroundColor Green
Get-ChildItem -Path $OutputDir -Filter *.exe | ForEach-Object { Write-Host "  -" $_.Name }