#!/bin/bash

# Script to run ruff and mypy on git-modified Python files
# Usage: ./scripts/check_modified_files.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Fetching modified files...${NC}"

TARGET_BRANCH="${CHANGE_TARGET_BRANCH:-main}"
TARGET_REF="origin/${TARGET_BRANCH}"
DIFF_BASE=$(git merge-base HEAD "${TARGET_REF}")

PYTHON_MODIFIED_FILES=$(git diff --name-only --diff-filter=ACMR "${DIFF_BASE}"..HEAD | grep '\.py$' || true)

RUFF_STATUS=0
MYPY_STATUS=0

if [ -n "$PYTHON_MODIFIED_FILES" ]; then
    echo -e "${YELLOW}Modified Python files:${NC}"
    echo "$PYTHON_MODIFIED_FILES"
    echo ""

    PYTHON_FILES_ARRAY=($PYTHON_MODIFIED_FILES)
    EXISTING_PYTHON_FILES=()
    for file in "${PYTHON_FILES_ARRAY[@]}"; do
        if [ -f "$file" ]; then
            EXISTING_PYTHON_FILES+=("$file")
        fi
    done

    if [ ${#EXISTING_PYTHON_FILES[@]} -gt 0 ]; then
        echo -e "${YELLOW}Running ruff check...${NC}"
        echo "================================"

        if command -v ruff &> /dev/null; then
            if ruff check "${EXISTING_PYTHON_FILES[@]}"; then
                echo -e "${GREEN}Ruff check passed!${NC}"
            else
                echo -e "${RED}Ruff check found issues.${NC}"
                RUFF_STATUS=1
            fi
        else
            echo -e "${RED}ruff not found. Install with: pip install ruff${NC}"
            RUFF_STATUS=1
        fi

        echo ""
        echo -e "${YELLOW}Running mypy analysis...${NC}"
        echo "================================"

        # Filter out examples/ from mypy (standalone scripts, not part of the package)
        MYPY_FILES=()
        for file in "${EXISTING_PYTHON_FILES[@]}"; do
            if [[ "$file" != examples/* ]]; then
                MYPY_FILES+=("$file")
            fi
        done

        if command -v mypy &> /dev/null; then
            if [ ${#MYPY_FILES[@]} -eq 0 ]; then
                echo -e "${GREEN}No files to check with mypy.${NC}"
                MYPY_STATUS=0
            elif mypy --config-file=./pyproject.toml "${MYPY_FILES[@]}"; then
                echo -e "${GREEN}Mypy analysis passed!${NC}"
            else
                echo -e "${RED}Mypy analysis found issues.${NC}"
                MYPY_STATUS=1
            fi
        else
            echo -e "${RED}mypy not found. Install with: pip install mypy${NC}"
            MYPY_STATUS=1
        fi
    else
        echo -e "${GREEN}No existing modified Python files to check.${NC}"
    fi
else
    echo -e "${GREEN}No modified Python files found.${NC}"
fi

echo ""
echo "================================"
echo -e "${YELLOW}Summary${NC}"
echo "================================"
echo "Python files checked: ${#EXISTING_PYTHON_FILES[@]}"
echo -e "Ruff status: $([ $RUFF_STATUS -eq 0 ] && echo -e "${GREEN}PASSED${NC}" || echo -e "${RED}FAILED${NC}")"
echo -e "Mypy status: $([ $MYPY_STATUS -eq 0 ] && echo -e "${GREEN}PASSED${NC}" || echo -e "${RED}FAILED${NC}")"

if [ $RUFF_STATUS -ne 0 ] || [ $MYPY_STATUS -ne 0 ]; then
    exit 1
fi

exit 0
