pipeline {
  agent any
  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
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
        bat 'py -3 --version'
        bat 'git --version'
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
    }
    failure {
      echo 'ASAA CI pipeline failed. Review the first failing stage.'
    }
    always {
      archiveArtifacts artifacts: 'asaa-dependencies.cdx.json', allowEmptyArchive: true
    }
  }
}
