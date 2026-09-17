from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import stress_model as sm


@pytest.fixture(scope="module")
def cfg():
    return sm.load_config(ROOT / "config/model_config.json")


@pytest.fixture(scope="module")
def data(cfg):
    return sm.load_dataset(ROOT / cfg.input_file, cfg.data_sheet)


@pytest.fixture(scope="module")
def products(data, cfg):
    return sm.build_scenarios(data, cfg)


@pytest.fixture(scope="module")
def grid(products, cfg):
    return sm.product_mix_grid(products, cfg)


@pytest.fixture(scope="module")
def mix(products, cfg):
    return sm.product_mix_summary(products, cfg)


def test_active_input_is_clean_and_contains_direct_components(cfg, data):
    assert cfg.input_file == "other/dataset_vtb_main_clean.xlsx"
    assert cfg.data_sheet == "DATA_MASTER"
    assert {"exposure", "ecl_reserve", "ecl_remeasurement", "pricing", "funding"}.issubset(data.columns)
    assert len(data) == 24
    assert set(pd.ExcelFile(ROOT / cfg.input_file).sheet_names) == {"DATA_MASTER", "SOURCES", "MODEL_DATA"}


def test_dynamic_total_weights_and_scale_invariance(data, cfg):
    original = sm.baseline_table(data, cfg)
    scaled_data = data.copy()
    scaled_data[["exposure", "ecl_reserve", "ecl_remeasurement"]] *= 1.37
    scaled = sm.baseline_table(scaled_data, cfg)
    assert scaled.exposure.sum() == pytest.approx(data.loc[data.report_date.eq(cfg.baseline_date), "exposure"].sum() * 1.37)
    assert scaled.weight.sum() == pytest.approx(1)
    np.testing.assert_allclose(scaled.weight, original.weight)
    np.testing.assert_allclose(scaled.credit_cost, original.credit_cost)
    scaled_products = sm.build_scenarios(scaled_data, cfg)
    original_products = sm.build_scenarios(data, cfg)
    np.testing.assert_allclose(scaled_products.raf_result_bn, original_products.raf_result_bn * 1.37)


def test_direct_credit_cost_is_calculated_from_components(data, cfg):
    base = sm.baseline_table(data, cfg).set_index("product")
    current = data[data.report_date.eq(cfg.baseline_date)].set_index("product")
    previous = data[data.report_date.eq(cfg.baseline_date - pd.offsets.MonthEnd(6))].set_index("product")
    expected = 2 * current.ecl_remeasurement / ((current.exposure + previous.exposure) / 2)
    np.testing.assert_allclose(base.credit_cost, expected.reindex(base.index), atol=1e-12)
    np.testing.assert_allclose(base.ecl_rate, (current.ecl_reserve / current.exposure).reindex(base.index))
    tampered = data.copy()
    tampered.loc[tampered.report_date.eq(cfg.baseline_date), "credit_cost"] = 0.99
    recalculated = sm.baseline_table(tampered, cfg).set_index("product")
    np.testing.assert_allclose(recalculated.credit_cost, base.credit_cost)
    assert sm.validate_data(tampered, cfg).status.eq("FAIL").any()


def test_missing_previous_half_year_cannot_use_older_exposure(data, cfg):
    incomplete = data[~data.report_date.eq(cfg.baseline_date - pd.offsets.MonthEnd(6))]
    with pytest.raises(ValueError, match="direct credit-cost"):
        sm.baseline_table(incomplete, cfg)
    assert sm.validate_data(incomplete, cfg).status.eq("FAIL").any()


def test_six_month_result_and_credit_loss(products, cfg):
    expected_cras = products.pricing - products.funding - products.credit_cost
    np.testing.assert_allclose(products.cras, expected_cras)
    np.testing.assert_allclose(products.raf_result_bn, products.exposure * expected_cras * 0.5)
    np.testing.assert_allclose(products.credit_loss_bn, products.exposure * products.credit_cost * 0.5)
    precredit = products.exposure * (products.pricing - products.funding) * cfg.horizon_years
    np.testing.assert_allclose(products.raf_result_bn + products.credit_loss_bn, precredit)


