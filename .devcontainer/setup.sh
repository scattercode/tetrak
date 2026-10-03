#!/usr/bin/env bash
# setup.sh — Tetrak OCR Codespace setup.
# Runs once after the container is created.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Derived from this script's own location rather than written down. The
# repository has been renamed twice -- ocr-pipeline-demo-la, then ocr-pipeline,
# now tetrak -- and each time the name appeared here it was left behind, so it
# does not appear here any more.
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACES="$(cd "$REPO_DIR/.." && pwd)"

# ---------------------------------------------------------------------------
# 1. Clone any companion repositories
# ---------------------------------------------------------------------------
# Optional, and none by default: set TETRAK_COMPANION_REPOS (for example as a
# Codespaces user secret) to a space-separated list of scattercode repositories
# to clone alongside this one, such as private notes you keep next to the work.
# They need their own Codespaces permission, which belongs in your user
# settings, not in this public repository's devcontainer.json.
#
# A failed clone warns rather than aborting. The script runs under `set -e`, so
# an unauthenticated gh, an ungranted permission or a network hiccup would
# otherwise take the whole postCreateCommand down with it -- and the Python
# environment below would never get built. A companion is a convenience
# alongside the work, not a dependency of it.
for repo in ${TETRAK_COMPANION_REPOS:-}; do
  if [ -d "$WORKSPACES/$repo" ]; then
    echo "Already cloned: $repo"
  elif gh repo clone "scattercode/$repo" "$WORKSPACES/$repo"; then
    echo "Cloned scattercode/$repo"
  else
    echo "warning: could not clone $repo; continuing without it" >&2
  fi
done

# ---------------------------------------------------------------------------
# 2. Python virtualenv and dependencies
# ---------------------------------------------------------------------------
# Dependencies are declared in pyproject.toml. This used to install from a
# requirements-dev.txt that does not exist in this repository -- it came from
# the demo repository this container was copied from -- so the step failed on
# every container build.
#
# `[dev]` is pytest and ruff, which is what a Codespace needs to run the fast
# suite. The OCR backends are separate extras: add ,easyocr ,paddle ,marker or
# use [all] if you need them, and expect a long install and model downloads on
# first use.
echo "Creating Python virtualenv..."
python3 -m venv "$REPO_DIR/.venv"

echo "Installing Python dependencies..."
"$REPO_DIR/.venv/bin/pip" install --upgrade pip
# Braced deliberately. Unbraced, `$REPO_DIR[dev]` is array-subscript
# syntax in zsh and expands to nothing; the script is bash, but the line
# gets copied into terminals that are not.
"$REPO_DIR/.venv/bin/pip" install -e "${REPO_DIR}[dev]"

echo ""
echo "Setup complete. Open .devcontainer/workspace.code-workspace, or your own *.local.code-workspace."
