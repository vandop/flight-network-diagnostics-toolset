#!/usr/bin/env bash
set -euo pipefail

# Usage: ./deploy/deploy_aws.sh /path/to/config.yaml
CONFIG_PATH=${1:-server/config.yaml}

sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip

cd "$(dirname "$0")/.."
./setup_env.sh
source .venv/bin/activate
python flight_server.py --config "${CONFIG_PATH}"
