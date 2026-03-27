#!/bin/bash
# StreamContext — Create GitHub repo and push all code

echo "🌊 Creating StreamContext GitHub repo..."

cd /Users/hive_mind/streamcontext

# Initialize git
git init
git add .
git commit -m "feat: StreamContext v1.0 — never lose AI conversation context again"
git branch -M main

# Create repo using GitHub API (using your token from git config)
curl -s -X POST \
  -H "Authorization: token $(git config --global github.token 2>/dev/null || cat ~/.github_token 2>/dev/null)" \
  -H "Content-Type: application/json" \
  -d '{"name":"streamcontext","description":"Never lose your AI conversation context again — continue any Claude or ChatGPT chat in a fresh window intelligently","private":false,"auto_init":false}' \
  https://api.github.com/user/repos

echo ""
echo "Now push:"
echo "git remote add origin https://github.com/KranthiNallagatla/streamcontext.git"
echo "git push -u origin main"
