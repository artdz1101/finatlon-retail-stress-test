# AGENTS.md — Finatlon retail stress-test

## Mission
Build and iteratively improve the reproducible stress-test for the Finatlon scientific article. The research object is a four-product retail credit portfolio: Mortgage, Consumer, Auto and Cards. The active stage is **03 — stress model**. Stages 01 (dataset) and 02 (methodology) are already working stages completed enough to proceed; reopen them only when a new source or a model result creates a concrete reason.

The repository is a **working research state**, not an immutable specification. The article may change materially.

## Article framing
- Working title: **«Стресс-тестирование риск-доходности продуктовой структуры розничного кредитного портфеля как инструмент управления рисками банка»**.
- The research object is a **synthetic four-product retail credit portfolio calibrated on public VTB and Bank of Russia data**, not VTB as a bank and not a reconstruction of VTB's internal profitability or portfolio-management decisions.
- Public VTB exposure values provide calibration anchors for the baseline size and weights. Once combined with external pricing/funding proxies and model assumptions, the resulting portfolio is synthetic and must not be presented as VTB's actual product economics.
- Central research question: **at what share of higher-risk products does additional modeled income cease to compensate for higher credit losses and loss of stress resilience?**
- The intended scientific output is a set of economically interpretable thresholds and sensitivity results, not a catalogue of source fields or scenario tables.
- Public-facing notebooks and article materials must read as research communication: problem, method, results, interpretation and limitations. Do not expose internal discussions, questionnaire history, implementation logs or environment-specific troubleshooting.

## Source priority
Unless the user explicitly changes it:
1. Latest explicit user instruction in the current session.
2. Newest numeric dataset in the repository (`other/dataset_vtb_main_v2.xlsx` now).
3. `other/AGENTS.md`, `other/MODEL_DECISIONS.md`, `other/DECISIONS_1_18.md`, `config/model_config.json`.
4. Older datasets/chats only for provenance or unresolved gaps.

Do not silently average conflicting values. Use the higher-priority source and document a material conflict.

## Context update command
When the user writes:

`UPDATE_CONTEXT: <instruction>`

apply it as a project-level change. Update the affected context files/config/code/tests, append a short entry to `other/CONTEXT_CHANGELOG.md`, run relevant QA, and continue from the revised context. Do not keep an older default merely because it is already coded.

Short numbered answers such as `1A 2B 3A...` are also project decisions and must be propagated into repository context when they affect the model.

## Interaction rules
- Check current files/data before asking a question.
- Do not ask again about a decision already present in context unless new evidence creates a real contradiction.
- Prefer a transparent working default over blocking progress, but label it as provisional in ordinary language.
- If a source cannot be verified, do not invent a value. Try the official source; if it is unavailable, use the documented fallback in `other/DATA_GAPS_AND_FALLBACKS.md` or keep the issue open.
- Keep outputs reproducible and code/config easy to change.

## Provenance wording
In public-facing research materials, clearly separate published facts, external market proxies, synthetic portfolio construction, scenario assumptions and formula-derived results. This is a conceptual provenance distinction, not a mandatory machine-readable label on every variable. Use normal precise wording.

Always distinguish:
- published VTB values from external Bank of Russia rates;
- observed inputs from formula-derived values and scenario assumptions;
- external funding proxies from VTB internal FTP;
- the research credit-cost proxy from official product CoR;
- model financial results from actual VTB profit, NIM, product margin or RAROC.

## Final methodological decisions from the 1–18 questionnaire
The current selections are:

`1A 2B 3A 4A 5A 6-direct-first 7A 8A 9A 10A 11C 12A+B 13A 14A 15A(2023–2026H1) 16B 17B 18A1-sum`

Detailed interpretation is in `other/DECISIONS_1_18.md`.

### Baseline and horizon
- Baseline date: **30.06.2026 (2026H1)**.
- Stress horizon: **2026H2**, i.e. 0.5 year.
- Baseline perimeter: the four product exposures at 30.06.2026 from the current dataset, if source QA remains consistent.
- Portfolio size is **not 7 tn by assumption**. It is calculated as `sum(exposure_i)` for the four baseline products. With the current dataset this is RUB 6,573.0 bn, but code must derive it dynamically.
- Structural experiments keep that baseline four-product total fixed and change only weights.

### History
- Current usable repository window: **31.12.2023–30.06.2026** (six reporting dates / 24 product rows in the current Excel).
- Use history for calibration, ranges, diagnostics and reasonableness checks.
- Do not claim that six reporting dates are enough for a robust regression, ML model, tail distribution or causal inference.
- This history is adequate for a transparent scenario/sensitivity/reverse-stress design, provided scenarios are treated as scenario assumptions rather than statistically estimated forecasts.

