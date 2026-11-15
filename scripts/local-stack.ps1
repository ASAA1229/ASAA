param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('Start', 'Stop', 'Status')]
  [string]$Action,

  [Parameter(Mandatory = $true)]
  [string]$Root
)

$ErrorActionPreference = 'Stop'
$rootPath = [IO.Path]::GetFullPath($Root)
$projectsPath = Join-Path $rootPath 'projects'
$statePath = Join-Path $rootPath '.local-stack'
$stateFile = Join-Path $statePath 'processes.json'
$templatesPath = Join-Path $projectsPath 'Templates'

$services = @(
  @{
    Name = 'ASAA'
    Directory = 'ASAA'
    Command = 'call npm.cmd run dev'
    Environment = @{
      WEB_PORT = '5173'
      API_PORT = '8001'
    }
    HealthUrls = @('http://127.0.0.1:5173/', 'http://127.0.0.1:8001/health')
  },
  @{
    Name = 'JARVIS'
    Directory = 'JARVIS'
    Command = 'call npm.cmd start'
    Environment = @{ PORT = '3000' }
    HealthUrls = @('http://127.0.0.1:3000/api/status')
  },
  @{
    Name = 'Templates'
    Directory = 'Templates'
    Command = 'call npm.cmd run dev'
    Environment = @{
      TEMPLATES_PG_PORT = '54339'
      WEB_PORT = '5000'
      WEB_ORIGIN = 'http://localhost:5000'
      API_PROXY_TARGET = 'http://127.0.0.1:4000'
    }
    HealthUrls = @('http://127.0.0.1:5000/', 'http://127.0.0.1:4000/api/health')
  },
  @{
    Name = 'Portfolio'
    Directory = 'Portfolio'
    Command = 'call npm.cmd run dev -- --host 127.0.0.1 --port 8080'
    Environment = @{}
    HealthUrls = @('http://127.0.0.1:8080/')
  }
)

function Save-State($entries) {
  New-Item -ItemType Directory -Force -Path $statePath | Out-Null
  ConvertTo-Json -InputObject @($entries) -Depth 5 |
    Set-Content -LiteralPath $stateFile -Encoding UTF8
}

function Read-State {
  if (-not (Test-Path -LiteralPath $stateFile -PathType Leaf)) {
    return @()
  }
  $parsed = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
  return @($parsed)
}

function Test-HealthUrl([string]$Url) {
  try {
    $response = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec 3 -UseBasicParsing
    return $response.StatusCode -ge 200 -and $response.StatusCode -lt 400
  } catch {
    return $false
  }
}

