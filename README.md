# finatlon-retail-stress-test

Воспроизводимая сценарная модель синтетического розничного кредитного портфеля для научной статьи IX Финатлон форума.

Главный исследовательский результат — критическая маржа (`critical_margin`): минимальная синтетическая маржа выбранного продукта, при которой финансовый результат портфеля с учётом кредитного риска достигает нуля. Ипотека используется как низкорисковый ориентир; показатель `required_margin_premium_vs_mortgage` равен разнице между критической маржой продукта и текущей синтетической маржой ипотеки.

Доходная часть рассчитывается по новой методике:

`m_i,t = M_t + lambda * (p_i,t - weighted_p_t)`

`RAR_i,t = m_i,t - credit_cost_i,t`

`RAFR_i,t = Exposure_i,t * RAR_i,t * 0.5`

Здесь `M_t` — якорь средней маржи `margin_anchor`, `lambda` — коэффициент передачи различий рыночного показателя-заменителя ставки в продуктовую маржу, `p_i,t` — рыночный pricing proxy. Эти входы берутся из листа `MODEL_DATA` файла `other/dataset_vtb_main_clean.xlsx`.

Финансовые сценарии намеренно просты:

- Base: текущие значения данных;
- Moderate: стоимость кредитного риска +1 п.п., якорь маржи −0,5 п.п.;
- Severe: стоимость кредитного риска +3 п.п., якорь маржи −1 п.п.

Изменение продуктового состава остаётся анализом чувствительности. Доли Consumer, Auto или Cards увеличиваются за счёт Mortgage при неизменной общей экспозиции; после сдвига пересчитываются средневзвешенный pricing proxy и синтетические маржи.

RAFR (risk-adjusted financial result — финансовый результат с учётом риска) не является прибылью ВТБ, фактической продуктовой прибылью, NIM или RAROC. Продуктовая доходность синтетическая. Комиссии, операционные расходы, налоги, капитал и RWA не рассчитываются.

## Основные результаты

- `outputs/scenario_summary.csv` — компактная сводка `scenario | RAFR`;
- `outputs/critical_margin.csv` — главная таблица текущей и критической маржи;
- `outputs/stress_critical_margin.csv` — критическая маржа в Base, Moderate и Severe;
- `outputs/portfolio_mix_sensitivity.csv` — изменение критической маржи при сдвиге доли;
- `outputs/reverse_stress.csv` — критическая маржа и вспомогательная критическая доля со статусами;
- `outputs/model_report.md` — краткий воспроизводимый отчёт.

## Запуск

```bash
python -m pip install -r other/requirements.txt
pytest -q
python src/stress_model.py --config config/model_config.json
```

Исследовательский блокнот: [`notebooks/03_stress_model_calibration.ipynb`](notebooks/03_stress_model_calibration.ipynb). Методологические решения: [`other/MODEL_DECISIONS.md`](other/MODEL_DECISIONS.md). Термины: [`other/TERMINOLOGY_RU.md`](other/TERMINOLOGY_RU.md).
