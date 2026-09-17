# AGENTS.md — Finatlon retail stress-test

## Mission and source priority

Build a reproducible research stress-test for a synthetic four-product retail portfolio.
The active stage is 03 — stress model. Canonical paths: src/stress_model.py, config/model_config.json,
tests/, notebooks/03_stress_model_calibration.ipynb, other/, outputs/.

Priority:
1. Latest explicit user instructions.
2. other/dataset_vtb_main_clean.xlsx, DATA_MASTER.
3. This file, other/MODEL_DECISIONS.md and active config.
4. Older datasets and decision files only for provenance.

The 17.09.2026 product-mix request supersedes the earlier critical-margin specification.
Do not retain a superseded formula merely because tests pass. Keep the design simple.

## Research framing and communication

- Working title: «Стресс-тестирование риск-доходности продуктовой структуры розничного кредитного портфеля как инструмент управления рисками банка».
- Main question: how does increasing Consumer / Auto / Cards at the expense of Mortgage affect credit losses and RAFR, and is there a critical share beyond which income no longer compensates for credit risk?
- The portfolio combines VTB calibration anchors and external Bank of Russia rates. It is synthetic; it is not VTB's internal product economics.
- Пишите пользователю и готовьте исследовательские материалы на русском; английские термины при первом употреблении поясняйте переводом/расшифровкой. Технические имена сохраняйте.
- Public materials should communicate problem, method, results and limitations; do not expose internal questionnaire history or environment troubleshooting.
- Check current context before asking questions. Use transparent provisional assumptions when explicitly permitted; document them.
- UPDATE_CONTEXT and explicit methodological decisions update affected code, config, tests and documents plus other/CONTEXT_CHANGELOG.md.

## Input and quality

Only other/dataset_vtb_main_clean.xlsx is active. DATA_MASTER contains exposure, ECL reserve,
ECL remeasurement, pricing and funding. MODEL_DATA contains a previous synthetic-margin specification;
it is not used in the current model. The v2 workbook remains an archive and must not be a silent fallback.

Baseline: 30.06.2026. Horizon: 2026H2 = 0.5 year. Products: Mortgage, Consumer, Auto, Cards.
Total exposure is sum of the four baseline exposures, always dynamic; no 7 tn or hard-coded 6,573 bn constraint.

History contains six reporting dates from 31.12.2023 to 30.06.2026. It supports arithmetic QA and ranges,
not robust regression, ML, tail inference or statistical calibration of stress. Reconstructed 2024 values
remain auxiliary. Pochta Bank integration changes the perimeter into 2026H1; do not call all changes organic.

## Direct credit risk and financial result

average_exposure_i = (exposure_i,2025YE + exposure_i,2026H1) / 2
credit_cost_i = 2 * ecl_remeasurement_i,H1 / average_exposure_i
ecl_rate_i = ecl_reserve_i / exposure_i

Use the exact previous half-year date. Recompute Base CC from direct components; verify stored Excel formulas.
ECL rate is a stock indicator; CC is a flow proxy, not official VTB product CoR. Group CoR scaling is only
a documented fallback if direct components become unavailable/non-comparable, never an automatic Base.

CRAS_i = pricing_i - funding_i - credit_cost_i
RAFR_i,6M = exposure_i * CRAS_i * 0.5
CreditLoss_i,6M = exposure_i * credit_cost_i * 0.5

Portfolio money results are sums; portfolio CRAS is exposure-weighted. No Opex, fees, taxes, capital,
RWA, RAROC, optimization, Monte Carlo, PD/LGD model or macroeconometric layer. RAFR is not VTB profit.

## Mortgage and Cards proxies

Main Mortgage pricing proxy: 17.8%, Bank of Russia market mortgage rate for June 2026, MARKET PROXY.
Never call it actual VTB yield. Preserve the workbook 9.0% blended borrower rate as separate sensitivity,
covering at least 9.0% to 17.8%. Other pricing/funding come from the active workbook.

Cards use the external short-term retail rate. It does not represent full card yield given grace,
utilization, interchange, commissions and transactor/revolver mix. If no Cards adverse threshold exists,
say it is conditional on the external proxy; never infer unrestricted permissible card growth.
Always include card pricing sensitivity with an explicitly hypothetical range.

## Stress and product mix

Only Base, Moderate, Severe are main financial states. Pricing, funding and exposure are identical across
them; only CC changes. Current multipliers 1 / 1.5 / 2 are PROVISIONAL MODEL ASSUMPTION,
not final expert decisions or historical sigma estimates.

Three independent experiments: raise exactly one of Consumer, Auto, Cards by reducing Mortgage.
The other two shares and total exposure are fixed. Start at current baseline share; end at current
target share plus Mortgage share. Default step is 0.001; always include the exact feasible endpoint.

Keep four shares/exposures, total, losses, RAFR, annualized CRAS, delta losses and delta RAFR in the raw grid.
Delta is relative to the original composition in the same financial state.

Main marginal results:
delta_RAFR_per_1pp = total * 0.5 * 0.01 * (CRAS_target - CRAS_Mortgage)
delta_CreditLoss_per_1pp = total * 0.5 * 0.01 * (CC_target - CC_Mortgage)

Compare analytical effects to numerical reallocation and raw grid.

## Reverse stress and sensitivities

Primary boundary: RAFR_6M = 0. Search from baseline share upward for the first feasible adverse crossing.
Return critical_share with a status; no fabricated thresholds.
- FEASIBLE_ADVERSE_CROSSING: crossing inside feasible range.
- NO_ADVERSE_CROSSING_WITHIN_FEASIBLE_RANGE: NA, no crossing.
- ALREADY_AT_OR_BELOW_BOUNDARY: NA, initial state already at/below boundary.

Secondary: portfolio CC multiplier at RAFR=0; own and marginal break-even CC may remain diagnostic only.
Factor sensitivity separately applies pricing +/-100 bp, funding +/-100 bp, CC +/-100 bp.
Negative CC from the isolated downward sensitivity is an explicit net-recovery assumption, not a Base input.
PortfolioMix / SevereMix arbitrary combined shifts are not main results.

## Source transparency

FACT: independently reconciled public data only.
MARKET PROXY: CBR pricing/funding, including Mortgage 17.8%.
SYNTHETIC: combined portfolio construction.
MODEL ASSUMPTION: provisional stress multipliers and card sensitivity range.
CALCULATED: CC, CRAS, RAFR, losses, marginal effects and shares.

VTB product exposure/ECL page/note mapping is currently PENDING. Formula consistency is not independent
source reconciliation. Try official sources when useful; never invent page numbers or promote unverified
workbook values to FACT. Document source access and reconciliation in other/SOURCE_QA_2026H1.md.

## Outputs and verification

Compact outputs: baseline_summary.csv (4 rows), scenario_summary.csv (3), product_mix_summary.csv (9),
reverse_stress_auxiliary.csv, factor_sensitivity.csv, mortgage_pricing_sensitivity.csv,
card_pricing_sensitivity.csv, QA and data adequacy reports, model_report.md.
Full product_mix_grid.csv and calculation components belong in outputs/raw/.

Three main share figures, one per target, with Base/Moderate/Severe lines, baseline share, RAFR=0,
and critical markers where feasible. Separate Mortgage sensitivity and optional Cards sensitivity plot.

Run pytest, full model, input/output QA and the research notebook. Validate the economic mechanism,
not merely code execution or predetermined existence/absence of thresholds.
