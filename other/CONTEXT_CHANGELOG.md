# Context changelog

## 2026-09-17 — новая постановка: credit-risk stress и независимые доли
- Последующее явное задание заменило постановку critical margin: главный результат — эффекты +1 п.п. и critical product share при RAFR = 0.
- Сравнены clean и v2: DATA_MASTER полностью совпадает (24 строки, 9 колонок). Единственный активный файл остаётся clean; активный лист изменён с MODEL_DATA на DATA_MASTER для прямых компонентов риска.
- Восстановлены прямой CC, ECL rate, pricing − funding − CC, денежные потери и RAFR за 0,5 года.
- Ипотечные 17,8% подтверждены на официальной странице Банка России и применяются как MARKET PROXY; исходные 9,0% сохранены в чувствительности, Excel не изменён.
- Предварительные множители CC: 1 / 1,5 / 2; pricing и funding между сценариями фиксированы. Sigma, синтетическая маржа и произвольные совместные сдвиги из основной модели исключены.
- Добавлены три независимые сетки от текущей доли до полного замещения ипотеки, компактная сводка из девяти строк, аналитические эффекты/пороги с численной сверкой и ипотечная/карточная чувствительность.
- Обновлены тесты, блокнот, отчёт и активная документация. Предыдущие локальные outputs сохранены в outputs/archive/critical_margin_ea1fd65; полные новые сетки — outputs/raw/.
- Повторная попытка доступа к официальному PDF ВТБ не завершила сверку; статус продуктовых компонентов остаётся PENDING.

## 2026-09-17 — synthetic margin and critical-margin methodology
- Switched the active input to `other/dataset_vtb_main_clean.xlsx`, sheet `MODEL_DATA`.
- Replaced `pricing - funding` as the primary income measure with `margin_anchor + lambda * (product_rate_proxy - weighted_product_rate)`.
- Made product critical margin at portfolio `RAFR = 0` the main reverse-stress result; critical share is now secondary.
- Replaced sigma scenarios with explicit Moderate (`credit cost +1 p.p.; margin anchor -0.5 p.p.`) and Severe (`+3 p.p.; -1 p.p.`) shocks.
- Added compact critical-margin, stress and portfolio-mix outputs; updated code, tests, report, notebook and public documentation.

## 2026-09-13 — русский язык исследовательских материалов
- Закреплено предпочтение русского языка в правилах проекта; английские термины и сокращения поясняются переводом и/или расшифровкой.
- Переведены README, текущая методика, генератор отчёта, подписи графиков и исследовательский блокнот; добавлен словарь `other/TERMINOLOGY_RU.md`.
- Технические имена полей, сценариев, файлов и статусов сохранены. Перевод применяется к представлению результатов; исходные данные, конфигурация и арифметика не менялись.

## 2026-09-13 — portfolio-mix terminology and presentation
- Renamed active Structural/Combined scenarios to PortfolioMix/SevereMix, presented as Portfolio-mix sensitivity and Severe + Portfolio Mix.
- Distinguished financial stress scenarios (Base/Moderate/Severe) from portfolio structure experiments (Base Mix/Portfolio-mix sensitivity/Severe + Portfolio Mix); added scenario_type to product results and summary.
- Renamed the active mix config key, sensitivity function/output and Severe figure; retained legacy configuration, constructor, callable and returned-key aliases.
- Aligned README, current methodological context, generated report and executed notebook with conditional critical-share search and management interpretation.
- Added a compact FACT / MARKET PROXY / SYNTHETIC / MODEL ASSUMPTION / CALCULATED note and clarified already-breached-boundary statuses without changing reverse-stress arithmetic.
- All 11 CSV artifacts retain exactly equal numerical results after scenario-name mapping; reverse-stress statuses and NA positions are unchanged. Configuration differs only in the mix-key name; both Excel files are unchanged by SHA-256. Validation details are in `other/RUN_VALIDATION.md` and `outputs/terminology_refactor_validation.csv`.

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
