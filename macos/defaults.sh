#!/usr/bin/env bash
# macOS System Preferences — Warren de Leon
# Run once after fresh install, then log out/restart to apply.

set -euo pipefail

echo "Applying macOS preferences..."

# ===========================================================================
# Finder
# ===========================================================================
# Show file extensions
defaults write NSGlobalDomain AppleShowAllExtensions -bool true

# Show hidden files
defaults write com.apple.finder AppleShowAllFiles -bool true

# Show path bar
defaults write com.apple.finder ShowPathbar -bool true

# Show status bar
defaults write com.apple.finder ShowStatusBar -bool true

# Default to list view
defaults write com.apple.finder FXPreferredViewStyle -string "Nlsv"

# Keep folders on top when sorting by name
defaults write com.apple.finder _FXSortFoldersFirst -bool true

# Disable warning when changing file extension
defaults write com.apple.finder FXEnableExtensionChangeWarning -bool false

# Avoid creating .DS_Store files on network or USB volumes
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool true
defaults write com.apple.desktopservices DSDontWriteUSBStores -bool true

# ===========================================================================
# Screenshots
# ===========================================================================
# Save screenshots to ~/Downloads
defaults write com.apple.screencapture location -string "$HOME/Downloads"

# Save as PNG
defaults write com.apple.screencapture type -string "png"

# ===========================================================================
# Safari (Development)
# ===========================================================================
# Enable Develop menu
defaults write com.apple.Safari IncludeDevelopMenu -bool true

# ===========================================================================
# Locale
# ===========================================================================
# British English
defaults write NSGlobalDomain AppleLanguages -array "en-GB"
defaults write NSGlobalDomain AppleLocale -string "en_GB"

# ===========================================================================
# App-specific
# ===========================================================================
# Prevent Spotify from opening at login
defaults write com.spotify.client AutoStartSettingIsHidden -int 0
defaults write com.spotify.client HasAutoStartBeenModified -int 1

# Disable Chrome's built-in password manager (use 1Password instead)
defaults write com.google.Chrome PasswordManagerEnabled -bool false
defaults write com.google.Chrome AutofillCreditCardEnabled -bool false

# ===========================================================================
# Appearance
# ===========================================================================
# Dark mode
defaults write NSGlobalDomain AppleInterfaceStyle -string "Dark"

# ===========================================================================
# Mission Control
# ===========================================================================
# Don't automatically rearrange Spaces based on most recent use
defaults write com.apple.dock mru-spaces -bool false

# ===========================================================================
# Security
# ===========================================================================
# Require password immediately after sleep or screen saver
defaults write com.apple.screensaver askForPassword -int 1
defaults write com.apple.screensaver askForPasswordDelay -int 0

# ===========================================================================
# Menu Bar
# ===========================================================================
# Show battery percentage
defaults write com.apple.controlcenter "NSStatusItem Visible Battery" -bool true
defaults -currentHost write com.apple.controlcenter BatteryShowPercentage -bool true

# ===========================================================================
# TextEdit
# ===========================================================================
# Default to plain text (not rich text)
defaults write com.apple.TextEdit RichText -int 0

# ===========================================================================
# iTerm2
# ===========================================================================
# Make iTerm2 the default terminal app
defaults write com.googlecode.iterm2 "Default Terminal" -string "iTerm2"

# ===========================================================================
# Dock
# ===========================================================================
# Auto-hide the Dock
defaults write com.apple.dock autohide -bool true

# Icon size (65pt)
defaults write com.apple.dock tilesize -int 65

# Magnification on hover (128pt)
defaults write com.apple.dock magnification -bool true
defaults write com.apple.dock largesize -int 128

# Bottom position (default)
defaults delete com.apple.dock orientation 2>/dev/null || true

# Minimise windows into their app icon
defaults write com.apple.dock minimize-to-application -bool true

# Don't show recent apps in Dock
defaults write com.apple.dock show-recents -bool false

# Remove all default Dock items and add custom ones
defaults write com.apple.dock persistent-apps -array

# Add apps to Dock
dock_add() {
  defaults write com.apple.dock persistent-apps -array-add \
    "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>file://$1</string><key>_CFURLStringType</key><integer>15</integer></dict></dict></dict>"
}

