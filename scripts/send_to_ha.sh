#!/bin/bash

DEST="satellite@192.168.1.67:/opt/homeassistant/config/custom_components/loup_garou"
SRC_DIR="$(cd "$(dirname "$0")/../custom_components/loup_garou" && pwd)"

echo "Sending $SRC_DIR to $DEST..."

rsync -avz --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.pytest_cache' \
    --exclude '*.egg-info' \
    "$SRC_DIR/" "$DEST/"

echo "Done."