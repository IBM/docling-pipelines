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
  def cfCredentialsId = '32d2a4d4-4a4e-4e21-a564-a292818604db'
  def cloudantCredentialsId = '70926b0c-ed2a-4895-9506-5a5dc78b559b'
  def datasiftwduCredentialsId = 'datasift_wdu_creds'
  def datasiftwducp4dCredentialsId = 'datasift_wdu_creds_cp4d'
  def datasifttwinpypiCredentialsId = 'pypi-creds'
  def jenkinsCredentialsId = 'd89ad365-9ac7-41b6-966d-578b07ae9242'
  def dataconnCredentialsId = 'efe499cb-0bf7-41ff-8a21-eec440e16153'
  def IAUTO1APIKEY = '9b498ed3-fc19-4a41-bb34-d91d6f202245'  // pragma: allowlist secret
  def datasiftstaging = 'datasift-staging'
  def stageCredentialsIds = [
    'funcTest': [
      'CLOUD_FOUNDRY': cfCredentialsId,
      'CLOUDANT': cloudantCredentialsId
    ],
    'integTest': [
      'CLOUD_FOUNDRY': cfCredentialsId,
      'CLOUDANT': cloudantCredentialsId
    ],
    'release': [
      'AFAAS_PUBLISH': afaasCredentialsId,
      'GRGIT': '27403a9f-356a-41ad-a55d-d101b2c615cb',
      'CONTAINER_REGISTRY': 'f147954a-e162-4196-8303-16acea5b80e9',
      'JENKINS': jenkinsCredentialsId,
      'IAUTO1APIKEY': '9b498ed3-fc19-4a41-bb34-d91d6f202245', // pragma: allowlist secret, False positive as per ghe-issue#125
      'ARMADA': '0208e2ad-5aea-4732-8889-f6d5d50459b4'
    ]
  ]

  def isReleaseBuild = (env.BRANCH_NAME == 'main')
  def isCodeAnalysis = isReleaseBuild
  def maxParallelForks = 4
  def image_name = 'datasift-opensource'
  def imageTag = ""
  def branch = scm.branches[0].name
  if (branch.contains("*/")) {
    branch = branch.split("\\*/")[1]
  }
  echo branch

  if (isReleaseBuild) {
    properties([
      disableConcurrentBuilds(),
      buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: isReleaseBuild ? '5' : '5')),
      parameters([
        booleanParam(name: 'SKIP_TESTS', defaultValue: false, description: 'Set to true to skip tests'),
        booleanParam(name: 'LOCAL_DOCKER_TEST', defaultValue: true, description: 'Run local docker validation')
      ]),
      pipelineTriggers([cron('H 1 * * 6')])
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
            usernamePassword(credentialsId: datasiftwduCredentialsId, usernameVariable: 'ARTIFACTORY_USERNAME', passwordVariable: 'ARTIFACTORY_API_KEY'),
            usernamePassword(credentialsId: datasiftwducp4dCredentialsId, usernameVariable: 'TEST_CP4D_USERNAME', passwordVariable: 'TEST_CP4D_PASSWORD'),
            usernamePassword(credentialsId: datasifttwinpypiCredentialsId, usernameVariable: 'PYPI_USERNAME', passwordVariable: 'PYPI_PASSWORD')
          ]) {
            sh """
              echo "TBD"
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