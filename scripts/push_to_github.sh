#!/usr/bin/env bash
set -euo pipefail

GITHUB_USER="lantomorroww"
REPO_NAME="dream-research-bot"

if ! command -v git >/dev/null; then
  echo "Git не установлен. sudo apt install git"
  exit 1
fi

if ! ssh -o BatchMode=yes -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
  echo "⚠️  SSH-ключ не настроен для GitHub."
  echo "  ssh-keygen -t ed25519 -C \"you@example.com\""
  echo "  cat ~/.ssh/id_ed25519.pub    # вставьте на https://github.com/settings/keys"
  echo "  ssh -T git@github.com"
  exit 1
fi

git init
git branch -M main
git add .
git commit -m "Initial commit: Dream Research Bot" || true

git remote add origin "git@github.com:${GITHUB_USER}/${REPO_NAME}.git" 2>/dev/null || \
    git remote set-url origin "git@github.com:${GITHUB_USER}/${REPO_NAME}.git"

git push -u origin main
echo
echo "✅ Готово: https://github.com/${GITHUB_USER}/${REPO_NAME}"
