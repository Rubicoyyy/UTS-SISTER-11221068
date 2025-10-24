# Helper to activate the project's virtualenv with a per-process bypass if necessary
# Usage:
#   powershell -ExecutionPolicy Bypass -File tools\activate_venv.ps1
# or to dot-source in the current session (if policy allows):
#   . .\tools\activate_venv.ps1

$venvActivate = Join-Path -Path $PSScriptRoot -ChildPath "..\.venv\Scripts\Activate.ps1" | Resolve-Path -ErrorAction SilentlyContinue
if (-not $venvActivate) {
    Write-Host "Could not find .venv in the repository root. Create it with:`n  python -m venv .venv`" -ForegroundColor Yellow
    exit 1
}

$activatePath = $venvActivate.Path

try {
    # If script is dot-sourced, Activate.ps1 will affect the current session.
    # If run as a child process (powershell -File ...), this will run in the child process.
    & $activatePath
} catch {
    Write-Host "Activation failed. You can run with a per-process bypass:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -NoProfile -Command \"& '$activatePath'\"" -ForegroundColor Cyan
    exit 1
}

# If this script was dot-sourced into the current session, show environment info
if ($MyInvocation.InvocationName -eq '.') {
    Write-Host "Activated venv in current session:" -ForegroundColor Green
    Write-Host "  Python: $(Get-Command python).Source"
} else {
    Write-Host "Activation script executed (note: if you ran this as a child process the parent shell won't be activated)." -ForegroundColor Yellow
    Write-Host "To activate your parent shell, either dot-source this file or run the per-process bypass from your shell:" -ForegroundColor Cyan
    Write-Host "  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass; & .\\.venv\\Scripts\\Activate.ps1" -ForegroundColor Cyan
}
