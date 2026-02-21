# =============================================================================
# Start Services - Windows PowerShell
# =============================================================================
# Run this script to start all required services for the AI Agent
# =============================================================================

Write-Host "Starting Biomedical Troubleshooting Agent Services..." -ForegroundColor Cyan

# Check if Docker is running
Write-Host "`n[1/3] Checking Docker..." -ForegroundColor Yellow
try {
    docker info | Out-Null
    Write-Host "  Docker is running" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Start ChromaDB
Write-Host "`n[2/3] Starting ChromaDB..." -ForegroundColor Yellow
docker-compose up -d chromadb
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ChromaDB started on port 8000" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Failed to start ChromaDB" -ForegroundColor Red
    exit 1
}

# Wait for ChromaDB to be ready
Write-Host "`n[3/3] Waiting for ChromaDB to be ready..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 0
while ($attempt -lt $maxAttempts) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/heartbeat" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "  ChromaDB is ready!" -ForegroundColor Green
            break
        }
    } catch {
        Start-Sleep -Seconds 1
        $attempt++
        Write-Host "  Waiting... ($attempt/$maxAttempts)" -ForegroundColor Gray
    }
}

if ($attempt -eq $maxAttempts) {
    Write-Host "  WARNING: ChromaDB may not be fully ready" -ForegroundColor Yellow
}

# Summary
Write-Host "`n" + "="*60 -ForegroundColor Cyan
Write-Host "Services Started Successfully!" -ForegroundColor Green
Write-Host "="*60 -ForegroundColor Cyan
Write-Host ""
Write-Host "ChromaDB:     http://localhost:8000" -ForegroundColor White
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Ingest knowledge:  python scripts/ingest_knowledge.py" -ForegroundColor White
Write-Host "  2. Run mock mode:     python -m src.interfaces.cli --mock" -ForegroundColor White
Write-Host "  3. Run USB mode:      python -m src.interfaces.cli --usb <equipment>" -ForegroundColor White
Write-Host ""
