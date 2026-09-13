# Sync main, delete old branch, create new branch.
# Usage: .\scripts\next.ps1 <new-branch-name>

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$NewBranch
)

$oldBranch = git branch --show-current

Write-Host "==> Switching to main..." -ForegroundColor Cyan
git checkout main

Write-Host "==> Fetching from origin..." -ForegroundColor Cyan
git fetch origin

Write-Host "==> Merging origin/main..." -ForegroundColor Cyan
git merge origin/main

if ($oldBranch -and $oldBranch -ne "main") {
    Write-Host ""
    Write-Host "==> Deleting local branch: $oldBranch" -ForegroundColor Cyan
    git branch -D $oldBranch 2>$null
    if ($?) { Write-Host "    Local branch deleted." } else { Write-Host "    Local branch not found, skipping." }

    Write-Host "==> Deleting remote branch: $oldBranch" -ForegroundColor Cyan
    git push origin --delete $oldBranch 2>$null
    if ($?) { Write-Host "    Remote branch deleted." } else { Write-Host "    Remote branch not found, skipping." }
}

Write-Host "==> Pruning stale remote references..." -ForegroundColor Cyan
git remote prune origin

Write-Host ""
Write-Host "==> Creating new branch: $NewBranch" -ForegroundColor Cyan
git checkout -b $NewBranch

Write-Host ""
Write-Host "Done! You are on branch '$NewBranch', ready to work." -ForegroundColor Green
