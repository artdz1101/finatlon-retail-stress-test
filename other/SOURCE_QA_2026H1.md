# SOURCE_QA_2026H1 — status at 2026-09-09

## Official VTB source

The official VTB IFRS results archive lists **"Финансовая отчетность по МСФО за 6М 2026 года"**, file size 2.18 MB, publication date **28 July 2026**:

`https://www.vtb.ru/ir/statements/results/`

The current workbook `other/dataset_vtb_main_v2.xlsx`, sheet `SOURCES`, contains this direct official PDF URL:

`https://www.vtb.ru/media-files/vtb.ru/sitepages/ir/statements/results/rus-vtb-group-ifrs-as-of-30-june-2026.pdf`

### Verification attempts in the current environment

- The official archive entry and publication date were confirmed through the indexed VTB archive result.
- Direct document retrieval through the web reader failed: the archive returned HTTP 502 and the direct PDF could not be fetched.
- A separate direct HTTPS request reached the VTB host only after disabling local TLS certificate validation, but the host returned a 63-byte `Forbidden` response rather than the 2.18 MB PDF.
- The in-app browser control required for a further interactive attempt is not available in this execution environment.

Therefore the exact PDF page/note mapping for product exposure, ECL reserve and ECL remeasurement remains **PENDING**. No page or note numbers are inferred or invented. This is a source-level reproducibility gap, not a missing numeric model input.

## Current 2026H1 workbook reconciliation

The workbook contains all direct components required by the approved Base method. Values below are RUB bn except rates.

| Product | Exposure 31.12.2025 | Exposure 30.06.2026 | Average exposure | ECL reserve 30.06.2026 | H1 2026 ECL remeasurement | ECL rate | Annualized credit cost |
|---|---:|---:|---:|---:|---:|---:|---:|
| Mortgage | 4,364.8 | 4,279.8 | 4,322.30 | 89.4 | 14.7 | 2.0889% | 0.6802% |
| Consumer | 1,644.8 | 1,525.9 | 1,585.35 | 246.7 | 33.7 | 16.1675% | 4.2514% |
| Auto | 560.7 | 543.9 | 552.30 | 96.9 | 12.0 | 17.8158% | 4.3455% |
| Cards | 248.9 | 223.4 | 236.15 | 47.0 | 6.6 | 21.0385% | 5.5897% |

Recalculation uses:

`ecl_rate = ecl_reserve / exposure_30.06.2026`

`average_exposure = (exposure_31.12.2025 + exposure_30.06.2026) / 2`

`annualized_credit_cost = 2 * ecl_remeasurement_H1_2026 / average_exposure`

For all four products the recalculated values match the workbook values within the configured tolerance (`1e-8`). The four-product 30.06.2026 exposure total is **RUB 6,573.0 bn**, calculated from the workbook rather than imposed as a constant.

## Base-method decision

The working Base continues to use the direct product formula because all required numeric components are present and internally consistent. Group CoR scaling is not used. It remains a documented fallback only if later page-level reconciliation shows that the product components are unavailable or non-comparable.

The unresolved check is whether the 31.12.2025 and 30.06.2026 product scopes and the ECL remeasurement definition are comparable in the official notes. If the official PDF later contradicts the workbook, the conflict must be reconciled before changing Base.
