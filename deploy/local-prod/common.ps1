# Shared helpers for the local-prod scripts (dot-source). Windows PowerShell 5.1 and PowerShell 7 compatible.
$ErrorActionPreference = 'Stop'
$Script:Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
# ASAA_LOCAL_PROD_HOME (optional) keeps secrets, keys and release state outside a disposable CI checkout.
$Script:Home_ = if ($env:ASAA_LOCAL_PROD_HOME) { $env:ASAA_LOCAL_PROD_HOME } else { $Repo }
$Script:StateDir = Join-Path $Home_ '.local-prod'
$Script:EnvFile = Join-Path $Home_ '.env.local-prod'
$Script:StateFile = Join-Path $StateDir 'state.json'
$Script:Compose = Join-Path $PSScriptRoot 'docker-compose.yml'

function Read-EnvFile {
  if (-not (Test-Path $EnvFile)) { throw "Missing $EnvFile. Run deploy\local-prod\setup.ps1 first." }
  $map = @{}
  foreach ($line in Get-Content $EnvFile) { if ($line -match '^\s*([A-Z0-9_]+)=(.*)$') { $map[$Matches[1]] = $Matches[2] } }
  return $map
}
function Get-VenvPython {
  $p = Join-Path $StateDir 'venv\Scripts\python.exe'
  if (-not (Test-Path $p)) { throw 'Run setup.ps1 first (it builds .local-prod\venv).' }
  return $p
}
function Invoke-Native {
  param([string]$Exe, [string[]]$Arguments)
  & $Exe @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$Exe $($Arguments -join ' ') failed with exit code $LASTEXITCODE" }
}
function Get-State {
  if (Test-Path $StateFile) { return Get-Content $StateFile -Raw | ConvertFrom-Json }
  return [pscustomobject]@{ current = ''; previous = ''; portal_current = ''; portal_previous = '' }
}
function Save-State($s) {
  New-Item -ItemType Directory -Force $StateDir | Out-Null
  $s | ConvertTo-Json | Set-Content -Encoding UTF8 $StateFile
}
function Invoke-Compose {
  param([string[]]$Arguments, [hashtable]$Env)
  $env:ASAA_KEYS_DIR = Join-Path $StateDir 'keys'
  foreach ($k in $Env.Keys) { Set-Item -Path "Env:$k" -Value $Env[$k] }
  Invoke-Native 'docker' (@('compose', '-f', $Compose, '--env-file', $EnvFile) + $Arguments)
}
function Wait-Ready {
  param([int]$Port, [int]$Seconds = 90)
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    try { if ((Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/ready" -TimeoutSec 3).StatusCode -eq 200) { return $true } } catch { }
    Start-Sleep -Seconds 2
  }
  return $false
}
function Invoke-Smoke {
  param([hashtable]$E)
  $py = Get-VenvPython
  $tokenFile = Join-Path $StateDir 'smoke.token'
  try {
    $token = & $py (Join-Path $PSScriptRoot 'tools.py') mint --key (Join-Path $StateDir 'keys\jwt_private.pem') --subject smoke-check --hours 0.25 --permissions 'supplier:read'
    if ($LASTEXITCODE -ne 0) { throw 'could not mint the smoke token' }
    Set-Content -NoNewline -Encoding ASCII -Path $tokenFile -Value $token
    & $py (Join-Path $Repo 'apps\ap-api\scripts\smoke_test.py') --base-url "http://127.0.0.1:$($E.API_PORT)" --token-file $tokenFile --expect-production
    return ($LASTEXITCODE -eq 0)
  } finally {
    if (Test-Path $tokenFile) { Microsoft.PowerShell.Management\Remove-Item -LiteralPath $tokenFile -Force }
  }
}
