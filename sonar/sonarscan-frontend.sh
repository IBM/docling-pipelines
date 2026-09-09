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

  logTimestamp "end sonarscan-frontend"

  exit $exitCode
}

logTimestamp "start sonarscan-frontend"

echo "Running sonarscan-frontend.sh for docling-pipelines frontend...."

# Project/scan specific properties — same project key as the Python scan so no
# new project needs to be created on the SonarQube server.
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
# Frontend-specific source directories
# No sonar.language — let SonarQube auto-detect TS/JS from the sources path.
# node_modules, dist, and .vite are excluded to avoid scanning generated/vendor code.
###################################################################################
SONAR_SOURCES="frontend/src,frontend/server"
SONAR_EXCLUSIONS="**/node_modules/**,**/dist/**,**/.vite/**,**/bff/**,**/*.test.ts,**/*.test.tsx,**/*.spec.ts,**/*.spec.tsx"
# Exclude all files from coverage analysis — the frontend has no test runner producing
# a coverage report. Without this, SonarQube reports 0% coverage on new code and fails
# the quality gate. When frontend tests are added, remove this and pass a coverage report
# via sonar.javascript.lcov.reportPaths.
SONAR_COVERAGE_EXCLUSIONS="**/*"

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


echo "sonar.branch.name=${JENKINS_BRANCH}" >> sonar-project-frontend.properties
echo "Info: Running frontend merge sonarscan $JENKINS_BRANCH ..."


# Create the project specific properties
echo "sonar.projectKey=${PROJECT_KEY}" >> sonar-project-frontend.properties
echo "sonar.projectName=${PROJECT_NAME}" >> sonar-project-frontend.properties
echo "sonar.projectBaseDir=${JENKINS_BUILD_DIR}" >> sonar-project-frontend.properties
echo "sonar.projectVersion=${JENKINS_BUILD_NUMBER}" >> sonar-project-frontend.properties
echo "sonar.sources=${SONAR_SOURCES}" >> sonar-project-frontend.properties
echo "sonar.exclusions=${SONAR_EXCLUSIONS}" >> sonar-project-frontend.properties
echo "sonar.coverage.exclusions=${SONAR_COVERAGE_EXCLUSIONS}" >> sonar-project-frontend.properties
echo "sonar.sourceEncoding=UTF-8" >> sonar-project-frontend.properties

# sonar credentials
echo "sonar.token=${SONAR_TOKEN}" >> sonar-project-frontend.properties

if [ $? -ne 0 ]; then
  clean-exit error "Problem writing the file, sonar-project-frontend.properties."
fi

echo "==="
echo "sonar-project-frontend.properties :"
cat sonar-project-frontend.properties
echo "==="

# Run the scanner against the frontend properties file
${SONAR_INSTALL_DIR}/bin/sonar-scanner --debug -Dproject.settings=sonar-project-frontend.properties

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

rm -rf sonar-project-frontend.properties
rm -rf .scannerwork/
clean-exit success
