# Enregistre (commit) et publie (push) sur GitHub toutes les modifications en cours.
# Usage :  .\scripts\valider.ps1 "Message du commit"
#          .\scripts\valider.ps1            (message par défaut horodaté)

param([string]$Message)

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

$changes = git status --porcelain
if (-not $changes) {
    Write-Host "Aucune modification à valider." -ForegroundColor Yellow
    exit 0
}

Write-Host "Modifications à valider :" -ForegroundColor Cyan
git status --short

if (-not $Message) {
    $Message = "Mise à jour du " + (Get-Date -Format 'yyyy-MM-dd HH:mm')
}

git add -A
git commit -m $Message
if ($LASTEXITCODE -ne 0) { Write-Host "Échec du commit." -ForegroundColor Red; exit 1 }

$branch = git branch --show-current
git push -u origin $branch
if ($LASTEXITCODE -ne 0) { Write-Host "Échec du push." -ForegroundColor Red; exit 1 }

Write-Host "Validé et publié sur GitHub ($branch)." -ForegroundColor Green
