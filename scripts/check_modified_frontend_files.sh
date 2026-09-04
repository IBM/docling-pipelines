#!/bin/bash

# Script to run ESLint on git-modified frontend files
# Usage: ./scripts/check_modified_frontend_files.sh
#
# Environment variables:
#   CHANGE_TARGET_BRANCH  — target branch to diff against (default: main)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

TARGET_BRANCH="${CHANGE_TARGET_BRANCH:-main}"
TARGET_REF="origin/${TARGET_BRANCH}"
DIFF_BASE=$(git merge-base HEAD "${TARGET_REF}")

FRONTEND_MODIFIED_FILES=$(git diff --name-only --diff-filter=ACMR "${DIFF_BASE}"..HEAD | grep '^frontend/.*\.\(ts\|tsx\|js\|jsx\)$' || true)

ESLINT_STATUS=0

if [ -n "$FRONTEND_MODIFIED_FILES" ]; then
    echo -e "${YELLOW}Modified frontend files:${NC}"
    echo "$FRONTEND_MODIFIED_FILES"
    echo ""

    FRONTEND_FILES_ARRAY=($FRONTEND_MODIFIED_FILES)
    EXISTING_FRONTEND_FILES=()
    for file in "${FRONTEND_FILES_ARRAY[@]}"; do
        if [ -f "$file" ]; then
            EXISTING_FRONTEND_FILES+=("$file")
        fi
    done

    if [ ${#EXISTING_FRONTEND_FILES[@]} -gt 0 ]; then
        echo -e "${YELLOW}Running ESLint...${NC}"
        echo "================================"

        if [ -d "frontend/node_modules" ]; then
            FRONTEND_FILES_REL=()
            for file in "${EXISTING_FRONTEND_FILES[@]}"; do
                FRONTEND_FILES_REL+=("${file#frontend/}")
            done

            if command -v npx &> /dev/null; then
                if cd frontend; then
                    if npx eslint "${FRONTEND_FILES_REL[@]}"; then
                        echo -e "${GREEN}ESLint passed!${NC}"
                    else
                        echo -e "${RED}ESLint found issues.${NC}"
                        ESLINT_STATUS=1
                    fi
                    cd - > /dev/null || true
                else
                    echo -e "${RED}Failed to change directory to frontend.${NC}"
                    ESLINT_STATUS=1
                fi
            else
                echo -e "${RED}npx not found. Install Node.js/npm first.${NC}"
                ESLINT_STATUS=1
            fi
        else
            echo -e "${RED}frontend/node_modules not found. Run npm install in frontend first.${NC}"
            ESLINT_STATUS=1
        fi

        echo ""
        echo "================================"
        echo -e "${YELLOW}Summary${NC}"
        echo "================================"
        echo "Frontend files checked: ${#EXISTING_FRONTEND_FILES[@]}"
        echo -e "ESLint status: $([ $ESLINT_STATUS -eq 0 ] && echo -e "${GREEN}PASSED${NC}" || echo -e "${RED}FAILED${NC}")"
    else
        echo -e "${GREEN}No existing modified frontend files to check.${NC}"
    fi
else
    echo -e "${GREEN}No modified frontend files found.${NC}"
fi

exit $ESLINT_STATUS
