<#
.SYNOPSIS
  Build images, migrate, deploy and smoke-test the LOCAL production deployment (portal :8100, API :8101). Rolls back on smoke failure.
  Exit code 0 = deployed and smoke passed; 1 = failed (previous release restored when one existed).
#>
[CmdletBinding()]
param([string]$Tag = '', [switch]$NoRollback)
. (Join-Path $PSScriptRoot 'common.ps1')
$e = Read-EnvFile
$env:COMPOSE_PROJECT_NAME = 'asaa-local-prod'
if (-not $Tag) { $sha = (& git -C $Repo rev-parse --short HEAD).Trim(); $Tag = "$sha-$(Get-Date -Format 'yyyyMMddHHmmss')" }
$vars = @{ API_IMAGE_TAG = $Tag; PORTAL_IMAGE_TAG = $Tag; API_PORT = $e.API_PORT; PORTAL_PORT = $e.PORTAL_PORT }
$state = Get-State
$py = Get-VenvPython
$tools = Join-Path $PSScriptRoot 'tools.py'

docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Docker daemon is not running.' }

# Build
Invoke-Native 'docker' @('build', '-q', '-t', "asaa-api:$Tag", (Join-Path $Repo 'apps\ap-api'))
Invoke-Native 'docker' @('build', '-q', '-f', (Join-Path $Repo 'Dockerfile.portal'), '-t', "asaa-portal:$Tag", '--build-arg', "VITE_API_BASE_URL=http://localhost:$($e.API_PORT)", $Repo)

# Migrate (migrator role), then tighten grants and verify the runtime role cannot alter schema or audit rows.
Invoke-Compose @('--profile', 'migrate', 'run', '--rm', 'migrate') $vars
$migratorUrl = "postgresql://$($e.ASAA_DB_MIGRATOR_ROLE):$($e.ASAA_DB_MIGRATOR_PASSWORD)@$($e.ASAA_PG_HOST):$($e.ASAA_PG_PORT)/$($e.ASAA_DB_NAME)"
$runtimeUrl = "postgresql://$($e.ASAA_DB_RUNTIME_ROLE):$($e.ASAA_DB_RUNTIME_PASSWORD)@$($e.ASAA_PG_HOST):$($e.ASAA_PG_PORT)/$($e.ASAA_DB_NAME)"
Invoke-Native $py @($tools, 'tighten', '--migrator-url', $migratorUrl, '--runtime', $e.ASAA_DB_RUNTIME_ROLE)
Invoke-Native $py @((Join-Path $Repo 'apps\ap-api\scripts\db_roles.py'), 'check', '--runtime-url', $runtimeUrl)

# Deploy
Invoke-Compose @('up', '-d', 'api', 'portal') $vars
$ok = (Wait-Ready -Port ([int]$e.API_PORT)) -and (Invoke-Smoke $e)
if ($ok) {
  try { $portal = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$($e.PORTAL_PORT)/" -TimeoutSec 5).StatusCode -eq 200 } catch { $portal = $false }
  $ok = $portal
}
if ($ok) {
  Save-State ([pscustomobject]@{ current = $Tag; previous = $state.current; portal_current = $Tag; portal_previous = $state.portal_current })
  Write-Host "DEPLOYED asaa-api:$Tag (portal http://localhost:$($e.PORTAL_PORT), API http://localhost:$($e.API_PORT)). Previous release: $($state.current)"
  exit 0
}
Write-Warning "Smoke or readiness failed for $Tag."
if (-not $NoRollback -and $state.current) {
  Write-Warning "Rolling back to $($state.current)."
  & (Join-Path $PSScriptRoot 'rollback.ps1') -To $state.current
}
exit 1
