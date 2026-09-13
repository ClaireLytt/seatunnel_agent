# Commit all changes and push to the current branch.
# Usage: .\scripts\ship.ps1 "commit message"

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Message
)

$branch = git branch --show-current

Write-Host "==> Staging changes..." -ForegroundColor Cyan
git add -A

Write-Host "==> Committing: $Message" -ForegroundColor Cyan
git commit -m $Message

Write-Host "==> Pushing to origin/$branch..." -ForegroundColor Cyan
git push origin $branch

Write-Host ""
Write-Host "Done! Pushed to origin/$branch." -ForegroundColor Green
Write-Host "Create PR: https://github.com/ClaireLytt/seatunnel_agent/compare/$($branch)?expand=1" -ForegroundColor Yellow
