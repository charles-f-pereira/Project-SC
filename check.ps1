# check.ps1 - Run frontend + backend checks from repo root
$ErrorActionPreference = "Stop"

function Run-Step([string]$Name, [scriptblock]$Command) {
  Write-Host ""
  Write-Host "=== $Name ===" -ForegroundColor Cyan
  & $Command
  if ($LASTEXITCODE -ne 0) {
    throw "Step failed: $Name (exit code $LASTEXITCODE)"
  }
}

Run-Step "Frontend: npm run check" {
  Push-Location "frontend"
  try {
    npm run check
  } finally {
    Pop-Location
  }
}

Run-Step "Backend: ruff format" {
  Push-Location "backend"
  try {
    ruff format .
  } finally {
    Pop-Location
  }
}

Run-Step "Backend: ruff check (no auto-fix in check gate)" {
  Push-Location "backend"
  try {
    ruff check .
  } finally {
    Pop-Location
  }
}

Run-Step "Backend: pyright" {
  Push-Location "backend"
  try {
    pyright
  } finally {
    Pop-Location
  }
}

Run-Step "Backend: pytest" {
  Push-Location "backend"
  try {
    pytest
    if ($LASTEXITCODE -eq 5) {
      Write-Host "No tests collected (pytest exit code 5) - skipping failure." -ForegroundColor Yellow
      $global:LASTEXITCODE = 0
    }
  } finally {
    Pop-Location
  }
}

Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green