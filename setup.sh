#!/bin/bash
# StreamContext — Setup Script
# Run this to create the GitHub repo and push all code

echo "🌊 Setting up StreamContext..."

cd /Users/hive_mind/streamcontext

# Init git
git init
git add .
git commit -m "feat: StreamContext v1.0 — never lose AI conversation context again"

# Create GitHub repo and push
gh repo create streamcontext --public --description "Never lose your AI conversation context again. Continue any Claude or ChatGPT chat in a fresh window — intelligently." --push --source=.

echo ""
echo "✅ StreamContext is on GitHub!"
echo ""
echo "Next steps:"
echo "1. cd service && pip install -r requirements.txt"
echo "2. cp .env.example .env && add your API key"
echo "3. python main.py"
echo "4. Install Chrome extension from extension/ folder"
echo ""
echo "🌊 Never lose context again!"
