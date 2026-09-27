$ErrorActionPreference = 'Stop'
python -m src.drone_ids.cli all --out reports\latest
python -m unittest discover -s tests -v
