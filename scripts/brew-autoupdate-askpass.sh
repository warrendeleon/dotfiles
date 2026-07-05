#!/bin/sh
# Askpass helper for homebrew-autoupdate's sudo casks (unattended upgrades).
#
# Returns the admin password from the macOS login Keychain so the background
# autoupdate job can upgrade casks that need sudo without a GUI prompt.
#
# No secret lives in this file. The password is stored once per machine with:
#   security add-generic-password -U -s brew-autoupdate-sudo -a "$(id -un)" \
#     -T /usr/bin/security -w
# (run it without -w value to be prompted, or pipe the password in).
#
# setup.sh repoints homebrew-autoupdate's generated askpass wrapper at this
# script after `brew autoupdate start`, because that wrapper is regenerated
# (defaulting back to pinentry-mac) on every start.
exec /usr/bin/security find-generic-password -w -s "brew-autoupdate-sudo" -a "$(id -un)"
