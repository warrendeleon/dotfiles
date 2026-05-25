#!/usr/bin/env bash
# macOS System Preferences
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

# Search current folder by default (not whole Mac)
defaults write com.apple.finder FXDefaultSearchScope -string "SCcf"

# New Finder windows open in the home folder (not Recents)
defaults write com.apple.finder NewWindowTarget -string "PfHm"
defaults write com.apple.finder NewWindowTargetPath -string "file://$HOME/"

# Avoid creating .DS_Store files on network or USB volumes
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool true
defaults write com.apple.desktopservices DSDontWriteUSBStores -bool true

# Manual: hide the Recents item from the Finder sidebar.
# No public defaults key exists for this — must be done in the UI.
echo ""
echo "⚠️  Manual step needed: open Finder → Settings (Cmd+,) → Sidebar tab → uncheck 'Recents'"
read -rp "Press ENTER once done... " _ </dev/tty

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
# Enable Develop menu (sandboxed on macOS 14+, use open command fallback)
defaults write com.apple.Safari IncludeDevelopMenu -bool true 2>/dev/null || true

# ===========================================================================
# Locale
# ===========================================================================
# British English (primary), Spanish (Spain), Catalan (Catalonia)
defaults write NSGlobalDomain AppleLanguages -array "en-GB" "es-ES" "ca-ES"
defaults write NSGlobalDomain AppleLocale -string "en_GB"

# Auto-detect language for spell checking (supports all three languages)
defaults write NSGlobalDomain NSSpellCheckerAutomaticallyIdentifiesLanguages -bool true

# ===========================================================================
# App-specific
# ===========================================================================
# Prevent Spotify from opening at login
defaults write com.spotify.client AutoStartSettingIsHidden -int 0
defaults write com.spotify.client HasAutoStartBeenModified -int 1

# Stop Photos.app from auto-opening when an iPhone/camera connects
defaults -currentHost write com.apple.ImageCapture disableHotPlug -bool true

# App Store: auto-update apps in the background
defaults write com.apple.commerce AutoUpdate -bool true

# Disable Chrome's built-in password manager and autofill (use Bitwarden instead).
# Must go in /Library/Managed Preferences/ for Chrome to treat as Mandatory;
# user-domain keys are only Recommended and can be overridden via UI or sync.
# Using PlistBuddy because `defaults` mishandles paths with spaces.
CHROME_MANAGED_PLIST="/Library/Managed Preferences/com.google.Chrome.plist"
sudo mkdir -p "/Library/Managed Preferences"
sudo /usr/libexec/PlistBuddy \
  -c "Delete :PasswordManagerEnabled" -c "Add :PasswordManagerEnabled bool false" \
  -c "Delete :PasswordLeakDetectionEnabled" -c "Add :PasswordLeakDetectionEnabled bool false" \
  -c "Delete :AutofillCreditCardEnabled" -c "Add :AutofillCreditCardEnabled bool false" \
  -c "Delete :AutofillAddressEnabled" -c "Add :AutofillAddressEnabled bool false" \
  -c "Save" \
  "$CHROME_MANAGED_PLIST" 2>/dev/null \
  || sudo /usr/libexec/PlistBuddy \
    -c "Add :PasswordManagerEnabled bool false" \
    -c "Add :PasswordLeakDetectionEnabled bool false" \
    -c "Add :AutofillCreditCardEnabled bool false" \
    -c "Add :AutofillAddressEnabled bool false" \
    -c "Save" \
    "$CHROME_MANAGED_PLIST"
# Clear stale user-domain and /Library/Preferences copies so nothing shadows Mandatory.
defaults delete com.google.Chrome PasswordManagerEnabled 2>/dev/null || true
defaults delete com.google.Chrome PasswordLeakDetectionEnabled 2>/dev/null || true
defaults delete com.google.Chrome AutofillCreditCardEnabled 2>/dev/null || true
defaults delete com.google.Chrome AutofillAddressEnabled 2>/dev/null || true
sudo defaults delete /Library/Preferences/com.google.Chrome PasswordManagerEnabled 2>/dev/null || true
sudo defaults delete /Library/Preferences/com.google.Chrome PasswordLeakDetectionEnabled 2>/dev/null || true
sudo defaults delete /Library/Preferences/com.google.Chrome AutofillCreditCardEnabled 2>/dev/null || true
sudo defaults delete /Library/Preferences/com.google.Chrome AutofillAddressEnabled 2>/dev/null || true

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

