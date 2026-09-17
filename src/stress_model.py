#!/usr/bin/env python3
"""Воспроизводимый анализ кредитного риска и продуктового состава портфеля."""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PRODUCTS = ["Mortgage", "Consumer", "Auto", "Cards"]
RISKIER_PRODUCTS = ["Consumer", "Auto", "Cards"]
SCENARIO_ORDER = ["Base", "Moderate", "Severe"]
PRODUCT_LABELS = {"Mortgage": "Ипотека", "Consumer": "Потребительские кредиты",
                  "Auto": "Автокредиты", "Cards": "Кредитные карты"}
SCENARIO_LABELS = {"Base": "Базовый", "Moderate": "Умеренный", "Severe": "Тяжёлый"}
STATUS_LABELS = {
    "FEASIBLE_ADVERSE_CROSSING": "Порог существует",
    "NO_ADVERSE_CROSSING_WITHIN_FEASIBLE_RANGE": "Нет порога в допустимом диапазоне",
    "ALREADY_AT_OR_BELOW_BOUNDARY": "Исходный результат уже на границе или ниже",
}
COLORS = {"Base": "#296d98", "Moderate": "#d58a20", "Severe": "#b84147"}
ALIASES = {
    "Отчетная дата": "report_date", "Report date": "report_date",
    "Продукт": "product", "Product": "product",
    "Экспозиция, млрд руб.": "exposure", "Exposure, RUB bn": "exposure",
    "Резерв ECL, млрд руб.": "ecl_reserve", "ECL reserve, RUB bn": "ecl_reserve",
    "Переоценка ECL, млрд руб.": "ecl_remeasurement", "ECL remeasurement, RUB bn": "ecl_remeasurement",
    "Уровень ECL, %": "ecl_rate", "ECL rate, %": "ecl_rate",
    "Стоимость кредитного риска, %": "credit_cost", "Credit cost, %": "credit_cost",
    "Ставка по продукту, %": "pricing", "Product rate, %": "pricing", "product_rate": "pricing",
    "Стоимость фондирования, %": "funding", "Funding rate, %": "funding", "funding_rate": "funding",
}
REQUIRED = ["report_date", "product", "exposure", "ecl_reserve", "ecl_remeasurement",
            "ecl_rate", "credit_cost", "pricing", "funding"]
NUMERIC = REQUIRED[2:]


@dataclass(frozen=True)
class ModelConfig:
    input_file: str
    data_sheet: str
    baseline_date: pd.Timestamp
    history_start_date: pd.Timestamp
    history_end_date: pd.Timestamp
    horizon_years: float
    products: list[str]
    critical_result_bn: float
    credit_cost_stress_multiplier: Mapping[str, float]
    mortgage_pricing_proxy: Mapping
    product_mix: Mapping
    mortgage_pricing_sensitivity: Mapping
    card_pricing_sensitivity: Mapping
    source_qa: Mapping
    stress_classification: str
    qa_tolerance: float
    output_dir: str
    research_title: str
    primary_research_question: str


def load_config(path: Path) -> ModelConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    fields = ModelConfig.__dataclass_fields__
    cfg = ModelConfig(**{key: pd.Timestamp(raw[key]) if key.endswith("_date") else raw[key]
                         for key in fields})
    if cfg.products != PRODUCTS:
        raise ValueError("Configured products must be Mortgage, Consumer, Auto, Cards in this order")
    if cfg.horizon_years != 0.5 or cfg.critical_result_bn != 0:
        raise ValueError("This research design requires horizon_years=0.5 and critical_result_bn=0")
    if not cfg.history_start_date <= cfg.baseline_date <= cfg.history_end_date:
        raise ValueError("Baseline date is outside the history window")
    if not math.isfinite(cfg.qa_tolerance) or cfg.qa_tolerance <= 0:
        raise ValueError("qa_tolerance must be positive and finite")
    mult = [float(cfg.credit_cost_stress_multiplier[s]) for s in SCENARIO_ORDER]
    if not all(math.isfinite(x) for x in mult) or not (mult[0] == 1 < mult[1] < mult[2]):
        raise ValueError("Credit-cost multipliers must satisfy 1 = Base < Moderate < Severe")
    step = float(cfg.product_mix["share_step"])
    if not math.isfinite(step) or not 0 < step <= 1:
        raise ValueError("share_step must be in (0, 1]")
    rate = float(cfg.mortgage_pricing_proxy["rate"])
    if not math.isfinite(rate) or rate < 0:
        raise ValueError("Mortgage market proxy must be finite and nonnegative")
    low, high = [float(cfg.mortgage_pricing_sensitivity[k]) for k in ("min_rate", "max_rate")]
    if not (math.isfinite(low) and math.isfinite(high) and 0 <= low < high and low <= rate <= high):
        raise ValueError("Invalid Mortgage sensitivity range")
    if int(cfg.mortgage_pricing_sensitivity["points"]) < 2:
        raise ValueError("Mortgage sensitivity needs at least two points")
    discounts = cfg.card_pricing_sensitivity["discounts_pp"]
    if not discounts or 0 not in discounts or any(not math.isfinite(x) or x < 0 for x in discounts):
        raise ValueError("Cards sensitivity requires finite nonnegative discounts including 0")
    return cfg