def test_mortgage_market_proxy_is_explicit_and_blended_rate_is_sensitivity(data, cfg, products):
    base = sm.baseline_table(data, cfg)
    mortgage = base.loc[base["product"].eq("Mortgage")].iloc[0]
    assert mortgage.pricing == pytest.approx(0.178)
    assert mortgage.source_pricing == pytest.approx(0.09)
    assert mortgage.pricing_classification == "MARKET PROXY"
    assert cfg.mortgage_pricing_proxy["classification"] == "MARKET PROXY"
    assert "не фактическая" in cfg.mortgage_pricing_proxy["description"]
    assert "cbr.ru" in cfg.mortgage_pricing_proxy["source"]
    sensitivity = sm.mortgage_pricing_sensitivity(products, cfg)
    assert sensitivity.mortgage_pricing.min() == pytest.approx(0.09)
    assert sensitivity.mortgage_pricing.max() == pytest.approx(0.178)
    assert sensitivity.iloc[-1].raf_result_bn == pytest.approx(products[products.scenario.eq("Base")].raf_result_bn.sum())
    expected_delta = mortgage.exposure * (0.178 - 0.09) * 0.5
    assert sensitivity.iloc[-1].raf_result_bn - sensitivity.iloc[0].raf_result_bn == pytest.approx(expected_delta)
    np.testing.assert_allclose(sensitivity.credit_loss_bn, sensitivity.credit_loss_bn.iloc[0])


def test_credit_risk_stress_fixes_pricing_funding_and_composition(products, cfg):
    base = products[products.scenario.eq("Base")].set_index("product")
    for scenario in sm.SCENARIO_ORDER:
        current = products[products.scenario.eq(scenario)].set_index("product")
        pd.testing.assert_frame_equal(current[["exposure", "weight", "pricing", "funding"]],
                                      base[["exposure", "weight", "pricing", "funding"]])
        np.testing.assert_allclose(current.credit_cost, base.credit_cost * cfg.credit_cost_stress_multiplier[scenario])
    summary = sm.scenario_summary(products, cfg.horizon_years)
    assert summary.scenario.tolist() == sm.SCENARIO_ORDER
    assert (np.diff(summary.credit_loss_bn) > 0).all()
    assert (np.diff(summary.raf_result_bn) < 0).all()


@pytest.mark.parametrize("target", sm.RISKIER_PRODUCTS)
@pytest.mark.parametrize("scenario", sm.SCENARIO_ORDER)
def test_only_target_and_mortgage_change_and_one_pp_matches_grid(target, scenario, products, grid, cfg):
    params = products[products.scenario.eq(scenario)]
    shifted = sm.apply_portfolio_mix_shift(params, target, 1.0)
    before = params.set_index("product")
    after = shifted.set_index("product")
    total = float(before.exposure.sum())
    assert after.exposure.sum() == pytest.approx(total)
    assert after.weight.sum() == pytest.approx(1)
    assert after.loc[target, "exposure"] - before.loc[target, "exposure"] == pytest.approx(total * 0.01)
    assert after.loc["Mortgage", "exposure"] - before.loc["Mortgage", "exposure"] == pytest.approx(-total * 0.01)
    for other in set(sm.PRODUCTS) - {target, "Mortgage"}:
        assert after.loc[other, "exposure"] == before.loc[other, "exposure"]
        assert after.loc[other, "weight"] == before.loc[other, "weight"]
    pd.testing.assert_frame_equal(after[["pricing", "funding", "credit_cost"]],
                                  before[["pricing", "funding", "credit_cost"]])
    result = sm.calculate_product_results(shifted, cfg.horizon_years, scenario)
    analytical = sm.marginal_effects(params, target, cfg)
    numerical = (result.raf_result_bn.sum() - params.raf_result_bn.sum(),
                 result.credit_loss_bn.sum() - params.credit_loss_bn.sum())
    np.testing.assert_allclose(analytical, numerical, atol=1e-10)
    g = grid[grid["product"].eq(target) & grid.scenario.eq(scenario)]
    one_pp = g[np.isclose(g.target_share, before.loc[target, "weight"] + 0.01, atol=1e-12, rtol=0)]
    assert len(one_pp) == 1
    np.testing.assert_allclose([one_pp.iloc[0].delta_raf_result_bn, one_pp.iloc[0].delta_credit_loss_bn],
                              analytical, atol=1e-10)