# Use the dotfiles dynamic profile as the default profile
defaults write com.googlecode.iterm2 "Default Bookmark Guid" -string "dotfiles-profile"

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

# Switch between full-screen apps / spaces: three-finger swipe left/right
defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerHorizSwipeGesture -int 2
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadThreeFingerHorizSwipeGesture -int 2

# Three-finger drag disabled — conflicts with three-finger swipe up for Mission Control.
# Use click-and-drag instead.
defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerDrag -bool false
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadThreeFingerDrag -bool false

# ===========================================================================
# Siri
# ===========================================================================
# Disable Siri
defaults write com.apple.assistant.support "Assistant Enabled" -bool false
defaults write com.apple.Siri StatusMenuVisible -bool false
defaults write com.apple.Siri UserHasDeclinedEnable -bool true

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
    duti -s com.colliderli.iina "$uti" all 2>/dev/null || true
  done

  for ext in "${VIDEO_EXTENSIONS[@]}"; do
    duti -s com.colliderli.iina ".$ext" all 2>/dev/null || true
  done

  # Sublime Text for Markdown files
  duti -s com.sublimetext.4 .md all 2>/dev/null || true
  duti -s com.sublimetext.4 .markdown all 2>/dev/null || true
  # Sublime Text for plain text and config files
  TEXT_EXTENSIONS=(
    txt log json yaml yml xml csv
    env conf cfg ini toml
  )

  for ext in "${TEXT_EXTENSIONS[@]}"; do
    duti -s com.sublimetext.4 ".$ext" all 2>/dev/null || true
  done
  # Sublime Text for source code files
  CODE_EXTENSIONS=(
    js ts tsx jsx py rb sh bash zsh
    css scss sass less sql swift kt
    java c cpp h m mm rs go php
  )

  for ext in "${CODE_EXTENSIONS[@]}"; do
    duti -s com.sublimetext.4 ".$ext" all 2>/dev/null || true
  done
  echo "Sublime Text set as default for source code files"

  echo "Sublime Text set as default for text/config files"

  echo "Sublime Text set as default for .md files"

  # The Unarchiver for archive formats
  ARCHIVE_EXTENSIONS=(
    zip rar 7z tar gz bz2 xz
    tar.gz tgz tar.bz2 tbz2 tar.xz txz
    cab lzh lha sit sitx
  )

  for ext in "${ARCHIVE_EXTENSIONS[@]}"; do
    duti -s cx.c3.theunarchiver ".$ext" all 2>/dev/null || true
  done
  echo "The Unarchiver set as default for archive formats"

  # Google Chrome as default browser
  duti -s com.google.Chrome http all 2>/dev/null || true
  duti -s com.google.Chrome https all 2>/dev/null || true
  duti -s com.google.Chrome .html all 2>/dev/null || true
  duti -s com.google.Chrome .htm all 2>/dev/null || true
  echo "Google Chrome set as default browser"

  # IINA for audio files (avoids Music.app importing)
  AUDIO_EXTENSIONS=(
    mp3 flac aac wav ogg m4a wma alac
    aiff aif opus ape wv
  )

  for ext in "${AUDIO_EXTENSIONS[@]}"; do
    duti -s com.colliderli.iina ".$ext" all 2>/dev/null || true
  done
  # Preview for image files (explicit, prevents other apps claiming them)
  IMAGE_EXTENSIONS=(
    png jpg jpeg gif webp svg tiff tif
    bmp ico heic heif raw cr2 nef
  )

  for ext in "${IMAGE_EXTENSIONS[@]}"; do
    duti -s com.apple.Preview ".$ext" all 2>/dev/null || true
  done
  # Preview for PDFs (prevents Chrome/Adobe hijacking)
  duti -s com.apple.Preview .pdf all 2>/dev/null || true
  # DB Browser for SQLite database files
  duti -s net.sourceforge.sqlitebrowser .db all 2>/dev/null || true
  duti -s net.sourceforge.sqlitebrowser .sqlite all 2>/dev/null || true
  duti -s net.sourceforge.sqlitebrowser .sqlite3 all 2>/dev/null || true
  echo "DB Browser set as default for SQLite files"

  echo "Preview set as default for PDFs"

  echo "Preview set as default for image formats"

  echo "IINA set as default for audio formats"

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
  if sudo sysctl iogpu.wired_limit_mb="$GPU_LIMIT_MB" 2>/dev/null; then
    echo "GPU wired memory set to ${GPU_LIMIT_MB}MB (75% of ${TOTAL_RAM_MB}MB)"
  else
    echo "Could not set iogpu.wired_limit_mb (sealed volume / SIP / non-Apple-Silicon)"
  fi
