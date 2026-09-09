# Data gaps, source QA and fallback hierarchy

## 1. 2026H1 product credit cost — what we already have
The current `other/dataset_vtb_main_v2.xlsx` contains, for all four products:
- exposure at 31.12.2025;
- exposure at 30.06.2026;
- ECL reserve at 30.06.2026;
- ECL remeasurement for H1 2026;
- a direct link in `SOURCES` to VTB IFRS 6M2026.

Therefore the 2026H1 Base credit-cost proxy is numerically computable without Group CoR scaling:

`average_exposure = (exposure_2025YE + exposure_2026H1) / 2`

`annualized_credit_cost = 2 * ECL_remeasurement_H1 / average_exposure`

Current recomputed values are approximately:
- Mortgage: 0.6802%;
- Consumer: 4.2514%;
- Auto: 4.3455%;
- Cards: 5.5897%.

## 2. What is still missing / needs source QA
The numerical components are present. The remaining gap is **source-level verification**, not a missing formula input:
1. exact VTB 6M2026 note/table/page for each 30.06.2026 product exposure;
2. exact note/table/page for product ECL reserve and ECL remeasurement;
3. confirmation that 31.12.2025 and 30.06.2026 rows use a comparable IFRS product scope;
4. confirmation that the ECL remeasurement component used in the dataset has a consistent meaning across the four products and periods;
5. page-level source mapping in a source-QA file so the final article is reproducible without relying on an unlabeled Excel row.

Official VTB results archive lists the 6M2026 IFRS statements dated 28 July 2026:
`https://www.vtb.ru/ir/statements/results/`

The workbook gives the direct report URL:
`https://www.vtb.ru/media-files/vtb.ru/sitepages/ir/statements/results/rus-vtb-group-ifrs-as-of-30-june-2026.pdf`

## 3. Required Codex verification attempt
When internet/browser access is available, Codex should:
1. open the official VTB 6M2026 IFRS PDF;
2. locate the retail/product loan breakdown and ECL movement tables;
3. record exact pages/note numbers and reconcile all four products;
4. write the result to `other/SOURCE_QA_2026H1.md`;
5. if values differ from the current Excel, stop and reconcile before changing Base.

## 4. Fallback hierarchy if direct product data fail
Use the first feasible method, in this order:

### Fallback A — direct components from another official VTB disclosure
If the same product exposure/ECL components are present in another official VTB publication with comparable scope, use them and document the source.

### Fallback B — last clean product credit-cost profile + Group CoR scaling
Only if direct 2026H1 product ECL remeasurement is genuinely unavailable or non-comparable, use the last source-verified product credit-cost profile and scale it by a clearly disclosed group-level risk factor such as the Group CoR ratio. This is a fallback/sensitivity, not the preferred Base, because Group CoR and the research product credit-cost proxy differ in scope and definition.

### Fallback C — credit-risk-only sensitivity
If even a defensible scaling anchor is unavailable, do not invent product credit costs. Keep Base from the last clean product risk snapshot and stress product credit cost through transparent sensitivity ranges. Document the limitation.

## 5. Pricing/funding gaps
Public product-specific VTB yields and internal FTP are not available. Base therefore uses Bank of Russia external rate proxies. Do not attempt to reconstruct internal VTB pricing/funding.

This means the modeled portfolio is synthetic even where its exposure anchors come from public VTB disclosures. The current CRAS/RAFR formula remains the working calculation, but the economic comparability of the income proxies—especially Mortgage and Cards—is a substantive limitation for threshold interpretation. A critical share must not be claimed if the selected proxy set produces no feasible adverse crossing.

June 2026 Bank of Russia reference page:
`https://www.cbr.ru/statistics/bank_sector/int_rat/0626/`

It reports 31.2% short-term household loans, 17.5% long-term household loans, 16.5% auto loans, 17.8% market mortgage, 5.7% concessional mortgage, 13.0% short-term household deposits and 10.9% long-term household deposits.

The dataset mortgage value of 9.0% is retained in Base per the user's choice; 17.8% is only an optional sensitivity because borrower-side subsidized mortgage pricing is not directly comparable with an economic asset yield.
