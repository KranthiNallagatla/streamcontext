#!/bin/bash
cd /Users/hive_mind/streamcontext
git init
git add .
git commit -m "feat: StreamContext v1.0 — never lose AI conversation context again" 2>/dev/null || true
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin https://KranthiNallagatla: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@github.com/KranthiNallagatla/streamcontext.git
git push -u origin main --force
echo "✅ DONE! StreamContext is on GitHub!"