else
  echo "GPU wired memory already at ${CURRENT_LIMIT}MB"
fi

# Persist across reboots via launchd
PLIST="/Library/LaunchDaemons/com.dotfiles.gpu-wired-memory.plist"
if [[ ! -f "$PLIST" ]]; then
  if ! sudo tee "$PLIST" > /dev/null << GPUEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dotfiles.gpu-wired-memory</string>
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
  then
    echo "Could not write GPU launchd plist (sudo refused)"
  else
    sudo chmod 644 "$PLIST" 2>/dev/null || true
    # launchctl load is deprecated on macOS 26 for sealed-volume services; try
    # modern bootstrap first, fall back to load, warn if both fail.
    if sudo launchctl bootstrap system "$PLIST" 2>/dev/null \
       || sudo launchctl load "$PLIST" 2>/dev/null; then
      echo "GPU wired memory will persist across reboots"
    else
      echo "Could not load GPU plist. Reboot will reapply the sysctl from the LaunchDaemon on retry."
    fi
  fi
else
  echo "GPU wired memory launchd plist already exists"
fi

# ===========================================================================
# Keyboard
# ===========================================================================
# Key repeat rate and delay: leave as macOS defaults

# Disable auto-capitalise (keep auto-correct enabled)
defaults write NSGlobalDomain NSAutomaticCapitalizationEnabled -bool false

# Enable press-and-hold for accent characters (needed for Spanish á, é, í, ó, ú, ñ)
defaults write NSGlobalDomain ApplePressAndHoldEnabled -bool true

# Disable smart quotes and dashes (breaks code when pasting)
defaults write NSGlobalDomain NSAutomaticQuoteSubstitutionEnabled -bool false
defaults write NSGlobalDomain NSAutomaticDashSubstitutionEnabled -bool false

# Disable double-space replaced with ". " (annoying for code and notes)
defaults write NSGlobalDomain NSAutomaticPeriodSubstitutionEnabled -bool false

# Don't reopen old windows when relaunching apps (cleaner state on launch)
defaults write NSGlobalDomain NSQuitAlwaysKeepsWindows -bool false
# Preview overrides the global setting — disable explicitly so it stops reopening old PDFs
defaults write com.apple.Preview NSQuitAlwaysKeepsWindows -bool false

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
# Power adapter: display off at 15 min, system never sleeps.
# Suppress stderr and exit code — on macOS 26 pmset needs Full Disk Access
# from some terminals and may reject otherwise-valid sudo calls.
sudo pmset -c displaysleep 15 2>/dev/null || true
sudo pmset -c sleep 0        2>/dev/null || true
# Battery: display off at 5 min, system sleep at 10 min
sudo pmset -b displaysleep 5  2>/dev/null || true
sudo pmset -b sleep 10        2>/dev/null || true

echo "Energy: OLED-safe sleep settings applied"

# ===========================================================================
# Screensaver (OLED burn-in protection)
# ===========================================================================
# Screensaver at 2 min (system-wide setting, protects OLED on both power sources)
# Display sleep (pmset) handles the power-specific timeouts above
defaults -currentHost write com.apple.screensaver idleTime -int 120
# Show clock on screensaver
defaults -currentHost write com.apple.screensaver showClock -bool true

echo "Screensaver: 2 min idle, clock enabled"

