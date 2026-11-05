#!/usr/bin/env bash
# Mask a database URL's parts in GitHub Actions logs before anything can print them.
#
# Prints ::add-mask:: for the URL held in the named environment variable, its libpq form
# (no SQLAlchemy driver suffix), its password and its host. Prints nothing else, and
# nothing at all when the variable is empty. The Python drill scripts never print any
# part of a connection string; the workflows run this first instead.
#
# Usage: bash scripts/staging/mask_db_url.sh VAR_NAME

set -euo pipefail

name="${1:?usage: mask_db_url.sh VAR_NAME}"
url="${!name:-}"
[ -n "$url" ] || exit 0

mask() {
  if [ -n "$1" ]; then printf '::add-mask::%s\n' "$1"; fi
}

mask "$url"
mask "$(printf '%s' "$url" | sed -E 's#^postgres(ql)?(\+[A-Za-z0-9_]+)?://#postgresql://#')"
rest="${url#*://}"
hostpart="$rest"
case "$rest" in
  *@*)
    # The host never contains '@'; user and password may (percent-encoded), so split on the last one.
    credentials="${rest%@*}"
    hostpart="${rest##*@}"
    case "$credentials" in
      *:*) mask "${credentials#*:}" ;;
    esac
    ;;
esac
mask "${hostpart%%[:/?]*}"
