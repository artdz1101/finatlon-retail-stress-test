# Is 2023–2026H1 enough data for this stress test?

## Current dataset size
The newest Excel currently contains six reporting dates:
- 31.12.2023;
- 30.06.2024;
- 31.12.2024;
- 30.06.2025;
- 31.12.2025;
- 30.06.2026.

With four products this is 24 product-date rows.

## Conclusion
**Yes — enough for the chosen scenario/sensitivity/reverse-stress design.**

It is enough to:
- anchor the 2026H1 Base;
- inspect historical ranges and direction of pricing/funding/credit-risk changes;
- calibrate transparent working stress magnitudes;
- run portfolio-mix sensitivity at fixed portfolio size;
- calculate reverse-stress thresholds mathematically;
- test robustness of conclusions under alternative assumptions.

It is **not enough** to claim a statistically estimated stress model. Do not use this sample to justify:
- complex regression with stable coefficients;
- ML;
- reliable tail probabilities/percentiles;
- causal inference;
- precise crisis-frequency estimates.

## Why this is acceptable for the article
The model is a scenario stress test, not a forecasting econometric model. Basel stress-testing principles explicitly allow a range from sensitivity analysis to scenario and reverse stress testing, and state that scenario design depends on purpose, data availability and horizon. Historical and hypothetical scenarios can be combined, particularly when the available history does not contain a severe crisis episode.

Reference:
`https://www.bis.org/committees/bcbs/basel-consolidated-guidelines/module/rma/30`

## Important qualification
The 30.06.2024 product exposures in the working dataset are reconstructed midpoint-like values rather than strict identities. Therefore the effective clean credit-cost history is shorter than six dates. This does not block the stress test, but it makes statistical calibration weaker and is one reason scenario coefficients remain explicit working assumptions.

## Recommended use of the history
1. Use all source-consistent rate observations to describe pricing/funding ranges.
2. Use only directly reproducible credit-cost observations for primary credit-risk calibration.
3. Use reconstructed values only as auxiliary diagnostics unless primary-source verification upgrades them.
4. Use hypothetical overlays for Severe if the observed history is not sufficiently adverse.
5. Keep scenario parameters in config so they can be changed without rewriting the model.