# ===========================================================================
# Spotlight (exclude dev directories from indexing)
# ===========================================================================
# Exclude ~/Developer from Spotlight via the .metadata_never_index marker file.
# Works on every macOS version; doesn't need sudo. macOS 26 dropped subdirectory
# support in `mdutil -i off`, but the marker file has always been honored at any
# directory level, so we use that as the durable mechanism and only attempt
# mdutil as a nice-to-have on older systems.
if [[ -d "$HOME/Developer" ]]; then
  touch "$HOME/Developer/.metadata_never_index"
  echo "Spotlight indexing excluded for ~/Developer (via .metadata_never_index)"
  # Flush anything already indexed. Non-fatal on macOS 26+ where the subdir form
  # is rejected — the marker file takes over on the next Spotlight pass.
  if command -v mdutil &>/dev/null; then
    sudo mdutil -i off "$HOME/Developer" >/dev/null 2>&1 || true
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
  # Expand globs — each matching directory gets excluded.
  # macOS 26 requires Full Disk Access for tmutil; swallow failures instead of
  # crashing the whole setup.
  for expanded in $path; do
    if [[ -d "$expanded" ]]; then
      if sudo tmutil addexclusion "$expanded" 2>/dev/null; then
        echo "Time Machine: excluded $expanded"
      fi
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
  # Ask for Pi-hole IP (optional — skip for Cloudflare + Quad9 only)
  echo ""
  echo "If you have a Pi-hole on your network, enter its IP address."
  echo "Example: 192.168.10.171"
  PIHOLE_IP=""
  read -rp "Pi-hole IP (press ENTER to skip): " PIHOLE_IP </dev/tty || PIHOLE_IP=""

  if [[ -n "$PIHOLE_IP" ]]; then
    # Pi-hole first, then Cloudflare, then Quad9
    networksetup -setdnsservers "$ACTIVE_SERVICE" "$PIHOLE_IP" 1.1.1.1 1.0.0.1 9.9.9.9 149.112.112.112 \
      && echo "DNS set on $ACTIVE_SERVICE: Pi-hole ($PIHOLE_IP) → Cloudflare → Quad9" \
      || echo "Could not set DNS on $ACTIVE_SERVICE (may need sudo or Network privilege)"
  else
    # Cloudflare + Quad9 only (no Pi-hole)
    networksetup -setdnsservers "$ACTIVE_SERVICE" 1.1.1.1 1.0.0.1 9.9.9.9 149.112.112.112 \
      && echo "DNS set on $ACTIVE_SERVICE: Cloudflare → Quad9" \
      || echo "Could not set DNS on $ACTIVE_SERVICE (may need sudo or Network privilege)"
  fi

  # Flush DNS cache — best-effort; macOS 26 can refuse with sealed-volume errors.
  sudo dscacheutil -flushcache 2>/dev/null || true
  sudo killall -HUP mDNSResponder 2>/dev/null || true
  echo "DNS cache flushed"
else
  echo "No active network service found — set DNS manually"
fi

# ===========================================================================
# Login Items
# ===========================================================================
# macOS 13+ replaced the "System Events → login items" AppleScript API with
# Background Task Management / SMAppService. The old API no longer actually
# registers items and returns "UNKNOWN" to stdout — which clutters output
# without doing anything useful. So redirect stdout to /dev/null as well, and
# print a clear manual-configuration hint after each group.

# Best-effort remove of legacy entries that may still exist from older macOS.
for app in "Spotify" "Microsoft Teams" "Zoom" "Slack" "NordVPN" "Notion" "Rectangle"; do
  osascript -e "tell application \"System Events\" to delete login item \"$app\"" >/dev/null 2>&1 || true
done
echo "Attempted removal of legacy login items: Spotify, Teams, Zoom, Slack, NordVPN, Notion, Rectangle"
echo "  On macOS 13+ these are managed via System Settings → General → Login Items & Extensions."
echo "  Disable any remaining entries there after first launch of each app."

# Best-effort add of login items. On macOS 13+ this usually no-ops silently; the
# apps themselves register via SMAppService on first launch.
for app in "Rocket" "Raycast" "Google Drive" "Tailscale" "1Password" "BetterDisplay" "Elgato Control Center" "Singlebox" "DisplayLink Manager"; do
  osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"/Applications/$app.app\", hidden:true}" >/dev/null 2>&1 || true
done
echo "Attempted to add login items: Rocket, Raycast, Google Drive, Tailscale, 1Password, BetterDisplay, Elgato Control Center, Singlebox, DisplayLink Manager"
echo "  On macOS 13+ each app registers its own login item when first launched; open each once to complete setup."

# 1Password: menu bar only, no main window
defaults write com.1password.1password showInMenuBar -bool true
defaults write com.1password.1password StartAtLogin -bool true
defaults write com.1password.1password ShowMainWindowAtLogin -bool false