dock_add "/System/Applications/Apps.app/"
dock_add "/System/Applications/System Settings.app/"
dock_add "/System/Applications/Messages.app/"
dock_add "/Applications/Google Chrome.app/"
dock_add "/System/Applications/Notes.app/"
dock_add "/System/Applications/Calendar.app/"
dock_add "/Applications/Singlebox.app/"
dock_add "/System/Applications/iPhone Mirroring.app/"
dock_add "/Applications/iTerm.app/"

# ===========================================================================
# Trackpad
# ===========================================================================
# Tracking speed (0-3, 3 = fastest)
defaults write NSGlobalDomain com.apple.trackpad.scaling -float 3

# Two-finger right-click
defaults write com.apple.AppleMultitouchTrackpad TrackpadRightClick -bool true

# Smart zoom (two-finger double tap)
defaults write com.apple.AppleMultitouchTrackpad TrackpadTwoFingerDoubleTapGesture -int 1

# Force click disabled
defaults write com.apple.AppleMultitouchTrackpad ForceSuppressed -bool false

# Haptic feedback
defaults write com.apple.AppleMultitouchTrackpad ActuationStrength -int 1

# Click weight (medium)
defaults write com.apple.AppleMultitouchTrackpad FirstClickThreshold -int 1

# Mission Control: three-finger swipe up
defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerVertSwipeGesture -int 2

# ===========================================================================
# Default Apps (IINA for all video formats)
# ===========================================================================
if command -v duti &>/dev/null; then
  VIDEO_TYPES=(
    public.movie
    public.avi
    public.mpeg
    public.mpeg-4
    public.3gpp
    public.3gpp2
    com.apple.quicktime-movie
    com.microsoft.windows-media-wmv
    org.matroska.mkv
    com.microsoft.advanced-systems-format
    public.avchd-mpeg-2-transport-stream
    io.mpv.m2ts
    public.mpeg-2-transport-stream
    com.apple.m4v-video
  )

  VIDEO_EXTENSIONS=(
    mp4 mov avi mkv wmv flv webm m4v
    mpg mpeg m2ts mts ts 3gp 3g2
    ogv vob divx f4v asf rm rmvb
  )

  for uti in "${VIDEO_TYPES[@]}"; do
    duti -s com.colliderli.iina "$uti" all 2>/dev/null
  done

  for ext in "${VIDEO_EXTENSIONS[@]}"; do
    duti -s com.colliderli.iina ".$ext" all 2>/dev/null
  done

  # Sublime Text for Markdown files
  duti -s com.sublimetext.4 .md all 2>/dev/null
  duti -s com.sublimetext.4 .markdown all 2>/dev/null
  echo "Sublime Text set as default for .md files"

  echo "IINA set as default video player for all formats"
else
  echo "duti not found — install via Homebrew to set default apps"
fi

# ===========================================================================
# GPU Wired Memory (Apple Silicon — for local LLMs via Ollama/MLX)
# ===========================================================================
# Allocate ~75% of total RAM to GPU wired memory
TOTAL_RAM_MB=$(( $(sysctl -n hw.memsize) / 1024 / 1024 ))
GPU_LIMIT_MB=$(( TOTAL_RAM_MB * 3 / 4 ))
CURRENT_LIMIT=$(sysctl -n iogpu.wired_limit_mb 2>/dev/null || echo "0")

if (( GPU_LIMIT_MB > CURRENT_LIMIT )); then
  sudo sysctl iogpu.wired_limit_mb="$GPU_LIMIT_MB"
  echo "GPU wired memory set to ${GPU_LIMIT_MB}MB (75% of ${TOTAL_RAM_MB}MB)"
else
  echo "GPU wired memory already at ${CURRENT_LIMIT}MB"
fi

# Persist across reboots via launchd
PLIST="/Library/LaunchDaemons/com.warrendeleon.gpu-wired-memory.plist"
if [[ ! -f "$PLIST" ]]; then
  sudo tee "$PLIST" > /dev/null << GPUEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.warrendeleon.gpu-wired-memory</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>sysctl iogpu.wired_limit_mb=$(( $(sysctl -n hw.memsize) / 1024 / 1024 * 3 / 4 ))</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
GPUEOF
  sudo chmod 644 "$PLIST"
  sudo launchctl load "$PLIST"
  echo "GPU wired memory will persist across reboots"
else
  echo "GPU wired memory launchd plist already exists"
fi

# ===========================================================================
# Keyboard
# ===========================================================================
# Fastest key repeat rate (1 = fastest)
defaults write NSGlobalDomain KeyRepeat -int 2

