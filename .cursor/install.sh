#!/usr/bin/env bash
# Idempotent Cloud Agent setup for the Skin-care-with-ML notebook project.
set -euo pipefail

# Run from the repository root regardless of where the script is invoked.
cd "$(dirname "$0")/.."

# The default image ships Python 3.12 but not the venv/ensurepip module, so
# install it once. Guarded so repeat runs skip the apt work when already present.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3.12-venv python3-pip
fi

# Create the virtual environment if it does not exist yet.
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo "Environment ready. Activate with: source .venv/bin/activate"
