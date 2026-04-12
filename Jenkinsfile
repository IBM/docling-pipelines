#!groovy
//
// Jenkins Pipeline for datasift-opensource
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
  def datasifttwinpypiCredentialsId = 'pypi-creds'
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

  def APP_NAME = "datasift-opensource"
  def APP_VERSION = "NA"
  def buildMinorVersion = env.BUILD_NUMBER
  env.VERSION = "0.1.${buildMinorVersion}"

  //
  // Execute On Slave Node
  //
  def nodeName = ""
  if (env.BUILD_URL.contains("hyc-wkc-devops-jenkins.swg-devops.com")) {
    nodeName = "taas_image_with_docker"
  } else {
    nodeName = "kube_ui"
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

      stage('Pre-commit Checks') {
        script {
          withCredentials([
            usernamePassword(credentialsId: datasifttwinpypiCredentialsId, usernameVariable: 'PYPI_USERNAME', passwordVariable: 'PYPI_PASSWORD')  // pragma: allowlist secret
          ]) {
            sh '''
              # Install uv
              curl -LsSf https://astral.sh/uv/install.sh | sh
              export PATH="$HOME/.cargo/bin:$PATH"
              
              # Install system dependencies
              sudo apt-get update
              sudo apt-get install -y software-properties-common python3-dev gcc
              
              # Navigate to backend directory and sync dependencies
              cd src/datasift_opensource/backend
              uv sync --all-groups --all-extras
              
              # Install pre-commit tools using uv
              uv pip install pre-commit ruff mypy detect-secrets types-requests types-cachetools
              
              # Return to project root for all checks
              cd ../../..
              
              echo "Running pre-commit checks..."
              
              # Initialize failure tracking
              CHECKS_FAILED=0
              FAILURE_SUMMARY=""
              
              # Get list of changed Python files (relative to project root)
              echo "Fetching changed files..."
              git fetch origin main:refs/remotes/origin/main || true
              CHANGED_FILES=$(git diff --diff-filter=ACMR --name-only origin/main...HEAD | grep '\\.py$' || true)
              # Normalize whitespace: convert whitespace-only strings to empty strings
              CHANGED_PYTHON_FILES=$(echo "$CHANGED_FILES" | tr '\n' ' ' | xargs)
              CHANGED_BACKEND_FILES=$(echo "$CHANGED_FILES" | grep '^src/datasift_opensource/backend/' || true)
              CHANGED_BACKEND_PYTHON_FILES=$(echo "$CHANGED_BACKEND_FILES" | tr '\n' ' ' | xargs)
              
              echo "Changed Python files: $CHANGED_PYTHON_FILES"
              echo "Changed backend Python files: $CHANGED_BACKEND_PYTHON_FILES"
              
              # 1. Ruff Format - Check Python code formatting (only changed files)
              echo "1/4 Running ruff-format..."
              RUFF_FORMAT_FAILED=0
              if [ -n "$CHANGED_PYTHON_FILES" ]; then
                RUFF_FORMAT_OUTPUT=$(cd src/datasift_opensource/backend && uv run ruff format --check $CHANGED_PYTHON_FILES 2>&1) || {
                  RUFF_FORMAT_FAILED=1
                  CHECKS_FAILED=1
                }
              else
                echo "No Python files changed, skipping ruff format check"
              fi
              
              # 2. Ruff - Lint Python code (only changed files)
              echo "2/4 Running ruff linting..."
              RUFF_CHECK_FAILED=0
              if [ -n "$CHANGED_PYTHON_FILES" ]; then
                RUFF_CHECK_OUTPUT=$(cd src/datasift_opensource/backend && uv run ruff check $CHANGED_PYTHON_FILES 2>&1) || {
                  RUFF_CHECK_FAILED=1
                  CHECKS_FAILED=1
                }
              else
                echo "No Python files changed, skipping ruff check"
              fi
              
              # 3. MyPy - Type checking (only changed backend files)
              echo "3/4 Running mypy type checking..."
              MYPY_FAILED=0
              if [ -n "$CHANGED_BACKEND_PYTHON_FILES" ]; then
                MYPY_OUTPUT=$(cd src/datasift_opensource/backend && uv run mypy --ignore-missing-imports --config-file=pyproject.toml $CHANGED_BACKEND_PYTHON_FILES 2>&1) || {
                  MYPY_FAILED=1
                  CHECKS_FAILED=1
                }
              else
                echo "No backend Python files changed, skipping mypy check"
              fi
              
              # 4. Detect Secrets - Check for secrets in code (only changed files)
              echo "4/4 Running detect-secrets..."
              SECRETS_FAILED=0
              if [ -n "$CHANGED_FILES" ]; then
                SECRETS_OUTPUT=$(detect-secrets scan --baseline .secrets.baseline $CHANGED_FILES 2>&1) || {
                  SECRETS_FAILED=1
                  CHECKS_FAILED=1
                }
              else
                echo "No files changed, skipping detect-secrets check"
              fi
              
              # Build failure summary if any checks failed
              if [ $CHECKS_FAILED -eq 1 ]; then
                echo ""
                echo "========================================================================"
                echo "                    PRE-COMMIT CHECKS FAILED"
                echo "========================================================================"
                echo ""
                
                # ruff-format failures
                if [ $RUFF_FORMAT_FAILED -eq 1 ]; then
                  echo "FAILED: ruff-format"
                  echo "------------------------------------------------------------------------"
                  # Parse files that would be reformatted
                  PARSED_COUNT=0
                  echo "$RUFF_FORMAT_OUTPUT" | grep -F "Would reformat:" | while read -r line; do
                    FILE=$(echo "$line" | sed 's/^Would reformat: *//')
                    if [ -n "$FILE" ]; then
                      echo "  $FILE"
                      PARSED_COUNT=$((PARSED_COUNT + 1))
                    fi
                  done
                  # Fallback: if parsing yielded nothing, show raw output
                  if [ $PARSED_COUNT -eq 0 ]; then
                    echo "  [Unable to parse output, showing raw diagnostics]"
                    echo "$RUFF_FORMAT_OUTPUT" | sed 's/^/  /'
                  fi
                  echo ""
                  echo "  Fix: ruff format <file>"
                  echo ""
                fi
                
                # ruff-check failures
                if [ $RUFF_CHECK_FAILED -eq 1 ]; then
                  echo "FAILED: ruff-check"
                  echo "------------------------------------------------------------------------"
                  # Robust parsing: match standard Unix path patterns with line:col
                  PARSED_COUNT=0
                  echo "$RUFF_CHECK_OUTPUT" | grep -E '^[a-zA-Z0-9_./\\-]+\\.py:[0-9]+:[0-9]+:' | while read -r line; do
                    # Extract file:line:col (everything before the 4th colon)
                    FILE_LOC=$(echo "$line" | sed -E 's/^([^:]+:[0-9]+:[0-9]+):.*$/\\1/')
                    # Extract error info (everything after file:line:col:)
                    ERROR_INFO=$(echo "$line" | sed -E 's/^[^:]+:[0-9]+:[0-9]+: *//')
                    if [ -n "$FILE_LOC" ] && [ -n "$ERROR_INFO" ]; then
                      echo "  $FILE_LOC - $ERROR_INFO"
                      PARSED_COUNT=$((PARSED_COUNT + 1))
                    fi
                  done
                  # Fallback: if parsing yielded nothing, show raw output
                  if [ $PARSED_COUNT -eq 0 ]; then
                    echo "  [Unable to parse output, showing raw diagnostics]"
                    echo "$RUFF_CHECK_OUTPUT" | sed 's/^/  /'
                  fi
                  echo ""
                  echo "  Fix: ruff check --fix <file>"
                  echo ""
                fi
                
                # mypy failures
                if [ $MYPY_FAILED -eq 1 ]; then
                  echo "FAILED: mypy"
                  echo "------------------------------------------------------------------------"
                  # Robust parsing: match standard Unix path patterns with line number
                  PARSED_COUNT=0
                  echo "$MYPY_OUTPUT" | grep -E '^[a-zA-Z0-9_./\\-]+\\.py:[0-9]+:' | while read -r line; do
                    # Extract file:line (everything before the 3rd colon)
                    FILE_LOC=$(echo "$line" | sed -E 's/^([^:]+:[0-9]+):.*$/\\1/')
                    # Extract error message (everything after file:line:)
                    ERROR_MSG=$(echo "$line" | sed -E 's/^[^:]+:[0-9]+: *//')
                    if [ -n "$FILE_LOC" ] && [ -n "$ERROR_MSG" ]; then
                      echo "  $FILE_LOC - $ERROR_MSG"
                      PARSED_COUNT=$((PARSED_COUNT + 1))
                    fi
                  done
                  # Fallback: if parsing yielded nothing, show raw output
                  if [ $PARSED_COUNT -eq 0 ]; then
                    echo "  [Unable to parse output, showing raw diagnostics]"
                    echo "$MYPY_OUTPUT" | sed 's/^/  /'
                  fi
                  echo ""
                  echo "  Fix: Add type hints or adjust type annotations"
                  echo ""
                fi
                
                # detect-secrets failures
                if [ $SECRETS_FAILED -eq 1 ]; then
                  echo "FAILED: detect-secrets"
                  echo "------------------------------------------------------------------------"
                  # Safer parsing: use awk to extract filename field from JSON
                  PARSED_COUNT=0
                  echo "$SECRETS_OUTPUT" | awk -F'"' '/"filename":/ {print $4}' | sort -u | while read -r file; do
                    if [ -n "$file" ]; then
                      echo "  $file"
                      PARSED_COUNT=$((PARSED_COUNT + 1))
                    fi
                  done
                  # Fallback: if parsing yielded nothing, show raw output
                  if [ $PARSED_COUNT -eq 0 ]; then
                    echo "  [Unable to parse output, showing raw diagnostics]"
                    echo "$SECRETS_OUTPUT" | sed 's/^/  /'
                  fi
                  echo ""
                  echo "  Fix: Review and update .secrets.baseline"
                  echo ""
                fi
                
                echo "========================================================================"
                echo ""
                exit 1
              fi
              
              echo "All pre-commit checks passed successfully!"
            '''
          }
        }
      }

      stage('Pytest') {
        script {
          withCredentials([
            usernamePassword(credentialsId: datasifttwinpypiCredentialsId, usernameVariable: 'PYPI_USERNAME', passwordVariable: 'PYPI_PASSWORD')  // pragma: allowlist secret
          ]) {
            sh """
              # Setup Python environment
              sudo rm -rf /usr/local/bin/python*
              sudo rm -rf /usr/bin/python*
              mkdir -p ~/miniconda3
              wget -q -c https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
              bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
              rm -rf ~/miniconda3/miniconda.sh
              export PATH=\${HOME}/miniconda3/bin:\$PATH
              eval "\$(conda shell.bash hook)"
              
              # Create conda environment with Python 3.12
              conda create -n datasift_py312 python=3.12 -y
              conda activate datasift_py312
              
              # Install uv
              curl -LsSf https://astral.sh/uv/install.sh | sh
              
              
              # Install system dependencies
              sudo apt-get update
              sudo apt-get install -y software-properties-common python3-dev gcc
              
              # Navigate to backend directory and install dependencies
              cd src/datasift_opensource/backend
              uv sync --all-groups --all-extras
              
              # Activate virtual environment and run tests from project root
              . .venv/bin/activate
              cd ../../.. && pwd
              export PYTHONPATH=./src/datasift_opensource/backend:./tests
              cp .env.example .env
              # Run unit tests with coverage
              pytest -m unit -v --cov=src --cov-report=xml:coverage.xml --cov-report=term
              
              # Generate coverage report
              coverage report -m
              
              # Display coverage summary
              echo "Unit test coverage report generated"
              coverage report
            """
          }
        }
      }

      stage('Sonar') {
        checkout scm
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
                  # Setup Python environment
                  export PATH=\${HOME}/miniconda3/bin:\$PATH
                  eval "\$(conda shell.bash hook)"
                  conda activate datasift_py312
                  
                  # Navigate to backend directory
                  cd src/datasift_opensource/backend
                  
                  # Build the wheel using uv
                  uv build --wheel
                  
                  # Find the generated wheel file
                  WHEEL_FILE=\$(ls -t dist/*.whl | head -n 1)
                  WHEEL_FILENAME=\$(basename "\$WHEEL_FILE")
                  
                  echo "Built wheel: \$WHEEL_FILENAME"
                  
                  # Push to Artifactory
                  curl -u "\${ARTIFACTORY_USERNAME}:\${ARTIFACTORY_PASSWORD}" \\
                    -T "\$WHEEL_FILE" \\
                    "https://na-public.artifactory.swg-devops.com/artifactory/dataconn-maven-local/datasift-opensource/${VERSION}/\${WHEEL_FILENAME}"
                  
                  echo "Wheel file pushed to Artifactory successfully"
                """
              }
            }
          }
          stage('Publish') {
            script {
              withCredentials([
                usernamePassword(credentialsId: datasifttwinpypiCredentialsId, usernameVariable: 'PYPI_USERNAME', passwordVariable: 'PYPI_PASSWORD') // pragma: allowlist secret
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
