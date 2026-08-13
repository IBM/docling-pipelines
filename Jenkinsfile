#!groovy
//
// Jenkins Pipeline for docling-pipelines
//

// Prefix Output With Timestamps
//
timestamps {
  //
  // Define Variables
  //
  def slackChannel = 'wdp-dc-devops-build'
  def slackTeamDomain = 'watsondataplatform'
  def slackTokenCredentialId = 'e317d69f-0b8d-4526-aa99-29a02c34ff7c'

  def afaasCredentialsId = 'bda93d3f-f988-4da0-9bc3-9dc0dba90f95'
  def docpipetwinpypiCredentialsId = 'pypi-creds'
  def jenkinsCredentialsId = 'd89ad365-9ac7-41b6-966d-578b07ae9242'
  def dataconnCredentialsId = 'efe499cb-0bf7-41ff-8a21-eec440e16153'

  def isReleaseBuild = (env.BRANCH_NAME == 'main')
  def isCodeAnalysis = isReleaseBuild

  if (isReleaseBuild) {
    properties([
      disableConcurrentBuilds(),
      buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: isReleaseBuild ? '5' : '5')),
      parameters([
        booleanParam(name: 'SKIP_TESTS', defaultValue: false, description: 'Set to true to skip tests')
      ])
    ])
  } else {
    properties([
      disableConcurrentBuilds(),
      buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: isReleaseBuild ? '5' : '5')),
      parameters([booleanParam(name: 'SKIP_TESTS', defaultValue: false, description: 'Set to true to skip tests')])
    ])
  }

  def APP_NAME = "docling-pipelines"
  def APP_VERSION = "NA"
  def buildMinorVersion = env.BUILD_NUMBER
  env.VERSION = "0.1.${buildMinorVersion}"

  //
  // Execute On Slave Node
  //
  def nodeName = ""
  if (env.BUILD_URL.contains("hyc-wkc-devops-jenkins.swg-devops.com")) {
    nodeName = "kube_ui"
  } else {
    nodeName = "taas_image_with_docker"
  }

  node(nodeName) {

    //
    // Catch Errors And Continue Execution
    //
    catchError {
      //
      // Checkout And Build Without Running Tests
      //

      stage('Build') {
        checkout scm
      }

      stage('Setup') {
        sh '''
          # Install uv (fast, ~5s — manages its own Python, no Miniconda needed)
          curl -LsSf https://astral.sh/uv/install.sh | sh
          export PATH="$HOME/.cargo/bin:$PATH"

          # Install system dependencies (only if missing)
          if ! dpkg -s libldap2-dev &>/dev/null 2>&1; then
            sudo apt-get update --allow-releaseinfo-change -o Acquire::Retries=3 || true
            sudo apt-get install -y software-properties-common python3-dev gcc libldap2-dev libsasl2-dev
          fi

          # Pin Python 3.12 via uv (no Miniconda download needed)
          uv python install 3.12
          uv sync --all-groups --all-extras --python 3.12

          # Install quality check tools
          uv pip install ruff mypy detect-secrets types-requests types-cachetools
        '''
      }

      stage('Code Quality Check') {
        script {
          withCredentials([
            usernamePassword(credentialsId: docpipetwinpypiCredentialsId, usernameVariable: 'PYPI_USERNAME', passwordVariable: 'PYPI_PASSWORD')  // pragma: allowlist secret
          ]) {
            sh '''
              export PATH="$HOME/.cargo/bin:$PATH"
              source .venv/bin/activate

              chmod +x scripts/check_modified_files.sh
              ./scripts/check_modified_files.sh
            '''
          }
        }
      }

      stage('Pytest') {
        script {
          withCredentials([
            usernamePassword(credentialsId: docpipetwinpypiCredentialsId, usernameVariable: 'PYPI_USERNAME', passwordVariable: 'PYPI_PASSWORD')  // pragma: allowlist secret
          ]) {
            sh """
              export PATH="\${HOME}/.cargo/bin:\$PATH"
              . .venv/bin/activate

              export PYTHONPATH=./src/:./tests
              cp .env.example .env

              pytest -m "unit and not slow" -n 2 --dist=loadfile \
                --cov=src/docpipe --cov-report=xml:coverage.xml --cov-report=term
              echo "Unit test coverage report generated"
            """
          }
        }
      }

      stage('Sonar') {
        script {
          withCredentials([string(credentialsId: 'sonarqube-auth-token-cio', variable: 'SONAR_PWD')]) {
            println "Running sonarqube.."
            sh("chmod +x sonar/sonarscan.sh")
            def scanBranch=''
            if (env.BRANCH_NAME.startsWith("PR-")) {
              scanBranch = env.CHANGE_BRANCH
            } else {
              scanBranch = env.BRANCH_NAME
            }
            println "Base branch is ${env.CHANGE_TARGET}"
            echo sh(script: 'env|sort', returnStdout: true)
            sh("./sonar/sonarscan.sh ${scanBranch} ${SONAR_PWD} ${WORKSPACE} ${env.BUILD_ID}")
          }
        }
      }

      if (isReleaseBuild) {
        if (currentBuild.currentResult == 'SUCCESS') {
          stage('Build and Push Wheel') {
            script {
              withCredentials([
                usernamePassword(credentialsId: afaasCredentialsId, usernameVariable: 'ARTIFACTORY_USERNAME', passwordVariable: 'ARTIFACTORY_PASSWORD') // pragma: allowlist secret
              ]) {
                sh """
                  export PATH="\${HOME}/.cargo/bin:\$PATH"
                  . .venv/bin/activate

                  # ── Main wheel ──────────────────────────────────────────────
                  # Build the wheel using uv
                  uv build --wheel

                  # Find the generated wheel file
                  WHEEL_FILE=\$(ls -t dist/*.whl | head -n 1)
                  WHEEL_FILENAME=\$(basename "\$WHEEL_FILE")

                  echo "Built wheel: \$WHEEL_FILENAME"

                  # Push to Artifactory
                  curl -u "\${ARTIFACTORY_USERNAME}:\${ARTIFACTORY_PASSWORD}" \\
                    -T "\$WHEEL_FILE" \\
                    "https://na-public.artifactory.swg-devops.com/artifactory/dataconn-maven-local/docling-pipelines/${VERSION}/\${WHEEL_FILENAME}"

                  echo "Wheel file pushed to Artifactory successfully"

                  # ── Slim wheel ───────────────────────────────────────────────
                  # Build the slim wheel from the slim/ sub-project
                  uv build --wheel --project slim

                  # Find the generated slim wheel file
                  SLIM_WHEEL_FILE=\$(ls -t slim/dist/*.whl | head -n 1)
                  SLIM_WHEEL_FILENAME=\$(basename "\$SLIM_WHEEL_FILE")

                  echo "Built slim wheel: \$SLIM_WHEEL_FILENAME"

                  # Push slim wheel to Artifactory (same folder as main wheel)
                  curl -u "\${ARTIFACTORY_USERNAME}:\${ARTIFACTORY_PASSWORD}" \\
                    -T "\$SLIM_WHEEL_FILE" \\
                    "https://na-public.artifactory.swg-devops.com/artifactory/dataconn-maven-local/docling-pipelines/${VERSION}/\${SLIM_WHEEL_FILENAME}"

                  echo "Slim wheel file pushed to Artifactory successfully"
                """
              }
            }
          }
          stage('Publish') {
            script {
              withCredentials([
                usernamePassword(credentialsId: docpipetwinpypiCredentialsId, usernameVariable: 'PYPI_USERNAME', passwordVariable: 'PYPI_PASSWORD') // pragma: allowlist secret
              ]) {
                sh """
                  echo "TBD"
                """
              }
            }
          }
          stage('Tag repo'){
            script {
              withCredentials([[$class: 'UsernamePasswordMultiBinding', credentialsId: '27403a9f-356a-41ad-a55d-d101b2c615cb', usernameVariable: 'GIT_USERNAME', passwordVariable: 'GIT_PASSWORD']]) {  // pragma: allowlist secret
                sh '''
                  git config credential.username $GIT_USERNAME
                  git config credential.helper '!f() { echo password=$GIT_PASSWORD; }; f'
                '''
                sh '''
                  git tag ${VERSION}
                  git push ${GIT_URL} --tags
                '''
              }
            }
          }
        }
      }
    }

    //
    // Clean The Workspace
    //
    try {
      deleteDir()
    } catch(e) {
      echo "Failed to clean workspace: \${e.message}"
    }
  }
}
