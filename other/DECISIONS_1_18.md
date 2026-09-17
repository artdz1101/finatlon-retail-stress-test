# Final interpretation of methodology questionnaire 1–18

> Историческая запись. Актуальная постановка от 17.09.2026 находится в MODEL_DECISIONS.md и AGENTS.md и имеет приоритет: прямой CC, CRAS = pricing − funding − CC, основной ипотечный MARKET PROXY 17,8%, 9,0% как чувствительность, предварительные множители CC 1/1,5/2, главные результаты — предельные эффекты и критические доли. Ниже сохранена история решений, включая уже отменённую постановку critical margin.

This file records the user's current choices. They are revisable through `UPDATE_CONTEXT:`.

## Methodology update: synthetic margin and critical margin

The later explicit methodology update supersedes questionnaire choices 7–12 where they conflict with it. The active income measure is `margin_anchor + lambda * (product_rate_proxy - weighted_product_rate)` from `MODEL_DATA`; `pricing - funding` is no longer the primary income formula. The main research result is `critical_margin` at portfolio `RAFR = 0`, with required margin premium versus Mortgage. Product-share thresholds remain secondary sensitivity indicators.

## Research framing added after the questionnaire

The article studies a synthetic four-product portfolio calibrated on public VTB and Bank of Russia data. Published VTB exposures anchor the initial size and weights, but the combination with external pricing/funding proxies and model assumptions must not be described as VTB's actual product profitability or management portfolio. The central output is the boundary at which additional modeled income from a riskier structure no longer compensates for credit losses and weaker stress resilience.

| # | Choice | Current interpretation |
|---|---|---|
| 1 | A | Use 2026H1 product IFRS exposure rows as Base after source consistency QA. |
| 2 | B | Keep reconstructed history in the working dataset, but do not treat interpolation as equal-quality observed history. |
| 3 | A | Main credit-risk measure = flow credit-cost proxy; ECL/exposure is secondary stock indicator. |
| 4 | A | Denominator = average exposure. |
| 5 | A | Credit cost is annualized. |
| 6 | Detailed | First try to use direct 2026H1 product components; document what exists/missing; verify official source; only if unavailable/non-comparable use the best documented fallback. |
| 7 | A | Product pricing uses Bank of Russia market rates as external proxies. |
| 8 | A | Funding uses matched household-deposit market proxies; Cards short-term, other products long-term. |
| 9 | A | Mortgage Base uses the published borrower-side proxy without synthetic subsidy compensation. |
| 10 | A | Cards Base uses the short-term retail rate proxy without utilization/grace adjustment. |
| 11 | C | Calculate both annualized percentage spread and six-month money result. |
| 12 | A + B | Percentage = credit-risk-adjusted spread; money = risk-adjusted financial result. |
| 13 | A | Do not add operating expenses in Base. |
| 14 | A | Do not add RWA/capital layer and do not call the result RAROC. |
| 15 | A, period changed | Use 2023–2026H1 history only for calibration/ranges; current Excel actually starts at 31.12.2023. Assess adequacy explicitly. |
| 16 | B | Fill/use a missing value as a primary calculated input only where a strict reproducible identity exists; interpolation remains auxiliary. |
| 17 | B | Main stress horizon = next six months (2026H2). |
| 18 | A modified by 1A | Fixed total in portfolio-mix experiments equals the sum of the four 2026H1 product exposures from 1A, not 7 tn. |

## Consequence of 1A + 18
Current dataset Base total is dynamically calculated:

`4,279.8 + 1,525.9 + 543.9 + 223.4 = 6,573.0 RUB bn`

This is a current numeric result, not a hard-coded model constraint. If the source dataset changes, the model total changes with it.

## Consequence of 5A + 17B
Rates and credit cost remain annualized, but money results are for a half-year:

`RAFR_6M = 0.5 * sum(exposure_i * (pricing_i - funding_i - credit_cost_i))`

## Consequence of 2B + 16B
The current 30.06.2024 exposure rows are midpoint-like reconstructions in the working dataset. They may remain for continuity, but should not silently determine primary scenario calibration. Until primary-source verification changes this conclusion, the adjacent credit-cost rows affected by that exposure are excluded from the main historical credit-cost sigma calibration.
