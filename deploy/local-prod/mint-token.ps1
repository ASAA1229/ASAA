<#
.SYNOPSIS  Print a signed login token for http://localhost:8100 (paste it into the portal). Local owner use only.
.PARAMETER Subject  Identity subject (use two different subjects to exercise maker-checker).
.PARAMETER Hours    Lifetime in hours (default 8).
#>
param([string]$Subject = 'local-owner', [double]$Hours = 8)
. (Join-Path $PSScriptRoot 'common.ps1')
$py = Get-VenvPython
& $py (Join-Path $PSScriptRoot 'tools.py') mint --key (Join-Path $StateDir 'keys\jwt_private.pem') --subject $Subject --hours $Hours
