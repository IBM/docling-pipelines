#!/usr/bin/env bash

function logTimestamp {
  echo "Build timestamp ($1):"
  echo $(date +%F_%T)
}

function clean-exit() {
  status=$1
  message=$2
  exitCode=0
  pfx="Info"

  if [[ $1 == "error" ]]; then
    exitCode=1
    pfx="Error"
  elif [[ $1 == "warning" ]]; then
    exitCode=0
    pfx="Warning"
  fi

  if [ ! -z "$message" ]; then
    printf "$pfx: $message\n"
  fi

  logTimestamp "end sonarscan"

  exit $exitCode
}

logTimestamp "start sonarscan"

echo "Running sonarscan.sh for docling-pipelines...."

# Project/scan specific properties
SONAR_HOST_URL="https://sonarqube-prod.apps.wdc-sonarqube-prod.core.cirrus.ibm.com"
SONAR_SCANNER_VERSION=7.0.2.4839
PROJECT_KEY="56865-docling-pipelines"
PROJECT_NAME="docling-pipelines"
JENKINS_BRANCH=$1
SONAR_TOKEN=$2
JENKINS_BUILD_DIR=$3
JENKINS_BUILD_NUMBER=$4

if [[ -z ${JENKINS_BUILD_DIR} ]]; then
  clean-exit error "JENKINS_BUILD_DIR not set!"
fi
if [[ -z ${JENKINS_BUILD_NUMBER} ]]; then
  clean-exit error "JENKINS_BUILD_NUMBER not set!"
fi
if [[ -z ${JENKINS_BRANCH} ]]; then
  clean-exit error "JENKINS_BRANCH not set!"
fi

###################################################################################
# Project-specific source directories for docling-pipelines
###################################################################################
SONAR_SOURCES="src"
SONAR_TESTS="tests"
SONAR_EXCLUSIONS="**/ui/**,**/__pycache__/**,**/*.pyc,tests/**"

# Check if running on MacOS or Linux
if [[ "$(uname -s)" == "Darwin" ]]; then
  SONAR_ZIP=sonar-scanner-cli-${SONAR_SCANNER_VERSION}-macosx-x64.zip
  SONAR_INSTALL_DIR=sonar-scanner-${SONAR_SCANNER_VERSION}-macosx-x64
else
  SONAR_ZIP=sonar-scanner-cli-${SONAR_SCANNER_VERSION}-linux-x64.zip
  SONAR_INSTALL_DIR=sonar-scanner-${SONAR_SCANNER_VERSION}-linux-x64
fi

# Download and extract the sonar-scanner if doesn't already exist
if [ ! -d "${SONAR_INSTALL_DIR}" ]; then
  wget -q https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/${SONAR_ZIP}
  if [ $? -ne 0 ]; then
    clean-exit error "Problem with downloading the sonar-scanner program."
  fi

  unzip ${SONAR_ZIP}
  if [ $? -ne 0 ]; then
    clean-exit error "Problem extracting the sonar-scanner program."
  fi
fi

# Set the host url for the sonar server
sed -e "s#.*sonar.host.url.*#sonar.host.url=${SONAR_HOST_URL}/#" ${SONAR_INSTALL_DIR}/conf/sonar-scanner.properties > /tmp/foo
if [ $? -ne 0 ]; then
  clean-exit error "Problem updating the file, sonar-scanner.properties."
fi
mv /tmp/foo ${SONAR_INSTALL_DIR}/conf/sonar-scanner.properties
if [ $? -ne 0 ]; then
  clean-exit error "Problem moving the file, sonar-scanner.properties."
fi


# Cleanse the branch name from special characters
SCAN_BRANCH=$(echo "$JENKINS_BRANCH" | tr -dc '|[^A-Za-z0-9-]|g')
echo "sonar.branch.name=${SCAN_BRANCH}" >> sonar-project.properties
echo "Info: Running merge sonarscan $JENKINS_BRANCH ..."


# Create the project specific properties
echo "sonar.projectKey=${PROJECT_KEY}" >> sonar-project.properties
echo "sonar.projectName=${PROJECT_NAME}" >> sonar-project.properties
echo "sonar.projectBaseDir=${JENKINS_BUILD_DIR}" >> sonar-project.properties
echo "sonar.projectVersion=${JENKINS_BUILD_NUMBER}" >> sonar-project.properties
echo "sonar.sources=${SONAR_SOURCES}" >> sonar-project.properties
echo "sonar.exclusions=${SONAR_EXCLUSIONS}" >> sonar-project.properties
echo "sonar.tests=${SONAR_TESTS}" >> sonar-project.properties
echo "sonar.sourceEncoding=UTF-8" >> sonar-project.properties
echo "sonar.python.version=3.12" >> sonar-project.properties
echo "sonar.python.coverage.reportPaths=coverage.xml" >> sonar-project.properties
echo "sonar.language=py" >> sonar-project.properties

# sonar credentials
echo "sonar.token=${SONAR_TOKEN}" >> sonar-project.properties

if [ $? -ne 0 ]; then
  clean-exit error "Problem writing the file, sonar-scanner.properties."
fi

echo "==="
echo "sonar-project.properties :"
cat sonar-project.properties
echo "==="

# Run the scanner
${SONAR_INSTALL_DIR}/bin/sonar-scanner --debug

RESULT=$?
if [ ${RESULT} -ne 0 ]; then
  clean-exit error "Problem while running sonar-scanner."
fi
echo "Waiting for sonar server to complete the analysis..."
COUNTER=0
ANALYSIS_ID=
if [ -z "$JENKINS_PULL_REQUEST_BRANCH" ]; then # this is not a pull request
  while [ -z ${ANALYSIS_ID} ]; do
    OUTPUT=$(curl -s -k -u ${SONAR_TOKEN}: "${SONAR_HOST_URL}/api/project_analyses/search?project=${PROJECT_KEY}&branch=${SCAN_BRANCH}&category=VERSION")
    ANALYSIS_ID=$(echo $OUTPUT | jq -r '.analyses[] | select(.events[].name == "'${JENKINS_BUILD_NUMBER}'") | .key')
    
    if [ -z "${ANALYSIS_ID}" ]; then
      let COUNTER+=1
      if [ ${COUNTER} -gt 30 ]; then
        clean-exit warning "Failed to get ANALYSIS_ID after ${COUNTER} attempts."
      fi
      sleep 2
    fi
  done
  echo "ANALYSIS_ID=${ANALYSIS_ID}"

  # Get the analysis from the service
  ANALYSIS_URL="${SONAR_HOST_URL}/api/qualitygates/project_status?analysisId=${ANALYSIS_ID}"
  echo "ANALYSIS_URL=${ANALYSIS_URL}"
  ANALYSIS=$(curl -s -k -u ${SONAR_TOKEN}: ${ANALYSIS_URL})
  echo ${ANALYSIS} | jq .

  # Check the quality gate pass/fail status
  SCAN_RESULT=$(echo ${ANALYSIS} | jq -r .projectStatus.status)
  if [[ "${SCAN_RESULT}" != "OK" ]]; then
    clean-exit error "Scan failed the quality gate.\nSee ${SONAR_HOST_URL}/dashboard?id=${PROJECT_KEY}."
  fi
fi

rm -rf sonar-scanner-cli-7.0.2.4839-linux.zip
rm -rf sonar-project.properties
rm -rf .scannerwork/
rm -rf sonar-scanner-7.0.2.4839-linux
clean-exit success