def normalize_columns(raw: pd.DataFrame) -> pd.DataFrame:
    """Remove only the known bilingual header rows; reject malformed data."""
    data = raw.rename(columns={c: ALIASES.get(str(c).strip(), str(c).strip()) for c in raw.columns})
    if data.columns.duplicated().any():
        raise ValueError("Duplicate input columns after normalization")
    missing = sorted(set(REQUIRED) - set(data.columns))
    if missing:
        raise ValueError(f"Missing DATA_MASTER columns: {missing}")
    data = data[REQUIRED].dropna(how="all").copy()
    header = (data["product"].isin(["Product", "product"]) &
              data["report_date"].isin(["Report date", "report_date"]))
    data = data.loc[~header].copy()
    data["product"] = data["product"].astype(str).str.strip()
    unknown = sorted(set(data["product"]) - set(PRODUCTS))
    if unknown:
        raise ValueError(f"Unknown products: {unknown}")
    data["report_date"] = pd.to_datetime(data["report_date"], format="mixed", dayfirst=True, errors="coerce")
    if data.report_date.isna().any():
        raise ValueError("Invalid report dates")
    for column in NUMERIC:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.sort_values(["report_date", "product"]).reset_index(drop=True)


def load_dataset(path: Path, sheet_name: str = "DATA_MASTER") -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return normalize_columns(pd.read_csv(path))
    return normalize_columns(pd.read_excel(path, sheet_name=sheet_name))


def add_recomputed_credit_cost(data: pd.DataFrame) -> pd.DataFrame:
    """Join the exact previous half-year date, never an arbitrary previous row."""
    out = data.copy()
    out["previous_date"] = out.report_date - pd.offsets.MonthEnd(6)
    previous = data[["report_date", "product", "exposure"]].rename(
        columns={"report_date": "previous_date", "exposure": "previous_exposure"})
    out = out.merge(previous, on=["previous_date", "product"], how="left", validate="one_to_one")
    out["average_exposure"] = (out.previous_exposure + out.exposure) / 2
    out["credit_cost_recomputed"] = 2 * out.ecl_remeasurement / out.average_exposure
    out["ecl_rate_recomputed"] = out.ecl_reserve / out.exposure
    return out


def validate_data(data: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    """Return auditable QA, including FAIL rows; run_model refuses failed inputs."""
    rows = []
    def check(name, ok, detail):
        rows.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)})

    duplicates = data.duplicated(["report_date", "product"]).sum()
    check("Уникальность даты и продукта", duplicates == 0, f"duplicates={duplicates}")
    check("Полнота и конечность чисел", np.isfinite(data[NUMERIC].to_numpy(dtype=float)).all(),
          f"missing_cells={data[NUMERIC].isna().sum().sum()}")
    check("Положительная экспозиция", (data.exposure > 0).all(), f"min={data.exposure.min()}")
    check("Допустимый резерв ECL", ((data.ecl_reserve >= 0) & (data.ecl_reserve <= data.exposure)).all(),
          "0 <= reserve <= exposure")
    check("Неотрицательные pricing и funding", (data[["pricing", "funding"]] >= 0).all().all(), "annual rates")
    dates = sorted(data.report_date.unique())
    halfyears = pd.date_range(cfg.history_start_date, cfg.history_end_date, freq="6ME")
    check("Полугодовые даты истории", list(pd.to_datetime(dates)) == list(halfyears),
          f"dates={len(dates)}")
    panel_ok = bool(len(data)) and all(len(g) == 4 and set(g["product"]) == set(PRODUCTS)
                                     for _, g in data.groupby("report_date"))
    check("Полная панель четырёх продуктов", panel_ok, f"rows={len(data)}")
    if not duplicates:
        computed = add_recomputed_credit_cost(data)
        mask = computed.credit_cost_recomputed.notna()
        diff = (computed.loc[mask, "credit_cost_recomputed"] - computed.loc[mask, "credit_cost"]).abs().max()
        check("Прямая формула годовой стоимости риска", mask.any() and diff <= cfg.qa_tolerance,
              f"comparable_rows={mask.sum()}, max_abs_diff={diff}")
        diff_ecl = (computed.ecl_rate_recomputed - computed.ecl_rate).abs().max()
        check("Формула доли резерва ECL", diff_ecl <= cfg.qa_tolerance, f"max_abs_diff={diff_ecl}")
        base = computed[computed.report_date.eq(cfg.baseline_date)]
        check("Прямые компоненты Base", len(base) == 4 and base.credit_cost_recomputed.notna().all(),
              f"previous_date={cfg.baseline_date - pd.offsets.MonthEnd(6):%Y-%m-%d}")
        check("Неотрицательная стоимость риска Base", len(base) == 4 and (base.credit_cost_recomputed >= 0).all(),
              "v1 credit-risk deterioration requires nonnegative baseline credit costs")
    rows.append({"check": "Сверка компонентов ВТБ с первоисточником",
                 "status": cfg.source_qa["vtb_product_components"],
                 "detail": cfg.source_qa["note"]})
    return pd.DataFrame(rows)


