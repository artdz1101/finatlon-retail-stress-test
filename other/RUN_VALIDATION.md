# Package validation

## Актуальная проверка — 17.09.2026: независимые доли и стресс стоимости риска

Ниже этой секции сохранена история; её предыдущие результаты не являются текущими выводами.

- pytest: **42 passed, 0 failed**.
- Полная модель: успешно; QA: **51 PASS, 0 FAIL**, сверка первоисточника ВТБ: **PENDING**.
- Исследовательский блокнот: **7 кодовых ячеек** выполнены без ошибок и валидированы.
- DATA_MASTER clean и v2 совпадает: **24 строки / 9 колонок**. Модель использует только clean, его контрольная сумма не изменена. Воспроизводимое сравнение: DATASET_COMPARISON_2026-09-17.md.
- Итоговые таблицы: Base — 4 строки; финансовые состояния — 3; основные эффекты и пороги — 9. Полные сетки вынесены в outputs/raw/.
- Прямой CC, денежные формулы, фиксированные доли остальных двух продуктов, точные конечные точки сетки и эффекты +1 п.п. проверены аналитически и численно.
- Тесты охватывают как существующее пересечение, включая конечную границу, так и его отсутствие или исходно достигнутую границу; NA не закреплено заранее для всех случаев.
- Три графика долей показывают исходные доли, нулевую границу, три состояния и найденные пороги. Ипотечная и карточная чувствительность сохранены отдельно.

| Состояние | Потери за 6 месяцев, млрд руб. | RAFR, млрд руб. | Годовой CRAS |
|---|---:|---:|---:|
| Base | 65,053 | 168,514 | 5,1274% |
| Moderate | 97,579 | 135,987 | 4,1377% |
| Severe | 130,106 | 103,461 | 3,1480% |

Критические доли: Consumer / Severe — **65,51%**; Auto / Moderate — **69,14%**; Auto / Severe — **44,75%**. Во всех остальных шести сочетаниях основного анализа допустимого adverse crossing нет; публикуется NA со статусом. Для Cards этот вывод условен относительно ставки: при снижении proxy до 21,2% порог в Severe появляется на **36,36%**.

Сравнение с прежней спецификацией pricing/funding: ипотечные 9,0% воспроизводят Base RAFR **−19,797671** млрд руб.; 17,8% дают **168,513529** млрд руб. Разница **188,3112** млрд руб. в точности равна ипотечной экспозиции × 8,8 п.п. × 0,5. Прямой CC, экспозиции и базовые потери не менялись. Прежние Moderate/Severe (−70,632/−121,467) включали другие финансовые шоки и не являются текущими сценариями.

Непосредственно предыдущий коммит ea1fd65 использовал синтетическую маржу и имел RAFR 20,396 / −28,901 / −111,064. Это другая доходная спецификация; она отменена последним заданием. Её локальные outputs сохранены в outputs/archive/critical_margin_ea1fd65.

Открытые модельные параметры: предварительные множители CC 1/1,5/2 и условный диапазон снижения карточного pricing proxy на 5/10/15 п.п. Открытый вопрос источников: страницы/примечания компонентов ВТБ, PENDING.

## Русская редакция материалов — 13.09.2026

README, текущие методологические решения, исследовательский блокнот, отчёт и подписи трёх графиков переведены на русский. Введён словарь `other/TERMINOLOGY_RU.md`; английские сокращения поясняются расшифровкой и переводом. Предпочтение русского языка закреплено в `other/AGENTS.md`. Технические имена полей, сценариев, файлов и статусов сохранены.

После перевода прошли все 12 тестов; полная модель и семь кодовых ячеек блокнота выполнены успешно. Повторное точное сравнение всех 11 таблиц CSV (comma-separated values — текстовый формат таблиц с разделителями) подтвердило сохранение численных результатов и статусов обратного стресс-тестирования. Значения конфигурации и контрольные суммы обоих Excel-файлов не изменились.

Validated on the bundled `other/dataset_vtb_main_v2.xlsx`.

