// ASAA (React/Vite web + FastAPI API) CI pipeline for a Windows Jenkins agent.
// Helpers live in ci/jenkins (Windows PowerShell 5.1 and PowerShell 7 compatible).
// Standard stage order: checkout + source verification, agent prerequisites (explicit Python resolution), locked install,
// SBOM + dependency audit, static analysis, tests (JUnit), build, package + checksum, archive.
// This pipeline never publishes or deploys anything unless TRIGGER_LOCAL_STACK_DEPLOY is explicitly enabled on branch new.
pipeline {
  agent any
  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
    skipDefaultCheckout(true)
    timeout(time: 60, unit: 'MINUTES')
  }
  environment {
    CI = 'true'
    PIP_DISABLE_PIP_VERSION_CHECK = '1'
    NPM_CONFIG_UPDATE_NOTIFIER = 'false'
    NPM_CONFIG_FUND = 'false'
  }
  parameters {
    booleanParam(name: 'TRIGGER_LOCAL_STACK_DEPLOY', defaultValue: false, description: 'After a green build of branch new, trigger the ASAA-Local-Stack job (local development stack only; the job must exist).')
  }
  stages {
    stage('Checkout and source verification') {
      steps {
        deleteDir()
        script {
          def scmVars = checkout scm
          env.GIT_COMMIT = scmVars.GIT_COMMIT
          env.GIT_BRANCH = scmVars.GIT_BRANCH
        }
        bat 'git --no-pager log -1 --oneline'
        powershell '''
          $ErrorActionPreference = "Stop"
          $head = (git rev-parse HEAD).Trim()
          if ($LASTEXITCODE -ne 0) { throw "git rev-parse failed." }
          if ($head -ne $env:GIT_COMMIT) { throw "Checked-out commit $head does not match the commit Jenkins resolved ($env:GIT_COMMIT)." }
        '''
      }
    }
    stage('Agent prerequisites') {
      steps {
        // Python is resolved explicitly: ASAA_PYTHON, then PYTHON (Jenkins global properties), then python3/python on PATH,
        // then "py -3". The interpreter is executed and must report >= 3.11, otherwise the build fails with remediation steps.
        bat 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ci\\jenkins\\agent-prereqs.ps1 -Require "node,npm,git,tar,python,lockfile,workspace" -NodeRange ">=22" -PythonMin 3.11 -PythonExportFile .jenkins-temp\\python.path -ReportFile .jenkins-temp\\agent-prereqs.json'
        script {
          env.PYTHON = readFile('.jenkins-temp/python.path').trim()
          echo "Using Python interpreter: ${env.PYTHON}"
        }
      }
    }
    stage('Install locked dependencies') {
      steps {
        bat 'npm ci'
        bat 'npm run setup:api'
      }
    }
    stage('SBOM and dependency audit') {
      steps {
        bat 'npm audit --audit-level=high'
        bat 'npm sbom --sbom-format=cyclonedx --output-file=asaa-dependencies.cdx.json'
        bat 'node scripts\\sbom-verify.mjs asaa-dependencies.cdx.json package-lock.json'
      }
    }
    stage('Static analysis') {
      steps {
        bat 'npm run lint'
        bat 'apps\\ap-api\\.venv\\Scripts\\python.exe -m compileall -q apps\\ap-api\\src apps\\ap-api\\tests'
      }
    }
    stage('Automated tests') {
      steps {
        bat 'npm run test:ci'
        bat 'apps\\ap-api\\.venv\\Scripts\\python.exe -m pytest -q apps\\ap-api\\tests --junitxml=test-results\\junit-pytest.xml'
      }
      post {
        always {
          junit testResults: 'test-results/junit-*.xml', allowEmptyResults: true
        }
      }
    }
    stage('Build') {
      steps {
        bat 'npm run build'
      }
    }
    stage('Package and verify checksum') {
      steps {
        bat 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ci\\jenkins\\package-dist.ps1'
      }
    }
    stage('Archive verified build') {
      steps {
        archiveArtifacts artifacts: 'asaa-web-dist.tar.gz,asaa-web-dist.tar.gz.sha256,asaa-dependencies.cdx.json', fingerprint: true, onlyIfSuccessful: true
      }
    }
  }
  post {
    success {
      echo 'ASAA CI pipeline passed.'
      script {
        if (params.TRIGGER_LOCAL_STACK_DEPLOY && currentBranchName() == 'new') {
          try {
            build job: 'ASAA-Local-Stack', parameters: [string(name: 'ACTION', value: 'DEPLOY')], wait: false
          } catch (err) {
            echo "WARNING: local stack deployment was requested but could not be triggered: ${err.message}"
            currentBuild.result = 'UNSTABLE'
          }
        } else {
          echo 'No deployment was performed.'
        }
      }
    }
    failure {
      echo 'ASAA CI pipeline failed. Review the first failing stage.'
    }
    always {
      archiveArtifacts artifacts: '.jenkins-temp/agent-prereqs.json', allowEmptyArchive: true
      powershell '''
        Remove-Item -Recurse -Force (Join-Path $env:WORKSPACE ".jenkins-temp") -ErrorAction SilentlyContinue
      '''
    }
  }
}

def currentBranchName() {
  def branch = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
  return branch.replaceFirst('^refs/heads/', '').replaceFirst('^origin/', '')
}
