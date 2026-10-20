#!/usr/bin/env bash
# Build the wheel and publish it to PyPI.
#
# The API token is NEVER stored in this file. Export it first, e.g.:
#
#   set -a && source .env && set +a   # .env is gitignored
#   ./build.sh
#
# Create/rotate the token at https://pypi.org/manage/account/token/
set -euo pipefail

if [[ -z "${PYPI_TOKEN:-}" ]]; then
    echo "error: PYPI_TOKEN is not set. See the comment at the top of build.sh." >&2
    exit 1
fi

rm -rf dist build steely.egg-info

uv build --wheel

twine upload dist/* -u __token__ -p "$PYPI_TOKEN"

rm -rf dist build steely.egg-info


