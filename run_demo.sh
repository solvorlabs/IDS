#!/usr/bin/env sh
set -eu
python3 -m src.drone_ids.cli all --out reports/latest
python3 -m unittest discover -s tests -v
