# ===========================================================================
# Warren de Leon — .zshrc
# ===========================================================================

# Default user
DEFAULT_USER=$(whoami)

# Make sure PREFIX doesn't conflict with nvm
unset PREFIX

# ---------------------------------------------------------------------------
# Powerlevel10k instant prompt (keep near top)
# ---------------------------------------------------------------------------
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

# ---------------------------------------------------------------------------
# Oh My Zsh
# ---------------------------------------------------------------------------
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="powerlevel10k/powerlevel10k"
plugins=(git zsh-autosuggestions)
[[ -f "$ZSH/oh-my-zsh.sh" ]] && source "$ZSH/oh-my-zsh.sh"

# Powerlevel10k config
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

# ---------------------------------------------------------------------------
# Homebrew
# ---------------------------------------------------------------------------
export PATH="/opt/homebrew/bin:$PATH"

# ---------------------------------------------------------------------------
# Ruby (rbenv + system Ruby for CocoaPods)
# ---------------------------------------------------------------------------
export PATH="/opt/homebrew/opt/ruby/bin:/opt/homebrew/lib/ruby/gems/3.0.0/bin:$PATH"
export LDFLAGS="-L/opt/homebrew/opt/ruby/lib"
export CPPFLAGS="-I/opt/homebrew/opt/ruby/include"
export PATH="$HOME/.rbenv/shims:$PATH"
command -v rbenv &>/dev/null && eval "$(rbenv init - zsh)"

# ---------------------------------------------------------------------------
# Android SDK
# ---------------------------------------------------------------------------
export ANDROID_HOME=$HOME/Library/Android/sdk
export PATH=$PATH:$ANDROID_HOME/emulator
export PATH=$PATH:$ANDROID_HOME/platform-tools
export PATH=$PATH:$ANDROID_HOME/tools
export PATH=$PATH:$ANDROID_HOME/tools/bin

# ---------------------------------------------------------------------------
# Java (Temurin 17 for React Native / Android)
# ---------------------------------------------------------------------------
if /usr/libexec/java_home -v 17 &>/dev/null; then
  export JAVA_HOME=$(/usr/libexec/java_home -v 17)
  export PATH="$JAVA_HOME/bin:$PATH"
fi

# ---------------------------------------------------------------------------
# Node (nvm)
# ---------------------------------------------------------------------------
export NVM_DIR="$HOME/.nvm"
[ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && . "/opt/homebrew/opt/nvm/nvm.sh"
[ -s "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm" ] && . "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm"

# ---------------------------------------------------------------------------
# pipx (Python CLI tools)
# ---------------------------------------------------------------------------
export PATH="$PATH:$HOME/.local/bin"

# ---------------------------------------------------------------------------
# ccache — compiler cache for faster C/C++ builds
# ---------------------------------------------------------------------------
export PATH="/opt/homebrew/opt/ccache/libexec:$PATH"

# ---------------------------------------------------------------------------
# Aliases
# ---------------------------------------------------------------------------

# Yarn / npm
alias nr="yarn"
alias nrd="yarn dev"
alias nrs="yarn start"
alias nrt="yarn test"
alias nrb="yarn build"
alias nrl="yarn lint"
alias nrlf="yarn lint:fix"
alias nrv="yarn validate"

# React Native
alias pod="cd ios && pod install && cd .."
alias podclean="cd ios && pod deintegrate && pod install && cd .."
alias rni="yarn ios"
alias rna="yarn android"
alias rns="yarn start"
alias rnsr="yarn start:reset"

# Navigation
alias dev="cd ~/Developer"
alias dots="cd ~/Developer/dotfiles"

# System
alias flush="sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder"
alias ip="curl -s ifconfig.me"
alias localip="ipconfig getifaddr en0"

# Docker (Colima)
alias dcu="docker compose up -d"
alias dcd="docker compose down"
alias dcl="docker compose logs -f"

# Git (beyond .gitconfig aliases)
alias gp="git push"
alias gpl="git pull"
alias gcm="git checkout main"

# Help table
aliases() {
  printf '\n'
  printf '┌────────────┬──────────────────────────────────────────────────┐\n'
  printf '│ Shortcut   │ Expands to                                       │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ nr         │ yarn                                             │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ nrd        │ yarn dev                                         │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ nrs        │ yarn start                                       │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ nrt        │ yarn test                                        │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ nrb        │ yarn build                                       │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ nrl        │ yarn lint                                        │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ nrlf       │ yarn lint:fix                                    │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ nrv        │ yarn validate                                    │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ pod        │ cd ios && pod install && cd ..                    │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ podclean   │ pod deintegrate + pod install                    │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ rni        │ yarn ios                                         │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ rna        │ yarn android                                     │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ rns        │ yarn start                                       │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ rnsr       │ yarn start:reset                                 │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ dev        │ cd ~/Developer                                   │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ dots       │ cd ~/Developer/dotfiles                          │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ flush      │ flush DNS cache                                  │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ ip         │ public IP address                                │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ localip    │ local IP address                                 │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ dcu        │ docker compose up -d                             │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ dcd        │ docker compose down                              │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ dcl        │ docker compose logs -f                           │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ gp         │ git push                                         │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ gpl        │ git pull                                         │\n'
  printf '├────────────┼──────────────────────────────────────────────────┤\n'
  printf '│ gcm        │ git checkout main                                │\n'
  printf '└────────────┴──────────────────────────────────────────────────┘\n'
  printf '\n  Git aliases: run "git aliases" for git-specific shortcuts\n\n'
}

# ---------------------------------------------------------------------------
# Secrets (API keys, tokens — NOT committed to git)
# ---------------------------------------------------------------------------
[[ -f ~/.secrets.env ]] && source ~/.secrets.env