- pytest: **12 passed** (`python -m pytest -q`, 2026-09-13);
- full model run: **completed successfully**;
- formula QA: ECL rate and annualized product credit cost reproduced;
- baseline direct credit-cost components: available for all four products;
- dynamic baseline total: RUB 6,573.0 bn;
- current history: six reporting dates / 24 product rows;
- generated modules: Base, Moderate, Severe, Portfolio-mix sensitivity (PortfolioMix), Severe + Portfolio Mix (SevereMix), factor sensitivity, product-share sensitivity, reverse stress and mortgage pricing sensitivity;
- research notebook: **7 code cells executed successfully**, notebook format validated.

## Terminology refactor validation — 2026-09-13

Saved all original model outputs before changing the active implementation. Compared original and regenerated CSVs with round-trip float parsing and exact pandas equality after mapping scenario identifiers; only the added `scenario_type` column was excluded. In the robustness text, all embedded numbers and classification rows were compared while allowing the requested wording changes.

All **11 CSV artifacts** match numerically: baseline (4 rows), calibration (4), data adequacy (8), factor sensitivity (75), mortgage sensitivity (101), QA (13), robustness (7), reverse stress (55), scenario products (20), scenario summary (5) and portfolio-mix sensitivity (11,315). Reverse-stress statuses and NA positions are unchanged. All configuration values remain identical after the mix-key rename. Both Excel files have identical SHA-256 hashes to their before-refactor copies.

| Scenario / experiment | RAFR 6M, RUB bn (before = after) |
|---|---:|
| Base | -19.797671370713196 |
| Moderate | -70.6323209462333 |
| Severe | -121.46697052175332 |
| Portfolio-mix sensitivity | -12.801526449869485 |
| Severe + Portfolio Mix | -112.34582646468601 |

Detailed comparison: `outputs/terminology_refactor_validation.csv`. Before-refactor copies: `outputs/rename_validation_before/`. Active sensitivity artifacts use `portfolio_mix_sensitivity.csv` and `figures/portfolio_mix_sensitivity_severe.png`. Legacy config/callable/returned-key aliases remain available; the legacy returned key resolves to the new artifact path.

## Questions requiring expert decisions

Income-side specification and economic comparability of mortgage/card proxies, final Moderate/Severe shock magnitudes and mix shifts remain open. Source reconciliation and limitations of the short history/perimeter break remain documented. No optimizer, automatic portfolio selection, LGD optimization, capital allocation, RWA, Monte Carlo or regression/ML was added. Exposure, pricing/funding, credit-cost components/formulas, mortgage sensitivity endpoints, horizon and critical boundary were preserved.

## Changed files

- `src/stress_model.py`: active identifiers, compatibility aliases, scenario_type, report and figure presentation.
- `config/model_config.json`: mix-key rename only.
- `tests/test_stress_model.py`: fixed-total/financial-assumption checks, compatibility and already-breached-boundary checks.
- `notebooks/03_stress_model_calibration.ipynb`: methodological wording, taxonomy, scenario labels and regenerated outputs.
- `README.md`: research sequence, financial/mix distinction, limitations and active names.
- `other/AGENTS.md`: current architecture and output terminology.
- `other/MODEL_DECISIONS.md`: aligned research framing, provenance and threshold interpretation.
- `other/DECISIONS_1_18.md`: portfolio-mix wording for the fixed-total decision.
- `other/DATA_ADEQUACY_2023_2026H1.md`: portfolio-mix sensitivity wording.
- `other/README_CODEX.md`: updated terminology in the context-change example.
- `other/CONTEXT_CHANGELOG.md`: recorded this presentation revision and unchanged arithmetic.
- `other/RUN_VALIDATION.md`: validation evidence, preserved results and open expert questions.

Generated `outputs/` artifacts were regenerated; this directory is ignored by Git. Archived legacy implementation/config/tests in `other/` were retained.

Important interpretation from the validation run: with the user's Base mortgage pricing choice (9.0% dataset proxy) and current funding proxy, the Base portfolio RAFR is negative. Therefore a zero-result reverse-stress boundary is already breached in the raw Base proxy setup. Codex must report this as a pricing-proxy limitation and must not manufacture a critical riskier-product share. Mortgage market-rate sensitivity is included precisely to test robustness of conclusions to this limitation.
