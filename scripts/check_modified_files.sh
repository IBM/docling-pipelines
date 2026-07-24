#!/bin/bash

# Script to run ruff check and mypy on git-modified files
# Usage: ./scripts/check_modified_files.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Fetching modified files...${NC}"


# Get list of modified Python files
MODIFIED_FILES=$(git diff --name-only --diff-filter=ACMR $(git merge-base HEAD origin/main)..HEAD | grep '\.py$' || true)

if [ -z "$MODIFIED_FILES" ]; then
    echo -e "${GREEN}No modified Python files found.${NC}"
    exit 0
fi

echo -e "${YELLOW}Modified Python files:${NC}"
echo "$MODIFIED_FILES"
echo ""

# Convert to array for processing
FILES_ARRAY=($MODIFIED_FILES)

# Check if files exist (in case of deletions)
EXISTING_FILES=()
for file in "${FILES_ARRAY[@]}"; do
    if [ -f "$file" ]; then
        EXISTING_FILES+=("$file")
    fi
done

if [ ${#EXISTING_FILES[@]} -eq 0 ]; then
    echo -e "${GREEN}No existing modified Python files to check.${NC}"
    exit 0
fi

echo -e "${YELLOW}Running ruff check...${NC}"
echo "================================"

# Run ruff check
if command -v ruff &> /dev/null; then
    if ruff check "${EXISTING_FILES[@]}"; then
        echo -e "${GREEN}Ruff check passed!${NC}"
        RUFF_STATUS=0
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

# Run mypy
if command -v mypy &> /dev/null; then
    if mypy --config-file=./pyproject.toml "${EXISTING_FILES[@]}"; then
        echo -e "${GREEN}Mypy analysis passed!${NC}"
        MYPY_STATUS=0
    else
        echo -e "${RED}Mypy analysis found issues.${NC}"
        MYPY_STATUS=1
    fi
else
    echo -e "${RED}mypy not found. Install with: pip install mypy${NC}"
    MYPY_STATUS=1
fi

echo ""
echo "================================"
echo -e "${YELLOW}Summary${NC}"
echo "================================"
echo "Files checked: ${#EXISTING_FILES[@]}"
echo -e "Ruff status: $([ $RUFF_STATUS -eq 0 ] && echo -e "${GREEN}PASSED${NC}" || echo -e "${RED}FAILED${NC}")"
echo -e "Mypy status: $([ $MYPY_STATUS -eq 0 ] && echo -e "${GREEN}PASSED${NC}" || echo -e "${RED}FAILED${NC}")"

# Exit with error if either check failed
if [ $RUFF_STATUS -ne 0 ] || [ $MYPY_STATUS -ne 0 ]; then
    exit 1
fi

exit 0