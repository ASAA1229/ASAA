<#
.SYNOPSIS
  Point the running API and portal back to the previous image tag (or -To <tag>) and smoke-test. The database is NOT downgraded:
  releases must stay backward compatible with the schema for one release (run alembic downgrade manually if a migration must be undone).
#>
[CmdletBinding()]
param([string]$To = '')
. (Join-Path $PSScriptRoot 'common.ps1')
$e = Read-EnvFile
$env:COMPOSE_PROJECT_NAME = 'asaa-local-prod'
$state = Get-State
if (-not $To) { $To = $state.previous }
if (-not $To) { throw 'No previous release is recorded; nothing to roll back to.' }
docker image inspect "asaa-api:$To" *> $null
if ($LASTEXITCODE -ne 0) { throw "Image asaa-api:$To no longer exists locally." }
$vars = @{ API_IMAGE_TAG = $To; PORTAL_IMAGE_TAG = $To; API_PORT = $e.API_PORT; PORTAL_PORT = $e.PORTAL_PORT }
Invoke-Compose @('up', '-d', 'api', 'portal') $vars
if (-not (Wait-Ready -Port ([int]$e.API_PORT))) { throw "Rolled back to $To but the API is not ready." }
if (-not (Invoke-Smoke $e)) { throw "Rolled back to $To but smoke checks failed." }
Save-State ([pscustomobject]@{ current = $To; previous = ''; portal_current = $To; portal_previous = '' })
Write-Host "ROLLED BACK to asaa-api:$To and smoke passed."
