# Package validation

Validated on the bundled `other/dataset_vtb_main_v2.xlsx`.

- pytest: **9 passed**;
- full model run: **completed successfully**;
- formula QA: ECL rate and annualized product credit cost reproduced;
- baseline direct credit-cost components: available for all four products;
- dynamic baseline total: RUB 6,573.0 bn;
- current history: six reporting dates / 24 product rows;
- generated modules: Base, Moderate, Severe, Structural, Combined, factor sensitivity, product-share sensitivity, reverse stress and mortgage pricing sensitivity.

Important interpretation from the validation run: with the user's Base mortgage pricing choice (9.0% dataset proxy) and current funding proxy, the Base portfolio RAFR is negative. Therefore a zero-result reverse-stress boundary is already breached in the raw Base proxy setup. Codex must report this as a pricing-proxy limitation and must not manufacture a critical riskier-product share. Mortgage market-rate sensitivity is included precisely to test robustness of conclusions to this limitation.
