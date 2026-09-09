#!/usr/bin/env bash
set -euo pipefail
python -m pip install -r other/requirements.txt
pytest -q
python src/stress_model.py --config config/model_config.json
