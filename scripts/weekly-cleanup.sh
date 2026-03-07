#!/usr/bin/env bash
# Weekly cleanup — reclaims disk space from caches and build artifacts.
# Installed as a launchd plist by setup.sh.

set -euo pipefail

LOG="/tmp/weekly-cleanup.log"
echo "$(date): cleanup started" >> "$LOG"

# Homebrew cache + old versions
brew cleanup --prune=7 >> "$LOG" 2>&1 || true

# System logs older than 7 days
sudo rm -rf /private/var/log/asl/*.asl 2>/dev/null || true

# User logs
rm -rf ~/Library/Logs/* 2>/dev/null || true

# Xcode derived data
rm -rf ~/Library/Developer/Xcode/DerivedData/* 2>/dev/null || true

# Xcode archives older than 30 days
find ~/Library/Developer/Xcode/Archives -mindepth 1 -mtime +30 -delete 2>/dev/null || true

# iOS Simulator caches
rm -rf ~/Library/Developer/CoreSimulator/Caches/* 2>/dev/null || true

# CocoaPods cache
rm -rf ~/Library/Caches/CocoaPods 2>/dev/null || true

# npm/yarn cache
npm cache clean --force >> "$LOG" 2>&1 || true
yarn cache clean >> "$LOG" 2>&1 || true

echo "$(date): cleanup complete" >> "$LOG"
