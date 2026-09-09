# Source review — 2026-09-09

## Current numeric source
Use `other/dataset_vtb_main_v2.xlsx` for calculations.

It contains six reporting dates from 31.12.2023 through 30.06.2026 and four products per date.

## 2026H1 baseline rows
| Product | Exposure, RUB bn | ECL reserve, RUB bn | ECL remeasurement, RUB bn | ECL rate | Annualized credit cost | Product rate | Funding rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| Mortgage | 4,279.8 | 89.4 | 14.7 | 2.09% | 0.68% | 9.0% | 10.9% |
| Consumer | 1,525.9 | 246.7 | 33.7 | 16.17% | 4.25% | 17.5% | 10.9% |
| Auto | 543.9 | 96.9 | 12.0 | 17.82% | 4.35% | 16.5% | 10.9% |
| Cards | 223.4 | 47.0 | 6.6 | 21.04% | 5.59% | 31.2% | 13.0% |

Current four-product total: RUB 6,573.0 bn. The model derives this from data rather than hard-coding it.

## Formula QA
- `ECL rate = ECL reserve / exposure` is reproducible.
- For rows with a prior exposure in the dataset, `credit_cost = 2 * ECL remeasurement / average(previous exposure, current exposure)` is reproducible.
- 2026H1 Base has all direct components needed to calculate product credit cost from 31.12.2025 and 30.06.2026 values.

## Official VTB availability
VTB official IFRS results archive lists the 6M2026 financial statements dated 28 July 2026:
`https://www.vtb.ru/ir/statements/results/`

Direct PDF URL stored in the workbook:
`https://www.vtb.ru/media-files/vtb.ru/sitepages/ir/statements/results/rus-vtb-group-ifrs-as-of-30-june-2026.pdf`

Page-level reconciliation of the four product rows remains an explicit source-QA task. Do not invent page numbers if the PDF cannot be opened from the execution environment.

## Bank of Russia June 2026 rates
Official page:
`https://www.cbr.ru/statistics/bank_sector/int_rat/0626/`

Relevant published values:
- short-term household loans: 31.2%;
- long-term household loans: 17.5%;
- auto loans: 16.5%;
- market mortgage: 17.8%;
- concessional mortgage: 5.7%;
- short-term household deposits: 13.0%;
- long-term household deposits: 10.9%.

Base follows the user's choice to retain the dataset mortgage proxy (9.0%) without synthetic subsidy adjustment. The 17.8% market mortgage rate is optional sensitivity only.

## Historical data quality
The 30.06.2024 exposures in the working Excel are midpoint-like reconstructions rather than strict identities. Retain them for continuity if useful, but do not silently treat them as equal-quality observed history in primary calibration. Because 31.12.2024 credit cost uses the previous 30.06.2024 exposure in its average-exposure denominator, current config excludes both 30.06.2024 and 31.12.2024 credit-cost rows from primary sigma calibration.

## Structural break
The 2026H1 snapshot is affected by the Pochta Bank integration perimeter change. Use it as Base, but do not describe the change into 2026H1 as purely organic.
