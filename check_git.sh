#!/bin/bash

# Get the remote URL for 'origin'
REMOTE_URL=$(git config --get https://github.com/jeonghoonkang)

# Check if a remote URL exists
if [ -z "$REMOTE_URL" ]; then
  echo "오류: 'origin' 원격 저장소를 찾을 수 없습니다."
  exit 1
fi

# Extract "owner/repo" from both HTTPS and SSH URLs
# e.g., https://github.com/owner/repo.git -> owner/repo
# e.g., git@github.com:owner/repo.git -> owner/repo
REPO_PATH=$(echo "$REMOTE_URL" | sed -e 's/.*github.com[:\/]//' -e 's/\.git$//')

# Call the GitHub API and get the 'private' status using jq
# The -s flag for curl makes it silent (no progress meter)
# We pipe the JSON output to jq to extract the value of the "private" key.
IS_PRIVATE=$(curl -s "https://api.github.com/repos/$REPO_PATH" | jq '.private')

# Check the result and print a user-friendly message
if [ "$IS_PRIVATE" == "true" ]; then
  echo "🔒 이 저장소는 Private 입니다."
elif [ "$IS_PRIVATE" == "false" ]; then
  echo "🌍 이 저장소는 Public 입니다."
else
  # Handle cases where the API call might fail (e.g., repo doesn't exist, network error)
  echo "⚠️ 저장소 상태를 확인할 수 없습니다. 저장소 주소가 정확한지 확인해주세요."
  echo "(API 경로: https://api.github.com/repos/$REPO_PATH)"
fi


