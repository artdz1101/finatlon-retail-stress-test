# finatlon-retail-stress-test

Reproducible stress testing of a synthetic four-product retail credit portfolio calibrated on public VTB and Bank of Russia data.

## Main research artifact

- [`notebooks/03_stress_model_calibration.ipynb`](notebooks/03_stress_model_calibration.ipynb) — presentation-style research notebook with methodology, tables, figures and findings.

## Run locally

```bash
python -m pip install -r other/requirements.txt
pytest -q
python src/stress_model.py --config config/model_config.json
```

Generated tables, figures and the model report are written to `outputs/`.

## Repository layout

- `src/` — model implementation;
- `tests/` — active automated tests;
- `config/` — active model configuration;
- `notebooks/` — research presentation;
- `other/` — datasets, methodology context, source QA and retained legacy files.
