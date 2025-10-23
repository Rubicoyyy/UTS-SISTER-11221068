param(
    [int]$Count = 5000,
    [double]$DupRatio = 0.2,
    [int]$BatchSize = 200,
    [string]$AppHost = 'http://localhost:8080',
    [int]$StartTimeout = 20
)

Write-Host "=== UTS Aggregator Benchmark Runner ==="
Write-Host "Count=$Count, DupRatio=$DupRatio, BatchSize=$BatchSize"

# 1) kill any python processes (careful in multi-user env)
Write-Host "Killing existing python processes..."
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# 2) start uvicorn server
Write-Host "Starting uvicorn server..."
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

# Resolve python executable inside venv, fallback to python in PATH
# Try venv python first, then pythonw, then system python
$venvPy = Join-Path $scriptDir '..\.venv\Scripts\python.exe'
$venvPyw = Join-Path $scriptDir '..\.venv\Scripts\pythonw.exe'
$pythonCmd = $null
if (Test-Path $venvPy) { $pythonCmd = $venvPy }
elseif (Test-Path $venvPyw) { $pythonCmd = $venvPyw }
else {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $pythonCmd = $cmd.Source }
}
if (-not $pythonCmd) {
    Write-Error "Could not find a python executable. Ensure virtualenv exists at .venv or python is on PATH."
    Exit 1
}
$pythonPath = $pythonCmd
Write-Host "Using python at: $pythonPath"

# Start server and redirect output to a temporary log file so we can tail for readiness
$serverLog = Join-Path $scriptDir "server.log"
if (Test-Path $serverLog) { Remove-Item $serverLog -Force }
$args = '-m','uvicorn','src.main:app','--host','0.0.0.0','--port','8080'
$server = Start-Process -FilePath $pythonPath -ArgumentList $args -RedirectStandardOutput $serverLog -RedirectStandardError $serverLog -PassThru
Write-Host "Server PID:" $server.Id

# 3) wait for server to be ready
Write-Host "Waiting for server to be ready..."
$ready = $false
for ($i=0; $i -lt $StartTimeout; $i++) {
    try {
        $r = Invoke-RestMethod -Uri "$AppHost/stats" -ErrorAction Stop
        $ready = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $ready) {
    Write-Error "Server did not become ready within $StartTimeout seconds"
    Exit 1
}
Write-Host "Server ready. Starting publisher..."

# 4) run publisher and measure time
$measure = Measure-Command {
    .\.venv\Scripts\python.exe scripts\publisher.py --url "$AppHost/publish" --count $Count --dup_ratio $DupRatio --batch_size $BatchSize
}
Write-Host "Publisher elapsed (s):" $measure.TotalSeconds

# 5) fetch stats
try {
    $stats = Invoke-RestMethod -Uri "$AppHost/stats"
    Write-Host "Stats:"
    $stats | ConvertTo-Json -Depth 5 | Write-Host
} catch {
    Write-Error "Failed to fetch stats: $_"
}

# 6) stop server
Write-Host "Stopping server (PID $($server.Id))"
Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
Write-Host "Benchmark complete."