### Missing/reconstructed history
User selected 2B together with 16B. Interpret jointly:
- reconstructed/interpolated values may remain in the working dataset for continuity;
- only values obtainable through a strict reproducible identity should be treated as equivalent-quality calculated inputs for primary calibration;
- midpoint/interpolation values are auxiliary and must not silently drive primary calibration;
- the known 30.06.2024 exposure reconstruction affects adjacent credit-cost calculations, so current config excludes 30.06.2024 and 31.12.2024 credit-cost rows from the primary historical sigma calibration. This exclusion is a working QA rule and can be revised after source verification.

## Credit risk
Primary risk measure: annualized product credit-cost proxy.

For product i and half-year t:

`average_exposure_i,t = (exposure_i,t-1 + exposure_i,t) / 2`

`credit_cost_i,t = 2 * ecl_remeasurement_i,t / average_exposure_i,t`

`ecl_rate_i,t = ecl_reserve_i,t / exposure_i,t`

ECL rate is an additional stock indicator, not CoR.

For 2026H1 Base, calculate credit cost **directly from the product components** when 31.12.2025 exposure, 30.06.2026 exposure and H1 2026 ECL remeasurement are available and source-consistent. Do not scale product credit cost by Group CoR in the main method.

If those product components become unavailable or prove non-comparable, follow the fallback hierarchy in `other/DATA_GAPS_AND_FALLBACKS.md`; Group CoR scaling is only a fallback/sensitivity, not Base.

## Pricing and funding
Base uses the Bank of Russia rate proxies already stored in the dataset:
- Mortgage: published borrower-side mortgage proxy in the dataset; do not add a subsidy compensation in Base.
- Consumer: long-term household loan rate proxy.
- Auto: auto-loan rate proxy.
- Cards: short-term household loan rate proxy; do not add grace/utilization adjustments in Base.
- Mortgage/Consumer/Auto funding: long-term household deposit proxy.
- Cards funding: short-term household deposit proxy.

The mortgage and card proxies have known economic limitations. Keep optional sensitivity analysis rather than silently correcting Base with invented coefficients.

## Financial result
Calculate both percentage and money results.

Annualized percentage metric:

`credit_risk_adjusted_spread_i = pricing_i - funding_i - credit_cost_i`

Portfolio annualized spread:

`credit_risk_adjusted_spread_P = sum(weight_i * credit_risk_adjusted_spread_i)`

Six-month money result:

`risk_adjusted_financial_result_i_6M = exposure_i * credit_risk_adjusted_spread_i * 0.5`

`risk_adjusted_financial_result_P_6M = sum_i(risk_adjusted_financial_result_i_6M)`

This is pre-operating and excludes fees/commissions, operating expenses, taxes and capital charges. Do not call it VTB profit, NIM, actual product margin or RAROC.

## Opex, capital and RWA
- No operating-cost layer in Base.
- No product RWA/capital denominator in Base.
- Do not calculate genuine product RAROC.
- These can be added later only through an explicit context change.

## Stress architecture
Keep these modules available:
- Base;
- Moderate;
- Severe;
- Structural;
- Combined;
- factor sensitivity;
- product-share sensitivity;
- reverse stress.

Current Moderate/Severe numerical calibration is a **working default**, not a final research claim. The short history is used only as a calibration anchor. Current structural shifts are explicit percentage-point assumptions in config so they do not depend on questionable interpolated half-year weights.

## Reverse stress
At minimum calculate:
- portfolio-wide credit-cost multiplier at which the six-month result reaches the critical boundary;
- critical Consumer/Auto/Cards share when that product replaces Mortgage, if a feasible crossing exists;
- product break-even credit cost;
- marginal break-even credit cost versus Mortgage.

If a threshold does not exist in the feasible domain, return `NA` with the direction/status. Do not force a number.

## Required outputs
`outputs/` should contain:
- QA report;
- data adequacy report;
- baseline product results;
- scenario product results;
- scenario summary;
- factor sensitivity;
- structural sensitivity;
- reverse stress;
- mortgage pricing sensitivity (if enabled);
- figures;
- `model_report.md`.

## Important scope limitation
Pochta Bank integration creates a structural break into 2026H1. Baseline 30.06.2026 can still be used as a snapshot, but historical changes into that date must not automatically be interpreted as purely organic portfolio dynamics.
