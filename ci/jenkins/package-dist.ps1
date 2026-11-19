<#
.SYNOPSIS
  Packages the production web build (dist) into a tarball with a SHA-256 checksum and verifies both.
.DESCRIPTION
  Windows PowerShell 5.1 and PowerShell 7 compatible; fails closed. Produces:
    asaa-web-dist.tar.gz, asaa-web-dist.tar.gz.sha256 ("<hash>  <file>")
  The archive is re-listed (no absolute or parent-relative member paths) and re-hashed before the script succeeds.
  This does not publish or deploy anything.
#>
[CmdletBinding()]
param(
  [string]$SourceDir = 'dist',
  [string]$ArchiveName = 'asaa-web-dist.tar.gz'
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $repoRoot

if (-not (Test-Path -LiteralPath $SourceDir -PathType Container)) { throw "Build output directory '$SourceDir' was not created by the build." }
if (-not (Test-Path -LiteralPath (Join-Path $SourceDir 'index.html') -PathType Leaf)) { throw "Build output '$SourceDir' has no index.html." }
$checksumName = "$ArchiveName.sha256"
Remove-Item -Force -LiteralPath $ArchiveName, $checksumName -ErrorAction SilentlyContinue

& tar -czf $ArchiveName -C $SourceDir .
if ($LASTEXITCODE -ne 0) { throw "tar failed with exit code $LASTEXITCODE." }

$entries = @(& tar -tzf $ArchiveName)
if ($LASTEXITCODE -ne 0 -or $entries.Count -eq 0) { throw 'The created archive cannot be listed or is empty.' }
foreach ($entry in $entries) {
  $normalized = ([string]$entry).Replace('\', '/')
  if ([string]::IsNullOrWhiteSpace($normalized) -or $normalized.StartsWith('/') -or $normalized -match '^[A-Za-z]:' -or ($normalized -split '/') -contains '..') {
    throw "Unsafe archive member path: $entry"
  }
}

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ArchiveName).Hash.ToLowerInvariant()
[IO.File]::WriteAllText((Join-Path $repoRoot $checksumName), "$hash  $ArchiveName`n", (New-Object System.Text.UTF8Encoding($false)))

$recorded = ((Get-Content -LiteralPath $checksumName -TotalCount 1) -split '\s+')[0]
$actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $ArchiveName).Hash.ToLowerInvariant()
if ($recorded -ne $actual) { throw "Checksum verification failed for $ArchiveName." }
Write-Host "Packaged and verified $ArchiveName ($($entries.Count) entries) sha256=$actual"
exit 0
