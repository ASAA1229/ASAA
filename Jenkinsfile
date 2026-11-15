pipeline {
  agent any
  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
    skipDefaultCheckout(true)
  }
  environment {
    CI = 'true'
    PIP_DISABLE_PIP_VERSION_CHECK = '1'
  }
  stages {
    stage('Checkout') {
      steps {
        deleteDir()
        checkout scm
      }
    }
    stage('Agent prerequisites') {
      steps {
        bat 'node --version'
        bat 'npm --version'
        bat 'git --version'
        powershell '''
          $ErrorActionPreference = "Stop"
          if ($env:PYTHON) {
            $python = $env:PYTHON
            if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
              throw "PYTHON is set but does not point to an executable file: $python"
            }
            $version = & $python --version
          } elseif (Get-Command py -ErrorAction SilentlyContinue) {
            $version = & py -3 --version
          } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            $python = (Get-Command python).Source
            $version = & $python --version
          } else {
            throw "Python 3.11+ is required. Install it for the Jenkins agent account and add it to PATH, or set the Jenkins agent environment variable PYTHON to its full executable path."
          }
          if ($LASTEXITCODE -ne 0 -or $version -notmatch 'Python 3[.](1[1-9]|[2-9][0-9])') {
            throw "Python 3.11 or newer is required; detected: $version"
          }
        '''
      }
    }
    stage('Install locked dependencies') {
      steps {
        bat 'npm ci'
        bat 'npm run setup:api'
        bat 'npm audit --audit-level=high'
        bat 'npm sbom --sbom-format=cyclonedx --output-file=asaa-dependencies.cdx.json'
      }
    }
    stage('Lint and test') {
      steps {
        bat 'npm run lint'
        bat 'npm test'
        bat 'apps\\ap-api\\.venv\\Scripts\\python.exe -m compileall -q apps\\ap-api\\src apps\\ap-api\\tests'
        bat 'apps\\ap-api\\.venv\\Scripts\\python.exe -m pytest -q apps\\ap-api\\tests'
      }
    }
    stage('Build') {
      steps {
        bat 'npm run build'
      }
    }
  }
  post {
    success {
      echo 'ASAA CI pipeline passed. No deployment was performed.'
      script {
        def branchName = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
        if (branchName == 'new' || branchName.endsWith('/new')) {
          build job: 'ASAA-Local-Stack',
            parameters: [string(name: 'ACTION', value: 'DEPLOY')],
            wait: false
        }
      }
    }
    failure {
      echo 'ASAA CI pipeline failed. Review the first failing stage.'
    }
    always {
      archiveArtifacts artifacts: 'asaa-dependencies.cdx.json', allowEmptyArchive: true
    }
  }
}
