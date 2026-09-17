from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import stress_model as sm  # noqa: E402


def cfg():
    return sm.load_config(ROOT / "config" / "model_config.json")


def sample_params():
    rows = [
        ["Mortgage", 60.0, 0.01, 0.10],
        ["Consumer", 20.0, 0.04, 0.18],
        ["Auto", 12.0, 0.05, 0.17],
        ["Cards", 8.0, 0.07, 0.30],
    ]
    frame = pd.DataFrame(rows, columns=["product", "exposure", "credit_cost", "product_rate_proxy"])
    frame["margin_anchor"] = 0.04
    frame["lambda"] = 0.2
    frame["period_factor"] = 0.5
    return sm.recompute_margin(frame)


def test_synthetic_margin_and_raf_result_are_correct():
    params = sample_params()
    weighted = float((params.exposure / params.exposure.sum() * params.product_rate_proxy).sum())
    consumer = params.set_index("product").loc["Consumer"]
    expected_margin = 0.04 + 0.2 * (0.18 - weighted)
    assert np.isclose(consumer.synthetic_margin, expected_margin)
    result = sm.calculate_product_results(params, 0.5, "Base").set_index("product").loc["Consumer"]
    assert np.isclose(result.risk_adjusted_financial_result_bn,
                      consumer.exposure * (expected_margin - consumer.credit_cost) * 0.5)


def test_critical_margin_exactly_zeroes_portfolio_raf_result():
    params = sm.calculate_product_results(sample_params(), 0.5, "Base")
    threshold, status = sm.solve_critical_margin(params, "Consumer", cfg())
    changed = params.copy()
    changed.loc[changed["product"].eq("Consumer"), "synthetic_margin"] = threshold
    changed["risk_adjusted_rate"] = changed.synthetic_margin - changed.credit_cost
    total = float((changed.exposure * changed.risk_adjusted_rate * 0.5).sum())
    assert status in {"FEASIBLE", "NEGATIVE_THRESHOLD"}
    assert np.isclose(total, 0.0, atol=1e-12)


def test_higher_credit_cost_does_not_reduce_critical_margin():
    params = sm.calculate_product_results(sample_params(), 0.5, "Base")
    before, _ = sm.solve_critical_margin(params, "Auto", cfg())
    stressed = params.copy()
    stressed.loc[stressed["product"].eq("Auto"), "credit_cost"] += 0.01
    after, _ = sm.solve_critical_margin(stressed, "Auto", cfg())
    assert after >= before
    assert np.isclose(after - before, 0.01)


def test_severe_is_not_less_stressful_than_moderate():
    config = cfg()
    data = sm.load_dataset(ROOT / config.input_file, config.data_sheet)
    products = sm.build_scenarios(data, config)
    summary = sm.scenario_summary(products).set_index("scenario")
    assert summary.loc["Severe", "risk_adjusted_financial_result_bn"] <= summary.loc[
        "Moderate", "risk_adjusted_financial_result_bn"
    ]
    assert summary.loc["Moderate", "risk_adjusted_financial_result_bn"] <= summary.loc[
        "Base", "risk_adjusted_financial_result_bn"
    ]


def test_portfolio_mix_shift_keeps_total_exposure_fixed():
    params = sample_params()
    shifted = sm.apply_portfolio_mix_shift(params, "Consumer", 10.0)
    assert np.isclose(shifted.exposure.sum(), params.exposure.sum())
    assert np.isclose(shifted.weight.sum(), 1.0)
    assert np.isclose(
        shifted.loc[shifted["product"].eq("Consumer"), "exposure"].iloc[0]
        - params.loc[params["product"].eq("Consumer"), "exposure"].iloc[0],
        10.0,
    )


def test_thresholds_always_have_statuses():
    params = sm.calculate_product_results(sample_params(), 0.5, "Base")
    reverse = sm.reverse_stress(params, cfg())
    assert reverse.status.notna().all()
    assert reverse.loc[reverse.threshold.isna(), "status"].ne("FEASIBLE").all()
    negative = reverse[reverse.threshold.lt(0, fill_value=False)]
    assert negative.status.eq("NEGATIVE_THRESHOLD").all()


def test_current_excel_passes_formula_qa_and_uses_model_data():
    config = cfg()
    assert config.data_sheet == "MODEL_DATA"
    assert config.input_file.endswith("dataset_vtb_main_clean.xlsx")
    data = sm.load_dataset(ROOT / config.input_file, config.data_sheet)
    qa = sm.validate_data(data, config)
    assert not qa.status.eq("FAIL").any()
    assert len(data) == 24


def test_output_tables_are_compact_and_complete():
    config = cfg()
    data = sm.load_dataset(ROOT / config.input_file, config.data_sheet)
    products = sm.build_scenarios(data, config)
    summary = sm.scenario_summary(products)
    critical = sm.critical_margin_table(products, config)
    stress = sm.stress_critical_margin(products, config)
    mix = sm.portfolio_mix_sensitivity(products, config)
    assert summary.columns.tolist() == ["scenario", "risk_adjusted_financial_result_bn"]
    assert summary.scenario.tolist() == sm.SCENARIO_ORDER
    assert critical["product"].tolist() == config.products
    assert {"current_margin", "critical_margin", "required_margin_premium_vs_mortgage", "status"}.issubset(critical.columns)
    assert stress.shape[0] == 4
    assert mix.shape[0] == 9
