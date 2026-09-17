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
          # Install uv (manages its own Python, no Miniconda needed)
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

      def targetBranch = env.CHANGE_TARGET ?: 'main'
      def targetRef = "origin/${targetBranch}"

      def nonFrontendChanged = sh(
        script: "git diff --name-only --diff-filter=ACMR \$(git merge-base HEAD ${targetRef})..HEAD | grep -v '^frontend/' | grep -q .",
        returnStatus: true
      ) == 0

      def frontendChanged = sh(
        script: "git diff --name-only --diff-filter=ACMR \$(git merge-base HEAD ${targetRef})..HEAD | grep -q '^frontend/'",
        returnStatus: true
      ) == 0

      stage('Code Quality Check') {
        script {
          withCredentials([
            usernamePassword(credentialsId: docpipetwinpypiCredentialsId, usernameVariable: 'PYPI_USERNAME', passwordVariable: 'PYPI_PASSWORD')  // pragma: allowlist secret
          ]) {
            if (frontendChanged && fileExists('frontend/package.json')) {
              echo "Installing frontend dependencies with npm"
              sh 'npm --prefix frontend ci'
            } else {
              echo "Skipping frontend dependency install"
            }

            withEnv(["CHANGE_TARGET_BRANCH=${targetBranch}"]) {
              sh '''
              export PATH="$HOME/.cargo/bin:$PATH"
              source .venv/bin/activate

              chmod +x scripts/check_modified_files.sh
              chmod +x scripts/check_modified_frontend_files.sh
              ./scripts/check_modified_files.sh
              ./scripts/check_modified_frontend_files.sh
              '''
            }
          }
        }
      }

      if (nonFrontendChanged && !params.SKIP_TESTS) {
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

                pytest tests/integration/orchestration/prefect_adapter/test_thread_pool_adapter_integration.py \
                  --timeout=600 \
                  -v --tb=short \
                  --cov=src/docpipe --cov-report=xml:coverage.xml --cov-report=term --cov-append
                echo "Thread pool integration tests completed"
              """
            }
          }
        }
      } else {
        echo "Skipping Pytest: nonFrontendChanged=${nonFrontendChanged}, SKIP_TESTS=${params.SKIP_TESTS}"
      }

      if (nonFrontendChanged && !params.SKIP_TESTS) {
        stage('Coverage Check') {
          script {
            withCredentials([
              usernamePassword(credentialsId: docpipetwinpypiCredentialsId, usernameVariable: 'PYPI_USERNAME', passwordVariable: 'PYPI_PASSWORD')  // pragma: allowlist secret
            ]) {
              sh """
                export PATH="\${HOME}/.cargo/bin:\$PATH"
                . .venv/bin/activate

                chmod +x scripts/check_pr_coverage.sh
                ./scripts/check_pr_coverage.sh
              """
            }
          }
        }
      } else {
        echo "Skipping Coverage Check: nonFrontendChanged=${nonFrontendChanged}, SKIP_TESTS=${params.SKIP_TESTS}"
      }

      if (nonFrontendChanged) {
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
      } else {
        echo "Skipping Sonar: only frontend files changed"
      }

      if (frontendChanged) {
        stage('Sonar (Frontend)') {
          script {
            withCredentials([string(credentialsId: 'sonarqube-auth-token-cio', variable: 'SONAR_PWD')]) {
              println "Running sonarqube for frontend.."
              sh("chmod +x sonar/sonarscan-frontend.sh")
              def scanBranch=''
              if (env.BRANCH_NAME.startsWith("PR-")) {
                scanBranch = env.CHANGE_BRANCH
              } else {
                scanBranch = env.BRANCH_NAME
              }
              println "Base branch is ${env.CHANGE_TARGET}"
              sh("./sonar/sonarscan-frontend.sh ${scanBranch} ${SONAR_PWD} ${WORKSPACE} ${env.BUILD_ID}")
            }
          }
        }
      } else {
        echo "Skipping Sonar (Frontend): no frontend files changed"
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

                  # ── Wheel content validation ─────────────────────────────────
                  # Verify that the frontend static assets and BFF bundle were
                  # included in the wheel by the hatch build hook (hatch_build.py).
                  # A wheel built without npm available will be missing these files
                  # and would ship a broken image/pod deployment silently.
                  python3 -c "
import zipfile, sys, pathlib
whl = next(pathlib.Path('dist').glob('*.whl'))
with zipfile.ZipFile(whl) as z:
    names = z.namelist()
    required = ['docpipe/api/static/index.html', 'docpipe/api/bff/server.cjs']
    missing = [r for r in required if not any(r in n for n in names)]
if missing:
    sys.exit('Wheel content validation FAILED — missing: ' + str(missing))
print('Wheel content OK — static assets and BFF bundle present')
"

                  # Push to Artifactory (versioned path)
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

                  # Push slim wheel to Artifactory (versioned path)
                  curl -u "\${ARTIFACTORY_USERNAME}:\${ARTIFACTORY_PASSWORD}" \\
                    -T "\$SLIM_WHEEL_FILE" \\
                    "https://na-public.artifactory.swg-devops.com/artifactory/dataconn-maven-local/docling-pipelines/${VERSION}/\${SLIM_WHEEL_FILENAME}"

                  # Push slim wheel to Artifactory (fixed path — always points to latest)
                  curl -u "\${ARTIFACTORY_USERNAME}:\${ARTIFACTORY_PASSWORD}" \\
                    -T "\$SLIM_WHEEL_FILE" \\
                    "https://na-public.artifactory.swg-devops.com/artifactory/dataconn-maven-local/docling-pipelines/\${SLIM_WHEEL_FILENAME}"

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