def test_grid_is_feasible_starts_at_current_share_and_ends_at_max(products, grid, cfg):
    for (scenario, target), group in grid.groupby(["scenario", "product"]):
        params = products[products.scenario.eq(scenario)].set_index("product")
        total = float(params.exposure.sum())
        current = params.loc[target, "exposure"] / total
        maximum = current + params.loc["Mortgage", "exposure"] / total
        assert group.iloc[0].target_share == pytest.approx(current)
        assert group.iloc[-1].target_share == pytest.approx(maximum)
        assert group.iloc[-1].mortgage_exposure_bn == pytest.approx(0, abs=1e-10)
        assert group.target_share.min() >= current - 1e-12
        assert group.target_share.max() <= maximum + 1e-12
        assert group.target_share.is_monotonic_increasing
        steps = np.diff(group.target_share)
        assert (steps > 0).all()
        assert (steps <= cfg.product_mix["share_step"] + 1e-12).all()
        for other in set(sm.RISKIER_PRODUCTS) - {target}:
            assert group[f"{other.lower()}_exposure_bn"].eq(params.loc[other, "exposure"]).all()
        np.testing.assert_allclose(group.total_exposure_bn, total, atol=1e-9)
        assert group.iloc[0].delta_credit_loss_bn == pytest.approx(0)
        assert group.iloc[0].delta_raf_result_bn == pytest.approx(0)


def test_mix_summary_and_every_raw_grid_point_agree(products, mix, grid, cfg):
    assert len(mix) == 9
    for _, row in mix.iterrows():
        g = grid[grid.scenario.eq(row.scenario) & grid["product"].eq(row["product"])]
        distance_pp = (g.target_share - row.baseline_share) * 100
        np.testing.assert_allclose(g.delta_raf_result_bn, distance_pp * row.delta_raf_result_per_1pp, atol=1e-9)
        np.testing.assert_allclose(g.delta_credit_loss_bn, distance_pp * row.delta_credit_loss_per_1pp, atol=1e-9)
        if np.isfinite(row.critical_share):
            params = products[products.scenario.eq(row.scenario)]
            changed = sm.apply_portfolio_mix_shift(params, row["product"], (row.critical_share - row.baseline_share) * 100)
            result = sm.calculate_product_results(changed, cfg.horizon_years, row.scenario)
            assert result.raf_result_bn.sum() == pytest.approx(0, abs=1e-8)
            assert np.interp(row.critical_share, g.target_share, g.raf_result_bn) == pytest.approx(0, abs=1e-8)
            assert g[g.target_share < row.critical_share - 1e-10].raf_result_bn.gt(0).all()
            assert g.iloc[-1].raf_result_bn <= 1e-8
        elif row.status == "ALREADY_AT_OR_BELOW_BOUNDARY":
            assert g.iloc[0].raf_result_bn <= 1e-8
        else:
            assert row.status == "NO_ADVERSE_CROSSING_WITHIN_FEASIBLE_RANGE"
            assert g.raf_result_bn.gt(0).all()


def hand_portfolio(target, target_cras):
    table = pd.DataFrame({"product": sm.PRODUCTS, "exposure": [70., 10., 10., 10.],
                          "pricing": [0.12] * 4, "funding": [0.06] * 4, "credit_cost": [0.02] * 4})
    table.loc[table["product"].eq(target), "credit_cost"] = 0.12 - 0.06 - target_cras
    return sm.calculate_product_results(table, 0.5, "Base")


