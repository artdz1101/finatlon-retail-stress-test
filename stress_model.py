# Current model decisions

This is the current working model state after the 1–18 methodology questionnaire. It is intentionally revisable.

## Research target
Quantify how the product structure of a four-product retail credit portfolio changes:
- annualized credit-risk-adjusted spread;
- six-month risk-adjusted financial result;
- credit-loss burden;
- stress resilience and reverse-stress thresholds.

The objective is not to reconstruct VTB internal profitability.

## Time design
- Historical/calibration window in the current Excel: 31.12.2023–30.06.2026.
- Baseline: 30.06.2026.
- Stress horizon: 2026H2 (0.5 year).

## Baseline perimeter
Use the four 2026H1 product exposures in the newest dataset, subject to source consistency QA. Do not rescale them to a broader 7 tn retail total.

`portfolio_total = sum(Mortgage, Consumer, Auto, Cards exposure at 30.06.2026)`

Current dataset result: RUB 6,573.0 bn.

## Credit risk
Primary product flow measure:

`CC_ann = 2 * ECL_remeasurement_H / ((Exposure_prev + Exposure_current)/2)`

Secondary stock indicator:

`ECL_rate = ECL_reserve / Exposure`

Base 2026H1 uses the direct product formula because the current dataset contains the required product components. Group CoR scaling is a fallback only.

## Pricing and funding
Use current Bank of Russia external proxies stored in the dataset. No bank-specific yield or FTP reconstruction.

Base does not synthetically correct:
- Mortgage for subsidy compensation;
- Cards for grace period/utilization/interchange.

These limitations are handled with sensitivity and discussion.

## Result metrics
Annualized percentage:

`CRAS_i = Pricing_i - Funding_i - CC_i`

`CRAS_P = sum(w_i * CRAS_i)`

Six-month money result:

`RAFR_i,6M = Exposure_i * CRAS_i * 0.5`

`RAFR_P,6M = sum(RAFR_i,6M)`

No opex, fees, taxes or capital charge in Base. No product RAROC.

## History and calibration
The six-date history is sufficient for scenario calibration/range checks but not for robust statistical estimation. Current Moderate/Severe coefficients in config are working defaults and can be replaced after further stress-scenario design.

Known reconstructed 30.06.2024 exposure values remain in the dataset for continuity but are not treated as equal-quality primary calibration inputs. Current config excludes 30.06.2024 and 31.12.2024 credit-cost rows from primary sigma calibration because the latter also depends on the reconstructed prior exposure.

## Structural stress
Total four-product exposure remains fixed at the dynamically calculated 2026H1 Base total. Current structural scenario shifts are explicit percentage-point assumptions from Mortgage into Consumer/Auto/Cards and are provisional.

## Reverse stress
Critical boundary default: `RAFR_6M = 0`.

Find where feasible:
- portfolio credit-cost multiplier;
- critical Consumer/Auto/Cards share when increased at Mortgage's expense;
- own break-even credit cost;
- marginal break-even credit cost versus Mortgage.

Return `NA` when no feasible crossing exists.

## Open tasks, not blockers
1. Page-level reconciliation of 2026H1 product exposure/ECL/ECL remeasurement to the official VTB IFRS PDF.
2. Final choice of Moderate/Severe shock magnitudes after inspecting generated adequacy/calibration diagnostics.
3. Final article wording around mortgage/card pricing limitations.
4. Optional later optimization only after scenario/sensitivity/reverse-stress results are stable.