def baseline_table(data: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    computed = add_recomputed_credit_cost(data)
    base = computed[computed.report_date.eq(cfg.baseline_date)].set_index("product").reindex(PRODUCTS).reset_index()
    needed = ["exposure", "average_exposure", "credit_cost_recomputed", "pricing", "funding", "ecl_rate_recomputed"]
    if not np.isfinite(base[needed].to_numpy(dtype=float)).all() or (base.exposure <= 0).any():
        raise ValueError("Baseline requires four products and finite direct credit-cost components")
    base["source_pricing"] = base.pricing
    base["source_credit_cost"] = base.credit_cost
    base["credit_cost"] = base.credit_cost_recomputed
    base["ecl_rate"] = base.ecl_rate_recomputed
    base.loc[base["product"].eq("Mortgage"), "pricing"] = float(cfg.mortgage_pricing_proxy["rate"])
    base["pricing_classification"] = "MARKET PROXY"
    base["funding_classification"] = "MARKET PROXY"
    base["components_source_qa"] = cfg.source_qa["vtb_product_components"]
    base["weight"] = base.exposure / base.exposure.sum()
    return base


def calculate_product_results(params: pd.DataFrame, horizon_years: float, scenario: str) -> pd.DataFrame:
    if not math.isfinite(horizon_years) or horizon_years <= 0:
        raise ValueError("Positive horizon required")
    out = params.copy()
    if not np.isfinite(out[["exposure", "pricing", "funding", "credit_cost"]].to_numpy(dtype=float)).all():
        raise ValueError("Nonfinite financial inputs")
    if (out.exposure < 0).any() or out.exposure.sum() <= 0:
        raise ValueError("Invalid exposure")
    out["weight"] = out.exposure / out.exposure.sum()
    out["cras"] = out.pricing - out.funding - out.credit_cost
    out["credit_loss_bn"] = out.exposure * out.credit_cost * horizon_years
    out["raf_result_bn"] = out.exposure * out.cras * horizon_years
    out["scenario"] = scenario
    return out


def build_scenarios(data: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    base = baseline_table(data, cfg)
    results = []
    for scenario in SCENARIO_ORDER:
        current = base.copy()
        current["credit_cost"] = base.credit_cost * cfg.credit_cost_stress_multiplier[scenario]
        results.append(calculate_product_results(current, cfg.horizon_years, scenario))
    return pd.concat(results, ignore_index=True)


def scenario_summary(products: pd.DataFrame, horizon_years: float) -> pd.DataFrame:
    summary = products.groupby("scenario").agg(
        total_exposure_bn=("exposure", "sum"), credit_loss_bn=("credit_loss_bn", "sum"),
        raf_result_bn=("raf_result_bn", "sum")).reindex(SCENARIO_ORDER)
    summary["cras"] = summary.raf_result_bn / summary.total_exposure_bn / horizon_years
    return summary[["credit_loss_bn", "raf_result_bn", "cras"]].reset_index()


def apply_portfolio_mix_shift(params: pd.DataFrame, target: str, share_change_pp: float) -> pd.DataFrame:
    """One independent transfer: only target and Mortgage exposures change."""
    if target not in RISKIER_PRODUCTS:
        raise ValueError("Invalid target product")
    change = float(share_change_pp) / 100
    if not math.isfinite(change) or change < 0:
        raise ValueError("Share increase must be finite and nonnegative")
    out = params.copy()
    total = float(out.exposure.sum())
    mortgage = out["product"].eq("Mortgage")
    target_mask = out["product"].eq(target)
    if mortgage.sum() != 1 or target_mask.sum() != 1:
        raise ValueError("Target and Mortgage rows must be unique")
    available = float(out.loc[mortgage, "exposure"].iloc[0])
    amount = change * total
    if amount > available + 1e-10:
        raise ValueError("Share increase exceeds available Mortgage exposure")
    amount = min(amount, available)
    out.loc[mortgage, "exposure"] = available - amount
    out.loc[target_mask, "exposure"] += amount
    out["weight"] = out.exposure / total
    return out


def marginal_effects(params: pd.DataFrame, target: str, cfg: ModelConfig) -> tuple[float, float]:
    group = params.set_index("product")
    scale = float(group.exposure.sum()) * cfg.horizon_years * 0.01
    cras = group.pricing - group.funding - group.credit_cost
    delta_result = scale * float(cras[target] - cras["Mortgage"])
    delta_loss = scale * float(group.loc[target, "credit_cost"] - group.loc["Mortgage", "credit_cost"])
    return delta_result, delta_loss


def critical_product_share(params: pd.DataFrame, target: str, cfg: ModelConfig) -> tuple[float, str]:
    """Exact first adverse crossing, from current share to full Mortgage replacement."""
    group = params.set_index("product")
    total = float(group.exposure.sum())
    current = float(group.loc[target, "exposure"] / total)
    maximum = current + float(group.loc["Mortgage", "exposure"] / total)
    result = float((group.exposure * (group.pricing - group.funding - group.credit_cost)).sum()) * cfg.horizon_years
    slope = marginal_effects(params, target, cfg)[0] * 100
    if result <= cfg.critical_result_bn + cfg.qa_tolerance:
        return math.nan, "ALREADY_AT_OR_BELOW_BOUNDARY"
    no_crossing = "NO_ADVERSE_CROSSING_WITHIN_FEASIBLE_RANGE"
    if slope >= 0:
        return math.nan, no_crossing
    threshold = current + (cfg.critical_result_bn - result) / slope
    if threshold < current - 1e-12 or threshold > maximum + 1e-12:
        return math.nan, no_crossing
    return min(maximum, max(current, threshold)), "FEASIBLE_ADVERSE_CROSSING"


def product_mix_summary(products: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    rows = []
    for target in RISKIER_PRODUCTS:
        for scenario in SCENARIO_ORDER:
            group = products[products.scenario.eq(scenario)]
            target_exposure = float(group.loc[group["product"].eq(target), "exposure"].iloc[0])
            delta_result, delta_loss = marginal_effects(group, target, cfg)
            critical, status = critical_product_share(group, target, cfg)
            rows.append({"product": target, "scenario": scenario, "baseline_share": target_exposure / group.exposure.sum(),
                         "delta_raf_result_per_1pp": delta_result, "delta_credit_loss_per_1pp": delta_loss,
                         "critical_share": critical, "status": status})
    return pd.DataFrame(rows)


def product_mix_grid(products: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    frames = []
    step = float(cfg.product_mix["share_step"])
    for scenario in SCENARIO_ORDER:
        group = products[products.scenario.eq(scenario)].set_index("product").reindex(PRODUCTS)
        total = float(group.exposure.sum())
        original = group.exposure.to_numpy(dtype=float)
        rates = (group.pricing - group.funding - group.credit_cost).to_numpy()
        costs = group.credit_cost.to_numpy()
        base_result = float(original @ rates * cfg.horizon_years)
        base_loss = float(original @ costs * cfg.horizon_years)
        for target in RISKIER_PRODUCTS:
            ti = PRODUCTS.index(target)
            current = original[ti] / total
            capacity = original[0] / total
            increases = np.arange(0, capacity, step)
            if not len(increases) or not np.isclose(increases[-1], capacity, atol=1e-14, rtol=0):
                increases = np.append(increases, capacity)
            else:
                increases[-1] = capacity
            exposure = np.tile(original, (len(increases), 1))
            amounts = np.minimum(increases * total, original[0])
            exposure[:, 0] = original[0] - amounts
            exposure[:, ti] = original[ti] + amounts
            weights = exposure / total
            result = exposure @ rates * cfg.horizon_years
            losses = exposure @ costs * cfg.horizon_years
            frame = pd.DataFrame({
                "product": target, "scenario": scenario, "target_share": current + increases,
                "total_exposure_bn": exposure.sum(axis=1), "credit_loss_bn": losses,
                "raf_result_bn": result, "cras": result / total / cfg.horizon_years,
                "delta_credit_loss_bn": losses - base_loss, "delta_raf_result_bn": result - base_result,
            })
            for index, product in enumerate(PRODUCTS):
                frame[f"{product.lower()}_share"] = weights[:, index]
                frame[f"{product.lower()}_exposure_bn"] = exposure[:, index]
            frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def reverse_stress_auxiliary(products: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    rows = []
    for scenario in SCENARIO_ORDER:
        group = products[products.scenario.eq(scenario)].set_index("product")
        precredit = float((group.exposure * (group.pricing - group.funding)).sum()) * cfg.horizon_years
        losses = float((group.exposure * group.credit_cost).sum()) * cfg.horizon_years
        if losses <= 0:
            threshold, status = math.nan, "NO_POSITIVE_CREDIT_LOSS_BASE"
        else:
            threshold = (precredit - cfg.critical_result_bn) / losses
            if threshold < 0:
                threshold, status = math.nan, "NO_NONNEGATIVE_SOLUTION"
            elif threshold < 1:
                status = "THRESHOLD_BELOW_CURRENT_1X"
            else:
                status = "FEASIBLE"
        rows.append({"scenario": scenario, "diagnostic": "portfolio_credit_cost_multiplier",
                     "product": "ALL", "threshold": threshold, "unit": "x_current_scenario", "status": status})
        for product in PRODUCTS:
            margin = float(group.loc[product, "pricing"] - group.loc[product, "funding"])
            rows.append({"scenario": scenario, "diagnostic": "product_break_even_credit_cost",
                         "product": product, "threshold": margin, "unit": "annual_rate",
                         "status": "FEASIBLE" if margin >= 0 else "NEGATIVE_BREAK_EVEN"})
            if product != "Mortgage":
                mortgage_cras = float(group.loc["Mortgage", "pricing"] - group.loc["Mortgage", "funding"]
                                      - group.loc["Mortgage", "credit_cost"])
                threshold = margin - mortgage_cras
                rows.append({"scenario": scenario, "diagnostic": "marginal_break_even_credit_cost_vs_mortgage",
                             "product": product, "threshold": threshold, "unit": "annual_rate",
                             "status": "FEASIBLE" if threshold >= 0 else "NEGATIVE_BREAK_EVEN"})
    return pd.DataFrame(rows)


def factor_sensitivity(products: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    """Portfolio-wide +/-100 bp shifts, separate from the three financial scenarios."""
    base = products[products.scenario.eq("Base")]
    original = float(base.raf_result_bn.sum())
    rows = []
    for factor in ["pricing", "funding", "credit_cost"]:
        for shift_bp in [-100, 100]:
            params = base.copy()
            params[factor] += shift_bp / 10000
            result = calculate_product_results(params, cfg.horizon_years, "FactorSensitivity")
            status = "NET_RECOVERY_ASSUMPTION" if (params.credit_cost < 0).any() else "FEASIBLE"
            rows.append({"factor": factor, "shift_bp": shift_bp, "raf_result_bn": result.raf_result_bn.sum(),
                         "credit_loss_bn": result.credit_loss_bn.sum(),
                         "delta_raf_result_bn": result.raf_result_bn.sum() - original, "status": status})
    return pd.DataFrame(rows)


def mortgage_pricing_sensitivity(products: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    base = products[products.scenario.eq("Base")]
    settings = cfg.mortgage_pricing_sensitivity
    rates = np.unique(np.append(np.linspace(settings["min_rate"], settings["max_rate"], settings["points"]),
                                cfg.mortgage_pricing_proxy["rate"]))
    rows = []
    for rate in rates:
        params = base.copy()
        params.loc[params["product"].eq("Mortgage"), "pricing"] = rate
        result = calculate_product_results(params, cfg.horizon_years, "MortgageSensitivity")
        rows.append({"mortgage_pricing": rate, "raf_result_bn": result.raf_result_bn.sum(),
                     "credit_loss_bn": result.credit_loss_bn.sum()})
    return pd.DataFrame(rows)


def card_pricing_sensitivity(products: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    rows = []
    for scenario in SCENARIO_ORDER:
        original = products[products.scenario.eq(scenario)]
        original_rate = float(original.loc[original["product"].eq("Cards"), "pricing"].iloc[0])
        for discount in cfg.card_pricing_sensitivity["discounts_pp"]:
            rate = original_rate - discount / 100
            if rate < 0:
                raise ValueError("Card pricing discount would make pricing negative")
            params = original.copy()
            params.loc[params["product"].eq("Cards"), "pricing"] = rate
            result = calculate_product_results(params, cfg.horizon_years, scenario)
            threshold, status = critical_product_share(result, "Cards", cfg)
            rows.append({"scenario": scenario, "pricing_discount_pp": discount, "card_pricing": rate,
                         "raf_result_bn": result.raf_result_bn.sum(),
                         "delta_raf_result_per_1pp": marginal_effects(result, "Cards", cfg)[0],
                         "critical_share": threshold, "status": status})
    return pd.DataFrame(rows)


def validate_outputs(products: pd.DataFrame, summary: pd.DataFrame, mix: pd.DataFrame,
                     grid: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    rows = []
    def check(name, ok, detail=""):
        rows.append({"check": name, "status": "PASS" if bool(ok) else "FAIL", "detail": str(detail)})

    total = float(products.loc[products.scenario.eq("Base"), "exposure"].sum())
    check("Компактные сводки", len(summary) == 3 and len(mix) == 9)
    check("Постоянная общая экспозиция", np.allclose(grid.total_exposure_bn, total, atol=cfg.qa_tolerance, rtol=0))
    shares = [f"{p.lower()}_share" for p in PRODUCTS]
    check("Допустимые веса сетки", (grid[shares] >= -1e-12).all().all()
          and np.allclose(grid[shares].sum(axis=1), 1, atol=1e-12, rtol=0))
    check("Упорядоченный стресс", np.all(np.diff(summary.raf_result_bn) < 0)
          and np.all(np.diff(summary.credit_loss_bn) > 0))
    for _, row in mix.iterrows():
        scenario, target = row["scenario"], row["product"]
        params = products[products.scenario.eq(scenario)]
        g = grid[grid.scenario.eq(scenario) & grid["product"].eq(target)]
        start, end = g.iloc[0], g.iloc[-1]
        check(f"{scenario}/{target}: начало и конец", np.isclose(start.target_share, row.baseline_share)
              and np.isclose(end.mortgage_share, 0))
        other = [p for p in RISKIER_PRODUCTS if p != target]
        check(f"{scenario}/{target}: фиксированные остальные продукты",
              all(np.allclose(g[f"{p.lower()}_exposure_bn"],
                              params.loc[params["product"].eq(p), "exposure"].iloc[0], atol=1e-10, rtol=0)
                  for p in other))
        distance = (g.target_share - row.baseline_share) * 100
        check(f"{scenario}/{target}: аналитика и сетка",
              np.allclose(g.delta_raf_result_bn, distance * row.delta_raf_result_per_1pp, atol=cfg.qa_tolerance, rtol=0)
              and np.allclose(g.delta_credit_loss_bn, distance * row.delta_credit_loss_per_1pp, atol=cfg.qa_tolerance, rtol=0))
        if np.isfinite(row.critical_share):
            crossing = apply_portfolio_mix_shift(params, target, (row.critical_share - row.baseline_share) * 100)
            value = calculate_product_results(crossing, cfg.horizon_years, scenario).raf_result_bn.sum()
            grid_value = np.interp(row.critical_share, g.target_share, g.raf_result_bn)
            check(f"{scenario}/{target}: порог обнуляет RAFR",
                  abs(value - cfg.critical_result_bn) <= cfg.qa_tolerance
                  and abs(grid_value - cfg.critical_result_bn) <= cfg.qa_tolerance)
        elif row.status == "NO_ADVERSE_CROSSING_WITHIN_FEASIBLE_RANGE":
            check(f"{scenario}/{target}: отсутствие пересечения",
                  (g.raf_result_bn > cfg.critical_result_bn - cfg.qa_tolerance).all())
        else:
            check(f"{scenario}/{target}: исходная граница",
                  start.raf_result_bn <= cfg.critical_result_bn + cfg.qa_tolerance)
    return pd.DataFrame(rows)


def data_adequacy_report(data: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    return pd.DataFrame([
        {"item": "История", "detail": f"{data.report_date.nunique()} отчётных дат / {len(data)} строк",
         "status": "SCENARIO_ANALYSIS_ONLY"},
        {"item": "Прямая стоимость риска", "detail": "Предыдущая и текущая экспозиции, переоценка ECL из DATA_MASTER",
         "status": "FORMULA_RECONCILED"},
        {"item": "Первичный источник ВТБ", "detail": cfg.source_qa["note"], "status": cfg.source_qa["vtb_product_components"]},
        {"item": "Вспомогательная история", "detail": "Реконструкция 30.06.2024 и зависимая стоимость риска 31.12.2024 не калибруют стресс",
         "status": "AUXILIARY"},
        {"item": "Изменение периметра", "detail": "Почта Банк: изменения к 2026H1 не интерпретируются как чисто органические",
         "status": "LIMITATION"},
    ])


def make_figures(grid: pd.DataFrame, mix: pd.DataFrame, mortgage: pd.DataFrame,
                 cards: pd.DataFrame, cfg: ModelConfig, outdir: Path) -> None:
    figdir = outdir / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    for product in RISKIER_PRODUCTS:
        fig, ax = plt.subplots(figsize=(8.5, 4.8))
        for scenario in SCENARIO_ORDER:
            g = grid[grid["product"].eq(product) & grid.scenario.eq(scenario)]
            ax.plot(g.target_share * 100, g.raf_result_bn, color=COLORS[scenario], label=SCENARIO_LABELS[scenario])
            r = mix[mix["product"].eq(product) & mix.scenario.eq(scenario)].iloc[0]
            if np.isfinite(r.critical_share):
                ax.scatter([r.critical_share * 100], [0], color=COLORS[scenario], zorder=5)
                ax.annotate(f"{r.critical_share:.1%}", (r.critical_share * 100, 0),
                            xytext=(3, 9 if scenario == "Moderate" else -18), textcoords="offset points", fontsize=9)
        baseline_share = mix.loc[mix["product"].eq(product), "baseline_share"].iloc[0]
        ax.axvline(baseline_share * 100, color="#666666", linestyle=":", label="Исходная доля")
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set(xlabel="Доля целевого продукта, %", ylabel="RAFR за 6 месяцев, млрд руб.",
               title=f"{PRODUCT_LABELS[product]}: замещение ипотеки")
        ax.legend(fontsize=9)
        ax.grid(alpha=0.15)
        fig.tight_layout()
        fig.savefig(figdir / f"{product.lower()}_share_sensitivity.png", dpi=160)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(mortgage.mortgage_pricing * 100, mortgage.raf_result_bn)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set(xlabel="Ипотечная ставка-заменитель, %", ylabel="RAFR за 6 месяцев, млрд руб.",
           title="Чувствительность Base к ипотечному pricing proxy")
    fig.tight_layout()
    fig.savefig(figdir / "mortgage_pricing_sensitivity.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for scenario in SCENARIO_ORDER:
        g = cards[cards.scenario.eq(scenario)].sort_values("card_pricing")
        ax.plot(g.card_pricing * 100, g.delta_raf_result_per_1pp, marker="o",
                color=COLORS[scenario], label=SCENARIO_LABELS[scenario])
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set(xlabel="Условный карточный pricing proxy, %", ylabel="ΔRAFR при +1 п.п. Cards, млрд руб.",
           title="Зависимость эффекта Cards от ставки-заменителя")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figdir / "card_pricing_sensitivity.png", dpi=160)
    plt.close(fig)


def presentation_table(table: pd.DataFrame, rates=(), pp=(), labels=None) -> str:
    view = table.copy()
    if "product" in view:
        view["product"] = view["product"].map(PRODUCT_LABELS).fillna(view["product"])
    if "scenario" in view:
        view["scenario"] = view.scenario.map(SCENARIO_LABELS).fillna(view.scenario)
    for column in rates:
        view[column] = view[column].map(lambda x: "NA" if pd.isna(x) else f"{x * 100:.2f}%")
    for column in pp:
        view[column] = view[column].map(lambda x: "NA" if pd.isna(x) else f"{x * 100:.2f}")
    if "status" in view:
        view["status"] = view.status.map(STATUS_LABELS).fillna(view.status)
    return view.rename(columns=labels or {}).to_markdown(index=False, floatfmt=".3f")


def build_report(cfg: ModelConfig, baseline: pd.DataFrame, summary: pd.DataFrame, mix: pd.DataFrame,
                 mortgage: pd.DataFrame, cards: pd.DataFrame, auxiliary: pd.DataFrame, qa: pd.DataFrame) -> str:
    baseline_labels = {"product": "Продукт", "exposure": "Экспозиция, млрд руб.", "weight": "Доля",
                       "pricing": "Кредитная ставка", "funding": "Фондирование", "credit_cost": "Стоимость риска",
                       "cras": "CRAS", "credit_loss_bn": "Потери за 6М", "raf_result_bn": "RAFR за 6М"}
    mix_labels = {"product": "Продукт", "scenario": "Сценарий", "baseline_share": "Исходная доля",
                  "delta_raf_result_per_1pp": "ΔRAFR на +1 п.п.", "delta_credit_loss_per_1pp": "Δпотери на +1 п.п.",
                  "critical_share": "Критическая доля", "status": "Статус"}
    lines = [f"# {cfg.research_title}", "", "## 1. Исследовательский вопрос", "", cfg.primary_research_question, "",
             "RAFR (risk-adjusted financial result) — финансовый результат с учётом кредитного риска за шесть месяцев; "
             "CRAS (credit-risk-adjusted spread) — годовой спред с учётом кредитного риска.", "",
             "Данные → Base → стресс стоимости риска → три независимых эксперимента с составом → обратное стресс-тестирование.", "",
             "## 2. Базовый портфель", "",
             f"Дата: {cfg.baseline_date:%d.%m.%Y}; горизонт: 2026H2, {cfg.horizon_years} года. "
             f"Общая экспозиция {baseline.exposure.sum():,.1f} млрд руб. получена суммированием Excel.", "",
             presentation_table(baseline, rates=["weight", "pricing", "funding", "credit_cost", "cras"],
                                labels=baseline_labels), "",
             "Все суммы — млрд руб.; ставки — годовые. Ипотека 17,8% — MARKET PROXY, внешний показатель Банка России, "
             "не фактическая доходность ВТБ. Исходная ставка Excel 9,0% сохранена в анализе чувствительности.", "",
             "## 3. Формулы", "",
             "- Средняя экспозиция = (экспозиция 31.12.2025 + экспозиция 30.06.2026) / 2.",
             "- Стоимость риска = 2 × переоценка ECL (expected credit losses — ожидаемых кредитных убытков) за H1 / средняя экспозиция.",
             "- Доля резерва ECL = резерв / экспозиция: показатель запаса, а стоимость риска — потоковый показатель.",
             "- CRAS (credit-risk-adjusted spread — спред с учётом кредитного риска) = pricing − funding − credit_cost.",
             "- RAFR (risk-adjusted financial result — финансовый результат с учётом риска) = exposure × CRAS × 0,5.",
             "- Кредитные потери за 6 месяцев = exposure × credit_cost × 0,5.", "",
             "Для роста доли продукта i за счёт ипотеки: ΔRAFR на +1 п.п. = total × 0,5 × 0,01 × (CRAS_i − CRAS_M). "
             "Δпотери на +1 п.п. = total × 0,5 × 0,01 × (CC_i − CC_M). Эти формулы сверены с полной численной сеткой.", "",
             "## 4. Base / Moderate / Severe", "",
             "Множители стоимости риска: " + "; ".join(f"{s} × {cfg.credit_cost_stress_multiplier[s]:g}" for s in SCENARIO_ORDER) + ". Это PROVISIONAL MODEL ASSUMPTION — "
             "предварительные сценарные предположения. Pricing и funding фиксированы; исторические sigma не используются.", "",
             presentation_table(summary, rates=["cras"],
                                labels={"scenario": "Сценарий", "credit_loss_bn": "Потери, млрд руб.",
                                        "raf_result_bn": "RAFR, млрд руб.", "cras": "Годовой CRAS"}), ""]
    for number, product in enumerate(RISKIER_PRODUCTS, 5):
        view = mix[mix["product"].eq(product)].drop(columns="product")
        lines += [f"## {number}. {PRODUCT_LABELS[product]}: чувствительность состава", "",
                  presentation_table(view, rates=["baseline_share", "critical_share"], labels=mix_labels), "",
                  f"![{PRODUCT_LABELS[product]}](figures/{product.lower()}_share_sensitivity.png)", ""]
    lines += ["Для Cards: при текущем внешнем pricing proxy отсутствие adverse threshold (пересечения нулевой границы "
              "в сторону ухудшения) в допустимом диапазоне является условным результатом. "
              "Его нельзя трактовать как разрешение увеличивать долю карт без ограничений.", "",
              "## 8. Пороги обратного стресс-тестирования", "",
              presentation_table(mix[["product", "scenario", "critical_share", "status"]],
                                 rates=["critical_share"], labels=mix_labels), "",
              "Порог решается аналитически от текущей доли вверх; остальные две доли фиксированы. "
              "Максимальная доля равна сумме исходных долей целевого продукта и ипотеки. NA означает отсутствие "
              "допустимого пересечения либо уже достигнутую исходную границу, согласно статусу.", ""]
    mult = auxiliary[auxiliary.diagnostic.eq("portfolio_credit_cost_multiplier")]
    lines += ["Вспомогательный множитель стоимости риска применяется к текущему уровню каждого сценария:", "",
              presentation_table(mult[["scenario", "threshold", "status"]],
                                 labels={"scenario": "Сценарий", "threshold": "Множитель", "status": "Статус"}), "",
              "## 9. Чувствительность ипотечных и карточных ставок", "",
              f"При ипотечном proxy {mortgage.iloc[0].mortgage_pricing:.1%} Base RAFR = {mortgage.iloc[0].raf_result_bn:.3f} млрд руб.; "
              f"при {mortgage.iloc[-1].mortgage_pricing:.1%} — {mortgage.iloc[-1].raf_result_bn:.3f} млрд руб.", "",
              "![Ипотечная ставка](figures/mortgage_pricing_sensitivity.png)", "",
              "Карточные ставки ниже — условные снижения внешнего proxy, а не измеренная доходность карточного портфеля.", "",
              presentation_table(cards[["scenario", "card_pricing", "delta_raf_result_per_1pp", "critical_share", "status"]],
                                 rates=["card_pricing", "critical_share"],
                                 labels={**mix_labels, "card_pricing": "Карточная ставка"}), "",
              "![Карточная ставка](figures/card_pricing_sensitivity.png)", "",
              "## 10. Что устойчиво", "",
              "При заданных входах точны тождества экспозиции, потерь и результата, линейные предельные эффекты "
              "и аналитические пороги. Все сдвиги начинаются с исходной структуры; сетка включает границу полного замещения ипотеки.", "",
              "## 11. Зависимость от рыночных показателей и предположений", "",
              f"Относительно прежнего случая ипотечной ставки {mortgage.iloc[0].mortgage_pricing:.1%} "
              f"изменение только ипотечного proxy повышает Base RAFR на "
              f"{mortgage.iloc[-1].raf_result_bn - mortgage.iloc[0].raf_result_bn:.3f} млрд руб. "
              "Экспозиции и кредитные потери при этом не меняются. Новые Moderate и Severe изолируют кредитный риск; "
              "они не воспроизводят прежние сценарии с одновременными сдвигами pricing/funding или синтетической маржи.", "",
              "Направление изменения RAFR зависит от разности продуктовых CRAS. Увеличение доли продукта с большей стоимостью "
              "риска повышает потери, но эффект на RAFR может иметь любой знак: он определяется также доходной частью. "
              "Численные пороги зависят от ипотечного и карточного proxy и предварительных множителей стресса.", "",
              "FACT — только независимо сверенные показатели первоисточника. Для компонентов ВТБ сохраняется PENDING; "
              "они используются как значения рабочего Excel и не объявляются независимо подтверждёнными фактами. "
              "MARKET PROXY — внешние ставки Банка России; SYNTHETIC — их сочетание с экспозициями ВТБ; "
              "MODEL ASSUMPTION — стрессовые множители и диапазон карточной чувствительности; "
              "CALCULATED — стоимость риска, CRAS, RAFR, потери, эффекты и пороги.", "",
              "## 12. Ограничения", "",
              "RAFR не является фактической прибылью ВТБ. Модель не включает комиссии, операционные расходы, налоги, "
              "капитал, RWA (активы, взвешенные по риску) и RAROC (доходность капитала с учётом риска). "
              "Внешняя краткосрочная розничная ставка для Cards не отражает льготный период, использование лимита, "
              "interchange (межбанковское вознаграждение), комиссии и соотношение клиентов с погашением долга и переносом остатка. "
              "Короткая история и изменение периметра из-за Почта Банка не допускают причинных или статистически устойчивых выводов.", "",
              f"Проверки: PASS={int(qa.status.eq('PASS').sum())}, FAIL={int(qa.status.eq('FAIL').sum())}; "
              f"сверка продуктовых компонентов ВТБ: {cfg.source_qa['vtb_product_components']}.",
              f"Источник ставок: [Банк России, июнь 2026]({cfg.mortgage_pricing_proxy['source']}). "
              "Постраничная сверка ВТБ описана в [журнале источников](../other/SOURCE_QA_2026H1.md).", ""]
    return "\n".join(lines)


def run_model(config_path: Path) -> dict[str, Path]:
    config_path = config_path.resolve()
    cfg = load_config(config_path)
    root = config_path.parent.parent
    outdir = root / cfg.output_dir
    outdir.mkdir(parents=True, exist_ok=True)
    rawdir = outdir / "raw"
    rawdir.mkdir(exist_ok=True)
    data = load_dataset(root / cfg.input_file, cfg.data_sheet)
    qa = validate_data(data, cfg)
    qa.to_csv(outdir / "qa_report.csv", index=False, encoding="utf-8-sig")
    if qa.status.eq("FAIL").any():
        raise ValueError("Input QA failed; see qa_report.csv")
    products = build_scenarios(data, cfg)
    columns = ["product", "exposure", "weight", "pricing", "funding", "credit_cost", "cras", "credit_loss_bn", "raf_result_bn"]
    baseline = products.loc[products.scenario.eq("Base"), columns].copy()
    summary = scenario_summary(products, cfg.horizon_years)
    mix = product_mix_summary(products, cfg)
    grid = product_mix_grid(products, cfg)
    auxiliary = reverse_stress_auxiliary(products, cfg)
    mortgage = mortgage_pricing_sensitivity(products, cfg)
    cards = card_pricing_sensitivity(products, cfg)
    qa = pd.concat([qa, validate_outputs(products, summary, mix, grid, cfg)], ignore_index=True)
    qa.to_csv(outdir / "qa_report.csv", index=False, encoding="utf-8-sig")
    if qa.status.eq("FAIL").any():
        raise ValueError("Output QA failed; see qa_report.csv")
    tables = {
        "baseline_summary": baseline, "scenario_summary": summary, "product_mix_summary": mix,
        "reverse_stress_auxiliary": auxiliary, "factor_sensitivity": factor_sensitivity(products, cfg),
        "card_pricing_sensitivity": cards,
        "mortgage_pricing_sensitivity": mortgage.iloc[[0, -1]].reset_index(drop=True),
        "data_adequacy": data_adequacy_report(data, cfg),
    }
    files = {"qa": outdir / "qa_report.csv"}
    for name, table in tables.items():
        files[name] = outdir / f"{name}.csv"
        table.to_csv(files[name], index=False, encoding="utf-8-sig", na_rep="NA")
    raw_tables = {"product_mix_grid": grid, "scenario_product_results": products[["scenario"] + columns],
                  "mortgage_pricing_grid": mortgage, "baseline_components": baseline_table(data, cfg)}
    for name, table in raw_tables.items():
        files[name] = rawdir / f"{name}.csv"
        table.to_csv(files[name], index=False, encoding="utf-8-sig", na_rep="NA")
    make_figures(grid, mix, mortgage, cards, cfg, outdir)
    files["report"] = outdir / "model_report.md"
    files["report"].write_text(build_report(cfg, baseline, summary, mix, mortgage, cards, auxiliary, qa), encoding="utf-8")
    return files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/model_config.json")
    args = parser.parse_args()
    files = run_model(Path(args.config))
    print("Модель рассчитана; формулы и согласованность сетки проверены.")
    for name, path in files.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
