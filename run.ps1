# DocuMind one-command start (Windows PowerShell)
# First run: creates the virtual environment, installs everything, builds the UI and seeds demo data.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv")) {
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe -m spacy download en_core_web_sm
}
if (-not (Test-Path "frontend\dist\index.html")) {
    Push-Location frontend; npm install; npm run build; Pop-Location
}
if (-not (Test-Path "data\app.db")) {
    .\.venv\Scripts\python.exe scripts\seed_demo.py
}
Write-Host "`nDocuMind running at http://localhost:8000  (first-run passwords: data/initial_credentials.txt)`n" -ForegroundColor Green
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
