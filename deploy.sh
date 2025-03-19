#!/bin/bash
# deploy.sh - Script to push changes to GitHub and deploy to PyPI

set -e  # Exit on any error

# Colors for better output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting deployment process for llmdirtree...${NC}"

# 1. Check for uncommitted changes
echo -e "\n${YELLOW}Checking git status...${NC}"
if [[ -n $(git status -s) ]]; then
    echo -e "${YELLOW}You have uncommitted changes. Would you like to:${NC}"
    echo "1. Commit all changes with a message"
    echo "2. Exit to handle changes manually"
    read -p "Enter your choice (1/2): " choice
    
    if [[ $choice == "1" ]]; then
        read -p "Enter commit message: " commit_msg
        git add .
        git commit -m "$commit_msg"
    else
        echo -e "${RED}Deployment aborted. Please commit your changes manually.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}No uncommitted changes.${NC}"
fi

# 2. Push to GitHub main branch
echo -e "\n${YELLOW}Pushing to GitHub main branch...${NC}"
git push origin main

# 3. Check current version and ask for version bump if needed
current_version=$(grep -m 1 "version=" setup.py | cut -d '"' -f 2)
echo -e "\n${YELLOW}Current version is ${current_version}${NC}"
read -p "Do you want to update the version? (y/n): " update_version

if [[ $update_version == "y" ]]; then
    read -p "Enter new version (current: ${current_version}): " new_version
    
    # Update version in setup.py
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS requires an empty string after -i
        sed -i '' "s/version=\"${current_version}\"/version=\"${new_version}\"/g" setup.py
    else
        # Linux version
        sed -i "s/version=\"${current_version}\"/version=\"${new_version}\"/g" setup.py
    fi
    
    # Update version in __init__.py if it exists
    if [[ -f "dirtree/__init__.py" ]]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/__version__ = \"${current_version}\"/__version__ = \"${new_version}\"/g" dirtree/__init__.py
        else
            sed -i "s/__version__ = \"${current_version}\"/__version__ = \"${new_version}\"/g" dirtree/__init__.py
        fi
    fi
    
    echo -e "${GREEN}Version updated to ${new_version}${NC}"
    
    # Commit version change
    git add setup.py dirtree/__init__.py
    git commit -m "Bump version to ${new_version}"
    git push origin main
    
    current_version=$new_version
fi

# 4. Clean previous builds
echo -e "\n${YELLOW}Cleaning previous builds...${NC}"
# Safer removal that won't error if directories don't exist
[[ -d "dist" ]] && rm -rf dist/
[[ -d "build" ]] && rm -rf build/
rm -rf *.egg-info/ 2>/dev/null || true  # Suppress errors for egg-info

# 5. Build the package
echo -e "\n${YELLOW}Building package...${NC}"
python -m build

# 6. Upload to PyPI
echo -e "\n${YELLOW}Uploading to PyPI...${NC}"

# Check for .env file with PyPI credentials
if [[ -f ".env" ]]; then
    echo -e "${YELLOW}Found .env file. Will use PyPI credentials from there.${NC}"
    # Source the .env file to get TWINE_USERNAME and TWINE_PASSWORD
    source .env
fi

# Inform about credential source
if [[ -n "$TWINE_USERNAME" && -n "$TWINE_PASSWORD" ]]; then
    echo -e "${GREEN}Using PyPI credentials from environment variables.${NC}"
elif [[ -f ~/.pypirc ]]; then
    echo -e "${YELLOW}Using PyPI credentials from ~/.pypirc file.${NC}"
else
    echo -e "${YELLOW}No credentials found. You'll be prompted to enter them.${NC}"
fi

read -p "Continue with upload? (y/n): " do_upload

if [[ $do_upload == "y" ]]; then
    python -m twine upload dist/*
    echo -e "${GREEN}Package v${current_version} successfully deployed to PyPI!${NC}"
    
    # 7. Create and push git tag for this version
    echo -e "\n${YELLOW}Creating git tag v${current_version}...${NC}"
    git tag -a "v${current_version}" -m "Release version ${current_version}"
    git push origin "v${current_version}"
    echo -e "${GREEN}Tag pushed to GitHub!${NC}"
else
    echo -e "${YELLOW}Upload skipped. You can manually upload later with:${NC}"
    echo "python -m twine upload dist/*"
fi

echo -e "\n${GREEN}Deployment process completed!${NC}"