# Google Drive: menu bar only
defaults write com.google.drivefs OpenAtLogin -bool true 2>/dev/null || true

# BetterDisplay: menu bar only
defaults write pro.betterdisplay.BetterDisplay launchAtLogin -bool true 2>/dev/null || true
defaults write pro.betterdisplay.BetterDisplay showDockIcon -bool false 2>/dev/null || true

# Singlebox: start minimised
defaults write com.nickvdp.singlebox hideOnLaunch -bool true 2>/dev/null || true

echo "All login items configured to start hidden or in menu bar"

# ===========================================================================
# Remote Access (opt-in)
# ===========================================================================
_remote_reply=""
read -r -p "Enable remote access (SSH + Screen Sharing)? [y/N] " _remote_reply </dev/tty || _remote_reply=""
if [[ "${_remote_reply:-}" =~ ^[Yy]$ ]]; then
  sudo systemsetup -setremotelogin on || echo "Could not enable Remote Login (sudo refused or not supported)"
  # Screen Sharing: the launchctl service name was locked down in macOS 26+.
  # Attempts below are best-effort; if they fail, enable manually in
  # System Settings → General → Sharing → Screen Sharing.
  if sudo launchctl enable system/com.apple.screensharing 2>/dev/null; then
    sudo launchctl kickstart -k system/com.apple.screensharing 2>/dev/null || true
    echo "Remote access enabled (SSH + Screen Sharing)"
  else
    echo "Remote Login enabled. Screen Sharing must be toggled manually on this macOS:"
    echo "  System Settings → General → Sharing → Screen Sharing"
  fi
else
  echo "Remote access skipped"
fi

# ===========================================================================
# Raycast (Spotlight replacement)
# ===========================================================================
# Disable Spotlight shortcut (Cmd+Space) so Raycast can use it
/usr/libexec/PlistBuddy -c "Set :AppleSymbolicHotKeys:64:enabled false" \
  ~/Library/Preferences/com.apple.symbolichotkeys.plist 2>/dev/null || true

echo "Spotlight Cmd+Space disabled"

# Set Raycast hotkey to Cmd+Space
defaults write com.raycast.macos raycastGlobalHotkey -string "Command-49"
echo "Raycast hotkey set to Cmd+Space"

# Note: Configure Raycast window management shortcuts in Raycast Preferences:
#   Ctrl+Option+Left/Right  → Left/Right half
#   Ctrl+Option+Up/Down     → Top/Bottom half
#   Ctrl+Option+Return      → Maximise
#   Ctrl+Option+C           → Centre
#   Ctrl+Option+F           → Fullscreen

# WebStorm keymap and fonts configured in setup.sh (Step 17)

# ===========================================================================
# Xcode
# ===========================================================================
# Show build duration in toolbar
defaults write com.apple.dt.Xcode ShowBuildOperationDuration -bool true

# ===========================================================================
# Gatekeeper
# ===========================================================================
# Disable "Are you sure you want to open this application?" dialog
defaults write com.apple.LaunchServices LSQuarantine -bool false
echo "Gatekeeper first-open dialog disabled"

# ===========================================================================
# Firewall
# ===========================================================================
# Enable macOS firewall (off by default). On macOS 26, socketfilterfw often
# requires Full Disk Access for the invoking terminal; swallow failures and let
# the user toggle manually from System Settings if needed.
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on  2>/dev/null || true
# Allow signed apps automatically
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setallowsigned on  2>/dev/null || true
# Enable stealth mode (don't respond to pings)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on  2>/dev/null || true

echo "Firewall settings applied (verify in System Settings → Network → Firewall)"

# ===========================================================================
# FileVault (disk encryption)
# ===========================================================================
if fdesetup status | grep -q "FileVault is Off"; then
  echo "⚠️  FileVault is OFF — enable it in System Settings > Privacy & Security > FileVault"
  echo "   (Requires interactive setup with recovery key, cannot be fully automated)"
else
  echo "FileVault is already enabled"
fi

# ===========================================================================
# Apply
# ===========================================================================
echo "Restarting affected apps..."
killall Finder 2>/dev/null || true
killall Dock 2>/dev/null || true

echo "macOS preferences applied. Some changes need a logout/restart."
