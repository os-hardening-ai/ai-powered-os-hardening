# Windows PowerShell — kullanım: .\run.ps1
# Execution policy hatası alırsan:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

if (-not (Test-Path .env)) {
    Write-Error "Hata: .env dosyası bulunamadı. Önce çalıştır: cp .env.example .env"
    exit 1
}

Write-Host "Docker image build ediliyor ve container başlatılıyor..."
docker compose up --build -d

Write-Host ""
Write-Host "API ayağa kalktı -> http://localhost:8000"
Write-Host "Swagger UI       -> http://localhost:8000/docs"
Write-Host "Health           -> http://localhost:8000/health"
Write-Host ""
Write-Host "Loglar için: docker compose logs -f"
Write-Host "Durdurmak için:  docker compose down"
