<#
.SYNOPSIS  Run the read-only production smoke test against the local deployment (exit 0 = pass).
#>
. (Join-Path $PSScriptRoot 'common.ps1')
$e = Read-EnvFile
if (Invoke-Smoke $e) { Write-Host 'SMOKE PASSED'; exit 0 }
Write-Host 'SMOKE FAILED'
exit 1
