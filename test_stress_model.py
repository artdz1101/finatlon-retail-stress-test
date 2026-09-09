# SOURCE_QA_2026H1 — current status

## VTB 6M2026
Official VTB IFRS results archive confirms that the 6M2026 financial statements were published on 28 July 2026:
`https://www.vtb.ru/ir/statements/results/`

The current workbook `SOURCES` sheet contains the direct official PDF URL:
`https://www.vtb.ru/media-files/vtb.ru/sitepages/ir/statements/results/rus-vtb-group-ifrs-as-of-30-june-2026.pdf`

### Current status
- existence/date of the official report: **verified via official VTB results archive**;
- direct PDF URL: **present in current workbook**;
- exact PDF page/note mapping for four-product exposure/ECL/ECL remeasurement: **PENDING**.

The current execution environment could not open the VTB PDF directly, so no page numbers are invented here. Codex should retry this verification when it has browser/internet access.

## Numerically available 2026H1 components
The current dataset contains all components necessary for the direct product credit-cost calculation for Mortgage, Consumer, Auto and Cards:
- 31.12.2025 exposure;
- 30.06.2026 exposure;
- H1 2026 ECL remeasurement.

Direct recalculation passes model QA for all four products.

## Bank of Russia June 2026
Official page:
`https://www.cbr.ru/statistics/bank_sector/int_rat/0626/`

Verified published June 2026 values relevant to the current proxies:
- short-term household loans 31.2%;
- long-term household loans 17.5%;
- auto loans 16.5%;
- market mortgage 17.8%;
- concessional mortgage 5.7%;
- short-term household deposits 13.0%;
- long-term household deposits 10.9%.

Base still uses the current dataset mortgage proxy of 9.0% according to the user's methodology choice; 17.8% remains sensitivity only.