@pytest.mark.parametrize("target", sm.RISKIER_PRODUCTS)
def test_reverse_stress_has_known_feasible_crossing_and_no_fabricated_crossing(target, cfg):
    adverse = hand_portfolio(target, -0.04)
    threshold, status = sm.critical_product_share(adverse, target, cfg)
    # 4% on the complement and -4% on target give an exact 50% crossing.
    assert threshold == pytest.approx(0.5)
    assert status == "FEASIBLE_ADVERSE_CROSSING"
    improving = hand_portfolio(target, 0.05)
    value, status = sm.critical_product_share(improving, target, cfg)
    assert np.isnan(value)
    assert status == "NO_ADVERSE_CROSSING_WITHIN_FEASIBLE_RANGE"
    decreasing_but_no_crossing = hand_portfolio(target, 0.01)
    value, status = sm.critical_product_share(decreasing_but_no_crossing, target, cfg)
    assert np.isnan(value)
    assert status == "NO_ADVERSE_CROSSING_WITHIN_FEASIBLE_RANGE"


def test_endpoint_crossing_is_included(cfg):
    params = hand_portfolio("Consumer", -0.01)  # max share .8, rest .2 at 4%.
    threshold, status = sm.critical_product_share(params, "Consumer", cfg)
    assert threshold == pytest.approx(0.8)
    assert status == "FEASIBLE_ADVERSE_CROSSING"


@pytest.mark.parametrize("at_boundary", [True, False])
def test_already_breached_boundary_has_na_not_a_past_share(cfg, at_boundary):
    params = hand_portfolio("Consumer", 0.04)
    params["credit_cost"] = params.pricing - params.funding + (0 if at_boundary else 0.01)
    value, status = sm.critical_product_share(params, "Consumer", cfg)
    assert np.isnan(value)
    assert status == "ALREADY_AT_OR_BELOW_BOUNDARY"


@pytest.mark.parametrize("amount", [-1, 100, float("nan")])
def test_infeasible_mix_requests_fail(amount, cfg):
    with pytest.raises(ValueError):
        sm.apply_portfolio_mix_shift(hand_portfolio("Consumer", 0.04), "Consumer", amount)


def test_auxiliary_multiplier_zeroes_the_result(products, cfg):
    auxiliary = sm.reverse_stress_auxiliary(products, cfg)
    for _, row in auxiliary[auxiliary.diagnostic.eq("portfolio_credit_cost_multiplier")].iterrows():
        params = products[products.scenario.eq(row.scenario)].copy()
        if np.isfinite(row.threshold):
            params["credit_cost"] *= row.threshold
            result = sm.calculate_product_results(params, cfg.horizon_years, row.scenario)
            assert result.raf_result_bn.sum() == pytest.approx(0, abs=1e-8)


def test_card_pricing_sensitivity_is_conditional_and_consistent(products, mix, cfg):
    table = sm.card_pricing_sensitivity(products, cfg)
    for scenario in sm.SCENARIO_ORDER:
        group = table[table.scenario.eq(scenario)]
        assert (np.diff(group.delta_raf_result_per_1pp) < 0).all()
        base_row = group[group.pricing_discount_pp.eq(0)].iloc[0]
        main_row = mix[mix["product"].eq("Cards") & mix.scenario.eq(scenario)].iloc[0]
        assert base_row.delta_raf_result_per_1pp == pytest.approx(main_row.delta_raf_result_per_1pp)
        assert base_row.status == main_row.status
        np.testing.assert_allclose(base_row.critical_share, main_row.critical_share, equal_nan=True)
        for _, row in group.iterrows():
            if np.isfinite(row.critical_share):
                params = products[products.scenario.eq(scenario)].copy()
                params.loc[params["product"].eq("Cards"), "pricing"] = row.card_pricing
                shifted = sm.apply_portfolio_mix_shift(params, "Cards",
                                                      (row.critical_share - main_row.baseline_share) * 100)
                result = sm.calculate_product_results(shifted, cfg.horizon_years, scenario)
                assert result.raf_result_bn.sum() == pytest.approx(0, abs=1e-8)