# Shortest delay before key repeat starts (15 = shortest)
defaults write NSGlobalDomain InitialKeyRepeat -int 15

# Disable auto-capitalise (keep auto-correct enabled)
defaults write NSGlobalDomain NSAutomaticCapitalizationEnabled -bool false

# ===========================================================================
# Sound
# ===========================================================================
# Ensure startup chime is enabled
sudo nvram StartupMute=%00 2>/dev/null || true

# Ensure UI sound effects are enabled
defaults write NSGlobalDomain com.apple.sound.uiaudio.enabled -int 1

# Ensure feedback sound when volume changes
defaults write NSGlobalDomain com.apple.sound.beep.feedback -int 1

# ===========================================================================
# Energy (prevent sleep when plugged in)
# ===========================================================================
# Disable display sleep when on power adapter (0 = never)
sudo pmset -c displaysleep 0 2>/dev/null
# Disable system sleep when on power adapter
sudo pmset -c sleep 0 2>/dev/null
# Keep default sleep on battery (5 min display, 10 min system)
sudo pmset -b displaysleep 5 2>/dev/null
sudo pmset -b sleep 10 2>/dev/null

echo "Energy: never sleep when plugged in, normal sleep on battery"

# ===========================================================================
# Spotlight (exclude dev directories from indexing)
# ===========================================================================
if command -v mdutil &>/dev/null; then
  # Disable Spotlight indexing for Developer folder
  if [[ -d "$HOME/Developer" ]]; then
    sudo mdutil -i off "$HOME/Developer" 2>/dev/null
    echo "Spotlight indexing disabled for ~/Developer"
  fi
fi

# ===========================================================================
# Time Machine (exclude heavy dev directories from backups)
# ===========================================================================
TM_EXCLUDES=(
  "$HOME/Developer/*/node_modules"
  "$HOME/Developer/*/ios/Pods"
  "$HOME/Developer/*/ios/build"
  "$HOME/Developer/*/android/.gradle"
  "$HOME/Developer/*/android/app/build"
  "$HOME/.gradle"
  "$HOME/.cocoapods"
  "$HOME/.npm"
  "$HOME/.nvm/.cache"
  "$HOME/Library/Android/sdk"
)

for path in "${TM_EXCLUDES[@]}"; do
  # Expand globs — each matching directory gets excluded
  for expanded in $path; do
    if [[ -d "$expanded" ]]; then
      sudo tmutil addexclusion "$expanded" 2>/dev/null
      echo "Time Machine: excluded $expanded"
    fi
  done
done
echo "Time Machine exclusions applied"

# ===========================================================================
# DNS (Pi-Hole at home, Cloudflare + Quad9 fallback)
# ===========================================================================
# Detect the active network service (Wi-Fi or Ethernet)
ACTIVE_SERVICE=""
while IFS= read -r service; do
  # Skip empty lines
  [[ -z "$service" ]] && continue
  # Check if this service has an IP (i.e., is active)
  if networksetup -getinfo "$service" 2>/dev/null | grep -q "^IP address: [0-9]"; then
    ACTIVE_SERVICE="$service"
    break
  fi
done < <(networksetup -listallnetworkservices 2>/dev/null | tail -n +2)

if [[ -n "$ACTIVE_SERVICE" ]]; then
  # Pi-Hole first (home network), then Cloudflare (1.1.1.1), then Quad9 (9.9.9.9)
  # When away from home, Pi-Hole is unreachable and falls through to Cloudflare/Quad9
  networksetup -setdnsservers "$ACTIVE_SERVICE" 192.168.10.171 1.1.1.1 1.0.0.1 9.9.9.9 149.112.112.112
  echo "DNS set on $ACTIVE_SERVICE: Pi-Hole → Cloudflare → Quad9"

  # Flush DNS cache
  sudo dscacheutil -flushcache 2>/dev/null
  sudo killall -HUP mDNSResponder 2>/dev/null
  echo "DNS cache flushed"
else
  echo "No active network service found — set DNS manually"
fi

# ===========================================================================
# Xcode
# ===========================================================================
# Show build duration in toolbar
defaults write com.apple.dt.Xcode ShowBuildOperationDuration -bool true

# ===========================================================================
# Apply
# ===========================================================================
echo "Restarting affected apps..."
killall Finder 2>/dev/null || true
killall Dock 2>/dev/null || true

echo "macOS preferences applied. Some changes need a logout/restart."
