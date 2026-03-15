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
    nodeName = "kube_pod_slave"
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

      stage('Pytest') {
        script {
          withCredentials([
            usernamePassword(credentialsId: datasifttwinpypiCredentialsId, usernameVariable: 'PYPI_USERNAME', passwordVariable: 'PYPI_PASSWORD')
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
              
              # Install pip and uv
              wget https://bootstrap.pypa.io/get-pip.py
              python3 get-pip.py
              python3 -m pip install --upgrade pip
              rm -f ./get-pip.py*
              pip install uv
              
              # Install system dependencies
              sudo apt-get update
              sudo apt-get install -y software-properties-common python3-dev gcc
              
              # Navigate to backend directory and install dependencies
              cd src/datasift_opensource/backend
              uv sync --extra dev
              
              # Activate virtual environment and run tests from project root
              # source .venv/bin/activate
              ls -la
              cd ../../..
              ls -la
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
            println "Base branch is \$env.CHANGE_TARGET"
            sh("./sonar/sonarscan.sh \$env.CHANGE_TARGET \$SONAR_PWD \$WORKSPACE \$env.BUILD_ID")
          }
        }
      }

      if (isReleaseBuild) {
        if (currentBuild.currentResult == 'SUCCESS') {
          stage('Publish') {
            script {
              withCredentials([
                usernamePassword(credentialsId: datasifttwinpypiCredentialsId, usernameVariable: 'PYPI_USERNAME', passwordVariable: 'PYPI_PASSWORD')
              ]) {
                sh """
                  echo "TBD"
                """
              }
            }
          }
          stage('Tag repo'){
            script {
              withCredentials([[$class: 'UsernamePasswordMultiBinding', credentialsId: '27403a9f-356a-41ad-a55d-d101b2c615cb', usernameVariable: 'GIT_USERNAME', passwordVariable: 'GIT_PASSWORD']]) {
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