def test_factor_sensitivity_separates_shocks_and_handles_net_recovery(products, cfg):
    table = sm.factor_sensitivity(products, cfg)
    assert len(table) == 6
    base = products[products.scenario.eq("Base")]
    scale = base.exposure.sum() * 0.5 / 10000
    for _, row in table.iterrows():
        sign = 1 if row.factor == "pricing" else -1
        assert row.delta_raf_result_bn == pytest.approx(sign * row.shift_bp * scale)
    assert table.loc[(table.factor == "credit_cost") & (table.shift_bp == -100), "status"].iloc[0] == "NET_RECOVERY_ASSUMPTION"


@pytest.mark.parametrize("fault", ["duplicate", "infinity", "missing_number", "missing_product", "bad_stock"])
def test_input_qa_rejects_bad_data(data, cfg, fault):
    changed = data.copy()
    if fault == "duplicate":
        changed = pd.concat([changed, changed.iloc[[0]]], ignore_index=True)
    elif fault == "infinity":
        changed.loc[0, "exposure"] = np.inf
    elif fault == "missing_number":
        changed.loc[0, "pricing"] = np.nan
    elif fault == "missing_product":
        changed = changed.drop(index=0)
    else:
        changed.loc[0, "ecl_reserve"] = -1
    assert sm.validate_data(changed, cfg).status.eq("FAIL").any()


@pytest.mark.parametrize("fault", ["date", "product"])
def test_parser_does_not_silently_discard_corrupt_rows(data, fault):
    changed = data.copy()
    column = "report_date" if fault == "date" else "product"
    changed[column] = changed[column].astype(object)
    changed.loc[0, column] = "bad_value"
    with pytest.raises(ValueError):
        sm.normalize_columns(changed)


def test_source_pending_does_not_masquerade_as_independent_fact(data, cfg):
    qa = sm.validate_data(data, cfg)
    assert not qa.status.eq("FAIL").any()
    assert qa.loc[qa["check"].eq("Сверка компонентов ВТБ с первоисточником"), "status"].iloc[0] == "PENDING"
    base = sm.baseline_table(data, cfg)
    assert base.components_source_qa.eq("PENDING").all()


@pytest.mark.parametrize("fault", ["multipliers", "step", "horizon"])
def test_config_rejects_invalid_economic_design(tmp_path, fault):
    raw = json.loads((ROOT / "config/model_config.json").read_text(encoding="utf-8"))
    if fault == "multipliers":
        raw["credit_cost_stress_multiplier"]["Severe"] = 1.1
    elif fault == "step":
        raw["product_mix"]["share_step"] = 0
    else:
        raw["horizon_years"] = 0
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        sm.load_config(path)


def test_full_run_exports_consistent_compact_tables_and_raw_grid(tmp_path, cfg):
    raw = json.loads((ROOT / "config/model_config.json").read_text(encoding="utf-8"))
    raw["input_file"] = str(ROOT / cfg.input_file)
    raw["output_dir"] = str(tmp_path / "outputs")
    path = tmp_path / "config/model_config.json"
    path.parent.mkdir()
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    files = sm.run_model(path)
    assert len(pd.read_csv(files["baseline_summary"])) == 4
    assert len(pd.read_csv(files["scenario_summary"])) == 3
    assert len(pd.read_csv(files["product_mix_summary"])) == 9
    exported = pd.read_csv(files["product_mix_grid"])
    assert files["product_mix_grid"].parent.name == "raw"
    assert len(exported) > 9
    qa = pd.read_csv(files["qa"])
    assert not qa.status.eq("FAIL").any()
    assert qa.status.eq("PENDING").any()
    for product in sm.RISKIER_PRODUCTS:
        assert (tmp_path / f"outputs/figures/{product.lower()}_share_sensitivity.png").exists()
