# Context changelog

## 2026-09-09 — methodology questionnaire integrated
- Integrated user selections: `1A 2B 3A 4A 5A 6(direct-data-first) 7A 8A 9A 10A 11C 12(A+B) 13A 14A 15A(2023–2026H1) 16B 17B 18(A1 sum)`.
- Baseline total is now explicitly dynamic: sum of the four 2026H1 product exposures, not 7 tn.
- Base credit cost is direct product calculation from average exposure and H1 ECL remeasurement; Group CoR scaling moved to fallback only.
- Base horizon fixed to 2026H2 / 0.5 year while rates and credit cost remain annualized.
- Added separate annualized credit-risk-adjusted spread and six-month risk-adjusted financial result outputs.
- Reconciled 2B + 16B: interpolated history can remain auxiliary, but primary calculation/calibration uses strict reproducible identities where possible.
- Current dataset window corrected to six dates from 31.12.2023 to 30.06.2026; no invented 2023H1.
- Added explicit data adequacy and data-gap/fallback documents.
- Mortgage 17.8% kept as sensitivity only; Base remains dataset proxy.
- Mandatory variable classification taxonomy remains removed.

## 2026-09-09 — flexible-context revision
- Added `UPDATE_CONTEXT: <instruction>` workflow.
- Reframed scenario settings as revisable working defaults.

## 2026-09-09 — article framing and presentation revision
- Reframed the research object as a synthetic four-product portfolio calibrated on public VTB and Bank of Russia data, rather than a bank-specific analysis of VTB.
- Fixed the central research question around the quantitative boundary where additional modeled income no longer compensates for credit losses and weaker stress resilience.
- Clarified that public VTB exposures are calibration anchors, while external pricing/funding proxies and scenario assumptions make the modeled portfolio synthetic.
- Added an editorial rule for notebooks and article materials: present problem, method, findings, interpretation and limitations without internal questionnaire history, implementation logs or environment-specific troubleshooting.
- Kept the current direct credit-cost, dynamic-total and CRAS/RAFR formulas unchanged; emphasized that income-proxy comparability remains a key robustness issue.

## 2026-09-09 — repository layout revision
- Moved datasets, detailed context, source QA and retained legacy files into `other/` to keep the repository root compact.
- Kept active code in `src/`, tests in `tests/`, configuration in `config/` and the research artifact in `notebooks/`.
- Updated the model input path, validation script and documentation references.
- Added root `AGENTS.md` and `README.md` navigation files and restricted pytest discovery to `tests/` so archived `other/test_stress_model.py` is never collected.
