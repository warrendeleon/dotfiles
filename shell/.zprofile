eval "$(/opt/homebrew/bin/brew shellenv)"
export PATH="$PATH:$HOME/.local/bin"

# Source machine-specific overrides (e.g. corporate proxy certs)
[[ -f "$HOME/.zprofile.local" ]] && source "$HOME/.zprofile.local"