function Stop-TrackedProcesses {
  $entries = Read-State
  if ($entries.Count -eq 0) {
    Write-Output 'No application processes are currently tracked.'
  }

  foreach ($entry in $entries) {
    $processes = @(Get-CimInstance Win32_Process)
    $rootProcess = $processes |
      Where-Object { $_.ProcessId -eq [int]$entry.Pid } |
      Select-Object -First 1
    if (-not $rootProcess) {
      Write-Output "$($entry.Name): process $($entry.Pid) is already stopped."
      continue
    }

    $runnerName = [IO.Path]::GetFileName([string]$entry.Runner)
    if (-not $rootProcess.CommandLine -or
        $rootProcess.CommandLine.IndexOf($runnerName, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
      throw "$($entry.Name): PID $($entry.Pid) no longer matches its recorded runner. Refusing to stop an unrelated process; inspect $stateFile."
    }

    $levels = @()
    $frontier = @([int]$entry.Pid)
    while ($frontier.Count -gt 0) {
      $children = @($processes | Where-Object { [int]$_.ParentProcessId -in $frontier })
      if ($children.Count -eq 0) { break }
      $levels += ,$children
      $frontier = @($children | ForEach-Object { [int]$_.ProcessId })
    }
    for ($level = $levels.Count - 1; $level -ge 0; $level--) {
      foreach ($child in $levels[$level]) {
        Stop-Process -Id ([int]$child.ProcessId) -Force -ErrorAction SilentlyContinue
      }
    }
    Stop-Process -Id ([int]$entry.Pid) -Force -ErrorAction SilentlyContinue
    if (Get-Process -Id ([int]$entry.Pid) -ErrorAction SilentlyContinue) {
      throw "$($entry.Name): could not stop the recorded process tree rooted at PID $($entry.Pid)."
    }
    Write-Output "$($entry.Name): stopped process tree rooted at PID $($entry.Pid)."
  }

  if (Test-Path -LiteralPath $stateFile -PathType Leaf) {
    Remove-Item -LiteralPath $stateFile -Force
  }

  if (Test-Path -LiteralPath (Join-Path $templatesPath 'scripts\local-db.mjs') -PathType Leaf) {
    Push-Location $templatesPath
    try {
      & node scripts/local-db.mjs stop
      if ($LASTEXITCODE -ne 0) {
        throw 'Could not stop the Templates local PostgreSQL cluster.'
      }
    } finally {
      Pop-Location
    }
  }
}

function Get-StackStatus {
  $entries = Read-State
  if ($entries.Count -eq 0) {
    Write-Output 'No local application processes are recorded. Run ACTION=DEPLOY or START.'
    return
  }
  foreach ($entry in $entries) {
    $processRunning = [bool](Get-Process -Id ([int]$entry.Pid) -ErrorAction SilentlyContinue)
    $health = @($entry.HealthUrls | ForEach-Object { Test-HealthUrl $_ })
    $healthy = $health.Count -gt 0 -and @($health | Where-Object { -not $_ }).Count -eq 0
    $status = if ($processRunning -and $healthy) { 'UP' } else { 'NOT HEALTHY' }
    Write-Output ("{0}: {1}; PID={2}; URLs={3}" -f $entry.Name, $status, $entry.Pid, ($entry.HealthUrls -join ', '))
  }
}

function Start-TrackedService($service) {
  $servicePath = Join-Path $projectsPath $service.Directory
  if (-not (Test-Path -LiteralPath (Join-Path $servicePath 'package.json') -PathType Leaf)) {
    throw "$($service.Name) checkout is missing. Run ACTION=DEPLOY before START."
  }

  $runnerPath = Join-Path $statePath ("run-{0}.cmd" -f $service.Name)
  $stdoutPath = Join-Path $statePath ("{0}.stdout.log" -f $service.Name)
  $stderrPath = Join-Path $statePath ("{0}.stderr.log" -f $service.Name)
  $runnerLines = @('@echo off', "cd /d `"$servicePath`"")
  foreach ($key in $service.Environment.Keys) {
    $runnerLines += "set `"$key=$($service.Environment[$key])`""
  }
  $runnerLines += $service.Command
  Set-Content -LiteralPath $runnerPath -Value $runnerLines -Encoding ASCII

  $arguments = "/d /c `"`"$runnerPath`"`""
  $process = Start-Process -FilePath $env:ComSpec -ArgumentList $arguments `
    -WorkingDirectory $servicePath -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath

  return [pscustomobject]@{
    Name = $service.Name
    Pid = $process.Id
    Runner = $runnerPath
    HealthUrls = $service.HealthUrls
  }
}

function Start-Stack {
  $entries = Read-State
  if ($entries.Count -gt 0) {
    $allHealthy = $true
    foreach ($entry in $entries) {
      if (-not (Get-Process -Id ([int]$entry.Pid) -ErrorAction SilentlyContinue)) {
        $allHealthy = $false
        break
      }
      foreach ($url in $entry.HealthUrls) {
        if (-not (Test-HealthUrl $url)) {
          $allHealthy = $false
          break
        }
      }
      if (-not $allHealthy) { break }
    }
    if ($allHealthy -and $entries.Count -eq $services.Count) {
      Write-Output 'All four local applications are already healthy.'
      Get-StackStatus
      return
    }
    Stop-TrackedProcesses
  }

  if (-not (Test-Path -LiteralPath (Join-Path $templatesPath 'scripts\local-db.mjs') -PathType Leaf)) {
    throw 'Templates checkout is missing. Run ACTION=DEPLOY before START.'
  }
  Push-Location $templatesPath
  try {
    $env:TEMPLATES_PG_PORT = '54339'
    & node scripts/local-db.mjs start
    if ($LASTEXITCODE -ne 0) {
      throw 'Templates PostgreSQL is not initialized. Run ACTION=DEPLOY to initialize it and apply migrations.'
    }
  } finally {
    Remove-Item Env:TEMPLATES_PG_PORT -ErrorAction SilentlyContinue
    Pop-Location
  }

  New-Item -ItemType Directory -Force -Path $statePath | Out-Null
  $started = @()
  try {
    foreach ($service in $services) {
      $entry = Start-TrackedService $service
      $started += $entry
      Save-State $started
      Write-Output "$($service.Name): started as PID $($entry.Pid); logs: $statePath"
    }

    foreach ($entry in $started) {
      $deadline = (Get-Date).AddSeconds(90)
      do {
        $healthy = @($entry.HealthUrls | ForEach-Object { Test-HealthUrl $_ })
        if ($healthy.Count -gt 0 -and @($healthy | Where-Object { -not $_ }).Count -eq 0) {
          break
        }
        if (-not (Get-Process -Id ([int]$entry.Pid) -ErrorAction SilentlyContinue)) {
          throw "$($entry.Name) exited before becoming healthy. Review $statePath\$($entry.Name).stderr.log."
        }
        Start-Sleep -Seconds 2
      } while ((Get-Date) -lt $deadline)

      if (@($entry.HealthUrls | ForEach-Object { Test-HealthUrl $_ } |
          Where-Object { -not $_ }).Count -gt 0) {
        throw "$($entry.Name) did not pass its localhost health checks within 90 seconds. Review $statePath\$($entry.Name).stderr.log."
      }
      Write-Output "$($entry.Name): health checks passed."
    }
  } catch {
    Stop-TrackedProcesses
    throw
  }

  Write-Output 'Local development URLs:'
  Write-Output '  ASAA:      http://127.0.0.1:5173/  (API http://127.0.0.1:8001/docs)'
  Write-Output '  JARVIS:    http://127.0.0.1:3000/'
  Write-Output '  Templates: http://127.0.0.1:5000/  (API http://127.0.0.1:4000)'
  Write-Output '  Portfolio: http://127.0.0.1:8080/'
}

switch ($Action) {
  'Stop' {
    Stop-TrackedProcesses
    Write-Output 'Local applications and the Templates PostgreSQL cluster are stopped; database files are preserved.'
  }
  'Status' {
    Get-StackStatus
  }
  'Start' {
    Start-Stack
  }
}
