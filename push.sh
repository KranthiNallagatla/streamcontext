#!/bin/bash
cd /Users/hive_mind/streamcontext
git add .
git commit -m "fix: update requirements for Python 3.14 compatibility"
git push -u origin main --force
echo "✅ DONE!"
