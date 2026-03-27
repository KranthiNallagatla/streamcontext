#!/bin/bash
cd /Users/hive_mind/streamcontext
git remote set-url origin https://KranthiNallagatla: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@github.com/KranthiNallagatla/streamcontext.git
git push -u origin main --force
echo "✅ Pushed!"
# Clean up token from remote after push
git remote set-url origin https://github.com/KranthiNallagatla/streamcontext.git
echo "✅ Remote cleaned up!"
