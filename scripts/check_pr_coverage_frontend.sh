#!/bin/bash

# Check that every frontend/src file committed in this branch meets the 80%
# line-coverage threshold. Reads coverage/lcov.info produced by the Vitest
# coverage stage — does NOT re-run vitest.
# Fails the build if any committed source file is below the threshold.
# Usage: ./scripts/check_pr_coverage_frontend.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

MIN_COVERAGE=80
LCOV_FILE="frontend/coverage/lcov.info"

if [ ! -f "${LCOV_FILE}" ]; then
    echo -e "${RED}${LCOV_FILE} not found. Run 'npm run test:coverage' in frontend/ first.${NC}"
    exit 1
fi

echo -e "${YELLOW}Fetching committed frontend source files in this branch...${NC}"

MERGE_BASE=$(git merge-base HEAD origin/main)
COMMITTED=$(git diff --name-only --diff-filter=ACMR "${MERGE_BASE}"..HEAD | grep '^frontend/src/.*\.\(ts\|tsx\)$' | grep -v '\.d\.ts$' | grep -v '\.module\.' || true)

SRC_FILES=()
for file in $COMMITTED; do
    if [ -f "$file" ]; then
        SRC_FILES+=("$file")
    fi
done

if [ ${#SRC_FILES[@]} -eq 0 ]; then
    echo -e "${GREEN}No committed source files under frontend/src/. Skipping coverage check.${NC}"
    exit 0
fi

echo -e "${YELLOW}Committed source files to check:${NC}"
printf '  %s\n' "${SRC_FILES[@]}"
echo ""

echo -e "${YELLOW}Checking per-file line coverage against ${LCOV_FILE}...${NC}"
echo "================================"

FAILED_FILES=()
PASSED_FILES=()
SKIPPED_FILES=()

for file in "${SRC_FILES[@]}"; do
    # lcov.info stores paths relative to the repo root after 'SF:' prefix
    # Extract lines found (LF) and lines hit (LH) for this file
    COVERAGE_DATA=$(python3 - <<EOF
import re, sys

lcov_path = "${LCOV_FILE}"
target    = "${file}"

with open(lcov_path, encoding="utf-8") as f:
    content = f.read()

# Each record is delimited by "end_of_record"
for record in content.split("end_of_record"):
    # Match source file — lcov paths may be absolute or relative
    sf_match = re.search(r"^SF:(.+)$", record, re.MULTILINE)
    if not sf_match:
        continue
    sf_path = sf_match.group(1).strip()
    # Accept if the lcov path ends with the target (handles absolute paths)
    if not sf_path.endswith(target) and not target.endswith(sf_path.lstrip("/")):
        continue
    lf_match = re.search(r"^LF:(\d+)$", record, re.MULTILINE)
    lh_match = re.search(r"^LH:(\d+)$", record, re.MULTILINE)
    if not lf_match or not lh_match:
        print("not_found")
        sys.exit(0)
    lf = int(lf_match.group(1))
    lh = int(lh_match.group(1))
    if lf == 0:
        print("100")  # No trackable lines — treat as fully covered
    else:
        print(int(lh / lf * 100))
    sys.exit(0)

print("not_found")
EOF
)

    if [ "$COVERAGE_DATA" = "not_found" ]; then
        echo -e "  ${YELLOW}SKIP${NC}  ${file} (not in coverage report)"
        SKIPPED_FILES+=("$file")
        continue
    fi

    PCT="$COVERAGE_DATA"

    if [ "$PCT" -ge "$MIN_COVERAGE" ]; then
        echo -e "  ${GREEN}PASS${NC}  ${file}: ${PCT}%"
        PASSED_FILES+=("$file")
    else
        echo -e "  ${RED}FAIL${NC}  ${file}: ${PCT}% (need ${MIN_COVERAGE}%)"
        FAILED_FILES+=("$file")
    fi
done

echo ""
echo "================================"
echo -e "${YELLOW}Summary${NC}"
echo "================================"
echo "Committed src files : ${#SRC_FILES[@]}"
echo "Passed              : ${#PASSED_FILES[@]}"
echo "Failed              : ${#FAILED_FILES[@]}"
echo "Skipped (no data)   : ${#SKIPPED_FILES[@]}"

if [ ${#FAILED_FILES[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}Files below the ${MIN_COVERAGE}% line-coverage threshold:${NC}"
    printf '  %s\n' "${FAILED_FILES[@]}"
    exit 1
fi

echo ""
echo -e "${GREEN}Frontend coverage check passed.${NC}"
exit 0
