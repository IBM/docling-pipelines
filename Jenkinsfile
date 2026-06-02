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

      stage('Code Quality Check') {
        script {
          withCredentials([
            usernamePassword(credentialsId: datasifttwinpypiCredentialsId, usernameVariable: 'PYPI_USERNAME', passwordVariable: 'PYPI_PASSWORD')  // pragma: allowlist secret
          ]) {
            sh '''
              # Install uv
              curl -LsSf https://astral.sh/uv/install.sh | sh
              export PATH="$HOME/.cargo/bin:$PATH"

              # Install system dependencies with robust apt-get update
              sudo rm -rf /var/lib/apt/lists/*
              sudo apt-get clean
              sudo apt-get update --allow-releaseinfo-change -o Acquire::Retries=3 || sudo apt-get update --allow-releaseinfo-change || true
              sudo apt-get install -y software-properties-common python3-dev gcc libldap2-dev libsasl2-dev

              uv sync --all-groups --all-extras

              # Install quality check tools using uv
              uv pip install ruff mypy detect-secrets types-requests types-cachetools

              # Activate virtual environment
              source .venv/bin/activate

              # Make the script executable and run it
              chmod +x scripts/check_modified_files.sh
              ./scripts/check_modified_files.sh
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
              
              # Navigate to backend directory and install dependencies
              uv sync --all-groups --all-extras
              
              # Activate virtual environment and run tests from project root
              . .venv/bin/activate
              pwd
              export PYTHONPATH=./src/:./tests
              cp .env.example .env
              # Run unit tests with coverage
              pytest -m "unit and not slow" -v --cov=src --cov-report=xml:coverage.xml --cov-report=term
              
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
