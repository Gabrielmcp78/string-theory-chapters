#!/bin/bash
# rebuild_and_deploy.sh — Manuscript build, analyze, and git deployment pipeline

set -e

# Change directory to the repository directory
cd "$(dirname "$0")"

echo "=== Starting Rebuild and Deploy: $(date) ==="

# 1. Pull latest changes
echo "--> Pulling latest repository updates..."
# Temporarily stash any EPUB or build files to avoid conflicts during pull
git stash -u || true
git pull origin main --rebase
git stash pop || true

# 2. Run initial build to compile docx to text
echo "--> Compiling DOCX to plain text and HTML..."
python3 build.py

# 3. Run agent analysis on modified scenes (using agy CLI)
echo "--> Running agent analysis for new/modified scenes..."
python3 agent_analysis.py

# 4. Run secondary build to integrate the analysis JSON files
echo "--> Rebuilding site with integrated scene analyses..."
python3 build.py

# 5. Commit and push changes if any diff exists
if [[ -n $(git status --porcelain) ]]; then
  echo "--> Found changes. Committing and pushing..."
  git add .
  git commit -m "Auto-rebuild: $(date '+%Y-%m-%d %H:%M')"
  git push origin main
  echo "--> Changes successfully pushed to GitHub Pages!"
else
  echo "--> No changes detected in build or analysis. Skipping push."
fi

echo "=== Pipeline Completed Successfully! ==="
