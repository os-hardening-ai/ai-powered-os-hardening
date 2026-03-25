# Windows PowerShell — kullanim: .\run.ps1
# Execution policy hatasi alirsan:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

if (-not (Test-Path .env)) {
    Write-Error "Hata: .env dosyasi bulunamadi. Once calistir: cp .env.example .env"
    exit 1
}

$HASH_FILE = ".requirements_hash"
$REQ_FILE  = "requirements-python311.txt"
$CURRENT_HASH = (Get-FileHash $REQ_FILE -Algorithm MD5).Hash

$requirements_changed = $true
if ((Test-Path $HASH_FILE) -and ((Get-Content $HASH_FILE -Raw).Trim() -eq $CURRENT_HASH)) {
    $requirements_changed = $false
}

if ($requirements_changed) {
    Write-Host "[requirements degisti] Container ve dangling image'lar temizleniyor..."
    docker compose down 2>$null
    docker image prune -f
    Write-Host "Image yeniden build ediliyor (pip yeniden kurulacak)..."
} else {
    Write-Host "[requirements ayni] Sadece kod katmani yeniden build edilecek (~10s)..."
}

docker compose up --build -d

if ($requirements_changed) {
    $CURRENT_HASH | Out-File -FilePath $HASH_FILE -NoNewline -Encoding ascii
}

Write-Host ""
Write-Host "API -> http://localhost:8000"
Write-Host "Docs -> http://localhost:8000/docs"
Write-Host ""
Write-Host "Loglar : docker compose logs -f"
Write-Host "Durdur : docker compose down"
